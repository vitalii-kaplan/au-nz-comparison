"""Tests for the Methods Section 11 comparability gate."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.analysis_11_comparability import run

ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class ComparabilityTest(unittest.TestCase):
    def test_gate_distinguishes_pairing_from_zero_filling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            outputs = run(
                config_path=ROOT / "src/analysis_config.json",
                coverage_path=ROOT / "data/results/validation/country_coverage.csv",
                issues_path=ROOT / "data/results/validation/data_issues_and_exclusions.csv",
                validation_checks_path=ROOT / "data/results/validation/data_validation_checks.csv",
                output_dir=target / "validation", manifest_dir=target / "manifests",
            )
            decisions = {row["analysis_component"]: row for row in rows(outputs["decisions"])}
            self.assertEqual(decisions["country_year_binomial_model"]["eligible"], "true")
            self.assertEqual(decisions["zero_filled_composition_distance"]["eligible"], "false")
            pairs = rows(outputs["pairs"])
            self.assertEqual(sum(row["scope"] == "pooled" and row["included"] == "1" for row in pairs), 173)
            self.assertEqual(sum(row["scope"] == "annual" and row["included"] == "1" for row in pairs), 564)
            classifications = rows(outputs["classification"])
            self.assertTrue(any(row["classification"] == "absent_country" for row in classifications))
            self.assertTrue(all(row["zero_assignment_allowed"] == "false" for row in classifications))
            pair_summary = rows(outputs["pair_summary"])
            self.assertEqual(len(pair_summary), 5)
            pooled = next(row for row in pair_summary if row["scope"] == "pooled")
            self.assertEqual(int(pooled["union_origins"]), 198)
            self.assertEqual(int(pooled["matched_origins"]), 173)
            self.assertEqual(int(pooled["au_only_origins"]), 19)
            self.assertEqual(int(pooled["nz_only_origins"]), 6)
            self.assertAlmostEqual(float(pooled["matched_share"]), 173 / 198)
            classification_summary = rows(outputs["classification_summary"])
            self.assertTrue(any(row["classification"] == "reviewed_non_m49_label" for row in classification_summary))
            self.assertEqual(
                sum(int(row["record_count"]) for row in classification_summary),
                len(classifications),
            )


if __name__ == "__main__":
    unittest.main()
