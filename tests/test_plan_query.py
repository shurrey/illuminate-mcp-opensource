import unittest

from illuminate_mcp.budget import BudgetTracker
from illuminate_mcp.config import AppConfig
from illuminate_mcp.domain_router import DomainRouter
from illuminate_mcp.execution import ProbeResult, SnowflakeExecutor
from illuminate_mcp.metadata import ColumnRecord, MetadataStore
from illuminate_mcp.output import OutputComposer
from illuminate_mcp.planner import SqlPlanner
from illuminate_mcp.policy import SqlPolicy
from illuminate_mcp.session import SessionState
from illuminate_mcp.tool_handlers import ToolRegistry


class PlanQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        config = AppConfig.from_env({})
        metadata = MetadataStore.from_records(
            allowed_domains=("CDM_LMS",),
            tables=[],
            columns=[
                ColumnRecord("CDM_LMS", "GRADE", "PERSON_COURSE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "GRADE", "NORMALIZED_SCORE", "FLOAT", ""),
                ColumnRecord("CDM_LMS", "GRADE", "SCORE", "FLOAT", ""),
                ColumnRecord("CDM_LMS", "GRADE", "ROW_DELETED_TIME", "TIMESTAMP", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "COURSE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "STUDENT_IND", "BOOLEAN", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "ROW_DELETED_TIME", "TIMESTAMP", ""),
                ColumnRecord("CDM_LMS", "COURSE", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "COURSE", "TERM_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "COURSE", "NAME", "VARCHAR", ""),
                ColumnRecord("CDM_LMS", "COURSE", "COURSE_NUMBER", "VARCHAR", ""),
                ColumnRecord("CDM_LMS", "COURSE", "ROW_DELETED_TIME", "TIMESTAMP", ""),
                ColumnRecord("CDM_LMS", "TERM", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "TERM", "NAME", "VARCHAR", ""),
                ColumnRecord("CDM_LMS", "TERM", "ROW_DELETED_TIME", "TIMESTAMP", ""),
            ],
            dictionary=[],
        )
        router = DomainRouter(config.allowed_domains)
        self.registry = ToolRegistry(
            config=config,
            metadata=metadata,
            router=router,
            policy=SqlPolicy(config.allowed_schemas, config.allowed_tables),
            session=SessionState(True, "per-query"),
            budget=BudgetTracker(config.monthly_credit_budget, config.budget_warning_thresholds),
            executor=SnowflakeExecutor(config),
            output=OutputComposer(config.max_text_summary_length),
            planner=SqlPlanner(config, router),
        )

    def test_plan_query_returns_candidates(self) -> None:
        payload = self.registry.call("plan_query", {"question": "How many courses are there?"})

        self.assertIn("candidates", payload)
        self.assertIn("recommended_strict_index", payload)
        self.assertIn("recommended_fallback_index", payload)
        self.assertGreaterEqual(len(payload["candidates"]), 1)
        candidate = payload["candidates"][0]
        self.assertIn("confidence", candidate)
        self.assertIn("complexity", candidate)

    def test_intent_alignment_boosts_avg_sql(self) -> None:
        engine = self.registry._engine  # pylint: disable=protected-access
        boosted = engine.apply_intent_alignment(
            0.5,
            "What is the average score?",
            "SELECT AVG(SCORE) FROM CDM_LMS.GRADE",
        )
        penalized = engine.apply_intent_alignment(
            0.5,
            "What is the average score?",
            "SELECT SCORE FROM CDM_LMS.GRADE LIMIT 100",
        )
        self.assertGreater(boosted, penalized)

    def test_probe_marks_relaxed_candidate_for_data_return(self) -> None:
        config = AppConfig.from_env(
            {
                "ENABLE_QUERY_EXECUTION": "true",
                "ENABLE_PLANNER_PROBES": "true",
                "PLANNER_MAX_PROBES": "2",
                "SNOWFLAKE_ACCOUNT": "acct",
                "SNOWFLAKE_USER": "user",
                "SNOWFLAKE_PASSWORD": "pass",
                "SNOWFLAKE_ROLE": "role",
                "SNOWFLAKE_WAREHOUSE": "wh",
                "SNOWFLAKE_DATABASE": "db",
            }
        )
        metadata = MetadataStore.from_records(
            allowed_domains=("CDM_LMS",),
            tables=[],
            columns=[
                ColumnRecord("CDM_LMS", "GRADE", "PERSON_COURSE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "GRADE", "NORMALIZED_SCORE", "FLOAT", ""),
                ColumnRecord("CDM_LMS", "GRADE", "SCORE", "FLOAT", ""),
                ColumnRecord("CDM_LMS", "GRADE", "ROW_DELETED_TIME", "TIMESTAMP", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "COURSE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "STUDENT_IND", "BOOLEAN", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "ROW_DELETED_TIME", "TIMESTAMP", ""),
                ColumnRecord("CDM_LMS", "COURSE", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "COURSE", "TERM_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "COURSE", "NAME", "VARCHAR", ""),
                ColumnRecord("CDM_LMS", "COURSE", "COURSE_NUMBER", "VARCHAR", ""),
                ColumnRecord("CDM_LMS", "COURSE", "ROW_DELETED_TIME", "TIMESTAMP", ""),
                ColumnRecord("CDM_LMS", "TERM", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "TERM", "NAME", "VARCHAR", ""),
                ColumnRecord("CDM_LMS", "TERM", "ROW_DELETED_TIME", "TIMESTAMP", ""),
            ],
            dictionary=[],
        )
        router = DomainRouter(config.allowed_domains)
        registry = ToolRegistry(
            config=config,
            metadata=metadata,
            router=router,
            policy=SqlPolicy(config.allowed_schemas, config.allowed_tables),
            session=SessionState(True, "per-query"),
            budget=BudgetTracker(config.monthly_credit_budget, config.budget_warning_thresholds),
            executor=SnowflakeExecutor(config),
            output=OutputComposer(config.max_text_summary_length),
            planner=SqlPlanner(config, router),
        )

        def _fake_probe(sql: str, timeout_seconds: int) -> ProbeResult:
            _ = timeout_seconds
            if "COURSE_NUMBER" in sql:
                return ProbeResult(status="ok", has_rows=False, execution_seconds=0.1, message="none")
            return ProbeResult(status="ok", has_rows=True, execution_seconds=0.1, message="yes")

        registry._executor.run_probe_exists = _fake_probe  # type: ignore[attr-defined]  # pylint: disable=protected-access
        registry._engine._executor.run_probe_exists = _fake_probe  # type: ignore[attr-defined]  # pylint: disable=protected-access
        payload = registry.call(
            "plan_query",
            {"question": "What was the average grade for students in chemistry courses in Spring 2020?"},
        )
        strict = payload["candidates"][payload["recommended_strict_index"]]
        fallback = payload["candidates"][payload["recommended_fallback_index"]]
        self.assertEqual(strict["planner_mode"], "metadata_analysis")
        self.assertEqual(fallback["planner_mode"], "metadata_analysis_relaxed")
        self.assertEqual(fallback["probe"]["has_rows"], True)

    def test_average_question_does_not_emit_count_candidate(self) -> None:
        payload = self.registry.call(
            "plan_query",
            {"question": "What was the average grade for students in chemistry courses in Spring 2020?"},
        )
        modes = [candidate["planner_mode"] for candidate in payload["candidates"]]
        self.assertIn("metadata_analysis", modes)
        self.assertNotIn("metadata_count", modes)
        self.assertNotIn("metadata_join_count", modes)

    def test_relaxed_candidate_is_penalized_for_missing_subject_constraint(self) -> None:
        payload = self.registry.call(
            "plan_query",
            {"question": "What is the average grade for students in chemistry courses in Spring 2020?"},
        )
        by_mode = {candidate["planner_mode"]: candidate for candidate in payload["candidates"]}
        self.assertIn("metadata_analysis", by_mode)
        self.assertIn("metadata_analysis_relaxed", by_mode)
        strict = by_mode["metadata_analysis"]
        relaxed = by_mode["metadata_analysis_relaxed"]
        self.assertGreaterEqual(strict["confidence"], relaxed["confidence"])
        self.assertIn("Missing requested constraints", str(relaxed.get("warning", "")))

    def test_generate_sql_returns_strict_and_fallback(self) -> None:
        payload = self.registry.call(
            "generate_sql",
            {"question": "What is the average grade for students in chemistry courses in Spring 2020?"},
        )
        self.assertIn("recommended_strict", payload)
        self.assertIn("recommended_fallback", payload)
        strict = payload["recommended_strict"]
        fallback = payload["recommended_fallback"]
        self.assertNotIn("relaxed", str(strict.get("planner_mode", "")).lower())
        self.assertEqual(payload["sql"], strict["sql"])
        self.assertTrue(
            "relaxed" in str(fallback.get("planner_mode", "")).lower()
            or "missing requested constraints" in str(fallback.get("warning", "")).lower()
        )

    def test_refine_sql_returns_strict_and_fallback(self) -> None:
        failed_sql = (
            "SELECT AVG(f.NORMALIZED_SCORE) AS AVG_NORMALIZED_SCORE, AVG(f.SCORE) AS AVG_SCORE, COUNT(*) AS RECORD_COUNT "
            "FROM CDM_LMS.GRADE f "
            "JOIN CDM_LMS.PERSON_COURSE pc ON f.PERSON_COURSE_ID = pc.ID "
            "JOIN CDM_LMS.COURSE c ON pc.COURSE_ID = c.ID "
            "JOIN CDM_LMS.TERM t ON c.TERM_ID = t.ID "
            "WHERE pc.STUDENT_IND = TRUE "
            "AND LOWER(t.NAME) LIKE '%spring%2020%' "
            "AND (LOWER(c.NAME) LIKE '%chemistry%' OR LOWER(c.COURSE_NUMBER) LIKE '%chemistry%') "
            "AND f.ROW_DELETED_TIME IS NULL "
            "AND pc.ROW_DELETED_TIME IS NULL "
            "AND c.ROW_DELETED_TIME IS NULL "
            "AND t.ROW_DELETED_TIME IS NULL "
            "LIMIT 100"
        )
        payload = self.registry.call(
            "refine_sql",
            {
                "question": "What is the average grade for students in chemistry courses in Spring 2020?",
                "failed_sql": failed_sql,
            },
        )
        self.assertIn("strict_refined", payload)
        self.assertIn("fallback_refined", payload)
        self.assertGreaterEqual(payload["candidate_count"], 2)
        self.assertEqual(payload["strict_refined"]["strictness"], "strict")
        self.assertEqual(payload["fallback_refined"]["strictness"], "fallback")

    def test_refine_sql_uses_execution_feedback(self) -> None:
        question = "What is the average grade for students in chemistry courses in Spring 2020?"
        failed_sql = (
            "SELECT AVG(f.NORMALIZED_SCORE) AS AVG_NORMALIZED_SCORE, AVG(f.SCORE) AS AVG_SCORE, COUNT(*) AS RECORD_COUNT "
            "FROM CDM_LMS.GRADE f "
            "JOIN CDM_LMS.PERSON_COURSE pc ON f.PERSON_COURSE_ID = pc.ID "
            "JOIN CDM_LMS.COURSE c ON pc.COURSE_ID = c.ID "
            "JOIN CDM_LMS.TERM t ON c.TERM_ID = t.ID "
            "WHERE pc.STUDENT_IND = TRUE "
            "AND LOWER(t.NAME) LIKE '%spring%2020%' "
            "AND (LOWER(c.NAME) LIKE '%chemistry%' OR LOWER(c.COURSE_NUMBER) LIKE '%chemistry%') "
            "AND f.ROW_DELETED_TIME IS NULL "
            "AND pc.ROW_DELETED_TIME IS NULL "
            "AND c.ROW_DELETED_TIME IS NULL "
            "AND t.ROW_DELETED_TIME IS NULL "
            "LIMIT 100"
        )
        engine = self.registry._engine  # pylint: disable=protected-access
        refinements = engine.build_sql_refinement_candidates(
            failed_sql,
            question,
        )
        fallback = next(item for item in refinements if item["strictness"] == "fallback")
        fallback_sql = fallback["sql"]
        from illuminate_mcp.refinement import extract_entities_from_sql
        signature = engine.sql_signature(
            sql=fallback_sql,
            grounded_entities=extract_entities_from_sql(fallback_sql),
            complexity=engine.estimate_complexity(fallback_sql),
        )
        for _ in range(3):
            self.registry._feedback.record(signature, success=True, execution_seconds=1.2)  # pylint: disable=protected-access

        payload = self.registry.call(
            "refine_sql",
            {"question": question, "failed_sql": failed_sql},
        )
        self.assertGreaterEqual(payload["fallback_refined"]["feedback"]["attempts"], 3)


if __name__ == "__main__":
    unittest.main()
