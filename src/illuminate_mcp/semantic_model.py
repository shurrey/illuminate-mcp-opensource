"""Semantic entity and relationship model for metadata-driven SQL planning."""

from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from .metadata import MetadataStore
from .tokens import tokenize


@dataclass(frozen=True)
class Relationship:
    source_entity: str
    source_column: str
    target_entity: str
    target_column: str
    confidence: float


class SemanticModel:
    def __init__(self, domain: str, entities: Dict[str, Set[str]], relationships: List[Relationship]):
        self.domain = domain
        self.entities = entities
        self.relationships = relationships
        self._adj: Dict[str, List[Relationship]] = {name: [] for name in entities}
        for rel in relationships:
            self._adj.setdefault(rel.source_entity, []).append(rel)

    @classmethod
    def from_metadata(cls, metadata: MetadataStore, domain: str) -> "SemanticModel":
        entity_names = [entry["name"].upper() for entry in metadata.list_entities(domain)]
        entities: Dict[str, Set[str]] = {}
        for name in entity_names:
            detail = metadata.describe_entity(domain, name) or {"columns": {}}
            entities[name] = {col.upper() for col in (detail.get("columns") or {}).keys()}

        relationships = _infer_relationships(entities)
        return cls(domain=domain, entities=entities, relationships=relationships)

    def resolve_entity_candidates(self, question: str) -> List[Tuple[str, float]]:
        tokens = tokenize(question)
        scored: List[Tuple[str, float]] = []

        for entity, columns in self.entities.items():
            entity_tokens = set(tokenize(entity.replace("_", " ")))
            col_tokens = set()
            for col in columns:
                col_tokens.update(tokenize(col.replace("_", " ")))

            score = 0.0
            score += len(tokens.intersection(entity_tokens)) * 3.0
            score += len(tokens.intersection(col_tokens)) * 1.0
            if entity in _semantic_hints(tokens):
                score += 4.0
            if score > 0:
                scored.append((entity, score))

        if not scored and self.entities:
            first = sorted(self.entities.keys())[0]
            return [(first, 0.0)]

        scored.sort(key=lambda item: (-item[1], item[0].count("_"), len(item[0])))
        return scored

    def shortest_join_path(self, start: str, goal: str) -> List[Relationship]:
        start = start.upper()
        goal = goal.upper()
        if start == goal:
            return []
        if start not in self.entities or goal not in self.entities:
            return []

        queue = deque([(start, [])])
        seen = {start}

        while queue:
            current, path = queue.popleft()
            for rel in self._adj.get(current, []):
                nxt = rel.target_entity
                if nxt in seen:
                    continue
                next_path = path + [rel]
                if nxt == goal:
                    return next_path
                seen.add(nxt)
                queue.append((nxt, next_path))
        return []

    def identity_column(self, entity: str) -> str | None:
        entity = entity.upper()
        cols = self.entities.get(entity, set())
        if not cols:
            return None
        if "ID" in cols:
            return "ID"
        prefix = entity.split("_")[0]
        preferred = f"{prefix}_ID"
        if preferred in cols:
            return preferred
        for col in ("COURSE_ID", "USER_ID", "SECTION_ID", "INSTANCE_ID", "TERM_ID"):
            if col in cols:
                return col
        for col in sorted(cols):
            if col.endswith("_ID"):
                return col
        return None

    def has_column(self, entity: str, column: str) -> bool:
        return column.upper() in self.entities.get(entity.upper(), set())


def _infer_relationships(entities: Dict[str, Set[str]]) -> List[Relationship]:
    rels: List[Relationship] = []

    for source, source_cols in entities.items():
        for col in source_cols:
            if not col.endswith("_ID"):
                continue
            if col in {"ROW_DELETED_TIME", "SOURCE_ID", "MODIFIER_PERSON_ID"}:
                continue

            base = col[:-3]
            best_target = None
            best_score = 0.0
            best_target_col = "ID"

            for target, target_cols in entities.items():
                if target == source:
                    continue

                target_id = _preferred_id_for_target(target, target_cols)
                if not target_id:
                    continue

                score = 0.0
                if col == f"{target}_ID":
                    score += 5.0
                if target.startswith(base) or base.startswith(target):
                    score += 3.0
                if target.split("_")[0] == base.split("_")[0]:
                    score += 2.0
                if target_id == col:
                    score += 1.5
                if target_id == "ID":
                    score += 0.5

                if score > best_score:
                    best_score = score
                    best_target = target
                    best_target_col = target_id

            if best_target and best_score >= 2.0:
                rels.append(
                    Relationship(
                        source_entity=source,
                        source_column=col,
                        target_entity=best_target,
                        target_column=best_target_col,
                        confidence=min(1.0, best_score / 7.0),
                    )
                )

    # Add reverse relationships for traversal/SQL generation.
    reverse: List[Relationship] = []
    for rel in rels:
        reverse.append(
            Relationship(
                source_entity=rel.target_entity,
                source_column=rel.target_column,
                target_entity=rel.source_entity,
                target_column=rel.source_column,
                confidence=rel.confidence,
            )
        )
    return rels + reverse


def _preferred_id_for_target(target: str, target_cols: Set[str]) -> str | None:
    if "ID" in target_cols:
        return "ID"
    pref = f"{target.split('_')[0]}_ID"
    if pref in target_cols:
        return pref
    for col in target_cols:
        if col.endswith("_ID"):
            return col
    return None



def _semantic_hints(tokens: Set[str]) -> Set[str]:
    hints = set()
    if any(token in tokens for token in {"course", "class"}):
        hints.add("COURSE")
    if any(token in tokens for token in {"grade", "score", "normalized", "evaluation"}):
        hints.update({"GRADE", "EVALUATION"})
    if any(token in tokens for token in {"enrollment", "student"}):
        hints.add("PERSON_COURSE")
    if any(token in tokens for token in {"term", "spring", "summer", "fall", "winter"}):
        hints.add("TERM")
    return hints
