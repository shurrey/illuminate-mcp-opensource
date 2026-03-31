import unittest
import tempfile
from pathlib import Path

from illuminate_mcp.feedback import PlannerFeedbackStore


class PlannerFeedbackStoreTests(unittest.TestCase):
    def test_records_success_and_failure(self) -> None:
        store = PlannerFeedbackStore()
        key = "entities=COURSE;complexity=low;join=0;group=0;trend=0"
        store.record(key, success=True, execution_seconds=1.2)
        store.record(key, success=False, execution_seconds=0.3)

        stats = store.get(key)
        self.assertEqual(stats.attempts, 2)
        self.assertEqual(stats.successes, 1)
        self.assertEqual(stats.failures, 1)
        self.assertAlmostEqual(stats.success_rate, 0.5, places=2)
        self.assertAlmostEqual(stats.avg_seconds, 1.2, places=2)

    def test_persists_and_loads_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback.json"
            key = "entities=COURSE;complexity=low;join=0;group=0;trend=0"

            writer = PlannerFeedbackStore(persist_path=str(path))
            writer.record(key, success=True, execution_seconds=2.5)

            reader = PlannerFeedbackStore(persist_path=str(path))
            stats = reader.get(key)
            self.assertEqual(stats.attempts, 1)
            self.assertEqual(stats.successes, 1)
            self.assertAlmostEqual(stats.avg_seconds, 2.5, places=2)


if __name__ == "__main__":
    unittest.main()
