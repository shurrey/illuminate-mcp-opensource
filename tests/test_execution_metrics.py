import unittest

from illuminate_mcp.config import AppConfig
from illuminate_mcp.execution import SnowflakeExecutor


class ExecutionMetricsTests(unittest.TestCase):
    def test_normalize_query_history_row(self) -> None:
        payload = SnowflakeExecutor._normalize_query_history_row(  # pylint: disable=protected-access
            columns=(
                "QUERY_ID",
                "TOTAL_ELAPSED_TIME",
                "BYTES_SCANNED",
                "ROWS_PRODUCED",
                "CREDITS_USED_CLOUD_SERVICES",
            ),
            row=("01abc", 1234, 98765, 42, 0.03125),
        )
        self.assertEqual(payload["source"], "query_history_by_session")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["query_id"], "01abc")
        self.assertEqual(payload["elapsed_ms"], 1234)
        self.assertEqual(payload["bytes_scanned"], 98765)
        self.assertEqual(payload["rows_produced"], 42)
        self.assertEqual(payload["credits_used_cloud_services"], 0.03125)

    def test_query_id_safety(self) -> None:
        safe = SnowflakeExecutor._is_safe_query_id("01c2b237-080b-08e4-0033-50830189c01e")  # pylint: disable=protected-access
        unsafe = SnowflakeExecutor._is_safe_query_id("01c2b237'; DROP TABLE X; --")  # pylint: disable=protected-access
        self.assertTrue(safe)
        self.assertFalse(unsafe)

    def test_estimate_warehouse_credits(self) -> None:
        config = AppConfig.from_env({"WAREHOUSE_CREDITS_PER_HOUR": "4.0"})
        executor = SnowflakeExecutor(config)
        estimated = executor._estimate_warehouse_credits(  # pylint: disable=protected-access
            metrics={"elapsed_ms": 300000},
            execution_seconds=0.0,
        )
        self.assertAlmostEqual(estimated, (300.0 / 3600.0) * 4.0, places=6)


if __name__ == "__main__":
    unittest.main()
