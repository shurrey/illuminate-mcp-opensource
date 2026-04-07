"""Diagnostic query catalog and anomaly detection for discover_insights."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Dict, List, Sequence, Tuple

from .config import AppConfig
from .execution import SnowflakeExecutor


@dataclass(frozen=True)
class DiagnosticQuery:
    id: str
    domain: str
    title: str
    description: str
    sql_template: str  # Uses {database}, {current_term_id}, {current_term_name} placeholders
    analysis_type: str  # "time_series" | "list_count" | "ratio" | "distribution" | "volume"
    threshold_pct: float
    severity_floor: str
    followup_template: str
    explanation: str = ""  # Human-readable explanation of what this check measures and why


@dataclass
class InsightFinding:
    query_id: str
    domain: str
    severity: str  # "critical" | "warning" | "info" | "ok"
    title: str
    description: str
    metric_value: Any
    comparison_value: Any
    change_pct: float | None
    suggested_followup: str
    detail_rows: list
    detail_columns: list
    explanation: str = ""
    sql: str = ""


# ---------------------------------------------------------------------------
# Diagnostic query catalog — uses TERM_ID for scoping
# ---------------------------------------------------------------------------

_CATALOG: List[DiagnosticQuery] = [
    # ── CDM_LMS ────────────────────────────────────────────
    DiagnosticQuery(
        id="lms_enrollment_trend",
        domain="CDM_LMS",
        title="Enrollment trend change",
        description="Monthly enrollment volume for current term vs prior months",
        sql_template="""
            SELECT
                DATE_TRUNC('month', pc.ENROLLMENT_TIME) AS enrollment_month,
                COUNT(*) AS enrollment_count
            FROM {database}.CDM_LMS.PERSON_COURSE pc
            JOIN {database}.CDM_LMS.COURSE c ON c.ID = pc.COURSE_ID AND c.ROW_DELETED_TIME IS NULL
            WHERE pc.ROW_DELETED_TIME IS NULL
              AND pc.STUDENT_IND = TRUE
              AND c.TERM_ID = '{current_term_id}'
            GROUP BY 1
            ORDER BY 1
        """,
        analysis_type="time_series",
        threshold_pct=15.0,
        severity_floor="warning",
        followup_template="Show me enrollment details for the current term broken down by month",
        explanation="Compares month-over-month enrollment counts from PERSON_COURSE for the current term. A significant drop may indicate registration issues, course availability problems, or seasonal patterns. Scoped to students only (STUDENT_IND=TRUE).",
    ),
    DiagnosticQuery(
        id="lms_zero_activity_courses",
        domain="CDM_LMS",
        title="Courses with zero activity",
        description="Current-term courses with enrolled students but no recorded activity in CDM_LMS.COURSE_ACTIVITY",
        sql_template="""
            WITH enrolled_courses AS (
                SELECT DISTINCT pc.COURSE_ID
                FROM {database}.CDM_LMS.PERSON_COURSE pc
                JOIN {database}.CDM_LMS.COURSE c ON c.ID = pc.COURSE_ID AND c.ROW_DELETED_TIME IS NULL
                WHERE pc.ROW_DELETED_TIME IS NULL
                  AND pc.STUDENT_IND = TRUE
                  AND c.TERM_ID = '{current_term_id}'
            ),
            active_courses AS (
                SELECT DISTINCT ca.COURSE_ID
                FROM {database}.CDM_LMS.COURSE_ACTIVITY ca
                WHERE ca.ROW_DELETED_TIME IS NULL
            )
            SELECT
                ec.COURSE_ID,
                c.NAME
            FROM enrolled_courses ec
            JOIN {database}.CDM_LMS.COURSE c ON c.ID = ec.COURSE_ID AND c.ROW_DELETED_TIME IS NULL
            LEFT JOIN active_courses ac ON ac.COURSE_ID = ec.COURSE_ID
            WHERE ac.COURSE_ID IS NULL
            ORDER BY c.NAME
            LIMIT 50
        """,
        analysis_type="list_count",
        threshold_pct=1.0,
        severity_floor="warning",
        followup_template="Show me all current-term courses with enrolled students but zero activity",
        explanation="Finds current-term courses that have student enrollments in PERSON_COURSE but zero rows in COURSE_ACTIVITY. These are courses where students are registered but no one has interacted with the course content yet.",
    ),
    DiagnosticQuery(
        id="lms_low_scores",
        domain="CDM_LMS",
        title="Low normalized score rate",
        description="Percentage of current-term grades with normalized score below 0.5 (50%)",
        sql_template="""
            SELECT
                COUNT(CASE WHEN g.NORMALIZED_SCORE < 0.5 THEN 1 END) AS low_count,
                COUNT(*) AS total_count
            FROM {database}.CDM_LMS.GRADE g
            JOIN {database}.CDM_LMS.PERSON_COURSE pc ON pc.ID = g.PERSON_COURSE_ID AND pc.ROW_DELETED_TIME IS NULL
            JOIN {database}.CDM_LMS.COURSE c ON c.ID = pc.COURSE_ID AND c.ROW_DELETED_TIME IS NULL
            WHERE g.ROW_DELETED_TIME IS NULL
              AND g.NORMALIZED_SCORE IS NOT NULL
              AND c.TERM_ID = '{current_term_id}'
        """,
        analysis_type="ratio",
        threshold_pct=20.0,
        severity_floor="warning",
        followup_template="Show me grade distribution by course for the current term where normalized score is below 0.5 (NORMALIZED_SCORE is a 0-to-1 ratio)",
        explanation="Checks what percentage of current-term grades have a NORMALIZED_SCORE below 0.5 (50%). NORMALIZED_SCORE is a 0-to-1 ratio where 1.0 = 100%. Joins GRADE → PERSON_COURSE → COURSE to scope to the current term. A high rate may indicate grading issues or data quality problems.",
    ),
    DiagnosticQuery(
        id="lms_attempt_completion",
        domain="CDM_LMS",
        title="Attempt completion breakdown",
        description="Distribution of attempt statuses for the current term",
        sql_template="""
            SELECT
                a.STATUS AS attempt_status,
                a.STATUS_SOURCE_DESC AS status_description,
                COUNT(*) AS attempt_count,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS pct_of_total
            FROM {database}.CDM_LMS.ATTEMPT a
            JOIN {database}.CDM_LMS.PERSON_COURSE pc ON pc.ID = a.PERSON_COURSE_ID AND pc.ROW_DELETED_TIME IS NULL
            JOIN {database}.CDM_LMS.COURSE c ON c.ID = pc.COURSE_ID AND c.ROW_DELETED_TIME IS NULL
            WHERE a.ROW_DELETED_TIME IS NULL
              AND c.TERM_ID = '{current_term_id}'
            GROUP BY 1, 2
            ORDER BY attempt_count DESC
        """,
        analysis_type="distribution",
        threshold_pct=30.0,
        severity_floor="info",
        followup_template="Show me attempt status breakdown by course for the current term",
        explanation="Shows how assignment attempts break down by status (e.g., Completed, Needs Grading, In Progress) for the current term. Joins ATTEMPT → PERSON_COURSE → COURSE for term scoping. Useful for identifying submission bottlenecks or grading backlogs.",
    ),
    # ── CDM_TLM ────────────────────────────────────────────
    DiagnosticQuery(
        id="tlm_activity_volume",
        domain="CDM_TLM",
        title="Telemetry event volume",
        description="Event counts across all TLM event tables",
        sql_template="""
            SELECT 'SESSION_EVENTS' AS event_source, COUNT(*) AS event_count FROM {database}.CDM_TLM.SESSION_EVENTS
            UNION ALL
            SELECT 'TOOL_USE_EVENTS', COUNT(*) FROM {database}.CDM_TLM.TOOL_USE_EVENTS
            UNION ALL
            SELECT 'ASSIGNABLE_EVENTS', COUNT(*) FROM {database}.CDM_TLM.ASSIGNABLE_EVENTS
            UNION ALL
            SELECT 'ULTRA_EVENTS', COUNT(*) FROM {database}.CDM_TLM.ULTRA_EVENTS
            UNION ALL
            SELECT 'MOBILE_EVENTS', COUNT(*) FROM {database}.CDM_TLM.MOBILE_EVENTS
            UNION ALL
            SELECT 'COLLAB_EVENTS', COUNT(*) FROM {database}.CDM_TLM.COLLAB_EVENTS
            UNION ALL
            SELECT 'ALLY_EVENTS', COUNT(*) FROM {database}.CDM_TLM.ALLY_EVENTS
            UNION ALL
            SELECT 'SAFEASSIGN_EVENTS', COUNT(*) FROM {database}.CDM_TLM.SAFEASSIGN_EVENTS
            ORDER BY event_count DESC
        """,
        analysis_type="volume",
        threshold_pct=0.0,
        severity_floor="info",
        followup_template="Show me telemetry event volumes by source and trend over time",
        explanation="Counts total events across all CDM_TLM Caliper event tables (sessions, tool use, assignments, Ultra, mobile, Collaborate, Ally, SafeAssign). Not term-scoped — shows all-time volume. Sources with zero events may indicate the product isn't in use or data isn't flowing.",
    ),
    DiagnosticQuery(
        id="lms_low_instructor_activity",
        domain="CDM_LMS",
        title="Low instructor activity this term",
        description="Current-term courses where instructors have fewer than 5 activity interactions",
        sql_template="""
            SELECT
                c.NAME AS course_name,
                pc.PERSON_ID AS instructor_id,
                COALESCE(SUM(ca.INTERACTION_CNT), 0) AS instructor_interactions
            FROM {database}.CDM_LMS.PERSON_COURSE pc
            JOIN {database}.CDM_LMS.COURSE c ON c.ID = pc.COURSE_ID AND c.ROW_DELETED_TIME IS NULL
            LEFT JOIN {database}.CDM_LMS.COURSE_ACTIVITY ca
                ON ca.COURSE_ID = pc.COURSE_ID
                AND ca.PERSON_ID = pc.PERSON_ID
                AND ca.ROW_DELETED_TIME IS NULL
            WHERE pc.ROW_DELETED_TIME IS NULL
              AND pc.ACT_AS_INSTRUCTOR_IND = TRUE
              AND c.TERM_ID = '{current_term_id}'
            GROUP BY 1, 2
            HAVING COALESCE(SUM(ca.INTERACTION_CNT), 0) < 5
            ORDER BY instructor_interactions ASC
            LIMIT 50
        """,
        analysis_type="list_count",
        threshold_pct=1.0,
        severity_floor="warning",
        followup_template="Show me current-term courses with low instructor activity, including instructor details and last access time",
        explanation="Flags current-term courses where the instructor has fewer than 5 interactions in COURSE_ACTIVITY. Joins PERSON_COURSE (ACT_AS_INSTRUCTOR_IND=TRUE) to COURSE_ACTIVITY by course and person. Relevant to Title II reporting — low instructor engagement may indicate courses that need attention.",
    ),
    # ── CDM_ALY ────────────────────────────────────────────
    DiagnosticQuery(
        id="aly_score_distribution",
        domain="CDM_ALY",
        title="Course accessibility score distribution",
        description="Distribution of course accessibility scores across score bands",
        sql_template="""
            SELECT
                CASE
                    WHEN cs.NUMERIC_SCORE >= 90 THEN 'A (90-100)'
                    WHEN cs.NUMERIC_SCORE >= 80 THEN 'B (80-89)'
                    WHEN cs.NUMERIC_SCORE >= 70 THEN 'C (70-79)'
                    WHEN cs.NUMERIC_SCORE >= 60 THEN 'D (60-69)'
                    ELSE 'F (<60)'
                END AS score_band,
                COUNT(*) AS course_count,
                ROUND(AVG(cs.NUMERIC_SCORE), 2) AS avg_score
            FROM {database}.CDM_ALY.COURSE_SCORE cs
            WHERE cs.ROW_DELETED_TIME IS NULL
            GROUP BY 1
            ORDER BY 1
        """,
        analysis_type="distribution",
        threshold_pct=30.0,
        severity_floor="warning",
        followup_template="Show me course accessibility scores with the lowest scores, including course names",
        explanation="Distributes COURSE_SCORE accessibility scores into letter-grade bands (A through F). Not term-scoped — reflects the latest score per course. A high concentration in D/F bands suggests systemic accessibility issues across course content.",
    ),
    DiagnosticQuery(
        id="aly_stale_content",
        domain="CDM_ALY",
        title="Stale content scores",
        description="Content with accessibility scores older than 90 days",
        sql_template="""
            SELECT
                COUNT(*) AS total_scored_content,
                COUNT_IF(cs.SCORING_TIMESTAMP < DATEADD('day', -90, CURRENT_DATE))
                    AS scored_over_90_days_ago,
                MIN(cs.SCORING_TIMESTAMP) AS oldest_score_time,
                MAX(cs.SCORING_TIMESTAMP) AS newest_score_time
            FROM {database}.CDM_ALY.CONTENT_SCORE cs
            WHERE cs.IS_LATEST_SCORE = TRUE
              AND cs.ROW_DELETED_TIME IS NULL
        """,
        analysis_type="ratio",
        threshold_pct=20.0,
        severity_floor="info",
        followup_template="Show me content items with the oldest accessibility scores",
        explanation="Checks how many content items have accessibility scores older than 90 days in CONTENT_SCORE (IS_LATEST_SCORE=TRUE). Not term-scoped. Stale scores mean content may have changed since it was last evaluated for accessibility compliance.",
    ),
    # ── CDM_SIS ────────────────────────────────────────────
    DiagnosticQuery(
        id="sis_enrollment_trend",
        domain="CDM_SIS",
        title="SIS enrollment trend",
        description="Monthly SIS enrollment volume over the past 24 months",
        sql_template="""
            SELECT
                DATE_TRUNC('month', e.ENROLLMENT_DATE) AS enrollment_month,
                COUNT(*) AS enrollment_count,
                COUNT(DISTINCT e.STUDENT_ID) AS unique_students
            FROM {database}.CDM_SIS.ENROLLMENT e
            WHERE e.ROW_DELETED_TIME IS NULL
              AND e.ENROLLMENT_DATE IS NOT NULL
            GROUP BY 1
            ORDER BY 1 DESC
            LIMIT 24
        """,
        analysis_type="time_series",
        threshold_pct=15.0,
        severity_floor="warning",
        followup_template="Show me SIS enrollment counts by month with student counts",
        explanation="Shows SIS enrollment volume by month over the past 24 months. Not term-scoped — intentionally cross-term to reveal registration trends. Compares the two most recent months to detect significant changes in institutional enrollment patterns.",
    ),
    DiagnosticQuery(
        id="sis_student_status",
        domain="CDM_SIS",
        title="Student status distribution",
        description="Breakdown of students by school status category",
        sql_template="""
            SELECT
                ss.SYSTEM_STATUS_SOURCE_DESC AS system_status,
                ss.ACTIVE_IND AS is_active,
                ss.DESCRIPTION AS status_description,
                COUNT(*) AS student_count
            FROM {database}.CDM_SIS.STUDENT s
            JOIN {database}.CDM_SIS.SCHOOL_STATUS ss ON ss.ID = s.SCHOOL_STATUS_ID
            WHERE s.ROW_DELETED_TIME IS NULL
              AND ss.ROW_DELETED_TIME IS NULL
            GROUP BY 1, 2, 3
            ORDER BY student_count DESC
        """,
        analysis_type="distribution",
        threshold_pct=20.0,
        severity_floor="info",
        followup_template="Show me the full breakdown of student statuses with counts and active indicators",
        explanation="Breaks down students by SCHOOL_STATUS (joined via SCHOOL_STATUS_ID). Uses ACTIVE_IND to separate active from inactive students. Not term-scoped — reflects current student roster. A high inactive percentage may warrant review of student retention or data cleanup.",
    ),
]


def get_diagnostic_queries(allowed_domains: Sequence[str]) -> List[DiagnosticQuery]:
    """Return diagnostic queries filtered to the configured domains."""
    domain_set = {d.upper() for d in allowed_domains}
    return [q for q in _CATALOG if q.domain in domain_set]


# ---------------------------------------------------------------------------
# Term resolution
# ---------------------------------------------------------------------------

def resolve_current_term(
    executor: SnowflakeExecutor,
) -> Dict[str, str]:
    """Query CDM_LMS.TERM for the current active term. Returns {id, name} or empty dict."""
    sql = """
        SELECT ID, NAME
        FROM {database}.CDM_LMS.TERM
        WHERE ROW_DELETED_TIME IS NULL
          AND START_DATE <= CURRENT_DATE()
          AND END_DATE >= CURRENT_DATE()
        ORDER BY START_DATE DESC
        LIMIT 1
    """.format(database=executor._config.snowflake_database)

    try:
        result = executor.run_query(sql, row_limit=1)
        if result.status == "ok" and result.rows:
            row = result.rows[0]
            return {"id": str(row[0]), "name": str(row[1])}
    except Exception:
        pass

    # Fallback: get the most recent term
    sql_fallback = """
        SELECT ID, NAME
        FROM {database}.CDM_LMS.TERM
        WHERE ROW_DELETED_TIME IS NULL
          AND START_DATE <= CURRENT_DATE()
        ORDER BY START_DATE DESC
        LIMIT 1
    """.format(database=executor._config.snowflake_database)

    try:
        result = executor.run_query(sql_fallback, row_limit=1)
        if result.status == "ok" and result.rows:
            row = result.rows[0]
            return {"id": str(row[0]), "name": str(row[1])}
    except Exception:
        pass

    return {}


# ---------------------------------------------------------------------------
# Anomaly detection — dispatches on analysis_type
# ---------------------------------------------------------------------------

def analyze_results(
    query: DiagnosticQuery,
    columns: Sequence[str],
    rows: Sequence[Sequence],
) -> InsightFinding:
    """Analyze query results. Always returns a finding (including 'ok' for passing checks)."""
    if not rows:
        finding = InsightFinding(
            query_id=query.id, domain=query.domain, severity="ok",
            title=f"{query.title}: no data",
            description=f"{query.description}. No records returned.",
            metric_value=0, comparison_value=None, change_pct=None,
            suggested_followup=query.followup_template,
            detail_rows=[], detail_columns=list(columns),
        )
        finding.explanation = query.explanation
        return finding

    handler = _ANALYZERS.get(query.analysis_type)
    if handler:
        result = handler(query, columns, rows)
        if result:
            result.explanation = query.explanation
            return result

    finding = InsightFinding(
        query_id=query.id, domain=query.domain, severity="ok",
        title=f"{query.title}: looks good",
        description=f"{query.description}. No anomalies detected.",
        metric_value=None, comparison_value=None, change_pct=None,
        suggested_followup=query.followup_template,
        detail_rows=[_safe_row(r) for r in rows[:3]],
        detail_columns=list(columns),
    )
    finding.explanation = query.explanation
    return finding


def _analyze_time_series(
    query: DiagnosticQuery, columns: Sequence[str], rows: Sequence[Sequence],
) -> InsightFinding | None:
    if len(rows) < 2:
        return None
    val_idx = 1
    recent = _to_float(rows[-1][val_idx])
    prior = _to_float(rows[-2][val_idx])
    if prior == 0 and recent == 0:
        return None
    change_pct = ((recent - prior) / prior * 100) if prior != 0 else (100.0 if recent > 0 else 0.0)
    if abs(change_pct) < query.threshold_pct:
        return None
    severity = _compute_severity(change_pct, query.threshold_pct, query.severity_floor)
    direction = "increased" if change_pct > 0 else "decreased"
    return InsightFinding(
        query_id=query.id, domain=query.domain, severity=severity,
        title=f"{query.title}: {direction} {abs(change_pct):.1f}%",
        description=f"{query.description}. Most recent period: {_fmt_num(recent)}, prior: {_fmt_num(prior)} ({direction} {abs(change_pct):.1f}%).",
        metric_value=recent, comparison_value=prior,
        change_pct=round(change_pct, 1),
        suggested_followup=query.followup_template,
        detail_rows=[_safe_row(r) for r in rows[-5:]],
        detail_columns=list(columns),
    )


def _analyze_list_count(
    query: DiagnosticQuery, columns: Sequence[str], rows: Sequence[Sequence],
) -> InsightFinding | None:
    count = len(rows)
    if count == 0:
        return None
    # Check if result was likely truncated by LIMIT
    truncated = "LIMIT" in query.sql_template.upper()
    display_count = f"{count}+" if truncated else str(count)
    severity = _compute_severity(count, max(1, query.threshold_pct), query.severity_floor)
    return InsightFinding(
        query_id=query.id, domain=query.domain, severity=severity,
        title=f"{query.title}: {display_count} found",
        description=f"{query.description}. Found {display_count} items.",
        metric_value=count, comparison_value=None, change_pct=None,
        suggested_followup=query.followup_template,
        detail_rows=[_safe_row(r) for r in rows[:5]],
        detail_columns=list(columns),
    )


def _analyze_ratio(
    query: DiagnosticQuery, columns: Sequence[str], rows: Sequence[Sequence],
) -> InsightFinding | None:
    if not rows or len(rows[0]) < 2:
        return None
    flagged = _to_float(rows[0][0])
    total = _to_float(rows[0][1])
    if total == 0:
        return InsightFinding(
            query_id=query.id, domain=query.domain, severity="ok",
            title=f"{query.title}: no data",
            description=f"{query.description}. No records found.",
            metric_value=0, comparison_value=0, change_pct=None,
            suggested_followup=query.followup_template,
            detail_rows=[_safe_row(r) for r in rows[:5]],
            detail_columns=list(columns),
        )
    pct = flagged / total * 100
    if pct < query.threshold_pct:
        return None
    severity = _compute_severity(pct, query.threshold_pct, query.severity_floor)
    return InsightFinding(
        query_id=query.id, domain=query.domain, severity=severity,
        title=f"{query.title}: {pct:.1f}%",
        description=f"{query.description}. {_fmt_num(flagged)} of {_fmt_num(total)} ({pct:.1f}%).",
        metric_value=flagged, comparison_value=total,
        change_pct=round(pct, 1),
        suggested_followup=query.followup_template,
        detail_rows=[_safe_row(r) for r in rows[:5]],
        detail_columns=list(columns),
    )


def _analyze_distribution(
    query: DiagnosticQuery, columns: Sequence[str], rows: Sequence[Sequence],
) -> InsightFinding | None:
    if not rows:
        return None
    upper_cols = [str(c).upper() for c in columns]

    # Check for active/inactive patterns
    if "IS_ACTIVE" in upper_cols:
        active_idx = upper_cols.index("IS_ACTIVE")
        count_idx = _find_count_column(upper_cols)
        if count_idx is not None:
            total = sum(_to_float(r[count_idx]) for r in rows)
            inactive = sum(_to_float(r[count_idx]) for r in rows if not r[active_idx])
            if total > 0:
                inactive_pct = inactive / total * 100
                if inactive_pct < query.threshold_pct:
                    return None
                severity = _compute_severity(inactive_pct, query.threshold_pct, query.severity_floor)
                return InsightFinding(
                    query_id=query.id, domain=query.domain, severity=severity,
                    title=f"{query.title}: {inactive_pct:.1f}% inactive",
                    description=f"{query.description}. {_fmt_num(inactive)} of {_fmt_num(total)} ({inactive_pct:.1f}%) are inactive.",
                    metric_value=inactive, comparison_value=total,
                    change_pct=round(inactive_pct, 1),
                    suggested_followup=query.followup_template,
                    detail_rows=[_safe_row(r) for r in rows[:5]],
                    detail_columns=list(columns),
                )

    # Generic distribution — always surface as info
    count_idx = _find_count_column(upper_cols)
    total = sum(_to_float(r[count_idx]) for r in rows) if count_idx is not None else len(rows)

    if total == 0:
        return None  # Falls through to "no data" in analyze_results

    return InsightFinding(
        query_id=query.id, domain=query.domain, severity=query.severity_floor,
        title=f"{query.title}: {_fmt_num(total)} records across {len(rows)} categories",
        description=f"{query.description}. {_fmt_num(total)} records across {len(rows)} categories.",
        metric_value=total, comparison_value=None, change_pct=None,
        suggested_followup=query.followup_template,
        detail_rows=[_safe_row(r) for r in rows[:5]],
        detail_columns=list(columns),
    )


def _analyze_volume(
    query: DiagnosticQuery, columns: Sequence[str], rows: Sequence[Sequence],
) -> InsightFinding | None:
    if not rows:
        return None
    upper_cols = [str(c).upper() for c in columns]
    count_idx = _find_count_column(upper_cols)
    if count_idx is None:
        count_idx = len(upper_cols) - 1
    total = sum(_to_float(r[count_idx]) for r in rows)
    zero_sources = [r for r in rows if _to_float(r[count_idx]) == 0]

    # All sources empty — treat as no data
    if total == 0:
        return InsightFinding(
            query_id=query.id, domain=query.domain, severity="ok",
            title=f"{query.title}: no data",
            description=f"{query.description}. No events found across {len(rows)} sources.",
            metric_value=0, comparison_value=len(rows), change_pct=None,
            suggested_followup=query.followup_template,
            detail_rows=[_safe_row(r) for r in rows[:8]],
            detail_columns=list(columns),
        )

    severity = query.severity_floor
    title_extra = ""
    if zero_sources:
        severity = "warning"
        title_extra = f", {len(zero_sources)} source{'s' if len(zero_sources) != 1 else ''} empty"
    return InsightFinding(
        query_id=query.id, domain=query.domain, severity=severity,
        title=f"{query.title}: {_fmt_num(total)} total events{title_extra}",
        description=f"{query.description}. Total: {_fmt_num(total)} across {len(rows)} sources." + (
            f" {len(zero_sources)} source(s) have zero events." if zero_sources else ""
        ),
        metric_value=total, comparison_value=len(rows), change_pct=None,
        suggested_followup=query.followup_template,
        detail_rows=[_safe_row(r) for r in rows[:8]],
        detail_columns=list(columns),
    )


_ANALYZERS = {
    "time_series": _analyze_time_series,
    "list_count": _analyze_list_count,
    "ratio": _analyze_ratio,
    "distribution": _analyze_distribution,
    "volume": _analyze_volume,
}


# ---------------------------------------------------------------------------
# Runner — uses executor for all queries (same pipeline as run_query)
# ---------------------------------------------------------------------------

_SKIP_PATTERNS = (
    "does not exist", "object does not exist", "insufficient privileges",
    "is not recognized", "invalid identifier", "no active warehouse",
)


def _is_skippable_error(msg: str) -> bool:
    lowered = msg.lower()
    return any(pattern in lowered for pattern in _SKIP_PATTERNS)


def run_diagnostics(
    executor: SnowflakeExecutor,
    config: AppConfig,
    allowed_domains: Sequence[str],
) -> Tuple[List[InsightFinding], Dict[str, Any]]:
    """Run all applicable diagnostic queries via the executor and return findings + stats."""
    queries = get_diagnostic_queries(allowed_domains)
    findings: List[InsightFinding] = []
    errors: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []
    started = time.time()

    if not queries:
        return findings, _stats(allowed_domains, 0, errors, skipped, started)

    # Resolve current term
    term = resolve_current_term(executor)
    current_term_id = term.get("id", "")
    current_term_name = term.get("name", "Unknown Term")

    database = config.snowflake_database

    for query in queries:
        sql = query.sql_template.format(
            database=database,
            domain=query.domain,
            current_term_id=current_term_id,
            current_term_name=current_term_name,
        )
        try:
            result = executor.run_query(sql, row_limit=100)
            if result.status != "ok":
                skipped.append({
                    "query_id": query.id, "domain": query.domain,
                    "error": result.message,
                })
                continue
            finding = analyze_results(query, result.columns, result.rows)
            finding.sql = sql.strip()
            findings.append(finding)
        except Exception as exc:
            msg = str(exc)
            entry = {"query_id": query.id, "domain": query.domain, "error": msg}
            if _is_skippable_error(msg):
                skipped.append(entry)
            else:
                errors.append(entry)

    # Sort: critical > warning > info > ok
    severity_rank = {"critical": 0, "warning": 1, "info": 2, "ok": 3}
    findings.sort(key=lambda f: (
        severity_rank.get(f.severity, 9),
        -(abs(f.change_pct) if f.change_pct is not None else 0),
    ))

    stats = _stats(allowed_domains, len(queries), errors, skipped, started)
    if current_term_id:
        stats["current_term"] = {"id": current_term_id, "name": current_term_name}
    return findings, stats


def _stats(domains, queries_run, errors, skipped, started):
    return {
        "domains_scanned": list(domains),
        "queries_run": queries_run,
        "queries_failed": len(errors),
        "queries_skipped": len(skipped),
        "errors": errors,
        "skipped": skipped,
        "scan_seconds": round(time.time() - started, 2),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_row(row: Sequence) -> list:
    from datetime import date, datetime, time
    from decimal import Decimal
    result = []
    for val in row:
        if isinstance(val, (datetime, date, time)):
            result.append(val.isoformat())
        elif isinstance(val, Decimal):
            result.append(float(val))
        else:
            result.append(val)
    return result


def _to_float(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _fmt_num(val: float) -> str:
    if val == int(val):
        return f"{int(val):,}"
    return f"{val:,.2f}"


def _find_count_column(upper_cols: Sequence[str]) -> int | None:
    for i, c in enumerate(upper_cols):
        if any(kw in c for kw in ("COUNT", "TOTAL", "CNT")):
            return i
    return None


def _compute_severity(value: float, threshold: float, floor: str) -> str:
    rank = {"critical": 0, "warning": 1, "info": 2, "ok": 3}
    if abs(value) >= threshold * 2:
        detected = "critical"
    elif abs(value) >= threshold:
        detected = "warning"
    else:
        detected = "info"
    if rank.get(detected, 9) > rank.get(floor, 9):
        return floor
    return detected
