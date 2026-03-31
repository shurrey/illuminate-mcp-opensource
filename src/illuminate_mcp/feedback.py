"""Planner feedback store with optional local persistence."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import threading
from typing import Dict


@dataclass
class FeedbackStats:
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    total_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.attempts == 0:
            return 0.0
        return self.successes / self.attempts

    @property
    def avg_seconds(self) -> float:
        if self.successes == 0:
            return 0.0
        return self.total_seconds / self.successes


class PlannerFeedbackStore:
    def __init__(self, persist_path: str | None = None):
        self._stats: Dict[str, FeedbackStats] = {}
        self._lock = threading.Lock()
        self._persist_path = Path(persist_path).expanduser() if persist_path else None
        if self._persist_path:
            self._load()

    def record(self, signature: str, success: bool, execution_seconds: float) -> None:
        with self._lock:
            stats = self._stats.setdefault(signature, FeedbackStats())
            stats.attempts += 1
            if success:
                stats.successes += 1
                stats.total_seconds += max(0.0, float(execution_seconds))
            else:
                stats.failures += 1
            self._persist()

    def get(self, signature: str) -> FeedbackStats:
        with self._lock:
            stats = self._stats.get(signature)
            if not stats:
                return FeedbackStats()
            return FeedbackStats(
                attempts=stats.attempts,
                successes=stats.successes,
                failures=stats.failures,
                total_seconds=stats.total_seconds,
            )

    def snapshot(self) -> dict:
        with self._lock:
            return {
                signature: {
                    "attempts": stats.attempts,
                    "successes": stats.successes,
                    "failures": stats.failures,
                    "success_rate": round(stats.success_rate, 3),
                    "avg_seconds": round(stats.avg_seconds, 4),
                }
                for signature, stats in self._stats.items()
            }

    def _persist(self) -> None:
        if not self._persist_path:
            return
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            signature: {
                "attempts": stats.attempts,
                "successes": stats.successes,
                "failures": stats.failures,
                "total_seconds": stats.total_seconds,
            }
            for signature, stats in self._stats.items()
        }
        temp_path = self._persist_path.with_suffix(self._persist_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        temp_path.replace(self._persist_path)

    def _load(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            payload = json.loads(self._persist_path.read_text())
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        for signature, raw in payload.items():
            if not isinstance(raw, dict):
                continue
            self._stats[str(signature)] = FeedbackStats(
                attempts=int(raw.get("attempts", 0)),
                successes=int(raw.get("successes", 0)),
                failures=int(raw.get("failures", 0)),
                total_seconds=float(raw.get("total_seconds", 0.0)),
            )
