import unittest

from illuminate_mcp.budget import BudgetTracker
from illuminate_mcp.config import AppConfig
from illuminate_mcp.domain_router import DomainRouter
from illuminate_mcp.execution import SnowflakeExecutor
from illuminate_mcp.metadata import ColumnRecord, MetadataStore
from illuminate_mcp.output import OutputComposer
from illuminate_mcp.planner import SqlPlanner
from illuminate_mcp.policy import SqlPolicy
from illuminate_mcp.session import SessionState
from illuminate_mcp.tool_handlers import ToolRegistry


class NoDataDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        config = AppConfig.from_env({})
        metadata = MetadataStore.from_records(
            allowed_domains=("CDM_LMS",),
            tables=[],
            columns=[
                ColumnRecord("CDM_LMS", "GRADE", "PERSON_COURSE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "GRADE", "NORMALIZED_SCORE", "FLOAT", ""),
                ColumnRecord("CDM_LMS", "GRADE", "SCORE", "FLOAT", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "COURSE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "STUDENT_IND", "BOOLEAN", ""),
                ColumnRecord("CDM_LMS", "COURSE", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "COURSE", "TERM_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "COURSE", "NAME", "VARCHAR", ""),
                ColumnRecord("CDM_LMS", "COURSE", "COURSE_NUMBER", "VARCHAR", ""),
                ColumnRecord("CDM_LMS", "TERM", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "TERM", "NAME", "VARCHAR", ""),
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

    def test_record_count_zero_returns_refinement_candidates(self) -> None:
        output = {
            "table": {
                "columns": ["AVG_SCORE", "RECORD_COUNT"],
                "rows": [[None, 0]],
            }
        }
        sql = (
            "SELECT AVG(f.SCORE) AS AVG_SCORE, COUNT(*) AS RECORD_COUNT "
            "FROM CDM_LMS.GRADE f "
            "JOIN CDM_LMS.PERSON_COURSE pc ON f.PERSON_COURSE_ID = pc.ID "
            "JOIN CDM_LMS.COURSE c ON pc.COURSE_ID = c.ID "
            "JOIN CDM_LMS.TERM t ON c.TERM_ID = t.ID "
            "WHERE pc.STUDENT_IND = TRUE "
            "AND LOWER(t.NAME) LIKE '%spring%2020%' "
            "AND (LOWER(c.NAME) LIKE '%chemistry%' OR LOWER(c.COURSE_NUMBER) LIKE '%chemistry%') "
            "AND f.ROW_DELETED_TIME IS NULL LIMIT 100"
        )
        diagnostics = self.registry._engine.diagnose_no_data(  # pylint: disable=protected-access
            output=output,
            normalized_sql=sql,
            question="What is the average grade for students in chemistry courses in Spring 2020?",
        )
        self.assertIsNotNone(diagnostics)
        probes = diagnostics.get("refinement_candidates", [])
        self.assertGreaterEqual(len(probes), 2)
        labels = [item["label"] for item in probes]
        self.assertIn("baseline_count_probe", labels)
        self.assertIn("subject_filter_probe", labels)

    def test_auto_refine_payload_contains_strict_and_fallback(self) -> None:
        sql = (
            "SELECT AVG(f.SCORE) AS AVG_SCORE, COUNT(*) AS RECORD_COUNT "
            "FROM CDM_LMS.GRADE f "
            "JOIN CDM_LMS.PERSON_COURSE pc ON f.PERSON_COURSE_ID = pc.ID "
            "JOIN CDM_LMS.COURSE c ON pc.COURSE_ID = c.ID "
            "JOIN CDM_LMS.TERM t ON c.TERM_ID = t.ID "
            "WHERE pc.STUDENT_IND = TRUE "
            "AND LOWER(t.NAME) LIKE '%spring%2020%' "
            "AND (LOWER(c.NAME) LIKE '%chemistry%' OR LOWER(c.COURSE_NUMBER) LIKE '%chemistry%') "
            "AND f.ROW_DELETED_TIME IS NULL LIMIT 100"
        )
        payload = self.registry._engine.build_auto_refine_payload(  # pylint: disable=protected-access
            "What is the average grade for students in chemistry courses in Spring 2020?",
            sql,
        )
        self.assertIn("strict_refined", payload)
        self.assertIn("fallback_refined", payload)
        self.assertGreaterEqual(payload["candidate_count"], 2)


if __name__ == "__main__":
    unittest.main()
