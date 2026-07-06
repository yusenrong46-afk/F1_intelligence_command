"""M7 status labels must stay honest."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_m7_status_report import (  # noqa: E402
    CURRENT_PRODUCT_RUNS,
    M7_PRODUCT_RUNS,
    display_command,
    m7_readiness_status,
    not_used_summary,
    overall_status_for_rows,
    render_markdown,
    status_label,
)


class M7StatusLabelTests(unittest.TestCase):
    def test_false_verified_is_unsafe_even_if_other_metrics_look_good(self) -> None:
        self.assertEqual(
            status_label({"false_verified_count": 1, "quality_gate_passed": True, "candidate_recall": 1.0}),
            "unsafe / needs fix",
        )

    def test_false_approval_is_unsafe(self) -> None:
        self.assertEqual(
            status_label({"false_verified_count": 0, "false_approval_count": 1, "quality_gate_passed": True}),
            "unsafe / needs fix",
        )

    def test_clean_gate_pass_is_pass(self) -> None:
        self.assertEqual(status_label({"false_verified_count": 0, "quality_gate_passed": True}), "pass")

    def test_low_candidate_recall_is_scope_mismatch(self) -> None:
        self.assertEqual(
            status_label({"false_verified_count": 0, "quality_gate_passed": False, "candidate_recall": 0.5}),
            "scope mismatch",
        )

    def test_full_verified_or_review_coverage_is_not_scope_mismatch(self) -> None:
        self.assertEqual(
            status_label(
                {
                    "false_verified_count": 0,
                    "quality_gate_passed": False,
                    "candidate_recall": 0.5,
                    "verified_or_review_recall": 1.0,
                    "extraction_coverage_recall": 1.0,
                    "verified_rule_count": 2,
                    "review_rule_count": 1,
                }
            ),
            "needs review",
        )


class M7ReportSummaryTests(unittest.TestCase):
    def test_current_product_runs_use_native_m7(self) -> None:
        self.assertTrue(CURRENT_PRODUCT_RUNS)
        for run in CURRENT_PRODUCT_RUNS:
            self.assertEqual(run.lane, "native_m7")
            self.assertIn("m7_runs", str(run.output_dir))

    def test_m7_readiness_requires_clean_safety(self) -> None:
        rows = [
            {
                "city": run.city,
                "false_verified_count": 0,
                "verified_source_support_failed_count": 0,
                "false_approval_count": 0,
                "m7_selected_rule_like_numeric_coverage": 1.0,
            }
            for run in M7_PRODUCT_RUNS
        ]
        status = m7_readiness_status(rows)
        self.assertTrue(status["ready"])
        rows[0]["false_verified_count"] = 1
        status = m7_readiness_status(rows)
        self.assertFalse(status["ready"])
        self.assertIn("m7_safety_gate_failed", status["reasons"])

    def test_not_used_summary_explains_outside_target_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "not_used.json").write_text(
                json.dumps(
                    [
                        {"rule_object": "height", "support_gaps": ["outside_target_section"]},
                        {"rule_object": "setback", "support_gaps": ["outside_target_section"]},
                    ]
                ),
                encoding="utf-8",
            )
            summary = not_used_summary(output_dir)
        self.assertEqual(summary["count"], 2)
        self.assertIn("outside", summary["plain_explanation"].lower())

    def test_overall_status_reports_unsafe_first(self) -> None:
        rows = [{"status_label": "pass"}, {"status_label": "unsafe / needs fix"}]
        self.assertEqual(overall_status_for_rows(rows), "unsafe_needs_fix")

    def test_render_markdown_lists_current_rows(self) -> None:
        md = render_markdown(
            {
                "safety_contract": "test contract",
                "overall_status": "m7_safety_ready",
                "current_false_verified_total": 0,
                "current_runs": [
                    {
                        "city": "burnaby_r1",
                        "status_label": "pass",
                        "verified_rule_count": 1,
                        "review_rule_count": 0,
                        "false_verified_count": 0,
                        "output_dir": "outputs/m7_runs/burnaby_r1/model",
                    }
                ],
                "interpretation": ["ok"],
            }
        )
        self.assertIn("# M7 Status Report", md)
        self.assertIn("burnaby_r1", md)

    def test_display_command_joins_parts(self) -> None:
        self.assertEqual(display_command(["python", "script.py"]), "python script.py")


class M7PlainSummaryTests(unittest.TestCase):
    def test_counter_type_is_supported_for_plain_explanation(self) -> None:
        from run_m7_status_report import not_used_plain_explanation

        self.assertIn("target", not_used_plain_explanation(Counter({"outside_target_section": 1})).lower())


if __name__ == "__main__":
    unittest.main()
