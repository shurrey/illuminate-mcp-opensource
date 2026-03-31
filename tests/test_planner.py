import unittest

from illuminate_mcp.config import AppConfig
from illuminate_mcp.domain_router import DomainRouter
from illuminate_mcp.metadata import ColumnRecord, MetadataStore
from illuminate_mcp.planner import SqlPlanner, _EntityInfo
from illuminate_mcp.semantic_model import SemanticModel


class SqlPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = AppConfig.from_env({})
        self.planner = SqlPlanner(self.config, DomainRouter(self.config.allowed_domains))
        self.metadata = MetadataStore.from_builtin_catalog(self.config.allowed_domains)

    def test_metadata_mode_by_default(self) -> None:
        plan = self.planner.plan("List courses", self.metadata)

        self.assertIn(plan.planner_mode, {"metadata_heuristic", "metadata_join_list"})
        self.assertIn("FROM CDM_LMS.COURSE", plan.sql)

    def test_enrollment_intent_uses_aggregate_template(self) -> None:
        plan = self.planner.plan("enrollment summary", self.metadata)

        self.assertEqual(plan.planner_mode, "metadata_heuristic")
        self.assertIn("FROM CDM_LMS.ENROLLMENT", plan.sql)

    def test_count_intent_groups_when_possible(self) -> None:
        plan = self.planner.plan("How many enrollments by course", self.metadata)

        self.assertIn(plan.planner_mode, {"metadata_count", "metadata_join_count"})
        self.assertIn("GROUP BY", plan.sql)
        self.assertIn("RECORD_COUNT", plan.sql)

    def test_total_courses_count_prefers_direct_distinct(self) -> None:
        plan = self.planner.plan("How many classes or courses are there?", self.metadata)

        self.assertEqual(plan.planner_mode, "metadata_direct_count")
        self.assertIn("COUNT(DISTINCT COURSE_ID)", plan.sql)
        self.assertIn("FROM CDM_LMS.COURSE", plan.sql)
        self.assertNotIn(" JOIN ", plan.sql)

    def test_active_filter_applies_when_row_deleted_time_exists(self) -> None:
        custom = MetadataStore.from_records(
            allowed_domains=("CDM_LMS",),
            tables=[],
            columns=[
                ColumnRecord("CDM_LMS", "COURSE", "COURSE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "COURSE", "COURSE_NAME", "VARCHAR", ""),
                ColumnRecord("CDM_LMS", "COURSE", "ROW_DELETED_TIME", "TIMESTAMP", ""),
            ],
            dictionary=[],
        )
        list_plan = self.planner.plan("List courses", custom)
        count_plan = self.planner.plan("How many courses are there?", custom)
        self.assertIn("ROW_DELETED_TIME IS NULL", list_plan.sql)
        self.assertIn("ROW_DELETED_TIME IS NULL", count_plan.sql)

    def test_deleted_prompt_disables_active_filter(self) -> None:
        plan = self.planner.plan("How many deleted courses are there?", self.metadata)
        self.assertNotIn("ROW_DELETED_TIME IS NULL", plan.sql)

    def test_best_id_column_prefers_id_over_term_id(self) -> None:
        selected = self.planner._best_id_column(  # pylint: disable=protected-access
            "COURSE",
            ("TERM_ID", "INSTANCE_ID", "ID", "SOURCE_ID"),
        )
        self.assertEqual(selected, "ID")

    def test_top_n_intent_uses_limit(self) -> None:
        plan = self.planner.plan("Top 7 courses by enrollments", self.metadata)

        self.assertIn("LIMIT 7", plan.sql)
        self.assertIn("ORDER BY RECORD_COUNT DESC", plan.sql)

    def test_trend_intent_uses_date_bucket(self) -> None:
        plan = self.planner.plan("Enrollment trend over time", self.metadata)

        self.assertIn("DATE_TRUNC('month'", plan.sql)
        self.assertIn("PERIOD", plan.sql)

    def test_analysis_intent_builds_joined_metric_query(self) -> None:
        custom = MetadataStore.from_records(
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
            ],
            dictionary=[],
        )
        plan = self.planner.plan(
            "What is the average grade (normalized_score) for students in chemistry classes in Spring 2020?",
            custom,
        )
        self.assertEqual(plan.planner_mode, "metadata_analysis")
        self.assertIn("AVG(f.NORMALIZED_SCORE)", plan.sql)
        self.assertIn("JOIN CDM_LMS.PERSON_COURSE", plan.sql)
        self.assertIn("JOIN CDM_LMS.COURSE", plan.sql)
        self.assertIn("JOIN CDM_LMS.TERM", plan.sql)
        self.assertIn("pc.STUDENT_IND = TRUE", plan.sql)
        self.assertIn("LOWER(t.NAME) LIKE '%spring%2020%'", plan.sql)
        self.assertIn("LOWER(c.NAME) LIKE '%chemistry%'", plan.sql)

    def test_analysis_prefers_direct_term_join_over_instance_bridge(self) -> None:
        custom = MetadataStore.from_records(
            allowed_domains=("CDM_LMS",),
            tables=[],
            columns=[
                ColumnRecord("CDM_LMS", "GRADE", "PERSON_COURSE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "GRADE", "INSTANCE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "GRADE", "NORMALIZED_SCORE", "FLOAT", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "COURSE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "COURSE", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "COURSE", "TERM_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "TERM", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "TERM", "INSTANCE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "INSTANCE", "ID", "NUMBER", ""),
            ],
            dictionary=[],
        )
        plan = self.planner.plan(
            "What is the average normalized_score for students in chemistry classes in Spring 2020?",
            custom,
        )
        self.assertIn("JOIN CDM_LMS.COURSE", plan.sql)
        self.assertIn("JOIN CDM_LMS.TERM", plan.sql)
        self.assertNotIn("JOIN CDM_LMS.INSTANCE", plan.sql)

    def test_routes_to_cdm_sis_for_sis_intent(self) -> None:
        config = AppConfig.from_env({"ALLOWED_DOMAINS": "CDM_LMS,CDM_SIS"})
        planner = SqlPlanner(config, DomainRouter(config.allowed_domains))
        metadata = MetadataStore.from_builtin_catalog(config.allowed_domains)
        plan = planner.plan("What is average GPA by major?", metadata)
        self.assertEqual(plan.domain, "CDM_SIS")

    def test_join_spec_prefers_course_id_over_instance_id(self) -> None:
        custom = MetadataStore.from_records(
            allowed_domains=("CDM_LMS",),
            tables=[],
            columns=[
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "COURSE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "INSTANCE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "COURSE", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "COURSE", "INSTANCE_ID", "NUMBER", ""),
            ],
            dictionary=[],
        )
        model = SemanticModel.from_metadata(custom, "CDM_LMS")
        primary = _EntityInfo(
            name="PERSON_COURSE",
            score=5,
            columns=("COURSE_ID", "INSTANCE_ID"),
        )
        secondary = _EntityInfo(
            name="COURSE",
            score=5,
            columns=("ID", "INSTANCE_ID"),
        )
        join_spec = self.planner._find_join_spec(  # pylint: disable=protected-access
            primary,
            secondary,
            model,
        )
        self.assertEqual(join_spec, ("COURSE_ID", "ID"))


if __name__ == "__main__":
    unittest.main()
