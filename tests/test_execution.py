import unittest

from illuminate_mcp.execution import SnowflakeExecutor


class ExecutionProbeTests(unittest.TestCase):
    def test_infer_probe_has_rows_from_record_count_zero(self) -> None:
        has_rows = SnowflakeExecutor._infer_probe_has_rows(  # pylint: disable=protected-access
            row=(None, None, 0),
            columns=("AVG_NORMALIZED_SCORE", "AVG_SCORE", "RECORD_COUNT"),
        )
        self.assertFalse(has_rows)

    def test_infer_probe_has_rows_from_record_count_positive(self) -> None:
        has_rows = SnowflakeExecutor._infer_probe_has_rows(  # pylint: disable=protected-access
            row=(0.88, 24.2, 5884),
            columns=("AVG_NORMALIZED_SCORE", "AVG_SCORE", "RECORD_COUNT"),
        )
        self.assertTrue(has_rows)

    def test_infer_probe_has_rows_when_no_record_count(self) -> None:
        has_rows = SnowflakeExecutor._infer_probe_has_rows(  # pylint: disable=protected-access
            row=(1,),
            columns=("ANY_VALUE",),
        )
        self.assertTrue(has_rows)


if __name__ == "__main__":
    unittest.main()
