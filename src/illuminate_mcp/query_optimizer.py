"""Pre-execution query optimizer — term scoping, EXPLAIN pre-check, simplification."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Sequence

from .config import AppConfig


@dataclass
class OptimizationResult:
    sql: str
    applied: List[str]  # list of optimization names applied
    warnings: List[str]  # warnings for the user (e.g., "large scan estimated")
    blocked: bool  # if True, suggest the user add filters instead of running


# Temporal column patterns
_TEMPORAL_COLUMNS = {
    "ENROLLMENT_TIME", "ENROLLMENT_DATE", "EVENT_TIME", "SUBMITTED_TIME",
    "CREATED_DATE", "DUE_DATE", "START_DATE", "END_DATE", "START_TIME",
    "END_TIME", "JOIN_TIME", "LEAVE_TIME", "ACTIVITY_TIME", "SNAPSHOT_TIME",
    "METRIC_DATE", "SCORING_TIMESTAMP", "LAST_ACCESSED_TIME", "ATTEMPT_DATE",
}

# Patterns that indicate the user wants historical/trend/comparative data
_HISTORICAL_PATTERNS = re.compile(
    r"\b(?:trend|over time|by month|by week|by day|by year|monthly|weekly|daily|yearly"
    r"|historical|all time|past \d+|last \d+|since|between|compare|comparison"
    r"|year over year|month over month|growth|decline|change over)\b",
    re.IGNORECASE,
)

# Patterns that indicate a specific time scope is already present
_HAS_TIME_FILTER = re.compile(
    r"(?:WHERE|AND)\s+\w+\.?\w*\s*(?:>=?|<=?|BETWEEN)\s*(?:DATEADD|CURRENT_DATE|GETDATE|'\d{4}|\d{4}-\d{2})",
    re.IGNORECASE,
)

# Tables known to have temporal columns (domain.entity -> column)
_ENTITY_TEMPORAL_COLUMNS: Dict[str, str] = {
    "PERSON_COURSE": "ENROLLMENT_TIME",
    "ENROLLMENT": "ENROLLMENT_DATE",
    "GRADE": "SUBMITTED_TIME",
    "ATTEMPT": "SUBMITTED_TIME",
    "LEARNER_ACTIVITY": "EVENT_TIME",
    "ULTRA_EVENTS": "EVENT_TIME",
    "SESSION_EVENTS": "EVENT_TIME",
    "COURSE_ACTIVITY": "LAST_ACCESSED_TIME",
    "COURSE_REGISTRATION": "ENROLLMENT_DATE",
    "METRIC_DAILY": "METRIC_DATE",
    "KPI_SNAPSHOT": "SNAPSHOT_TIME",
    "CONTENT_SCORE": "SCORING_TIMESTAMP",
    "COURSE_SCORE": "SCORE_COMPUTED_TIME",
}


def optimize_query(
    sql: str,
    question: str,
    config: AppConfig,
    executor: Any = None,
) -> OptimizationResult:
    """Apply pre-execution optimizations to a SQL query."""
    try:
        return _optimize_query_inner(sql, question, config, executor)
    except Exception:
        # Optimizer should never block query execution
        return OptimizationResult(sql=sql, applied=[], warnings=[], blocked=False)


def _optimize_query_inner(
    sql: str,
    question: str,
    config: AppConfig,
    executor: Any,
) -> OptimizationResult:
    applied = []
    warnings = []
    optimized = sql

    # 1. Term scoping — add date filter if missing and question isn't historical
    scoped, scope_applied = _apply_term_scoping(optimized, question, config)
    if scope_applied:
        optimized = scoped
        applied.append(scope_applied)

    # 2. Query simplification — check for common issues
    simplified, simp_notes = _simplify_query(optimized, question)
    if simp_notes:
        optimized = simplified
        applied.extend(simp_notes)

    # 3. EXPLAIN pre-check — estimate scan size
    if executor and config.enable_query_execution:
        explain_warnings = _explain_precheck(optimized, executor)
        warnings.extend(explain_warnings)

    blocked = any("Consider adding filters" in w for w in warnings)

    return OptimizationResult(
        sql=optimized,
        applied=applied,
        warnings=warnings,
        blocked=blocked,
    )


# ---------------------------------------------------------------------------
# 1. Term scoping
# ---------------------------------------------------------------------------

def _apply_term_scoping(sql: str, question: str, config: AppConfig) -> tuple[str, str | None]:
    """Add current-term date filter if the query lacks a time constraint."""

    # Skip if question asks for historical/trend data
    if _HISTORICAL_PATTERNS.search(question):
        return sql, None

    # Skip if SQL already has a temporal filter
    if _HAS_TIME_FILTER.search(sql):
        return sql, None

    # Find which entity tables are referenced and if they have temporal columns
    sql_upper = sql.upper()
    temporal_col = None
    table_alias = None

    _SQL_KEYWORDS = {
        "WHERE", "ON", "AND", "OR", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS",
        "JOIN", "GROUP", "ORDER", "LIMIT", "HAVING", "UNION", "SET", "AS", "SELECT",
    }
    for entity, col in _ENTITY_TEMPORAL_COLUMNS.items():
        # Match patterns like: FROM schema.ENTITY alias, JOIN schema.ENTITY alias
        pattern = re.compile(
            rf"(?:FROM|JOIN)\s+\w+\.(?:\w+\.)?{entity}\s+(\w+)",
            re.IGNORECASE,
        )
        match = pattern.search(sql)
        if match:
            candidate_alias = match.group(1)
            # Skip if the "alias" is actually a SQL keyword
            if candidate_alias.upper() in _SQL_KEYWORDS:
                continue
            temporal_col = col
            table_alias = candidate_alias
            break

    if not temporal_col:
        return sql, None

    # Build the filter — default to current term (~120 days)
    qualifier = f"{table_alias}.{temporal_col}" if table_alias else temporal_col
    term_filter = f"{qualifier} >= DATEADD('day', -120, CURRENT_DATE())"

    # Insert the filter into the WHERE clause
    scoped = _inject_where_clause(sql, term_filter)
    if scoped == sql:
        return sql, None

    return scoped, f"term_scoped:{temporal_col}>=current_term(~120d)"


def _inject_where_clause(sql: str, condition: str) -> str:
    """Inject an AND condition into the first WHERE clause, or add WHERE if missing."""
    # Find the first WHERE
    where_match = re.search(r"\bWHERE\b", sql, re.IGNORECASE)
    if where_match:
        # Insert after WHERE as the first condition
        pos = where_match.end()
        return sql[:pos] + f" {condition} AND" + sql[pos:]

    # No WHERE clause — find FROM ... and add WHERE before GROUP BY/ORDER BY/LIMIT
    for keyword in ("GROUP BY", "ORDER BY", "LIMIT", "HAVING"):
        kw_match = re.search(rf"\b{keyword}\b", sql, re.IGNORECASE)
        if kw_match:
            pos = kw_match.start()
            return sql[:pos] + f" WHERE {condition} " + sql[pos:]

    # No structure keywords — append WHERE at the end
    stripped = sql.rstrip().rstrip(";")
    return stripped + f" WHERE {condition}"


# ---------------------------------------------------------------------------
# 2. Query simplification
# ---------------------------------------------------------------------------

def _infer_limit(question: str) -> int:
    """Infer an appropriate LIMIT based on what the user is asking for."""
    q = question.lower()

    # Explicit "all" / "every" — user wants the full set, use a high ceiling
    if re.search(r"\b(?:all|every|entire|complete|full list)\b", q):
        return 5000

    # Explicit number in question — "top 25", "show me 50"
    match = re.search(r"\b(?:top|show|first|limit|give me)\s+(\d{1,4})\b", q)
    if match:
        return min(int(match.group(1)), 5000)

    # Preview / sample / peek — small result set
    if re.search(r"\b(?:preview|sample|peek|example|few|glance|quick look)\b", q):
        return 25

    # Detail about specific items — "which courses", "what students"
    if re.search(r"\b(?:which|what|who|where|find|identify|flag)\b", q):
        return 500

    # List / show — moderate
    if re.search(r"\b(?:list|show|display|report)\b", q):
        return 200

    # Default — reasonable middle ground
    return 200


def _simplify_query(sql: str, question: str = "") -> tuple[str, List[str]]:
    """Apply lightweight simplification passes."""
    notes = []
    result = sql

    # Check for SELECT * and suggest explicit columns
    if re.search(r"\bSELECT\s+\*\s+FROM\b", result, re.IGNORECASE):
        notes.append("hint:SELECT * detected — consider selecting specific columns")

    # Ensure LIMIT exists on non-aggregate queries, with smart sizing
    has_limit = bool(re.search(r"\bLIMIT\s+\d+", result, re.IGNORECASE))
    has_aggregate = bool(re.search(r"\b(?:COUNT|SUM|AVG|MIN|MAX)\s*\(", result, re.IGNORECASE))
    has_group_by = bool(re.search(r"\bGROUP\s+BY\b", result, re.IGNORECASE))

    if not has_limit and not has_aggregate and not has_group_by:
        limit = _infer_limit(question)
        result = result.rstrip().rstrip(";") + f" LIMIT {limit}"
        notes.append(f"added_limit:{limit}")

    # Check for unnecessary DISTINCT on primary key queries
    if re.search(r"\bSELECT\s+DISTINCT\b", result, re.IGNORECASE):
        # If selecting an _ID column that's likely unique, DISTINCT is redundant
        id_cols = re.findall(r"\b(\w+_ID)\b", result)
        pk_cols = [c for c in id_cols if c in ("COURSE_ID", "USER_ID", "STUDENT_ID", "ENROLLMENT_ID")]
        if pk_cols and not has_group_by:
            notes.append(f"hint:DISTINCT may be unnecessary — {pk_cols[0]} is likely unique")

    return result, notes


# ---------------------------------------------------------------------------
# 3. EXPLAIN pre-check
# ---------------------------------------------------------------------------

def _explain_precheck(sql: str, executor: Any) -> List[str]:
    """Run EXPLAIN and check estimated scan size."""
    warnings = []
    try:
        from .snowflake_conn import create_connection
        config = executor._config
        connection = create_connection(config, {
            "QUERY_TAG": "illuminate_mcp:explain_precheck",
            "STATEMENT_TIMEOUT_IN_SECONDS": 10,
        })
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(f"EXPLAIN {sql}")
                rows = cursor.fetchall()
                columns = [col[0] for col in (cursor.description or [])]
            finally:
                cursor.close()

            # Parse EXPLAIN output for partition and row estimates
            total_partitions = 0
            total_rows_estimate = 0
            col_upper = [c.upper() for c in columns]

            # Snowflake EXPLAIN returns JSON or tabular depending on format
            if rows and len(rows) == 1 and len(columns) == 1:
                # JSON format — parse for statistics
                import json
                try:
                    plan = json.loads(str(rows[0][0]))
                    stats = _extract_plan_stats(plan)
                    total_partitions = stats.get("partitionsTotal", 0)
                    total_rows_estimate = stats.get("outputRows", 0)
                except (json.JSONDecodeError, TypeError):
                    pass
            elif "PARTITIONS_TOTAL" in col_upper:
                pt_idx = col_upper.index("PARTITIONS_TOTAL")
                for row in rows:
                    try:
                        total_partitions += int(row[pt_idx] or 0)
                    except (ValueError, TypeError):
                        pass

            if total_rows_estimate > 10_000_000:
                warnings.append(
                    f"Large scan estimated: ~{total_rows_estimate:,} rows. "
                    "Consider adding filters (date range, specific course/term) to reduce scan size."
                )
            elif total_partitions > 500:
                warnings.append(
                    f"Scanning {total_partitions:,} partitions. "
                    "Consider adding a time-based filter to enable partition pruning."
                )

        finally:
            connection.close()
    except Exception:
        # EXPLAIN failed — don't block execution, just skip the check
        pass

    return warnings


def _extract_plan_stats(plan: Any) -> Dict[str, int]:
    """Recursively extract statistics from a Snowflake EXPLAIN JSON plan."""
    stats: Dict[str, int] = {}
    if isinstance(plan, dict):
        for key in ("partitionsTotal", "partitionsAssigned", "outputRows"):
            if key in plan:
                try:
                    stats[key] = max(stats.get(key, 0), int(plan[key]))
                except (ValueError, TypeError):
                    pass
        for value in plan.values():
            child_stats = _extract_plan_stats(value)
            for k, v in child_stats.items():
                stats[k] = max(stats.get(k, 0), v)
    elif isinstance(plan, list):
        for item in plan:
            child_stats = _extract_plan_stats(item)
            for k, v in child_stats.items():
                stats[k] = max(stats.get(k, 0), v)
    return stats
