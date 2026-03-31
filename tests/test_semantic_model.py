import unittest

from illuminate_mcp.metadata import ColumnRecord, MetadataStore
from illuminate_mcp.semantic_model import SemanticModel


class SemanticModelTests(unittest.TestCase):
    def test_infers_join_path_for_grade_to_term(self) -> None:
        metadata = MetadataStore.from_records(
            allowed_domains=("CDM_LMS",),
            tables=[],
            columns=[
                ColumnRecord("CDM_LMS", "GRADE", "PERSON_COURSE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "GRADE", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "PERSON_COURSE", "COURSE_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "COURSE", "ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "COURSE", "TERM_ID", "NUMBER", ""),
                ColumnRecord("CDM_LMS", "TERM", "ID", "NUMBER", ""),
            ],
            dictionary=[],
        )

        model = SemanticModel.from_metadata(metadata, "CDM_LMS")
        path = model.shortest_join_path("GRADE", "TERM")

        self.assertGreaterEqual(len(path), 3)
        steps = [(p.source_entity, p.target_entity) for p in path]
        self.assertIn(("GRADE", "PERSON_COURSE"), steps)
        self.assertIn(("PERSON_COURSE", "COURSE"), steps)
        self.assertIn(("COURSE", "TERM"), steps)


if __name__ == "__main__":
    unittest.main()
