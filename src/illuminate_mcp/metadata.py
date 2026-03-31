"""Metadata store and Snowflake-backed catalog loading."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from .config import AppConfig
from .snowflake_conn import create_connection


@dataclass(frozen=True)
class EntityMetadata:
    name: str
    description: str
    columns: Dict[str, str]


@dataclass(frozen=True)
class DomainMetadata:
    name: str
    description: str
    entities: Dict[str, EntityMetadata]


@dataclass(frozen=True)
class MetadataLoadStatus:
    source: str
    warning: str | None = None


@dataclass(frozen=True)
class TableRecord:
    table_schema: str
    table_name: str
    table_comment: str


@dataclass(frozen=True)
class ColumnRecord:
    table_schema: str
    table_name: str
    column_name: str
    data_type: str
    column_comment: str


@dataclass(frozen=True)
class DictionaryRecord:
    table_schema: str
    table_name: str
    column_name: str
    description: str


class MetadataStore:
    def __init__(self, domains: Dict[str, DomainMetadata]):
        self._domains = domains

    @classmethod
    def from_builtin_catalog(cls, allowed_domains: Sequence[str]) -> "MetadataStore":
        return cls(_build_builtin_catalog(allowed_domains))

    @classmethod
    def from_records(
        cls,
        allowed_domains: Sequence[str],
        tables: Sequence[TableRecord],
        columns: Sequence[ColumnRecord],
        dictionary: Sequence[DictionaryRecord],
    ) -> "MetadataStore":
        domain_set = {value.upper() for value in allowed_domains}
        table_comments: Dict[Tuple[str, str], str] = {}
        for table in tables:
            table_comments[(table.table_schema.upper(), table.table_name.upper())] = (
                table.table_comment or ""
            ).strip()

        dictionary_map: Dict[Tuple[str, str, str], str] = {}
        for record in dictionary:
            key = (
                record.table_schema.upper(),
                record.table_name.upper(),
                record.column_name.upper(),
            )
            dictionary_map[key] = record.description.strip()

        grouped: Dict[str, Dict[str, Dict[str, str]]] = {}
        for col in columns:
            schema = col.table_schema.upper()
            if schema not in domain_set:
                continue

            table_name = col.table_name.upper()
            column_name = col.column_name.upper()
            domain_tables = grouped.setdefault(schema, {})
            entity_columns = domain_tables.setdefault(table_name, {})

            description = dictionary_map.get((schema, table_name, column_name))
            if not description:
                description = (col.column_comment or "").strip()
            if not description:
                description = f"{col.data_type.upper()} column"
            entity_columns[column_name] = description

        domains: Dict[str, DomainMetadata] = {}
        for domain in allowed_domains:
            normalized_domain = domain.upper()
            entities: Dict[str, EntityMetadata] = {}
            for table_name, cols in grouped.get(normalized_domain, {}).items():
                table_comment = table_comments.get((normalized_domain, table_name), "")
                entity_description = table_comment or f"{table_name} table"
                entities[table_name] = EntityMetadata(
                    name=table_name,
                    description=entity_description,
                    columns=cols,
                )
            domains[normalized_domain] = DomainMetadata(
                name=normalized_domain,
                description=f"Snowflake introspected domain {normalized_domain}",
                entities=entities,
            )

        return cls(domains)

    def list_domains(self) -> List[dict]:
        return [
            {
                "name": domain.name,
                "description": domain.description,
                "entity_count": len(domain.entities),
            }
            for domain in self._domains.values()
        ]

    def list_entities(self, domain: str) -> List[dict]:
        selected = self._domains.get(domain.upper())
        if not selected:
            return []
        return [
            {
                "name": entity.name,
                "description": entity.description,
                "column_count": len(entity.columns),
            }
            for entity in selected.entities.values()
        ]

    def describe_entity(self, domain: str, entity_name: str) -> dict | None:
        selected = self._domains.get(domain.upper())
        if not selected:
            return None
        entity = selected.entities.get(entity_name.upper())
        if not entity:
            return None
        return {
            "domain": selected.name,
            "name": entity.name,
            "description": entity.description,
            "columns": entity.columns,
        }

    def domains(self) -> List[str]:
        return list(self._domains.keys())

    def resource_snapshot(self) -> dict:
        return {
            domain: {
                "description": details.description,
                "entities": {
                    entity_name: {
                        "description": entity.description,
                        "columns": entity.columns,
                    }
                    for entity_name, entity in details.entities.items()
                },
            }
            for domain, details in self._domains.items()
        }


def build_metadata_store(config: AppConfig) -> Tuple[MetadataStore, MetadataLoadStatus]:
    if not config.enable_metadata_introspection:
        return (
            MetadataStore.from_builtin_catalog(config.allowed_domains),
            MetadataLoadStatus(source="builtin", warning=None),
        )

    try:
        tables, columns, dictionary = _load_from_snowflake(config)
        return (
            MetadataStore.from_records(config.allowed_domains, tables, columns, dictionary),
            MetadataLoadStatus(source="snowflake", warning=None),
        )
    except Exception as exc:
        return (
            MetadataStore.from_builtin_catalog(config.allowed_domains),
            MetadataLoadStatus(
                source="builtin_fallback",
                warning=f"Metadata introspection failed: {exc}",
            ),
        )


def _load_from_snowflake(
    config: AppConfig,
) -> Tuple[List[TableRecord], List[ColumnRecord], List[DictionaryRecord]]:
    connection = create_connection(config, {
        "QUERY_TAG": "illuminate_mcp:metadata_introspection",
    })

    try:
        tables = _query_tables(connection, config.allowed_schemas)
        columns = _query_columns(connection, config.allowed_schemas)
        dictionary = _query_dictionary(connection, config.metadata_dictionary_query)
    finally:
        connection.close()

    return tables, columns, dictionary


def _query_tables(connection: object, schemas: Sequence[str]) -> List[TableRecord]:
    if not schemas:
        return []
    placeholders = ",".join(["%s"] * len(schemas))
    sql = (
        "SELECT TABLE_SCHEMA, TABLE_NAME, COALESCE(COMMENT, '') AS TABLE_COMMENT "
        "FROM INFORMATION_SCHEMA.TABLES "
        f"WHERE TABLE_SCHEMA IN ({placeholders}) "
        "ORDER BY TABLE_SCHEMA, TABLE_NAME"
    )

    with connection.cursor() as cur:
        cur.execute(sql, tuple(schemas))
        rows = cur.fetchall()

    return [
        TableRecord(
            table_schema=str(row[0]),
            table_name=str(row[1]),
            table_comment=str(row[2] or ""),
        )
        for row in rows
    ]


def _query_columns(connection: object, schemas: Sequence[str]) -> List[ColumnRecord]:
    if not schemas:
        return []
    placeholders = ",".join(["%s"] * len(schemas))
    sql = (
        "SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, "
        "COALESCE(COMMENT, '') AS COLUMN_COMMENT "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        f"WHERE TABLE_SCHEMA IN ({placeholders}) "
        "ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION"
    )

    with connection.cursor() as cur:
        cur.execute(sql, tuple(schemas))
        rows = cur.fetchall()

    return [
        ColumnRecord(
            table_schema=str(row[0]),
            table_name=str(row[1]),
            column_name=str(row[2]),
            data_type=str(row[3]),
            column_comment=str(row[4] or ""),
        )
        for row in rows
    ]


def _query_dictionary(connection: object, dictionary_query: str) -> List[DictionaryRecord]:
    if not dictionary_query:
        return []

    with connection.cursor() as cur:
        cur.execute(dictionary_query)
        rows = cur.fetchall()
        columns = [desc[0].upper() for desc in (cur.description or [])]

    name_to_idx = {name: idx for idx, name in enumerate(columns)}
    required = {"TABLE_NAME", "COLUMN_NAME", "DESCRIPTION"}
    if not required.issubset(name_to_idx):
        missing = sorted(required - set(name_to_idx))
        raise RuntimeError(
            "METADATA_DICTIONARY_QUERY must return columns TABLE_NAME, COLUMN_NAME, DESCRIPTION"
            f"; missing: {', '.join(missing)}"
        )

    schema_idx = name_to_idx.get("TABLE_SCHEMA")
    output: List[DictionaryRecord] = []
    for row in rows:
        output.append(
            DictionaryRecord(
                table_schema=str(row[schema_idx]) if schema_idx is not None else "",
                table_name=str(row[name_to_idx["TABLE_NAME"]]),
                column_name=str(row[name_to_idx["COLUMN_NAME"]]),
                description=str(row[name_to_idx["DESCRIPTION"]] or ""),
            )
        )
    return output


def _build_builtin_catalog(allowed_domains: Iterable[str]) -> Dict[str, DomainMetadata]:
    catalog: Dict[str, DomainMetadata] = {}
    allowed = [domain.upper() for domain in allowed_domains]
    if "CDM_LMS" in allowed:
        catalog["CDM_LMS"] = DomainMetadata(
            name="CDM_LMS",
            description="Learning Management System canonical domain",
            entities={
                "COURSE": EntityMetadata(
                    name="COURSE",
                    description="Course-level metadata",
                    columns={
                        "COURSE_ID": "Unique course identifier",
                        "COURSE_NAME": "Course display name",
                        "COURSE_NUMBER": "Catalog course number",
                        "TERM_ID": "Academic term identifier",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "COURSE_SECTION": EntityMetadata(
                    name="COURSE_SECTION",
                    description="Section-level representation of a course",
                    columns={
                        "SECTION_ID": "Unique section identifier",
                        "COURSE_ID": "Parent course identifier",
                        "INSTRUCTOR_ID": "Primary instructor identifier",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "ENROLLMENT": EntityMetadata(
                    name="ENROLLMENT",
                    description="Learner enrollment facts",
                    columns={
                        "ENROLLMENT_ID": "Unique enrollment identifier",
                        "USER_ID": "Learner identifier",
                        "COURSE_ID": "Associated course",
                        "ENROLLMENT_DATE": "Date learner was enrolled",
                        "ENROLLMENT_STATUS": "Current enrollment status",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "USER": EntityMetadata(
                    name="USER",
                    description="Person dimension for LMS participants",
                    columns={
                        "USER_ID": "Unique user identifier",
                        "ROLE": "User role in LMS context",
                        "STATUS": "Activity or enrollment status",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "GRADE": EntityMetadata(
                    name="GRADE",
                    description="Grade records for course assignments and assessments",
                    columns={
                        "GRADE_ID": "Unique grade identifier",
                        "USER_ID": "Learner identifier",
                        "COURSE_ID": "Associated course identifier",
                        "GRADE_COLUMN_ID": "Grade column identifier",
                        "SCORE": "Raw score value",
                        "NORMALIZED_SCORE": "Normalized score (0-100)",
                        "LETTER_GRADE": "Letter grade value",
                        "SUBMITTED_TIME": "Submission timestamp",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "GRADE_COLUMN": EntityMetadata(
                    name="GRADE_COLUMN",
                    description="Grade center column definitions",
                    columns={
                        "GRADE_COLUMN_ID": "Unique column identifier",
                        "COURSE_ID": "Associated course identifier",
                        "COLUMN_NAME": "Display name of the grade column",
                        "POSSIBLE_SCORE": "Maximum possible score",
                        "COLUMN_TYPE": "Column type (assignment, test, etc.)",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "ASSIGNMENT": EntityMetadata(
                    name="ASSIGNMENT",
                    description="Course assignment definitions",
                    columns={
                        "ASSIGNMENT_ID": "Unique assignment identifier",
                        "COURSE_ID": "Associated course identifier",
                        "ASSIGNMENT_NAME": "Assignment display name",
                        "DUE_DATE": "Assignment due date",
                        "POSSIBLE_SCORE": "Maximum possible score",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "ATTEMPT": EntityMetadata(
                    name="ATTEMPT",
                    description="Assignment and assessment submission attempts",
                    columns={
                        "ATTEMPT_ID": "Unique attempt identifier",
                        "USER_ID": "Learner identifier",
                        "COURSE_ID": "Associated course identifier",
                        "ASSIGNMENT_ID": "Associated assignment identifier",
                        "SCORE": "Attempt score",
                        "SUBMITTED_TIME": "Submission timestamp",
                        "ATTEMPT_STATUS": "Attempt status",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "CONTENT_ITEM": EntityMetadata(
                    name="CONTENT_ITEM",
                    description="Course content items and learning materials",
                    columns={
                        "CONTENT_ID": "Unique content identifier",
                        "COURSE_ID": "Associated course identifier",
                        "CONTENT_NAME": "Content display name",
                        "CONTENT_TYPE": "Content type category",
                        "CREATED_DATE": "Content creation date",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "DISCUSSION": EntityMetadata(
                    name="DISCUSSION",
                    description="Discussion forum topics and threads",
                    columns={
                        "DISCUSSION_ID": "Unique discussion identifier",
                        "COURSE_ID": "Associated course identifier",
                        "DISCUSSION_NAME": "Discussion topic name",
                        "CREATED_DATE": "Discussion creation date",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "ANNOUNCEMENT": EntityMetadata(
                    name="ANNOUNCEMENT",
                    description="Course announcements",
                    columns={
                        "ANNOUNCEMENT_ID": "Unique announcement identifier",
                        "COURSE_ID": "Associated course identifier",
                        "ANNOUNCEMENT_TITLE": "Announcement title",
                        "CREATED_DATE": "Announcement creation date",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "PERSON_COURSE": EntityMetadata(
                    name="PERSON_COURSE",
                    description="Person-course membership facts with role indicators",
                    columns={
                        "PERSON_COURSE_ID": "Unique person-course identifier",
                        "USER_ID": "Person identifier",
                        "COURSE_ID": "Course identifier",
                        "STUDENT_IND": "Whether person is a student in this course",
                        "INSTRUCTOR_IND": "Whether person is an instructor in this course",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
            },
        )

    if "CDM_SIS" in allowed:
        catalog["CDM_SIS"] = DomainMetadata(
            name="CDM_SIS",
            description="Student Information System canonical domain",
            entities={
                "STUDENT": EntityMetadata(
                    name="STUDENT",
                    description="Student master records",
                    columns={
                        "STUDENT_ID": "Unique student identifier",
                        "INSTITUTION_ID": "Institution identifier",
                        "ADMIT_TERM_ID": "Initial admit term",
                        "FIRST_NAME": "Student first name",
                        "LAST_NAME": "Student last name",
                        "EMAIL": "Student email address",
                        "STUDENT_STATUS": "Current student status",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "ACADEMIC_TERM": EntityMetadata(
                    name="ACADEMIC_TERM",
                    description="Academic term dimension",
                    columns={
                        "TERM_ID": "Unique term identifier",
                        "TERM_NAME": "Term display label",
                        "START_DATE": "Term start date",
                        "END_DATE": "Term end date",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "STUDENT_PROGRAM": EntityMetadata(
                    name="STUDENT_PROGRAM",
                    description="Student program enrollment",
                    columns={
                        "STUDENT_ID": "Student identifier",
                        "PROGRAM_ID": "Program identifier",
                        "TERM_ID": "Effective term",
                        "STATUS": "Program status",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "COURSE_REGISTRATION": EntityMetadata(
                    name="COURSE_REGISTRATION",
                    description="SIS course registration facts",
                    columns={
                        "STUDENT_ID": "Student identifier",
                        "COURSE_ID": "Course identifier",
                        "TERM_ID": "Registration term",
                        "REGISTRATION_STATUS": "Registration status",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "INSTITUTION": EntityMetadata(
                    name="INSTITUTION",
                    description="Institution master records",
                    columns={
                        "INSTITUTION_ID": "Unique institution identifier",
                        "INSTITUTION_NAME": "Institution display name",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "DEGREE": EntityMetadata(
                    name="DEGREE",
                    description="Degree program definitions",
                    columns={
                        "DEGREE_ID": "Unique degree identifier",
                        "DEGREE_NAME": "Degree display name",
                        "DEGREE_TYPE": "Degree type (BA, BS, MA, etc.)",
                        "INSTITUTION_ID": "Institution identifier",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
            },
        )

    if "CDM_TLM" in allowed:
        catalog["CDM_TLM"] = DomainMetadata(
            name="CDM_TLM",
            description="Teaching and Learning Metadata canonical domain",
            entities={
                "LEARNER_ACTIVITY": EntityMetadata(
                    name="LEARNER_ACTIVITY",
                    description="Learner activity telemetry events",
                    columns={
                        "EVENT_ID": "Unique event identifier",
                        "USER_ID": "Learner identifier",
                        "COURSE_ID": "Associated course identifier",
                        "EVENT_TIME": "Event timestamp",
                        "ACTIVITY_TYPE": "Activity category",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "LEARNING_RESOURCE": EntityMetadata(
                    name="LEARNING_RESOURCE",
                    description="Learning object and content metadata",
                    columns={
                        "RESOURCE_ID": "Unique resource identifier",
                        "COURSE_ID": "Owning course identifier",
                        "RESOURCE_TYPE": "Resource type",
                        "TITLE": "Resource title",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "ASSESSMENT_EVENT": EntityMetadata(
                    name="ASSESSMENT_EVENT",
                    description="Assessment attempt events and outcomes",
                    columns={
                        "ATTEMPT_ID": "Attempt identifier",
                        "USER_ID": "Learner identifier",
                        "COURSE_ID": "Associated course identifier",
                        "SCORE": "Assessment score",
                        "SUBMITTED_TIME": "Submission timestamp",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "ULTRA_EVENTS": EntityMetadata(
                    name="ULTRA_EVENTS",
                    description="Ultra experience telemetry events",
                    columns={
                        "EVENT_ID": "Unique event identifier",
                        "USER_ID": "User identifier",
                        "COURSE_ID": "Associated course identifier",
                        "EVENT_TYPE": "Event type category",
                        "EVENT_TIME": "Event timestamp",
                        "SESSION_ID": "Browser session identifier",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
            },
        )

    if "CDM_ALY" in allowed:
        catalog["CDM_ALY"] = DomainMetadata(
            name="CDM_ALY",
            description="Analytics domain for institutional metrics",
            entities={
                "METRIC_DAILY": EntityMetadata(
                    name="METRIC_DAILY",
                    description="Daily metric values by domain and institution",
                    columns={
                        "METRIC_DATE": "Metric observation date",
                        "METRIC_NAME": "Metric identifier",
                        "METRIC_VALUE": "Metric value",
                        "DIMENSION_KEY": "Dimension key",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "METRIC_DIMENSION": EntityMetadata(
                    name="METRIC_DIMENSION",
                    description="Dimension attributes for analytics metrics",
                    columns={
                        "DIMENSION_KEY": "Dimension key",
                        "DIMENSION_NAME": "Dimension display name",
                        "CATEGORY": "Dimension category",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "KPI_SNAPSHOT": EntityMetadata(
                    name="KPI_SNAPSHOT",
                    description="Point-in-time KPI snapshots",
                    columns={
                        "SNAPSHOT_TIME": "Snapshot timestamp",
                        "KPI_NAME": "KPI identifier",
                        "KPI_VALUE": "KPI value",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
            },
        )

    if "CDM_CLB" in allowed:
        catalog["CDM_CLB"] = DomainMetadata(
            name="CDM_CLB",
            description="Collaborate virtual classroom canonical domain",
            entities={
                "SESSION": EntityMetadata(
                    name="SESSION",
                    description="Collaborate session (virtual classroom meeting)",
                    columns={
                        "SESSION_ID": "Unique session identifier",
                        "SESSION_NAME": "Session display name",
                        "COURSE_ID": "Associated course identifier",
                        "START_TIME": "Scheduled start time",
                        "END_TIME": "Scheduled end time",
                        "DURATION_MINUTES": "Session duration in minutes",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "ATTENDANCE": EntityMetadata(
                    name="ATTENDANCE",
                    description="Session attendance records for participants",
                    columns={
                        "ATTENDANCE_ID": "Unique attendance identifier",
                        "SESSION_ID": "Associated session identifier",
                        "USER_ID": "Participant identifier",
                        "JOIN_TIME": "Time participant joined",
                        "LEAVE_TIME": "Time participant left",
                        "DURATION_MINUTES": "Attendance duration in minutes",
                        "ROLE": "Participant role (moderator, participant)",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "RECORDING": EntityMetadata(
                    name="RECORDING",
                    description="Session recordings",
                    columns={
                        "RECORDING_ID": "Unique recording identifier",
                        "SESSION_ID": "Associated session identifier",
                        "RECORDING_NAME": "Recording display name",
                        "DURATION_MINUTES": "Recording duration in minutes",
                        "CREATED_DATE": "Recording creation date",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
            },
        )

    if "CDM_MAP" in allowed:
        catalog["CDM_MAP"] = DomainMetadata(
            name="CDM_MAP",
            description="Cross-system mapping domain linking users and courses across CDMs",
            entities={
                "USER_MAP": EntityMetadata(
                    name="USER_MAP",
                    description="Maps user identifiers across CDM domains",
                    columns={
                        "USER_MAP_ID": "Unique mapping identifier",
                        "SOURCE_DOMAIN": "Source CDM domain",
                        "SOURCE_USER_ID": "User identifier in source domain",
                        "TARGET_DOMAIN": "Target CDM domain",
                        "TARGET_USER_ID": "User identifier in target domain",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "COURSE_MAP": EntityMetadata(
                    name="COURSE_MAP",
                    description="Maps course identifiers across CDM domains",
                    columns={
                        "COURSE_MAP_ID": "Unique mapping identifier",
                        "SOURCE_DOMAIN": "Source CDM domain",
                        "SOURCE_COURSE_ID": "Course identifier in source domain",
                        "TARGET_DOMAIN": "Target CDM domain",
                        "TARGET_COURSE_ID": "Course identifier in target domain",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
            },
        )

    if "CDM_MEDIA" in allowed:
        catalog["CDM_MEDIA"] = DomainMetadata(
            name="CDM_MEDIA",
            description="Video Studio media content and interaction domain",
            entities={
                "MEDIA": EntityMetadata(
                    name="MEDIA",
                    description="Video and media content items",
                    columns={
                        "MEDIA_ID": "Unique media identifier",
                        "MEDIA_NAME": "Media display name",
                        "MEDIA_TYPE": "Media type (video, audio, etc.)",
                        "DURATION_SECONDS": "Media duration in seconds",
                        "CREATED_DATE": "Media creation date",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "ACTIVITY": EntityMetadata(
                    name="ACTIVITY",
                    description="Media viewing and interaction activity",
                    columns={
                        "ACTIVITY_ID": "Unique activity identifier",
                        "MEDIA_ID": "Associated media identifier",
                        "USER_ID": "Viewer identifier",
                        "ACTIVITY_TYPE": "Activity type (view, comment, etc.)",
                        "ACTIVITY_TIME": "Activity timestamp",
                        "DURATION_SECONDS": "Viewing duration in seconds",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "CONTAINER": EntityMetadata(
                    name="CONTAINER",
                    description="Media container (collection or channel)",
                    columns={
                        "CONTAINER_ID": "Unique container identifier",
                        "CONTAINER_NAME": "Container display name",
                        "COURSE_ID": "Associated course identifier",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "PERSON": EntityMetadata(
                    name="PERSON",
                    description="Person records in the media system",
                    columns={
                        "PERSON_ID": "Unique person identifier",
                        "USER_ID": "Linked user identifier",
                        "DISPLAY_NAME": "Person display name",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
                "SESSION_ACTIVITY": EntityMetadata(
                    name="SESSION_ACTIVITY",
                    description="Session-level media interaction summary",
                    columns={
                        "SESSION_ID": "Unique session identifier",
                        "MEDIA_ID": "Associated media identifier",
                        "USER_ID": "Viewer identifier",
                        "START_TIME": "Session start time",
                        "END_TIME": "Session end time",
                        "INSTANCE_ID": "Source instance identifier",
                        "ROW_DELETED_TIME": "Soft delete timestamp",
                    },
                ),
            },
        )

    if "CDM_META" in allowed:
        catalog["CDM_META"] = DomainMetadata(
            name="CDM_META",
            description="Metadata and reference data domain (static tables)",
            entities={
                "DATA_SOURCE": EntityMetadata(
                    name="DATA_SOURCE",
                    description="Data source and integration reference records",
                    columns={
                        "SOURCE_ID": "Unique source identifier",
                        "SOURCE_NAME": "Data source display name",
                        "SOURCE_TYPE": "Data source type",
                        "INSTANCE_ID": "Source instance identifier",
                    },
                ),
                "INSTANCE": EntityMetadata(
                    name="INSTANCE",
                    description="Client instance records",
                    columns={
                        "INSTANCE_ID": "Unique instance identifier",
                        "INSTANCE_NAME": "Instance display name",
                        "PRODUCT": "Associated product name",
                        "REGION": "Deployment region",
                    },
                ),
            },
        )

    if "LEARN" in allowed:
        catalog["LEARN"] = DomainMetadata(
            name="LEARN",
            description="Blackboard Learn Open Database Schema (Premium, requires ENABLE_LEARN_SCHEMA)",
            entities={
                "USERS": EntityMetadata(
                    name="USERS",
                    description="Blackboard Learn user records",
                    columns={
                        "PK1": "Primary key",
                        "USER_ID": "Login username",
                        "FIRSTNAME": "First name",
                        "LASTNAME": "Last name",
                        "EMAIL": "Email address",
                        "INSTITUTION_ROLE_PK1": "Institution role key",
                        "ROW_STATUS": "Row status indicator",
                        "AVAILABLE_IND": "Availability flag",
                    },
                ),
                "COURSE_MAIN": EntityMetadata(
                    name="COURSE_MAIN",
                    description="Blackboard Learn course master table",
                    columns={
                        "PK1": "Primary key",
                        "COURSE_ID": "Course identifier string",
                        "COURSE_NAME": "Course display name",
                        "TERM_PK1": "Term primary key",
                        "AVAILABLE_IND": "Availability flag",
                        "ROW_STATUS": "Row status indicator",
                    },
                ),
                "COURSE_USERS": EntityMetadata(
                    name="COURSE_USERS",
                    description="Course membership (enrollment) table",
                    columns={
                        "PK1": "Primary key",
                        "CRSMAIN_PK1": "Course primary key",
                        "USERS_PK1": "User primary key",
                        "ROLE": "Course role",
                        "AVAILABLE_IND": "Availability flag",
                        "ENROLLMENT_DATE": "Enrollment date",
                        "ROW_STATUS": "Row status indicator",
                    },
                ),
                "GRADEBOOK_MAIN": EntityMetadata(
                    name="GRADEBOOK_MAIN",
                    description="Grade center column definitions",
                    columns={
                        "PK1": "Primary key",
                        "CRSMAIN_PK1": "Course primary key",
                        "TITLE": "Column title",
                        "POSSIBLE": "Possible points",
                        "CALCULATED_IND": "Calculated column flag",
                        "SCORABLE_IND": "Scorable column flag",
                    },
                ),
                "GRADEBOOK_GRADE": EntityMetadata(
                    name="GRADEBOOK_GRADE",
                    description="Individual grade entries",
                    columns={
                        "PK1": "Primary key",
                        "GRADEBOOK_MAIN_PK1": "Grade column primary key",
                        "COURSE_USERS_PK1": "Course membership primary key",
                        "MANUAL_GRADE": "Manual grade value",
                        "MANUAL_SCORE": "Manual score value",
                        "AVERAGE_SCORE": "Average score",
                    },
                ),
                "COURSE_CONTENTS": EntityMetadata(
                    name="COURSE_CONTENTS",
                    description="Course content items",
                    columns={
                        "PK1": "Primary key",
                        "CRSMAIN_PK1": "Course primary key",
                        "TITLE": "Content title",
                        "CONTENT_TYPE_PK1": "Content type key",
                        "AVAILABLE_IND": "Availability flag",
                        "CREATED_DATE": "Creation date",
                    },
                ),
                "ATTEMPT": EntityMetadata(
                    name="ATTEMPT",
                    description="Assignment attempt submissions",
                    columns={
                        "PK1": "Primary key",
                        "COURSE_USERS_PK1": "Course membership primary key",
                        "GRADEBOOK_MAIN_PK1": "Grade column primary key",
                        "SCORE": "Attempt score",
                        "ATTEMPT_DATE": "Attempt date",
                        "STATUS": "Attempt status",
                    },
                ),
                "FORUM_MAIN": EntityMetadata(
                    name="FORUM_MAIN",
                    description="Discussion forum definitions",
                    columns={
                        "PK1": "Primary key",
                        "CRSMAIN_PK1": "Course primary key",
                        "TITLE": "Forum title",
                        "AVAILABLE_IND": "Availability flag",
                    },
                ),
                "ANNOUNCEMENTS": EntityMetadata(
                    name="ANNOUNCEMENTS",
                    description="System and course announcements",
                    columns={
                        "PK1": "Primary key",
                        "CRSMAIN_PK1": "Course primary key",
                        "SUBJECT": "Announcement subject",
                        "MESSAGE": "Announcement body text",
                        "CREATED_DATE": "Creation date",
                        "AVAILABLE_IND": "Availability flag",
                    },
                ),
            },
        )

    for domain in allowed:
        if domain not in catalog:
            catalog[domain] = DomainMetadata(
                name=domain,
                description=f"Configured domain placeholder for {domain}",
                entities={},
            )
    return catalog
