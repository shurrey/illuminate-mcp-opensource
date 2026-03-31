import unittest

from illuminate_mcp.metadata import ColumnRecord, DictionaryRecord, MetadataStore, TableRecord


class MetadataStoreTests(unittest.TestCase):
    def test_builds_entities_from_records(self) -> None:
        store = MetadataStore.from_records(
            allowed_domains=("CDM_LMS",),
            tables=[
                TableRecord(
                    table_schema="CDM_LMS",
                    table_name="COURSE",
                    table_comment="Course table",
                )
            ],
            columns=[
                ColumnRecord(
                    table_schema="CDM_LMS",
                    table_name="COURSE",
                    column_name="COURSE_ID",
                    data_type="NUMBER",
                    column_comment="",
                ),
                ColumnRecord(
                    table_schema="CDM_LMS",
                    table_name="COURSE",
                    column_name="COURSE_NAME",
                    data_type="TEXT",
                    column_comment="Name of course",
                ),
            ],
            dictionary=[
                DictionaryRecord(
                    table_schema="CDM_LMS",
                    table_name="COURSE",
                    column_name="COURSE_ID",
                    description="Dictionary description",
                )
            ],
        )

        entity = store.describe_entity("CDM_LMS", "COURSE")
        assert entity is not None
        self.assertEqual(entity["description"], "Course table")
        self.assertEqual(entity["columns"]["COURSE_ID"], "Dictionary description")
        self.assertEqual(entity["columns"]["COURSE_NAME"], "Name of course")

    def test_fills_default_type_description(self) -> None:
        store = MetadataStore.from_records(
            allowed_domains=("CDM_LMS",),
            tables=[],
            columns=[
                ColumnRecord(
                    table_schema="CDM_LMS",
                    table_name="ENROLLMENT",
                    column_name="USER_ID",
                    data_type="VARCHAR",
                    column_comment="",
                )
            ],
            dictionary=[],
        )

        entity = store.describe_entity("CDM_LMS", "ENROLLMENT")
        assert entity is not None
        self.assertEqual(entity["columns"]["USER_ID"], "VARCHAR column")

    def test_builtin_catalog_includes_cdm_sis_entities(self) -> None:
        store = MetadataStore.from_builtin_catalog(("CDM_LMS", "CDM_SIS"))
        domains = store.list_domains()
        names = {entry["name"] for entry in domains}
        self.assertIn("CDM_SIS", names)
        entities = store.list_entities("CDM_SIS")
        entity_names = {entry["name"] for entry in entities}
        self.assertIn("STUDENT", entity_names)
        self.assertIn("ACADEMIC_TERM", entity_names)

    def test_builtin_catalog_includes_cdm_tlm_entities(self) -> None:
        store = MetadataStore.from_builtin_catalog(("CDM_LMS", "CDM_TLM"))
        domains = store.list_domains()
        names = {entry["name"] for entry in domains}
        self.assertIn("CDM_TLM", names)
        entities = store.list_entities("CDM_TLM")
        entity_names = {entry["name"] for entry in entities}
        self.assertIn("LEARNER_ACTIVITY", entity_names)
        self.assertIn("LEARNING_RESOURCE", entity_names)

    def test_builtin_catalog_includes_cdm_aly_entities(self) -> None:
        store = MetadataStore.from_builtin_catalog(("CDM_LMS", "CDM_ALY"))
        domains = store.list_domains()
        names = {entry["name"] for entry in domains}
        self.assertIn("CDM_ALY", names)
        entities = store.list_entities("CDM_ALY")
        entity_names = {entry["name"] for entry in entities}
        self.assertIn("METRIC_DAILY", entity_names)
        self.assertIn("KPI_SNAPSHOT", entity_names)


    def test_builtin_catalog_includes_cdm_lms_expanded_entities(self) -> None:
        store = MetadataStore.from_builtin_catalog(("CDM_LMS",))
        entities = store.list_entities("CDM_LMS")
        entity_names = {entry["name"] for entry in entities}
        self.assertIn("GRADE", entity_names)
        self.assertIn("ASSIGNMENT", entity_names)
        self.assertIn("ATTEMPT", entity_names)
        self.assertIn("CONTENT_ITEM", entity_names)
        self.assertIn("DISCUSSION", entity_names)
        self.assertIn("ANNOUNCEMENT", entity_names)
        self.assertIn("PERSON_COURSE", entity_names)
        self.assertIn("GRADE_COLUMN", entity_names)

    def test_builtin_catalog_includes_cdm_clb(self) -> None:
        store = MetadataStore.from_builtin_catalog(("CDM_CLB",))
        entities = store.list_entities("CDM_CLB")
        entity_names = {entry["name"] for entry in entities}
        self.assertIn("SESSION", entity_names)
        self.assertIn("ATTENDANCE", entity_names)
        self.assertIn("RECORDING", entity_names)

    def test_builtin_catalog_includes_cdm_map(self) -> None:
        store = MetadataStore.from_builtin_catalog(("CDM_MAP",))
        entities = store.list_entities("CDM_MAP")
        entity_names = {entry["name"] for entry in entities}
        self.assertIn("USER_MAP", entity_names)
        self.assertIn("COURSE_MAP", entity_names)

    def test_builtin_catalog_includes_cdm_media(self) -> None:
        store = MetadataStore.from_builtin_catalog(("CDM_MEDIA",))
        entities = store.list_entities("CDM_MEDIA")
        entity_names = {entry["name"] for entry in entities}
        self.assertIn("MEDIA", entity_names)
        self.assertIn("ACTIVITY", entity_names)
        self.assertIn("CONTAINER", entity_names)
        self.assertIn("PERSON", entity_names)
        self.assertIn("SESSION_ACTIVITY", entity_names)

    def test_builtin_catalog_includes_cdm_meta(self) -> None:
        store = MetadataStore.from_builtin_catalog(("CDM_META",))
        entities = store.list_entities("CDM_META")
        entity_names = {entry["name"] for entry in entities}
        self.assertIn("DATA_SOURCE", entity_names)
        self.assertIn("INSTANCE", entity_names)

    def test_builtin_catalog_includes_learn_when_allowed(self) -> None:
        store = MetadataStore.from_builtin_catalog(("LEARN",))
        entities = store.list_entities("LEARN")
        entity_names = {entry["name"] for entry in entities}
        self.assertIn("USERS", entity_names)
        self.assertIn("COURSE_MAIN", entity_names)
        self.assertIn("COURSE_USERS", entity_names)
        self.assertIn("GRADEBOOK_MAIN", entity_names)
        self.assertIn("GRADEBOOK_GRADE", entity_names)

    def test_builtin_catalog_excludes_learn_when_not_allowed(self) -> None:
        store = MetadataStore.from_builtin_catalog(("CDM_LMS",))
        domains = store.list_domains()
        names = {entry["name"] for entry in domains}
        self.assertNotIn("LEARN", names)

    def test_builtin_catalog_cdm_sis_expanded_entities(self) -> None:
        store = MetadataStore.from_builtin_catalog(("CDM_SIS",))
        entities = store.list_entities("CDM_SIS")
        entity_names = {entry["name"] for entry in entities}
        self.assertIn("INSTITUTION", entity_names)
        self.assertIn("DEGREE", entity_names)

    def test_builtin_catalog_cdm_tlm_ultra_events(self) -> None:
        store = MetadataStore.from_builtin_catalog(("CDM_TLM",))
        entities = store.list_entities("CDM_TLM")
        entity_names = {entry["name"] for entry in entities}
        self.assertIn("ULTRA_EVENTS", entity_names)


if __name__ == "__main__":
    unittest.main()
