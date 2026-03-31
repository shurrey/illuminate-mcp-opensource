"""Metadata-grounded SQL planner (no server-side LLM credentials required)."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Sequence, Set, Tuple

from .config import AppConfig
from .domain_router import DomainRouter
from .metadata import MetadataStore
from .semantic_model import Relationship, SemanticModel
from .tokens import tokenize

_JOIN_KEY_PRIORITY = (
    "COURSE_ID",
    "USER_ID",
    "SECTION_ID",
    "TERM_ID",
    "INSTRUCTOR_ID",
    "INSTANCE_ID",
)
_BRIDGE_ENTITY_PENALTY = {
    "INSTANCE": 1.5,
    "DATA_SOURCE": 1.0,
}


@dataclass(frozen=True)
class SqlPlan:
    domain: str
    sql: str
    planner_mode: str
    rationale: str
    grounded_entities: Sequence[str]
    warning: str | None = None


@dataclass(frozen=True)
class _EntityInfo:
    name: str
    score: int
    columns: Sequence[str]


class SqlPlanner:
    def __init__(self, config: AppConfig, router: DomainRouter):
        self._config = config
        self._router = router

    def plan(
        self,
        question: str,
        metadata: MetadataStore,
        domain_override: str | None = None,
        output_intent: str | None = None,
    ) -> SqlPlan:
        domain = self._router.resolve(question, domain_override)
        intent = self._infer_intent(question, output_intent)
        limit = self._infer_limit(question)
        include_deleted = self._wants_deleted_data(question)
        model = SemanticModel.from_metadata(metadata, domain)

        entities = self._rank_entities(question, metadata, domain, model=model)
        if not entities:
            return SqlPlan(
                domain=domain,
                sql=f"SELECT * FROM {domain}.COURSE LIMIT {limit}",
                planner_mode="metadata_fallback",
                rationale="No entities available in metadata; defaulted to COURSE preview.",
                grounded_entities=["COURSE"],
                warning="No metadata entities detected for selected domain.",
            )

        primary = entities[0]
        secondary = entities[1] if len(entities) > 1 else None
        join_spec = self._find_join_spec(primary, secondary, model) if secondary else None

        if intent == "trend":
            return self._plan_trend(
                question=question,
                domain=domain,
                primary=primary,
                secondary=secondary,
                join_spec=join_spec,
                limit=limit,
                include_deleted=include_deleted,
            )
        if intent == "analysis":
            analysis = self._plan_analysis(
                question=question,
                domain=domain,
                metadata=metadata,
                model=model,
                limit=limit,
                include_deleted=include_deleted,
            )
            if analysis:
                return analysis
        if intent == "count":
            return self._plan_count(
                question=question,
                domain=domain,
                primary=primary,
                secondary=secondary,
                join_spec=join_spec,
                limit=limit,
                include_deleted=include_deleted,
            )
        if intent == "top":
            return self._plan_top(
                question=question,
                domain=domain,
                primary=primary,
                secondary=secondary,
                join_spec=join_spec,
                limit=limit,
                include_deleted=include_deleted,
            )

        return self._plan_list_or_preview(
            question=question,
            domain=domain,
            primary=primary,
            secondary=secondary,
            join_spec=join_spec,
            limit=limit,
            include_deleted=include_deleted,
        )

    def _plan_analysis(
        self,
        question: str,
        domain: str,
        metadata: MetadataStore,
        model: SemanticModel,
        limit: int,
        include_deleted: bool,
    ) -> SqlPlan | None:
        lowered = question.lower()
        if not model.entities:
            return None

        entity_columns = model.entities

        # Choose a fact table with score-like metrics when averaging.
        metric_col = None
        if "normalized_score" in lowered:
            metric_col = "NORMALIZED_SCORE"
        elif "score" in lowered or "grade" in lowered:
            metric_col = "SCORE"

        fact = None
        ranked = self._rank_entities(question, metadata, domain, model=model)
        for candidate in ranked:
            cols = entity_columns.get(candidate.name, set())
            if metric_col and metric_col in cols:
                fact = candidate.name
                break
        if fact is None:
            for name, cols in entity_columns.items():
                if metric_col and metric_col in cols:
                    fact = name
                    break
        if fact is None and "GRADE" in entity_columns:
            fact = "GRADE"
        if fact is None:
            return None

        required = self._required_entities_for_analysis(lowered, entity_columns)
        from_clause, aliases, grounded = self._build_join_chain(
            domain=domain,
            model=model,
            fact_entity=fact,
            required_entities=required,
        )

        measures = []
        fact_cols = entity_columns.get(fact, set())
        if "NORMALIZED_SCORE" in fact_cols:
            measures.append("AVG(f.NORMALIZED_SCORE) AS AVG_NORMALIZED_SCORE")
        if "SCORE" in fact_cols:
            measures.append("AVG(f.SCORE) AS AVG_SCORE")
        measures.append("COUNT(*) AS RECORD_COUNT")

        where_clauses: List[str] = []
        person_course_alias = aliases.get("PERSON_COURSE")
        if (
            "student" in lowered
            and person_course_alias
            and "STUDENT_IND" in entity_columns.get("PERSON_COURSE", set())
        ):
            where_clauses.append(f"{person_course_alias}.STUDENT_IND = TRUE")

        term_match = re.search(r"(spring|summer|fall|winter)\s+(20\d{2})", lowered)
        term_alias = aliases.get("TERM")
        if term_match and term_alias and "NAME" in entity_columns.get("TERM", set()):
            season, year = term_match.groups()
            where_clauses.append(f"LOWER({term_alias}.NAME) LIKE '%{season}%{year}%'")

        subject_match = re.search(
            r"(?:in|for)\s+([a-z0-9\-]+)\s+(?:class|classes|course|courses)",
            lowered,
        )
        course_alias = aliases.get("COURSE")
        if subject_match and course_alias:
            subject = subject_match.group(1)
            course_filters = []
            if "NAME" in entity_columns.get("COURSE", set()):
                course_filters.append(f"LOWER({course_alias}.NAME) LIKE '%{subject}%'")
            if "COURSE_NUMBER" in entity_columns.get("COURSE", set()):
                course_filters.append(f"LOWER({course_alias}.COURSE_NUMBER) LIKE '%{subject}%'")
            if course_filters:
                where_clauses.append("(" + " OR ".join(course_filters) + ")")

        if not include_deleted:
            for entity_name, alias in aliases.items():
                cols = entity_columns.get(entity_name, set())
                if "ROW_DELETED_TIME" in cols:
                    where_clauses.append(f"{alias}.ROW_DELETED_TIME IS NULL")

        sql = "SELECT " + ", ".join(measures) + " FROM " + from_clause
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        sql += f" LIMIT {limit}"

        return SqlPlan(
            domain=domain,
            sql=sql,
            planner_mode="metadata_analysis",
            rationale="Analysis intent detected; built metric query with metadata-driven joins and filters.",
            grounded_entities=grounded,
            warning=None,
        )

    @staticmethod
    def _required_entities_for_analysis(lowered_question: str, entity_columns: Dict[str, Set[str]]) -> List[str]:
        required: List[str] = []
        if "student" in lowered_question and "PERSON_COURSE" in entity_columns:
            required.append("PERSON_COURSE")
        if any(token in lowered_question for token in ("course", "class", "chemistry")) and "COURSE" in entity_columns:
            required.append("COURSE")
        if (
            re.search(r"(spring|summer|fall|winter)\s+(20\d{2})", lowered_question)
            and "TERM" in entity_columns
        ):
            required.append("TERM")
        return required

    def _build_join_chain(
        self,
        domain: str,
        model: SemanticModel,
        fact_entity: str,
        required_entities: Sequence[str],
    ) -> Tuple[str, Dict[str, str], List[str]]:
        aliases: Dict[str, str] = {fact_entity: "f"}
        grounded: List[str] = [fact_entity]
        from_clause = f"{domain}.{fact_entity} f"

        alias_sequence = ["pc", "c", "t", "d", "e", "x", "y", "z"]
        alias_idx = 0
        added_pairs = set()

        for required in required_entities:
            required = required.upper()
            if required == fact_entity or required in grounded:
                continue
            path = self._best_path_from_joined(model, grounded, required)
            if not path:
                continue
            for rel in path:
                pair = (rel.source_entity, rel.target_entity, rel.source_column, rel.target_column)
                if pair in added_pairs:
                    continue
                added_pairs.add(pair)

                if rel.source_entity not in aliases:
                    aliases[rel.source_entity] = alias_sequence[min(alias_idx, len(alias_sequence) - 1)]
                    alias_idx += 1
                if rel.target_entity not in aliases:
                    aliases[rel.target_entity] = alias_sequence[min(alias_idx, len(alias_sequence) - 1)]
                    alias_idx += 1

                source_alias = aliases[rel.source_entity]
                target_alias = aliases[rel.target_entity]
                if rel.target_entity not in grounded:
                    grounded.append(rel.target_entity)
                    from_clause += (
                        f" JOIN {domain}.{rel.target_entity} {target_alias} "
                        f"ON {source_alias}.{rel.source_column} = {target_alias}.{rel.target_column}"
                    )

        return from_clause, aliases, grounded

    def _best_path_from_joined(
        self,
        model: SemanticModel,
        joined_entities: Sequence[str],
        target: str,
    ) -> List[Relationship]:
        best_path: List[Relationship] = []
        best_cost = float("inf")
        for source in joined_entities:
            path = model.shortest_join_path(source, target)
            if not path:
                continue
            cost = self._path_cost(path)
            if cost < best_cost:
                best_cost = cost
                best_path = path
        return best_path

    @staticmethod
    def _path_cost(path: Sequence[Relationship]) -> float:
        if not path:
            return 0.0
        cost = float(len(path))
        for rel in path:
            cost += (1.0 - float(rel.confidence))
            cost += _BRIDGE_ENTITY_PENALTY.get(rel.target_entity, 0.0)
        return cost

    def _plan_count(
        self,
        question: str,
        domain: str,
        primary: _EntityInfo,
        secondary: _EntityInfo | None,
        join_spec: Tuple[str, str] | None,
        limit: int,
        include_deleted: bool,
    ) -> SqlPlan:
        lowered = question.lower()
        primary_filter = self._active_filter(primary, "a", include_deleted)
        secondary_filter = (
            self._active_filter(secondary, "b", include_deleted) if secondary else None
        )
        if self._is_total_count_request(lowered):
            distinct_requested = self._is_distinct_requested(lowered) or self._should_default_distinct(
                lowered
            )
            id_col = (
                self._best_id_column(primary.name, primary.columns) if distinct_requested else None
            )
            where_clause = f" WHERE {primary_filter}" if primary_filter else ""
            if id_col and distinct_requested:
                sql = (
                    f"SELECT COUNT(DISTINCT {id_col}) AS RECORD_COUNT "
                    f"FROM {domain}.{primary.name}{where_clause} "
                    f"LIMIT {limit}"
                )
            else:
                sql = (
                    f"SELECT COUNT(*) AS RECORD_COUNT FROM {domain}.{primary.name}"
                    f"{where_clause} LIMIT {limit}"
                )
            return SqlPlan(
                domain=domain,
                sql=sql,
                planner_mode="metadata_direct_count",
                rationale=f"Detected total count request; used direct count from {primary.name}.",
                grounded_entities=[primary.name],
                warning=None,
            )

        group_col = self._choose_grouping_column(question, primary.columns, secondary.columns if secondary else ())

        if self._should_join_for_count_or_top(
            lowered_question=lowered,
            primary=primary,
            secondary=secondary,
            join_spec=join_spec,
            group_col=group_col,
        ):
            left_col, right_col = join_spec  # type: ignore[misc]
            filters = [item for item in (primary_filter, secondary_filter) if item]
            where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
            sql = (
                f"SELECT b.{group_col}, COUNT(*) AS RECORD_COUNT "
                f"FROM {domain}.{primary.name} a "
                f"JOIN {domain}.{secondary.name} b ON a.{left_col} = b.{right_col} "
                f"{where_clause}"
                f"GROUP BY b.{group_col} "
                f"ORDER BY RECORD_COUNT DESC "
                f"LIMIT {limit}"
            )
            return SqlPlan(
                domain=domain,
                sql=sql,
                planner_mode="metadata_join_count",
                rationale=(
                    f"Count intent detected; joined {primary.name} to {secondary.name} "
                    f"on {left_col}={right_col}."
                ),
                grounded_entities=[primary.name, secondary.name],
                warning=None,
            )

        if group_col and group_col in primary.columns:
            where_clause = f" WHERE {primary_filter}" if primary_filter else ""
            sql = (
                f"SELECT {group_col}, COUNT(*) AS RECORD_COUNT "
                f"FROM {domain}.{primary.name} "
                f"{where_clause}"
                f"GROUP BY {group_col} "
                f"ORDER BY RECORD_COUNT DESC "
                f"LIMIT {limit}"
            )
        else:
            where_clause = f" WHERE {primary_filter}" if primary_filter else ""
            sql = (
                f"SELECT COUNT(*) AS RECORD_COUNT FROM {domain}.{primary.name}"
                f"{where_clause} LIMIT {limit}"
            )

        return SqlPlan(
            domain=domain,
            sql=sql,
            planner_mode="metadata_count",
            rationale=f"Count intent detected; aggregated {primary.name}.",
            grounded_entities=[primary.name],
            warning=None,
        )

    @staticmethod
    def _is_total_count_request(lowered_question: str) -> bool:
        return (
            ("count" in lowered_question or "how many" in lowered_question or "number of" in lowered_question)
            and not SqlPlanner._is_grouped_request(lowered_question)
            and "top " not in lowered_question
        )

    @staticmethod
    def _is_distinct_requested(lowered_question: str) -> bool:
        return "distinct" in lowered_question or "unique" in lowered_question

    @staticmethod
    def _should_default_distinct(lowered_question: str) -> bool:
        return "how many" in lowered_question or "number of" in lowered_question

    @staticmethod
    def _best_id_column(entity_name: str, columns: Sequence[str]) -> str | None:
        normalized_columns = set(columns)
        if "ID" in normalized_columns:
            return "ID"

        entity_token = entity_name.upper().split("_")[0]
        entity_id = f"{entity_token}_ID"
        if entity_id in normalized_columns:
            return entity_id

        preferred = ("COURSE_ID", "USER_ID", "SECTION_ID", "INSTANCE_ID", "SOURCE_ID", "TERM_ID")
        for col in preferred:
            if col in normalized_columns:
                return col

        for col in columns:
            if col.endswith("_ID"):
                return col
        return None

    def _plan_top(
        self,
        question: str,
        domain: str,
        primary: _EntityInfo,
        secondary: _EntityInfo | None,
        join_spec: Tuple[str, str] | None,
        limit: int,
        include_deleted: bool,
    ) -> SqlPlan:
        top_n = self._extract_top_n(question) or min(10, limit)
        group_col = self._choose_grouping_column(question, primary.columns, secondary.columns if secondary else ())
        primary_filter = self._active_filter(primary, "a", include_deleted)
        secondary_filter = (
            self._active_filter(secondary, "b", include_deleted) if secondary else None
        )

        if self._should_join_for_count_or_top(
            lowered_question=question.lower(),
            primary=primary,
            secondary=secondary,
            join_spec=join_spec,
            group_col=group_col,
        ):
            left_col, right_col = join_spec  # type: ignore[misc]
            filters = [item for item in (primary_filter, secondary_filter) if item]
            where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
            sql = (
                f"SELECT b.{group_col}, COUNT(*) AS RECORD_COUNT "
                f"FROM {domain}.{primary.name} a "
                f"JOIN {domain}.{secondary.name} b ON a.{left_col} = b.{right_col} "
                f"{where_clause}"
                f"GROUP BY b.{group_col} "
                f"ORDER BY RECORD_COUNT DESC "
                f"LIMIT {top_n}"
            )
            return SqlPlan(
                domain=domain,
                sql=sql,
                planner_mode="metadata_join_top",
                rationale=(
                    f"Top-N intent detected; grouped over joined {primary.name}/{secondary.name} "
                    f"on {left_col}={right_col} by {group_col}."
                ),
                grounded_entities=[primary.name, secondary.name],
                warning=None,
            )

        target_col = group_col if group_col and group_col in primary.columns else self._best_name_or_id(primary.columns)
        where_clause = f" WHERE {primary_filter}" if primary_filter else ""
        sql = (
            f"SELECT {target_col}, COUNT(*) AS RECORD_COUNT "
            f"FROM {domain}.{primary.name} "
            f"{where_clause}"
            f"GROUP BY {target_col} "
            f"ORDER BY RECORD_COUNT DESC "
            f"LIMIT {top_n}"
        )
        return SqlPlan(
            domain=domain,
            sql=sql,
            planner_mode="metadata_top",
            rationale=f"Top-N intent detected; aggregated {primary.name} by {target_col}.",
            grounded_entities=[primary.name],
            warning=None,
        )

    def _plan_trend(
        self,
        question: str,
        domain: str,
        primary: _EntityInfo,
        secondary: _EntityInfo | None,
        join_spec: Tuple[str, str] | None,
        limit: int,
        include_deleted: bool,
    ) -> SqlPlan:
        date_col = self._first_date_column(primary.columns)
        if not date_col and secondary:
            date_col = self._first_date_column(secondary.columns)

        if not date_col:
            # Fallback to count behavior when no date-like column is available.
            return self._plan_count(
                question=question,
                domain=domain,
                primary=primary,
                secondary=secondary,
                join_spec=join_spec,
                limit=limit,
                include_deleted=include_deleted,
            )

        primary_filter = self._active_filter(primary, "a", include_deleted)
        secondary_filter = (
            self._active_filter(secondary, "b", include_deleted) if secondary else None
        )

        if secondary and join_spec and date_col in secondary.columns:
            left_col, right_col = join_spec
            filters = [item for item in (primary_filter, secondary_filter) if item]
            where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
            sql = (
                f"SELECT DATE_TRUNC('month', b.{date_col}) AS PERIOD, COUNT(*) AS RECORD_COUNT "
                f"FROM {domain}.{primary.name} a "
                f"JOIN {domain}.{secondary.name} b ON a.{left_col} = b.{right_col} "
                f"{where_clause}"
                f"GROUP BY PERIOD "
                f"ORDER BY PERIOD "
                f"LIMIT {limit}"
            )
            grounded = [primary.name, secondary.name]
            mode = "metadata_join_trend"
            rationale = (
                f"Trend intent detected; joined {primary.name}/{secondary.name} on {left_col}={right_col} and "
                f"bucketed by {date_col}."
            )
        else:
            source = primary.name if date_col in primary.columns else (secondary.name if secondary else primary.name)
            alias = "a" if source == primary.name else "b"
            from_clause = f"{domain}.{primary.name} a"
            if secondary and join_spec:
                left_col, right_col = join_spec
                from_clause += f" JOIN {domain}.{secondary.name} b ON a.{left_col} = b.{right_col}"
            filters = [item for item in (primary_filter, secondary_filter) if item]
            where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
            sql = (
                f"SELECT DATE_TRUNC('month', {alias}.{date_col}) AS PERIOD, COUNT(*) AS RECORD_COUNT "
                f"FROM {from_clause} "
                f"{where_clause}"
                f"GROUP BY PERIOD "
                f"ORDER BY PERIOD "
                f"LIMIT {limit}"
            )
            grounded = [primary.name] + ([secondary.name] if secondary else [])
            mode = "metadata_trend"
            rationale = f"Trend intent detected; bucketed records by {date_col}."

        return SqlPlan(
            domain=domain,
            sql=sql,
            planner_mode=mode,
            rationale=rationale,
            grounded_entities=grounded,
            warning=None,
        )

    def _plan_list_or_preview(
        self,
        question: str,
        domain: str,
        primary: _EntityInfo,
        secondary: _EntityInfo | None,
        join_spec: Tuple[str, str] | None,
        limit: int,
        include_deleted: bool,
    ) -> SqlPlan:
        primary_filter = self._active_filter(primary, "a", include_deleted)
        secondary_filter = (
            self._active_filter(secondary, "b", include_deleted) if secondary else None
        )
        if self._should_join_for_list(question, primary, secondary, join_spec):
            a_cols = self._list_columns(primary.columns, "a")
            b_cols = self._list_columns(secondary.columns, "b")
            selected = (a_cols + b_cols)[:8]
            left_col, right_col = join_spec  # type: ignore[misc]
            filters = [item for item in (primary_filter, secondary_filter) if item]
            where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
            sql = (
                f"SELECT {', '.join(selected)} "
                f"FROM {domain}.{primary.name} a "
                f"JOIN {domain}.{secondary.name} b ON a.{left_col} = b.{right_col} "
                f"{where_clause} "
                f"LIMIT {limit}"
            )
            return SqlPlan(
                domain=domain,
                sql=sql,
                planner_mode="metadata_join_list",
                rationale=(
                    f"List intent detected; joined {primary.name}/{secondary.name} "
                    f"on {left_col}={right_col}."
                ),
                grounded_entities=[primary.name, secondary.name],
                warning=None,
            )

        selected = self._list_columns(primary.columns)[:8]
        if not selected:
            selected = ["*"]
        where_clause = f" WHERE {primary_filter}" if primary_filter else ""

        warning = None
        if primary.score < 2:
            warning = "Low-confidence entity match; verify selected table and columns."

        return SqlPlan(
            domain=domain,
            sql=f"SELECT {', '.join(selected)} FROM {domain}.{primary.name}{where_clause} LIMIT {limit}",
            planner_mode="metadata_heuristic",
            rationale=f"Selected {primary.name} from metadata keyword matching.",
            grounded_entities=[primary.name],
            warning=warning,
        )

    def _rank_entities(
        self,
        question: str,
        metadata: MetadataStore,
        domain: str,
        model: SemanticModel | None = None,
    ) -> List[_EntityInfo]:
        if model is not None:
            ranked = model.resolve_entity_candidates(question)
            if ranked:
                output: List[_EntityInfo] = []
                for entity, score in ranked[:3]:
                    cols = sorted(list(model.entities.get(entity, set())))
                    output.append(_EntityInfo(name=entity, score=int(score), columns=cols))
                return output

        tokens = tokenize(question)
        scored: List[_EntityInfo] = []

        for item in metadata.list_entities(domain):
            name = str(item["name"]).upper()
            detail = metadata.describe_entity(domain, name) or {"columns": {}}
            columns = list((detail.get("columns") or {}).keys())
            name_tokens = tokenize(name.replace("_", " "))
            column_tokens = set()
            for column_name in columns:
                column_tokens.update(tokenize(column_name.replace("_", " ")))

            score = 0
            score += len(tokens.intersection(name_tokens)) * 3
            score += len(tokens.intersection(column_tokens))
            if score > 0:
                scored.append(_EntityInfo(name=name, score=score, columns=columns))

        if not scored:
            # No keyword matches. Use first entity from metadata as fallback.
            entities = metadata.list_entities(domain)
            if not entities:
                return []
            first = str(entities[0]["name"]).upper()
            detail = metadata.describe_entity(domain, first) or {"columns": {}}
            return [_EntityInfo(name=first, score=0, columns=list((detail.get("columns") or {}).keys()))]

        return sorted(
            scored,
            key=lambda row: (-row.score, row.name.count("_"), len(row.name)),
        )[:3]

    @staticmethod
    def _is_grouped_request(lowered_question: str) -> bool:
        return " by " in lowered_question or " per " in lowered_question

    @staticmethod
    def _should_join_for_count_or_top(
        lowered_question: str,
        primary: _EntityInfo,
        secondary: _EntityInfo | None,
        join_spec: Tuple[str, str] | None,
        group_col: str | None,
    ) -> bool:
        if secondary is None or not join_spec or not group_col:
            return False
        if not SqlPlanner._is_grouped_request(lowered_question):
            return False
        return group_col in secondary.columns and group_col not in primary.columns

    @staticmethod
    def _should_join_for_list(
        question: str,
        primary: _EntityInfo,
        secondary: _EntityInfo | None,
        join_spec: Tuple[str, str] | None,
    ) -> bool:
        if secondary is None or not join_spec:
            return False
        lowered = question.lower()
        asks_for_multi_entity = any(
            marker in lowered
            for marker in (" with ", " including ", " along with ", " plus ", " joined ")
        )
        if not asks_for_multi_entity:
            return False
        return secondary.score >= max(1, primary.score - 1)

    @staticmethod
    def _find_join_key(primary: _EntityInfo, secondary: _EntityInfo | None) -> str | None:
        if secondary is None:
            return None

        primary_keys = set(col for col in primary.columns if col.endswith("_ID"))
        secondary_keys = set(col for col in secondary.columns if col.endswith("_ID"))
        shared = primary_keys.intersection(secondary_keys)
        if not shared:
            return None
        for key in _JOIN_KEY_PRIORITY:
            if key in shared:
                return key
        return sorted(shared)[0]

    @staticmethod
    def _find_join_spec(
        primary: _EntityInfo,
        secondary: _EntityInfo | None,
        model: SemanticModel,
    ) -> Tuple[str, str] | None:
        if secondary is None:
            return None

        candidates: List[Tuple[float, Tuple[str, str]]] = []
        for rel in model.relationships:
            if rel.source_entity == primary.name and rel.target_entity == secondary.name:
                score = SqlPlanner._join_edge_score(rel)
                candidates.append((score, (rel.source_column, rel.target_column)))
            elif rel.source_entity == secondary.name and rel.target_entity == primary.name:
                score = SqlPlanner._join_edge_score(rel)
                candidates.append((score, (rel.target_column, rel.source_column)))

        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            return candidates[0][1]

        shared = SqlPlanner._find_join_key(primary, secondary)
        if shared:
            return (shared, shared)
        return None

    @staticmethod
    def _join_edge_score(rel: Relationship) -> float:
        score = float(rel.confidence) * 10.0
        preferred = {"COURSE_ID", "PERSON_COURSE_ID", "TERM_ID", "USER_ID", "SECTION_ID", "ID"}
        if rel.source_column in preferred:
            score += 2.0
        if rel.target_column in preferred:
            score += 2.0
        if rel.source_column == "INSTANCE_ID" or rel.target_column == "INSTANCE_ID":
            score -= 3.0
        if rel.source_column == "SOURCE_ID" or rel.target_column == "SOURCE_ID":
            score -= 2.0
        return score

    @staticmethod
    def _choose_grouping_column(
        question: str,
        primary_columns: Sequence[str],
        secondary_columns: Sequence[str],
    ) -> str | None:
        tokens = tokenize(question)
        candidates = list(primary_columns) + list(secondary_columns)

        # Prefer *_NAME columns that match question keywords.
        for col in candidates:
            if col.endswith("_NAME") and tokens.intersection(tokenize(col)):
                return col

        # Then preferred dimensions.
        for col in ("COURSE_ID", "TERM_ID", "USER_ID", "SECTION_ID"):
            if col in candidates:
                return col

        return None

    @staticmethod
    def _best_name_or_id(columns: Sequence[str]) -> str:
        for col in columns:
            if col.endswith("_NAME"):
                return col
        for col in columns:
            if col.endswith("_ID"):
                return col
        return columns[0] if columns else "*"

    @staticmethod
    def _first_date_column(columns: Sequence[str]) -> str | None:
        for col in columns:
            upper = col.upper()
            if upper.endswith("_DATE") or "DATE" in upper or "TIMESTAMP" in upper:
                return col
        return None

    @staticmethod
    def _list_columns(columns: Sequence[str], alias: str | None = None) -> List[str]:
        preferred = [col for col in columns if col.endswith("_NAME") or col.endswith("_ID")]
        selected = preferred if preferred else list(columns)
        if alias:
            return [f"{alias}.{col}" for col in selected]
        return list(selected)

    @staticmethod
    def _infer_intent(question: str, output_intent: str | None) -> str:
        explicit = (output_intent or "").strip().lower()
        if explicit in {"viz", "trend", "table", "text", "count", "top", "analysis"}:
            return "trend" if explicit == "viz" else explicit

        lowered = question.lower()
        if "average" in lowered or "avg" in lowered or "median" in lowered:
            return "analysis"
        if "trend" in lowered or "over time" in lowered or "by month" in lowered:
            return "trend"
        if "top " in lowered or lowered.startswith("top"):
            return "top"
        if "count" in lowered or "how many" in lowered or "number of" in lowered:
            return "count"
        if "list" in lowered:
            return "text"
        return "table"

    def _infer_limit(self, question: str) -> int:
        matches = re.findall(r"\b(?:top|limit)\s+(\d{1,4})\b", question.lower())
        if matches:
            value = int(matches[0])
            return max(1, min(value, self._config.max_rows))
        return min(100, self._config.max_rows)

    @staticmethod
    def _extract_top_n(question: str) -> int | None:
        matches = re.findall(r"\btop\s+(\d{1,4})\b", question.lower())
        if not matches:
            return None
        return int(matches[0])

    @staticmethod
    def _wants_deleted_data(question: str) -> bool:
        lowered = question.lower()
        return any(
            marker in lowered
            for marker in (
                "deleted",
                "soft-deleted",
                "soft deleted",
                "including deleted",
                "include deleted",
                "all rows",
                "historical rows",
            )
        )

    @staticmethod
    def _active_filter(entity: _EntityInfo | None, alias: str, include_deleted: bool) -> str | None:
        if include_deleted or entity is None:
            return None
        if "ROW_DELETED_TIME" not in set(entity.columns):
            return None
        return f"{alias}.ROW_DELETED_TIME IS NULL"
