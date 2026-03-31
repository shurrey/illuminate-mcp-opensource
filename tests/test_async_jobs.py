import time
import unittest

from illuminate_mcp.async_jobs import AsyncJobManager


class AsyncJobManagerTests(unittest.TestCase):
    def test_async_job_succeeds(self) -> None:
        manager = AsyncJobManager()

        def _work() -> dict:
            time.sleep(0.05)
            return {"status": "ok", "value": 42}

        job_id = manager.start("SELECT 1", _work)

        deadline = time.time() + 2
        status = manager.get_status(job_id)
        while status and status["status"] in {"queued", "running"} and time.time() < deadline:
            time.sleep(0.02)
            status = manager.get_status(job_id)

        self.assertIsNotNone(status)
        self.assertEqual(status["status"], "succeeded")

        result = manager.get_result(job_id)
        assert result is not None
        self.assertEqual(result["result"]["status"], "ok")

    def test_async_job_failure(self) -> None:
        manager = AsyncJobManager()

        def _work() -> dict:
            raise RuntimeError("boom")

        job_id = manager.start("SELECT 1", _work)

        deadline = time.time() + 2
        status = manager.get_status(job_id)
        while status and status["status"] in {"queued", "running"} and time.time() < deadline:
            time.sleep(0.02)
            status = manager.get_status(job_id)

        self.assertIsNotNone(status)
        self.assertEqual(status["status"], "failed")

        result = manager.get_result(job_id)
        assert result is not None
        self.assertIn("boom", result["error"])


    def test_sweep_removes_expired_jobs(self) -> None:
        manager = AsyncJobManager(ttl_minutes=0)  # immediate expiry

        def _work() -> dict:
            return {"ok": True}

        job_id = manager.start("SELECT 1", _work)

        deadline = time.time() + 2
        while True:
            status = manager.get_status(job_id)
            if status and status["status"] == "succeeded":
                break
            if time.time() > deadline:
                break
            time.sleep(0.02)

        # Job exists now
        self.assertIsNotNone(manager.get_status(job_id))

        # Starting a new job triggers sweep — ttl_minutes=0 means min 1 minute,
        # so we manually call sweep after patching completed_at to the past.
        from datetime import datetime, timezone, timedelta
        with manager._lock:
            job = manager._jobs[job_id]
            past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            job.completed_at = past

        manager._sweep_expired()
        self.assertIsNone(manager.get_status(job_id))


if __name__ == "__main__":
    unittest.main()
