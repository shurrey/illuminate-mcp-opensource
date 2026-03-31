import unittest
from datetime import datetime
from decimal import Decimal

from illuminate_mcp.output import OutputComposer


class OutputComposerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.composer = OutputComposer(max_summary_length=1200)

    def test_auto_includes_text_and_table(self) -> None:
        payload = self.composer.compose(
            question="List courses",
            columns=("COURSE_ID", "COURSE_NAME"),
            rows=[(1, "Chem 101")],
            output_mode="auto",
        )
        self.assertIn("summary_text", payload)
        self.assertIn("table", payload)
        self.assertEqual(payload["output_parts"], ["text", "table"])

    def test_text_mode_excludes_table(self) -> None:
        payload = self.composer.compose(
            question="Just summarize",
            columns=("A", "B"),
            rows=[(1, 2)],
            output_mode="text",
        )
        self.assertIn("summary_text", payload)
        self.assertNotIn("table", payload)
        self.assertEqual(payload["output_parts"], ["text"])

    def test_viz_mode_builds_line_for_temporal_x(self) -> None:
        payload = self.composer.compose(
            question="Show trend chart over time",
            columns=("PERIOD", "RECORD_COUNT"),
            rows=[
                ("2020-01-01", 10),
                ("2020-02-01", 20),
            ],
            output_mode="viz",
        )
        self.assertIn("vega_lite_spec", payload)
        self.assertEqual(payload["vega_lite_spec"]["mark"], "line")
        self.assertEqual(payload["chart_hint"]["intent"], "trend")
        self.assertIn("viz", payload["output_parts"])

    def test_viz_mode_builds_histogram_for_distribution(self) -> None:
        payload = self.composer.compose(
            question="Show score distribution histogram",
            columns=("SCORE",),
            rows=[(10,), (11,), (12,), (13,)],
            output_mode="viz",
        )
        self.assertIn("vega_lite_spec", payload)
        self.assertEqual(payload["chart_hint"]["intent"], "distribution")
        self.assertEqual(payload["vega_lite_spec"]["encoding"]["x"]["bin"], True)

    def test_viz_mode_builds_scatter_for_relationship(self) -> None:
        payload = self.composer.compose(
            question="Show relationship between score and time spent",
            columns=("TIME_SPENT", "SCORE"),
            rows=[(1.2, 0.4), (2.1, 0.7)],
            output_mode="viz",
        )
        self.assertIn("vega_lite_spec", payload)
        self.assertEqual(payload["vega_lite_spec"]["mark"], "point")
        self.assertEqual(payload["chart_hint"]["intent"], "relationship")

    def test_viz_mode_adds_warning_when_unsuitable(self) -> None:
        payload = self.composer.compose(
            question="Show a chart",
            columns=("TERM_NAME", "COURSE_NAME"),
            rows=[("Spring 2020", "Chem")],
            output_mode="viz",
        )
        self.assertIn("visualization_warning", payload)
        self.assertNotIn("vega_lite_spec", payload)

    def test_json_safety_for_decimal_datetime_nan(self) -> None:
        payload = self.composer.compose(
            question="List values",
            columns=("SCORE", "TS", "BAD"),
            rows=[(Decimal("1.5"), datetime(2020, 1, 2, 3, 4, 5), float("nan"))],
            output_mode="table",
        )
        row = payload["table"]["rows"][0]
        self.assertEqual(row[0], 1.5)
        self.assertEqual(row[1], "2020-01-02T03:04:05")
        self.assertIsNone(row[2])


if __name__ == "__main__":
    unittest.main()
