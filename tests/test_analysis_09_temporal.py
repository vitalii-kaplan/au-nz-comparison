"""Tests for Methods Section 9 temporal comparison."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.analysis_09_temporal import distribution_summary, run
from src.analysis_common import sha256


ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class TemporalAnalysisTest(unittest.TestCase):
    def test_distribution_summary_uses_type_7_quartiles(self) -> None:
        result = distribution_summary([1.0, 2.0, 3.0, 4.0])
        self.assertEqual(result["n"], 4)
        self.assertEqual(result["median"], 2.5)
        self.assertEqual(result["q1"], 1.75)
        self.assertEqual(result["q3"], 3.25)
        self.assertEqual(result["iqr"], 1.5)

    def test_temporal_outputs_are_complete_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            arguments = dict(
                config_path=ROOT / "src/analysis_config.json",
                destination_year_path=ROOT / "data/prepared/comparison/destination_country_year.csv",
                matched_year_path=ROOT / "data/prepared/comparison/matched_country_year.csv",
                validation_checks_path=ROOT / "data/results/validation/data_validation_checks.csv",
                comparability_path=ROOT / "data/results/validation/comparability_decisions.csv",
            )
            first = run(**arguments, output_dir=target / "first", manifest_dir=target / "manifests-first")
            second = run(**arguments, output_dir=target / "second", manifest_dir=target / "manifests-second")
            annual = rows(first["annual_destination_summary"])
            matched = rows(first["annual_matched_difference_summary"])
            differences = rows(first["matched_country_year_differences"])
            distributions = rows(first["annual_distribution_statistics"])
            self.assertEqual(len(annual), 8)
            self.assertEqual(len(matched), 4)
            self.assertEqual(len(differences), 564)
            self.assertEqual(len(distributions), 16)
            self.assertEqual({int(row["year"]) for row in annual}, {2022, 2023, 2024, 2025})
            self.assertTrue(all(int(row["n_pairs"]) > 130 for row in matched))
            self.assertTrue(all(float(row["mean_ci_lower"]) < float(row["mean_ci_upper"]) for row in matched))
            for key in ("annual_destination_summary", "annual_matched_difference_summary",
                        "matched_country_year_differences", "annual_distribution_statistics"):
                self.assertEqual(sha256(first[key]), sha256(second[key]))


if __name__ == "__main__":
    unittest.main()
