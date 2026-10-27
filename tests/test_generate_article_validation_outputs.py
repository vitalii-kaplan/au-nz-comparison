"""Tests for generated article validation table and coverage chart."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.generate_article_validation_outputs import collect_summary, generate_outputs


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_DIR = PROJECT_ROOT / "data/results/validation"


class ArticleValidationOutputsTest(unittest.TestCase):
    def test_verified_summary_values_and_generated_outputs(self) -> None:
        registry = VALIDATION_DIR / "input_registry.csv"
        coverage = VALIDATION_DIR / "country_coverage.csv"
        checks = VALIDATION_DIR / "data_validation_checks.csv"

        summary = collect_summary(registry, coverage, checks)
        self.assertEqual(summary["validation_checks"], 38)
        self.assertEqual(summary["destinations"]["AU"]["decision_total"], 737424)
        self.assertEqual(summary["destinations"]["NZ"]["decision_total"], 148746)
        self.assertEqual(
            summary["pooled_coverage"],
            {"both": 173, "australia_only": 19, "new_zealand_only": 6},
        )
        self.assertEqual(
            summary["annual_matched"],
            {2022: 139, 2023: 142, 2024: 139, 2025: 144},
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            outputs = generate_outputs(
                registry_path=registry,
                coverage_path=coverage,
                checks_path=checks,
                table_output=root / "table.tex",
                figure_output=root / "figure.tex",
            )
            table = outputs["table"].read_text(encoding="utf-8")
            figure = outputs["figure"].read_text(encoding="utf-8")
            self.assertIn("737,424", table)
            self.assertIn("Represented in both destinations & 173", table)
            self.assertIn("(AU,737424) (NZ,148746)", figure)
            self.assertIn("(2022,139) (2023,142) (2024,139) (2025,144)", figure)

    def test_failed_blocking_check_prevents_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            checks_path = root / "checks.csv"
            with checks_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["status", "blocking"],
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerow({"status": "failed", "blocking": "true"})

            with self.assertRaisesRegex(ValueError, "blocking validation checks failed"):
                collect_summary(
                    VALIDATION_DIR / "input_registry.csv",
                    VALIDATION_DIR / "country_coverage.csv",
                    checks_path,
                )


if __name__ == "__main__":
    unittest.main()
