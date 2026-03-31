"""Candidate scoring, SQL refinement, probe profiling, and no-data diagnostics."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

from .config import AppConfig
from .execution import SnowflakeExecutor
from .feedback import PlannerFeedbackStore
from .policy import SqlPolicy


class CandidateEngine:
    """Scores, refines, and profiles SQL candidates for plan_query and refine_sql."""

    def __init__(
        self,
        config: AppConfig,
        executor: SnowflakeExecutor,
        feedback: PlannerFeedbackStore,
        policy: SqlPolicy,
    ):
        self._config = config
        self._executor = executor
        self._feedback = feedback
        self._policy = policy

    # ------------------------------------------------------------------
    # Candidate intent resolution
    # ------------------------------------------------------------------

    @staticmethod
    def candidate_intents(question: str, output_intent: Any) -> List[str]:
        explicit = str(output_intent).strip().lower() if output_intent is not None else ""
        if explicit in {"count", "top", "trend", "table", "text", "viz", "analysis"}:
            normalized = "trend" if explicit == "viz" else explicit
            return [normalized, "table", "count"]

        lowered = question.lower()
        asks_average = "average" in lowered or "avg" in lowered or "median" in lowered or "mean" in lowered
        asks_top = "top " in lowered
        asks_trend = "trend" in lowered or "over time" in lowered or "by month" in lowered
        asks_count = "how many" in lowered or "count" in lowered or "number of" in lowered
        asks_list = "list" in lowered

        intents = ["table"]
        if asks_average:
            intents.insert(0, "analysis")
        if asks_top:
            intents.insert(0, "top")
        if asks_trend:
            intents.insert(0, "trend")
        if asks_count:
            intents.insert(0, "count")
        if asks_list:
            intents.insert(0, "text")
        if not any((asks_average, asks_top, asks_trend, asks_count, asks_list)):
            intents.append("count")
        unique: List[str] = []
        for intent in intents:
            if intent not in unique:
                unique.append(intent)
        return unique[:4]

    # ------------------------------------------------------------------
    # Confidence / complexity / signature
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_confidence(warning: str | None, planner_mode: str, sql: str) -> float:
        confidence = 0.85
        if warning:
            confidence -= 0.25
        if "fallback" in planner_mode:
            confidence -= 0.2
        if "join" in planner_mode:
            confidence -= 0.1
        if "SELECT *" in sql.upper():
            confidence -= 0.15
        if planner_mode == "metadata_analysis_relaxed":
            confidence -= 0.05
        return round(max(0.1, min(0.99, confidence)), 2)

    @staticmethod
    def apply_feedback_adjustment(confidence: float, success_rate: float, avg_seconds: float) -> float:
        adjusted = confidence
        if success_rate > 0:
            adjusted += (success_rate - 0.5) * 0.2
        if avg_seconds > 0:
            if avg_seconds <= 2:
                adjusted += 0.03
            elif avg_seconds >= 30:
                adjusted -= 0.08
            elif avg_seconds >= 10:
                adjusted -= 0.04
        return round(max(0.1, min(0.99, adjusted)), 2)

    @staticmethod
    def apply_intent_alignment(confidence: float, question: str, sql: str) -> float:
        lowered_q = question.lower()
        upper_sql = sql.upper()
        adjusted = confidence

        asks_average = "average" in lowered_q or "avg" in lowered_q or "mean" in lowered_q
        asks_count = "how many" in lowered_q or "count" in lowered_q or "number of" in lowered_q
        asks_trend = "trend" in lowered_q or "over time" in lowered_q or "by month" in lowered_q

        if asks_average:
            adjusted += 0.22 if "AVG(" in upper_sql else -0.32
        if asks_count:
            adjusted += 0.15 if "COUNT(" in upper_sql else -0.15
        if asks_trend:
            adjusted += 0.15 if "DATE_TRUNC(" in upper_sql else -0.1

        return round(max(0.1, min(0.99, adjusted)), 2)

    @staticmethod
    def estimate_complexity(sql: str) -> str:
        upper = sql.upper()
        score = 0
        score += upper.count(" JOIN ")
        score += 1 if " GROUP BY " in upper else 0
        score += 1 if " ORDER BY " in upper else 0
        score += 1 if " DATE_TRUNC(" in upper else 0
        if score <= 1:
            return "low"
        if score <= 3:
            return "moderate"
        return "high"

    @staticmethod
    def sql_signature(sql: str, grounded_entities: List[str], complexity: str) -> str:
        upper = sql.upper()
        has_join = " JOIN " in upper
        has_group = " GROUP BY " in upper
        has_trend = "DATE_TRUNC(" in upper
        entities = ",".join(sorted(grounded_entities)) if grounded_entities else "UNKNOWN"
        return (
            f"entities={entities};complexity={complexity};"
            f"join={int(has_join)};group={int(has_group)};trend={int(has_trend)}"
        )

    # ------------------------------------------------------------------
    # Relaxed / requirement alignment
    # ------------------------------------------------------------------

    @staticmethod
    def is_relaxed_candidate(candidate: dict) -> bool:
        mode = str(candidate.get("planner_mode", "")).lower()
        warning = str(candidate.get("warning", "")).lower()
        return "relaxed" in mode or "missing requested constraints" in warning

    def add_relaxed_analysis_candidates(self, candidates: List[dict]) -> List[dict]:
        extra: List[dict] = []
        for candidate in candidates:
            if candidate.get("planner_mode") != "metadata_analysis":
                continue
            sql = str(candidate.get("sql", ""))
            relaxed_sql = re.sub(
                r"\s+AND\s+\(LOWER\([^)]+\)\s+LIKE\s+'%[^%]+%'\s+OR\s+LOWER\([^)]+\)\s+LIKE\s+'%[^%]+%'\)",
                "",
                sql,
                flags=re.IGNORECASE,
            )
            if relaxed_sql == sql:
                continue
            extra.append(
                {
                    "sql": relaxed_sql,
                    "planner_mode": "metadata_analysis_relaxed",
                    "rationale": candidate.get("rationale", "")
                    + " Relaxed subject filter to avoid false zero-result due anonymized course names.",
                    "grounded_entities": candidate.get("grounded_entities", []),
                    "warning": "Relaxed subject filter; result may include non-target courses.",
                    "confidence": max(0.4, float(candidate.get("confidence", 0.7)) - 0.2),
                    "complexity": candidate.get("complexity", "moderate"),
                    "feedback": {"attempts": 0, "success_rate": 0.0, "avg_seconds": 0.0},
                }
            )
        return candidates + extra

    def apply_requirement_alignment(self, question: str, candidates: List[dict]) -> List[dict]:
        required = self._extract_required_constraints(question)
        if not required:
            return candidates
        for candidate in candidates:
            sql_upper = str(candidate.get("sql", "")).upper()
            penalty = 0.0
            missing: List[str] = []
            for constraint in required:
                kind = constraint["kind"]
                value = constraint["value"]
                if kind == "subject":
                    if value.upper() not in sql_upper:
                        penalty += 0.22
                        missing.append(f"subject:{value}")
                elif kind == "season_year":
                    if value.upper() not in sql_upper:
                        penalty += 0.18
                        missing.append(f"term:{value}")
                elif kind == "population":
                    if value.upper() not in sql_upper:
                        penalty += 0.14
                        missing.append(f"population:{value}")
            if penalty > 0:
                candidate["confidence"] = round(max(0.1, float(candidate["confidence"]) - penalty), 2)
                warning = candidate.get("warning")
                extra = f"Missing requested constraints ({', '.join(missing)})."
                candidate["warning"] = f"{warning} {extra}".strip() if warning else extra
        return candidates

    @staticmethod
    def _extract_required_constraints(question: str) -> List[dict]:
        lowered = question.lower()
        constraints: List[dict] = []
        term_match = re.search(r"(spring|summer|fall|winter)\s+(20\d{2})", lowered)
        if term_match:
            season, year = term_match.groups()
            constraints.append({"kind": "season_year", "value": f"{season}%{year}"})

        if "student" in lowered:
            constraints.append({"kind": "population", "value": "STUDENT_IND"})

        subject_match = re.search(
            r"(?:in|for)\s+([a-z0-9\-]+)\s+(?:class|classes|course|courses)",
            lowered,
        )
        if subject_match:
            constraints.append({"kind": "subject", "value": subject_match.group(1)})
        return constraints

    # ------------------------------------------------------------------
    # Probe profiling
    # ------------------------------------------------------------------

    def profile_candidates(self, question: str, candidates: List[dict]) -> None:
        if not self._config.enable_planner_probes:
            return
        ranked_for_probe = sorted(
            candidates,
            key=lambda candidate: (
                0 if "analysis" in str(candidate.get("planner_mode", "")).lower() else 1,
                0 if "relaxed" in str(candidate.get("planner_mode", "")).lower() else 1,
                -float(candidate.get("confidence", 0.0)),
            ),
        )
        to_probe = [
            candidate
            for candidate in ranked_for_probe
            if self._should_probe_candidate(question, candidate)
        ][: self._config.planner_max_probes]
        for candidate in to_probe:
            candidate["probe"] = self._run_probe(candidate)

    def profile_refinement_candidates(self, question: str, candidates: List[dict]) -> None:
        if not self._config.enable_planner_probes:
            return
        ranked_for_probe = sorted(
            candidates,
            key=lambda candidate: (
                0 if candidate.get("strictness") == "strict" else 1,
                -float(candidate.get("confidence", 0.0)),
            ),
        )
        for candidate in ranked_for_probe[: self._config.planner_max_probes]:
            candidate["probe"] = self._run_probe(candidate)

    def _run_probe(self, candidate: dict) -> dict:
        try:
            probe = self._executor.run_probe_exists(
                str(candidate.get("sql", "")),
                timeout_seconds=self._config.planner_probe_timeout_seconds,
            )
            return {
                "status": probe.status,
                "has_rows": probe.has_rows,
                "execution_seconds": round(probe.execution_seconds, 4),
                "message": probe.message,
            }
        except Exception as exc:
            return {
                "status": "probe_failed",
                "has_rows": None,
                "execution_seconds": 0.0,
                "message": f"Probe failed: {exc}",
            }

    @staticmethod
    def _should_probe_candidate(question: str, candidate: dict) -> bool:
        sql = str(candidate.get("sql", "")).upper()
        planner_mode = str(candidate.get("planner_mode", "")).lower()
        lowered_q = question.lower()
        has_aggregate = "AVG(" in sql or "COUNT(" in sql or "SUM(" in sql
        has_filters = " WHERE " in sql and " LIKE " in sql
        analysis_like = "analysis" in planner_mode
        question_is_specific = any(token in lowered_q for token in (" in ", " for ", "spring", "fall", "summer", "winter"))
        return has_aggregate and (has_filters or analysis_like or question_is_specific)

    # ------------------------------------------------------------------
    # Robustness adjustments
    # ------------------------------------------------------------------

    def apply_robustness_adjustments(self, question: str, candidates: List[dict]) -> List[dict]:
        for candidate in candidates:
            penalty = 0.0
            probe = candidate.get("probe") or {}
            has_rows = probe.get("has_rows")
            if has_rows is False:
                penalty += 0.3
            elif has_rows is None and probe.get("status") == "probe_failed":
                penalty += 0.06

            sql_upper = str(candidate.get("sql", "")).upper()
            lowered_q = question.lower()
            if (
                " LIKE '%" in sql_upper
                and any(token in lowered_q for token in ("chemistry", "biology", "physics", "math", "history", "english"))
                and "metadata_analysis" in str(candidate.get("planner_mode", ""))
            ):
                penalty += 0.08

            if penalty > 0:
                candidate["confidence"] = round(max(0.1, float(candidate["confidence"]) - penalty), 2)

        return candidates

    # ------------------------------------------------------------------
    # SQL refinement candidates
    # ------------------------------------------------------------------

    def build_sql_refinement_candidates(self, normalized_sql: str, question: str) -> List[dict]:
        sql = normalized_sql.strip().rstrip(";")
        candidates: List[dict] = [
            {
                "label": "baseline_strict",
                "strictness": "strict",
                "rationale": "Baseline strict query for reference.",
                "sql": sql,
                "confidence": 0.55,
            }
        ]
        seen = {sql}

        strict_variants = self._strict_variants(sql, question)
        for item in strict_variants:
            if item["sql"] in seen:
                continue
            seen.add(item["sql"])
            candidates.append(item)

        fallback_variants = self._fallback_variants(sql)
        for item in fallback_variants:
            if item["sql"] in seen:
                continue
            seen.add(item["sql"])
            candidates.append(item)

        return candidates

    def apply_refinement_feedback(self, question: str, refinements: List[dict]) -> List[dict]:
        for candidate in refinements:
            sql = str(candidate.get("sql", ""))
            entities = extract_entities_from_sql(sql)
            signature = self.sql_signature(
                sql=sql,
                grounded_entities=entities,
                complexity=self.estimate_complexity(sql),
            )
            feedback = self._feedback.get(signature)
            confidence = float(candidate.get("confidence", 0.5))
            confidence = self.apply_feedback_adjustment(
                confidence,
                feedback.success_rate,
                feedback.avg_seconds,
            )
            confidence = self.apply_intent_alignment(confidence, question, sql)
            candidate["confidence"] = confidence
            candidate["feedback"] = {
                "attempts": feedback.attempts,
                "success_rate": round(feedback.success_rate, 3),
                "avg_seconds": round(feedback.avg_seconds, 4),
            }
        return refinements

    def build_auto_refine_payload(self, question: str, normalized_sql: str) -> dict:
        refinements = self.build_sql_refinement_candidates(normalized_sql, question)
        refinements = self.apply_refinement_feedback(question, refinements)
        if self._config.enable_planner_probes:
            self.profile_refinement_candidates(question, refinements)
        refinements = sorted(
            refinements,
            key=lambda item: (
                0 if item.get("strictness") == "strict" else 1,
                -probe_rank(item),
                -float(item.get("confidence", 0.0)),
            ),
        )
        strict = [item for item in refinements if item.get("strictness") == "strict"]
        fallback = [item for item in refinements if item.get("strictness") == "fallback"]
        strict_best = strict[0] if strict else (refinements[0] if refinements else None)
        fallback_best = fallback[0] if fallback else strict_best
        return {
            "strict_refined": strict_best,
            "fallback_refined": fallback_best,
            "candidate_count": len(refinements),
            "candidates": refinements[:4],
            "note": "Auto-generated from no_data result. You can also call refine_sql for full set.",
        }

    def _strict_variants(self, sql: str, question: str) -> List[dict]:
        variants: List[dict] = []
        subject = _extract_subject_token(question)
        if subject:
            token = subject.lower()
            stem = token[:4] if len(token) >= 4 else token
            if stem and stem != token:
                expanded = re.sub(
                    rf"%{re.escape(token)}%",
                    f"%{token}%' OR LOWER(c.COURSE_NUMBER) LIKE '%{stem}%",
                    sql,
                    count=1,
                    flags=re.IGNORECASE,
                )
                if expanded != sql:
                    variants.append(
                        {
                            "label": "strict_subject_code_expansion",
                            "strictness": "strict",
                            "rationale": "Expand subject matching to include course-code style prefixes.",
                            "sql": expanded,
                            "confidence": 0.62,
                        }
                    )

        season_year = re.search(r"(spring|summer|fall|winter)\s+(20\d{2})", question.lower())
        if season_year:
            season, year = season_year.groups()
            term_pattern = rf"LOWER\(([^)]+)\)\s+LIKE\s+'%{season}%{year}%'"
            replacement = (
                r"(LOWER(\1) LIKE '%" + season + "%" + year + "%' "
                r"OR (LOWER(\1) LIKE '%" + season + "%' AND LOWER(\1) LIKE '%" + year + "%'))"
            )
            expanded_term = re.sub(term_pattern, replacement, sql, flags=re.IGNORECASE)
            if expanded_term != sql:
                variants.append(
                    {
                        "label": "strict_term_pattern_expansion",
                        "strictness": "strict",
                        "rationale": "Keep same term intent while broadening naming-pattern matching.",
                        "sql": expanded_term,
                        "confidence": 0.6,
                    }
                )
        return variants

    def _fallback_variants(self, sql: str) -> List[dict]:
        variants: List[dict] = []
        subject_relaxed = remove_predicate(
            sql,
            r"\(\s*LOWER\([^)]+(?:NAME|COURSE_NUMBER)\)\s+LIKE\s+'%[^%]+%'\s+OR\s+LOWER\([^)]+(?:NAME|COURSE_NUMBER)\)\s+LIKE\s+'%[^%]+%'\s*\)",
        )
        if subject_relaxed != sql:
            variants.append(
                {
                    "label": "fallback_relax_subject",
                    "strictness": "fallback",
                    "rationale": "Drop subject filter to validate broader data availability.",
                    "sql": subject_relaxed,
                    "confidence": 0.52,
                }
            )

        active_relaxed = remove_predicate(
            sql,
            r"[A-Za-z0-9_]+\.ROW_DELETED_TIME\s+IS\s+NULL",
        )
        if active_relaxed != sql:
            variants.append(
                {
                    "label": "fallback_include_soft_deleted",
                    "strictness": "fallback",
                    "rationale": "Include soft-deleted rows to diagnose active-only data gaps.",
                    "sql": active_relaxed,
                    "confidence": 0.5,
                }
            )

        student_relaxed = remove_predicate(
            sql,
            r"[A-Za-z0-9_]+\.STUDENT_IND\s*=\s*TRUE",
        )
        if student_relaxed != sql:
            variants.append(
                {
                    "label": "fallback_relax_population",
                    "strictness": "fallback",
                    "rationale": "Drop student-only filter to verify population-specific sparsity.",
                    "sql": student_relaxed,
                    "confidence": 0.48,
                }
            )
        return variants

    # ------------------------------------------------------------------
    # No-data diagnostics
    # ------------------------------------------------------------------

    def diagnose_no_data(self, output: dict, normalized_sql: str, question: str) -> dict | None:
        table = output.get("table", {})
        rows = table.get("rows", [])
        columns = [str(col).upper() for col in table.get("columns", [])]
        if not rows:
            return {
                "reason": "zero_rows",
                "suggested_next_actions": [
                    "Run plan_query for alternative candidates.",
                    "Relax term/subject filters and rerun.",
                ],
                "refinement_candidates": self._build_refinement_candidates(normalized_sql, question),
            }
        if "RECORD_COUNT" in columns and len(rows) == 1:
            idx = columns.index("RECORD_COUNT")
            try:
                value = rows[0][idx]
                if value == 0:
                    return {
                        "reason": "record_count_zero",
                        "suggested_next_actions": [
                            "Try a relaxed analysis candidate from generate_sql alternatives.",
                            "Check term/course naming conventions in source data.",
                        ],
                        "refinement_candidates": self._build_refinement_candidates(
                            normalized_sql,
                            question,
                        ),
                    }
            except Exception:
                return None
        return None

    def _build_refinement_candidates(self, normalized_sql: str, question: str) -> List[dict]:
        sql = normalized_sql.strip().rstrip(";")
        if not sql:
            return []

        candidates: List[dict] = []
        seen: set = set()
        base_probe = as_count_probe(sql)
        candidates.append(
            {
                "label": "baseline_count_probe",
                "rationale": "Confirm whether current SQL shape can return any records.",
                "sql": base_probe,
            }
        )
        seen.add(base_probe)

        removals = [
            (
                "subject_filter_probe",
                r"\(\s*LOWER\([^)]+(?:NAME|COURSE_NUMBER)\)\s+LIKE\s+'%[^%]+%'\s+OR\s+LOWER\([^)]+(?:NAME|COURSE_NUMBER)\)\s+LIKE\s+'%[^%]+%'\s*\)",
                "Test if subject constraint is eliminating all rows.",
            ),
            (
                "term_filter_probe",
                r"LOWER\([^)]+\.NAME\)\s+LIKE\s+'%(spring|summer|fall|winter)%20\d{2}%'",
                "Test if term matching pattern is too restrictive.",
            ),
            (
                "student_filter_probe",
                r"[A-Za-z0-9_]+\.STUDENT_IND\s*=\s*TRUE",
                "Test if student-only filter removes all rows.",
            ),
            (
                "active_rows_filter_probe",
                r"[A-Za-z0-9_]+\.ROW_DELETED_TIME\s+IS\s+NULL",
                "Test whether soft-delete filter is removing matching records.",
            ),
        ]
        for label, predicate, rationale in removals:
            relaxed = remove_predicate(sql, predicate)
            if relaxed == sql:
                continue
            probe = as_count_probe(relaxed)
            if probe in seen:
                continue
            seen.add(probe)
            candidates.append(
                {
                    "label": label,
                    "rationale": rationale,
                    "sql": probe,
                }
            )

        if "distinct" in question.lower() and all(item["label"] != "raw_count_probe" for item in candidates):
            raw_probe = as_count_probe(strip_terminal_limit(sql))
            if raw_probe not in seen:
                candidates.append(
                    {
                        "label": "raw_count_probe",
                        "rationale": "Check non-distinct record availability.",
                        "sql": raw_probe,
                    }
                )
        return candidates[:5]


# ------------------------------------------------------------------
# Module-level utility functions (used by CandidateEngine and ToolRegistry)
# ------------------------------------------------------------------

def probe_rank(candidate: dict) -> int:
    probe = candidate.get("probe") or {}
    if probe.get("has_rows") is True:
        return 2
    if probe.get("has_rows") is False:
        return 0
    return 1


def extract_entities_from_sql(sql: str) -> List[str]:
    refs = re.findall(r"\b(?:FROM|JOIN)\s+([A-Z0-9_\.]+)", sql.upper())
    entities: List[str] = []
    for ref in refs:
        entity = ref.split(".")[-1]
        if entity and entity not in entities:
            entities.append(entity)
    return entities


def as_count_probe(sql: str) -> str:
    base = strip_terminal_limit(sql)
    return f"SELECT COUNT(*) AS RECORD_COUNT FROM ({base}) AS diagnostics_q"


def strip_terminal_limit(sql: str) -> str:
    return re.sub(r"\s+LIMIT\s+\d+\s*$", "", sql, flags=re.IGNORECASE).strip()


def remove_predicate(sql: str, predicate_pattern: str) -> str:
    predicate = f"(?:{predicate_pattern})"
    updated = sql
    updated = re.sub(
        rf"\s+AND\s+{predicate}",
        "",
        updated,
        flags=re.IGNORECASE,
    )
    updated = re.sub(
        rf"WHERE\s+{predicate}\s+AND\s+",
        "WHERE ",
        updated,
        flags=re.IGNORECASE,
    )
    updated = re.sub(
        rf"WHERE\s+{predicate}(?=(\s+GROUP\s+BY|\s+ORDER\s+BY|\s+LIMIT|$))",
        "",
        updated,
        flags=re.IGNORECASE,
    )
    updated = re.sub(r"\s{2,}", " ", updated).strip()
    return updated


def _extract_subject_token(question: str) -> str | None:
    match = re.search(
        r"(?:in|for)\s+([a-z0-9\-]+)\s+(?:class|classes|course|courses)",
        question.lower(),
    )
    if not match:
        return None
    return match.group(1)
