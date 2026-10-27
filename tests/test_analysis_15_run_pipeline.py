"""Tests for the Step 15 dependency-ordered pipeline runner."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.analysis_15_run_pipeline import STAGES, execute_pipeline


class PipelineRunnerTest(unittest.TestCase):
    def write_gate(self, path: Path, *, model: bool = True, annual: bool = True) -> None:
        path.write_text(
            "analysis_component,eligible\n"
            f"country_year_binomial_model,{str(model).lower()}\n"
            f"annual_paired_analysis,{str(annual).lower()}\n",
            encoding="utf-8",
        )

    def test_executes_dependency_order_and_records_skips(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            gate = target / "gate.csv"
            self.write_gate(gate, model=False, annual=False)
            called: list[str] = []
            passed, rows = execute_pipeline(status_path=target / "status.csv", gate_path=gate, runner=lambda module: (called.append(module) or 0, "ok"))
            self.assertTrue(passed)
            self.assertEqual([row["step"] for row in rows], [step for step, _ in STAGES])
            self.assertEqual([row["step"] for row in rows if row["status"] == "skipped"], ["07", "09"])
            self.assertIn("src.analysis_08_origin_composition", called)
            self.assertNotIn("src.analysis_07_binomial_regression", called)
            publication_modules = [
                module for step, module in STAGES if step.startswith("P")
            ]
            self.assertEqual(
                publication_modules,
                [
                    "scripts.generate_article_validation_outputs",
                    "scripts.generate_article_comparability_outputs",
                    "scripts.generate_article_analysis_outputs",
                    "scripts.generate_article_concordance_country_outputs",
                    "scripts.generate_article_model_outputs",
                    "scripts.generate_article_sensitivity_outputs",
                ],
            )
            self.assertLess(
                [step for step, _ in STAGES].index("P06"),
                [step for step, _ in STAGES].index("12"),
            )

    def test_stops_after_first_failed_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            gate = target / "gate.csv"
            self.write_gate(gate)
            def runner(module: str) -> tuple[int, str]:
                return (2, "controlled failure") if module == "src.analysis_04_matched_comparison" else (0, "ok")
            passed, rows = execute_pipeline(status_path=target / "status.csv", gate_path=gate, runner=runner)
            self.assertFalse(passed)
            self.assertEqual(rows[-1]["step"], "04")
            self.assertEqual(rows[-1]["status"], "failed")
            with (target / "status.csv").open(newline="", encoding="utf-8") as handle:
                written = list(csv.DictReader(handle))
            self.assertEqual(len(written), len(rows))


if __name__ == "__main__":
    unittest.main()
