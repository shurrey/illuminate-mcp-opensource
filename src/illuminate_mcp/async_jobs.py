"""In-memory async query job manager for long-running executions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import threading
import uuid
from typing import Callable, Dict, List


@dataclass
class AsyncJob:
    job_id: str
    status: str
    created_at: str
    started_at: str | None
    completed_at: str | None
    sql: str
    result: dict | None
    error: str | None


class AsyncJobManager:
    def __init__(self, ttl_minutes: int = 60):
        self._jobs: Dict[str, AsyncJob] = {}
        self._lock = threading.Lock()
        self._ttl_minutes = max(1, ttl_minutes)

    def start(self, sql: str, work: Callable[[], dict]) -> str:
        self._sweep_expired()
        job_id = str(uuid.uuid4())
        job = AsyncJob(
            job_id=job_id,
            status="queued",
            created_at=_utc_now(),
            started_at=None,
            completed_at=None,
            sql=sql,
            result=None,
            error=None,
        )
        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(target=self._run_job, args=(job_id, work), daemon=True)
        thread.start()
        return job_id

    def _run_job(self, job_id: str, work: Callable[[], dict]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "running"
            job.started_at = _utc_now()

        try:
            result = work()
            with self._lock:
                job = self._jobs[job_id]
                job.status = "succeeded"
                job.result = result
                job.completed_at = _utc_now()
        except Exception as exc:  # pragma: no cover
            with self._lock:
                job = self._jobs[job_id]
                job.status = "failed"
                job.error = str(exc)
                job.completed_at = _utc_now()

    def get_status(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            return {
                "job_id": job.job_id,
                "status": job.status,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "has_result": job.result is not None,
                "has_error": job.error is not None,
            }

    def get_result(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            return {
                "job_id": job.job_id,
                "status": job.status,
                "error": job.error,
                "result": job.result,
            }

    def _sweep_expired(self) -> None:
        """Remove completed/failed jobs older than TTL. Called on each new start()."""
        now = datetime.now(timezone.utc)
        expired: List[str] = []
        with self._lock:
            for job_id, job in self._jobs.items():
                if job.completed_at is None:
                    continue
                completed = datetime.fromisoformat(job.completed_at)
                age_minutes = (now - completed).total_seconds() / 60.0
                if age_minutes >= self._ttl_minutes:
                    expired.append(job_id)
            for job_id in expired:
                del self._jobs[job_id]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
