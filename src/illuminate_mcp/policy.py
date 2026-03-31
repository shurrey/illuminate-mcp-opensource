"""SQL policy checks for safe read-only query execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Tuple

from .exceptions import PolicyError

_BLOCKED_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "merge",
    "create",
    "alter",
    "drop",
    "truncate",
    "grant",
    "revoke",
    "call",
    "copy",
    "put",
    "get",
    "use",
)

_OBJECT_PATTERN = re.compile(r"\b(?:from|join)\s+([A-Za-z0-9_\.\"$]+)", re.IGNORECASE)


@dataclass(frozen=True)
class PolicyResult:
    normalized_sql: str
    referenced_objects: Tuple[str, ...]


class SqlPolicy:
    def __init__(self, allowed_schemas: Iterable[str], allowed_tables: Iterable[str]):
        self._allowed_schemas = {value.upper() for value in allowed_schemas if value}
        self._allowed_tables = {self._normalize_table_name(value) for value in allowed_tables if value}

    def validate(self, sql: str) -> PolicyResult:
        normalized = (sql or "").strip()
        if not normalized:
            raise PolicyError("SQL is required")

        if "--" in normalized or "/*" in normalized or "*/" in normalized:
            raise PolicyError("SQL comments are not allowed")

        normalized = normalized.rstrip(";").strip()
        if ";" in normalized:
            raise PolicyError("Only single-statement SQL is allowed")

        lowered = normalized.lower()
        if not (lowered.startswith("select") or lowered.startswith("with")):
            raise PolicyError("Only SELECT and CTE queries are allowed")

        for keyword in _BLOCKED_KEYWORDS:
            if re.search(rf"\b{keyword}\b", lowered):
                raise PolicyError(f"SQL contains blocked keyword: {keyword}")

        references = tuple(sorted(set(self._extract_references(normalized))))
        self._enforce_allowlists(references)

        return PolicyResult(
            normalized_sql=normalized,
            referenced_objects=references,
        )

    def _extract_references(self, sql: str) -> Tuple[str, ...]:
        references = []
        for match in _OBJECT_PATTERN.finditer(sql):
            token = match.group(1).strip().rstrip(",")
            if token.startswith("("):
                continue
            normalized = self._normalize_table_name(token)
            if normalized:
                references.append(normalized)
        return tuple(references)

    @staticmethod
    def _normalize_table_name(raw_name: str) -> str:
        cleaned = raw_name.replace('"', "").strip()
        parts = [part for part in cleaned.split(".") if part]
        if not parts:
            return ""
        return ".".join(part.upper() for part in parts)

    def _enforce_allowlists(self, references: Tuple[str, ...]) -> None:
        if not references:
            return

        for ref in references:
            parts = ref.split(".")
            schema = parts[-2] if len(parts) >= 2 else ""

            if self._allowed_schemas and schema and schema not in self._allowed_schemas:
                raise PolicyError(f"Reference uses disallowed schema: {schema}")

            if self._allowed_tables and ref not in self._allowed_tables:
                # Allow schema.table comparison when configured names omit database.
                short_ref = ".".join(parts[-2:]) if len(parts) >= 2 else ref
                if short_ref not in self._allowed_tables:
                    raise PolicyError(f"Reference uses disallowed table: {ref}")
