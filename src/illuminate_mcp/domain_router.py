"""Domain routing logic for query planning."""

from __future__ import annotations

from typing import Iterable

from .exceptions import ToolError


class DomainRouter:
    _domain_keywords = {
        "CDM_LMS": (
            "lms",
            "course",
            "section",
            "assignment",
            "enrollment",
            "student",
            "learner",
            "grade",
            "attempt",
            "content",
            "discussion",
            "announcement",
        ),
        "CDM_TLM": (
            "telemetry",
            "usage",
            "ultra event",
            "activity event",
        ),
        "CDM_ALY": (
            "analytics",
            "dashboard",
            "kpi",
            "metric",
            "insight",
            "retention",
        ),
        "CDM_SIS": (
            "sis",
            "program",
            "admission",
            "transcript",
            "major",
            "gpa",
            "academic standing",
            "demographic",
            "degree",
            "institution",
        ),
        "CDM_CLB": (
            "collaborate",
            "virtual classroom",
            "session",
            "attendance",
            "recording",
            "meeting",
            "webinar",
        ),
        "CDM_MAP": (
            "mapping",
            "cross-system",
            "user map",
            "course map",
        ),
        "CDM_MEDIA": (
            "video",
            "media",
            "video studio",
            "recording view",
            "media activity",
        ),
        "CDM_META": (
            "metadata",
            "data source",
            "instance",
        ),
        "LEARN": (
            "learn schema",
            "open database",
            "bb learn",
            "blackboard learn",
            "source table",
        ),
    }

    def __init__(self, allowed_domains: Iterable[str]):
        self._allowed_domains = tuple(value.upper() for value in allowed_domains)

    def resolve(self, question: str, override: str | None = None) -> str:
        if override:
            if override not in self._allowed_domains:
                raise ToolError(f"domain override {override!r} is not configured")
            return override

        lowered = question.lower()
        for domain in self._allowed_domains:
            keywords = self._domain_keywords.get(domain, ())
            if keywords and any(keyword in lowered for keyword in keywords):
                return domain

        # V1 fallback when no confident signal is present.
        return self._allowed_domains[0]
