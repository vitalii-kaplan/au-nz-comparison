"""Tests for Methods Section 4 matched-country comparison."""

from __future__ import annotations

import csv
import math
import tempfile
import unittest
from pathlib import Path

from src.analysis_04_matched_comparison import (
    run,
    student_t_cdf,
    student_t_ppf,
    wilcoxon_signed_rank,
)
from src.analysis_common import sha256


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT_ROOT / "src/analysis_config.json"
INPUT = PROJECT_ROOT / "data/prepared/comparison/matched_country_2022-2025.csv"
CHECKS = PROJECT_ROOT / "data/results/validation/data_validation_checks.csv"


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class MatchedComparisonTest(unittest.TestCase):
    def test_distribution_and_rank_helpers(self) -> None:
        self.assertEqual(student_t_cdf(0.0, 10), 0.5)
        self.assertAlmostEqual(student_t_ppf(0.975, 10), 2.228138852, places=8)
        self.assertAlmostEqual(student_t_cdf(-2.228138852, 10), 0.025, places=8)
        result = wilcoxon_signed_rank([-1.0, 2.0, 3.0, 0.0])
        self.assertEqual(result["n"], 3)
        self.assertEqual(result["n_zero"], 1)
        self.assertEqual(result["negative_rank_sum"], 1.0)
        self.assertEqual(result["positive_rank_sum"], 5.0)
        self.assertEqual(result["statistic"], 1.0)

    def test_matched_comparison_artifacts_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = run(
                config_path=CONFIG,
                input_path=INPUT,
                validation_checks_path=CHECKS,
                output_dir=root / "paired-first",
                manifest_dir=root / "manifests-first",
            )
            second = run(
                config_path=CONFIG,
                input_path=INPUT,
                validation_checks_path=CHECKS,
                output_dir=root / "paired-second",
                manifest_dir=root / "manifests-second",
            )
            differences = csv_rows(first["matched_differences"])
            summary = csv_rows(first["difference_summary"])[0]
            tests = csv_rows(first["test_results"])
            bootstrap = csv_rows(first["bootstrap_distribution"])

            self.assertEqual(len(differences), 173)
            self.assertEqual(int(summary["n_pairs"]), 173)
            self.assertEqual(
                int(summary["n_positive"])
                + int(summary["n_negative"])
                + int(summary["n_zero"]),
                173,
            )
            self.assertEqual(len(tests), 2)
            self.assertEqual(tests[0]["test_name"], "Wilcoxon signed-rank")
            self.assertEqual(tests[0]["role"], "primary")
            self.assertEqual(tests[1]["role"], "sensitivity")
            self.assertTrue(
                math.isclose(
                    float(tests[1]["p_value"]),
                    6.411439610056284e-16,
                    rel_tol=1e-12,
                )
            )
            self.assertEqual(len(bootstrap), 10000)
            for key in (
                "matched_differences",
                "difference_summary",
                "test_results",
                "bootstrap_distribution",
            ):
                self.assertEqual(sha256(first[key]), sha256(second[key]))


if __name__ == "__main__":
    unittest.main()
