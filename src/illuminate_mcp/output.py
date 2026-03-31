"""Adaptive output shaping for query results."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
import math
from typing import Mapping, Sequence


class OutputComposer:
    def __init__(self, max_summary_length: int):
        self._max_summary_length = max_summary_length

    def compose(
        self,
        question: str,
        columns: Sequence[str],
        rows: Sequence[Sequence],
        output_mode: str = "auto",
    ) -> dict:
        mode = self._normalize_mode(output_mode)
        safe_rows = [self._to_json_safe_row(row) for row in rows]
        summary = self._build_summary(columns, rows)
        payload = {"summary_text": summary[: self._max_summary_length]}
        parts = ["text"]

        include_table = mode in {"auto", "table", "viz"}
        include_viz = mode == "viz" or (mode == "auto" and self._wants_visualization(question))
        viz_intent = self._infer_visual_intent(question)

        if include_table:
            payload["table"] = {
                "columns": list(columns),
                "rows": safe_rows,
                "row_count": len(safe_rows),
            }
            parts.append("table")

        if include_viz:
            spec = self._build_vega_lite_spec(question, columns, safe_rows)
            if spec:
                payload["vega_lite_spec"] = spec
                payload["chart_hint"] = {
                    "intent": viz_intent,
                    "mark": spec.get("mark"),
                }
                parts.append("viz")
            elif mode == "viz":
                payload["visualization_warning"] = "Visualization requested but no suitable chart shape was found."

        payload["output_parts"] = parts

        return payload

    @staticmethod
    def _build_summary(columns: Sequence[str], rows: Sequence[Sequence]) -> str:
        if not rows:
            return "Query returned 0 rows."
        return f"Query returned {len(rows)} rows across {len(columns)} columns."

    @staticmethod
    def _normalize_mode(output_mode: str) -> str:
        lowered = str(output_mode or "auto").strip().lower()
        if lowered in {"auto", "text", "table", "viz"}:
            return lowered
        return "auto"

    @staticmethod
    def _wants_visualization(question: str) -> bool:
        lowered = question.lower()
        return any(token in lowered for token in ("chart", "graph", "plot", "visual", "trend", "over time"))

    @staticmethod
    def _infer_visual_intent(question: str) -> str:
        lowered = question.lower()
        if any(token in lowered for token in ("over time", "trend", "month", "daily", "weekly", "yearly")):
            return "trend"
        if any(token in lowered for token in ("distribution", "histogram", "spread")):
            return "distribution"
        if any(token in lowered for token in ("correlation", "relationship", "vs", "versus", "scatter")):
            return "relationship"
        return "comparison"

    @staticmethod
    def _build_vega_lite_spec(
        question: str,
        columns: Sequence[str],
        rows: Sequence[Sequence],
    ) -> Mapping | None:
        if not rows:
            return None
        intent = OutputComposer._infer_visual_intent(question)

        if intent == "distribution" and len(columns) >= 1 and OutputComposer._is_numeric_column(rows, 0):
            x_col = columns[0]
            values = [{x_col: row[0]} for row in rows[:200] if len(row) >= 1]
            return {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "description": "Auto-generated distribution chart",
                "data": {"values": values},
                "mark": "bar",
                "encoding": {
                    "x": {"field": x_col, "bin": True, "type": "quantitative"},
                    "y": {"aggregate": "count", "type": "quantitative"},
                },
            }

        if len(columns) < 2:
            return None
        x_col = columns[0]
        y_col = columns[1]
        if not OutputComposer._is_numeric_column(rows, 1):
            return None

        is_temporal_x = OutputComposer._is_temporal_column(rows, 0)
        is_numeric_x = OutputComposer._is_numeric_column(rows, 0)
        if not is_temporal_x and not is_numeric_x and OutputComposer._distinct_count(rows, 0) > 50:
            return None

        values = [{x_col: row[0], y_col: row[1]} for row in rows[:200] if len(row) >= 2]

        if intent == "relationship" and is_numeric_x:
            mark = "point"
            x_type = "quantitative"
        elif is_temporal_x:
            mark = "line"
            x_type = "temporal"
        else:
            mark = "bar"
            x_type = "quantitative" if is_numeric_x else "nominal"

        return {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "description": "Auto-generated chart suggestion",
            "data": {"values": values},
            "mark": mark,
            "encoding": {
                "x": {"field": x_col, "type": x_type},
                "y": {"field": y_col, "type": "quantitative"},
            },
        }

    @staticmethod
    def _is_numeric_column(rows: Sequence[Sequence], index: int) -> bool:
        numeric_seen = False
        for row in rows[:200]:
            if index >= len(row):
                return False
            value = row[index]
            if value is None:
                continue
            if isinstance(value, bool):
                return False
            if isinstance(value, (int, float)):
                numeric_seen = True
                continue
            try:
                float(str(value))
                numeric_seen = True
            except Exception:
                return False
        return numeric_seen

    @staticmethod
    def _is_temporal_column(rows: Sequence[Sequence], index: int) -> bool:
        for row in rows[:200]:
            if index >= len(row):
                return False
            value = row[index]
            if value is None:
                continue
            if isinstance(value, (datetime, date, time)):
                return True
            text = str(value)
            if "T" in text and "-" in text:
                return True
            if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
                return True
            return False
        return False

    @staticmethod
    def _distinct_count(rows: Sequence[Sequence], index: int) -> int:
        values = set()
        for row in rows[:500]:
            if index >= len(row):
                continue
            values.add(row[index])
        return len(values)

    @staticmethod
    def _to_json_safe_row(row: Sequence) -> list:
        return [OutputComposer._to_json_safe_value(value) for value in row]

    @staticmethod
    def _to_json_safe_value(value):
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return value
