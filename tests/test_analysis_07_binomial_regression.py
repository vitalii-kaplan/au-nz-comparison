"""Tests for Methods Section 7 binomial regression."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.analysis_07_binomial_regression import read_gate, run

ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class BinomialRegressionTest(unittest.TestCase):
    def test_gate_and_fitted_outputs(self) -> None:
        gates = read_gate(ROOT / "data/results/validation/comparability_decisions.csv")
        self.assertTrue(gates["country_year_binomial_model"])
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            outputs = run(
                config_path=ROOT / "src/analysis_config.json",
                pooled_input_path=ROOT / "data/prepared/comparison/matched_country_2022-2025.csv",
                annual_input_path=ROOT / "data/prepared/comparison/matched_country_year.csv",
                validation_checks_path=ROOT / "data/results/validation/data_validation_checks.csv",
                comparability_path=ROOT / "data/results/validation/comparability_decisions.csv",
                output_dir=target / "models", manifest_dir=target / "manifests",
            )
            coefficients = rows(outputs["coefficients"])
            destination = {row["model"]: row for row in coefficients if row["term"] == "destinationAU"}
            self.assertEqual(set(destination), {"pooled_country_fixed_effects", "country_year_fixed_effects"})
            self.assertGreater(float(destination["pooled_country_fixed_effects"]["estimate"]), 0)
            self.assertGreater(float(destination["country_year_fixed_effects"]["estimate"]), 0)
            self.assertTrue(all("cluster-robust" in row["covariance_method"] for row in destination.values()))
            contrasts = rows(outputs["contrasts"])
            self.assertEqual(len(contrasts), 2)
            self.assertTrue(all(float(row["au_minus_nz_probability_contrast"]) > 0 for row in contrasts))
            diagnostics = rows(outputs["diagnostics"])
            self.assertTrue(all(row["value"] == "true" for row in diagnostics if row["diagnostic"] == "converged"))
            self.assertTrue(all(row["value"].startswith("passed") for row in diagnostics if row["diagnostic"] == "separation_check"))


if __name__ == "__main__":
    unittest.main()
