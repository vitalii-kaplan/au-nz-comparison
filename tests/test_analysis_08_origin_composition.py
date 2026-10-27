"""Tests for Methods Section 8 applicant-origin composition."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.analysis_08_origin_composition import concentration, gini, run

ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class OriginCompositionTest(unittest.TestCase):
    def test_concentration_helpers(self) -> None:
        self.assertAlmostEqual(gini([0, 0, 1]), 2 / 3)
        result = concentration([0.5, 0.3, 0.2])
        self.assertAlmostEqual(result["hhi_0_1"], 0.38)
        self.assertAlmostEqual(result["top_1_share"], 0.5)
        self.assertAlmostEqual(result["top_5_share"], 1.0)
        with self.assertRaises(ValueError):
            concentration([0.2, 0.2])

    def test_outputs_and_jsd_skip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            outputs = run(
                config_path=ROOT / "src/analysis_config.json",
                long_input_path=ROOT / "data/prepared/comparison/destination_country_2022-2025.csv",
                matched_input_path=ROOT / "data/prepared/comparison/matched_country_2022-2025.csv",
                validation_checks_path=ROOT / "data/results/validation/data_validation_checks.csv",
                comparability_path=ROOT / "data/results/validation/comparability_decisions.csv",
                output_dir=target / "composition", manifest_dir=target / "manifests",
            )
            shares = rows(outputs["shares"])
            self.assertEqual(len(shares), 371)
            for code in ("AU", "NZ"):
                self.assertAlmostEqual(sum(float(row["decision_share"]) for row in shares if row["destination_code"] == code), 1.0)
            statistics = rows(outputs["concentration"])
            self.assertEqual(len(statistics), 2)
            self.assertTrue(all(0 <= float(row["hhi_0_1"]) <= 1 for row in statistics))
            self.assertEqual(len(rows(outputs["scatter"])), 173)
            distance = rows(outputs["distance"])[0]
            self.assertEqual(distance["eligible"], "false")
            self.assertEqual(distance["value"], "")


if __name__ == "__main__":
    unittest.main()
