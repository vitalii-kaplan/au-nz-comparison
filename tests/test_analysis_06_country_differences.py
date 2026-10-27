"""Tests for Methods Section 6 country-specific comparisons."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.analysis_06_country_differences import benjamini_hochberg, fisher_exact_two_sided, newcombe_difference_interval, run

ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle: return list(csv.DictReader(handle))


class CountryDifferenceTest(unittest.TestCase):
    def test_statistical_helpers(self) -> None:
        self.assertAlmostEqual(fisher_exact_two_sided(1, 9, 11, 3), 0.0027594561852201, places=13)
        self.assertEqual(benjamini_hochberg([0.01, 0.04, 0.03, 0.002]), [0.02, 0.04, 0.04, 0.008])
        lower, upper = newcombe_difference_interval(8, 10, 5, 10, 1.959963984540054)
        self.assertLess(lower, 0.3); self.assertGreater(upper, 0.3)

    def test_outputs_cover_full_test_family(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = run(config_path=ROOT / "src/analysis_config.json", input_path=ROOT / "data/prepared/comparison/matched_country_2022-2025.csv", validation_checks_path=ROOT / "data/results/validation/data_validation_checks.csv", output_dir=Path(temporary) / "results", manifest_dir=Path(temporary) / "manifests")
            effects, forest = rows(output["effects"]), rows(output["forest_selection"])
            self.assertEqual(len(effects), 173); self.assertEqual(len(forest), 173)
            self.assertEqual(sum(int(row["displayed"]) for row in forest), 20)
            self.assertTrue(all(0 <= float(row["p_value"]) <= 1 for row in effects))
            self.assertTrue(all(0 <= float(row["bh_q_value"]) <= 1 for row in effects))
            ordered = sorted(effects, key=lambda row: float(row["p_value"]))
            self.assertEqual([float(row["bh_q_value"]) for row in ordered], sorted(float(row["bh_q_value"]) for row in ordered))
            self.assertTrue(any(row["selected_test"].startswith("Fisher") for row in effects))
            self.assertTrue(any(row["selected_test"].startswith("Pearson") for row in effects))


if __name__ == "__main__": unittest.main()
