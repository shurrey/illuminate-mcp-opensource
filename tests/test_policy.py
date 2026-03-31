import unittest

from illuminate_mcp.exceptions import PolicyError
from illuminate_mcp.policy import SqlPolicy


class SqlPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = SqlPolicy(
            allowed_schemas=("CDM_LMS",),
            allowed_tables=("CDM_LMS.COURSE", "CDM_LMS.ENROLLMENT"),
        )

    def test_allows_select_query(self) -> None:
        result = self.policy.validate("SELECT COURSE_ID FROM CDM_LMS.COURSE")
        self.assertEqual(result.normalized_sql, "SELECT COURSE_ID FROM CDM_LMS.COURSE")

    def test_blocks_mutating_query(self) -> None:
        with self.assertRaises(PolicyError):
            self.policy.validate("DELETE FROM CDM_LMS.COURSE")

    def test_blocks_multi_statement(self) -> None:
        with self.assertRaises(PolicyError):
            self.policy.validate("SELECT 1; SELECT 2")

    def test_blocks_disallowed_schema(self) -> None:
        with self.assertRaises(PolicyError):
            self.policy.validate("SELECT * FROM OTHER.COURSE")


if __name__ == "__main__":
    unittest.main()
