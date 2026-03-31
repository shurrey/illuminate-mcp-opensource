"""Shared tokenization utilities for entity matching and SQL planning."""

from __future__ import annotations

import re
from typing import Set


def tokenize(value: str) -> Set[str]:
    """Split a value into lowercase tokens with basic stemming and synonyms."""
    raw = [token for token in re.split(r"[^a-zA-Z0-9]+", value.lower()) if token]
    expanded: Set[str] = set()
    for token in raw:
        expanded.add(token)
        if len(token) > 4 and token.endswith("es"):
            expanded.add(token[:-2])
        if len(token) > 3 and token.endswith("s"):
            expanded.add(token[:-1])
        if token in {"class", "classes"}:
            expanded.add("course")
    return expanded
