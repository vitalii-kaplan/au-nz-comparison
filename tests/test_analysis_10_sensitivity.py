"""Tests for Methods Section 10 sensitivity analysis."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.analysis_10_sensitivity import bootstrap_interval, run


ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class SensitivityAnalysisTest(unittest.TestCase):
    def test_seeded_bootstrap_is_reproducible(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0]
        first = bootstrap_interval(values, None, statistic="median", replicates=200,
                                   seed=19, confidence=0.95)
        second = bootstrap_interval(values, None, statistic="median", replicates=200,
                                    seed=19, confidence=0.95)
        self.assertEqual(first, second)
        self.assertEqual(first[2], 200)

    def test_pre_specified_sensitivity_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            outputs = run(
                config_path=ROOT / "src/analysis_config.json",
                matched_path=ROOT / "data/prepared/comparison/matched_country_2022-2025.csv",
                validation_checks_path=ROOT / "data/results/validation/data_validation_checks.csv",
                comparability_path=ROOT / "data/results/validation/comparability_decisions.csv",
                model_contrasts_path=ROOT / "data/results/models/destination_probability_contrasts.csv",
                model_fit_path=ROOT / "data/results/models/model_fit_statistics.csv",
                temporal_summary_path=ROOT / "data/results/temporal/annual_matched_difference_summary.csv",
                output_dir=target / "robustness", manifest_dir=target / "manifests",
            )
            sensitivity = rows(outputs["sensitivity_analysis_summary"])
            counts = rows(outputs["threshold_population_counts"])
            models = rows(outputs["model_sensitivity_comparison"])
            stability = rows(outputs["result_stability_flags"])
            self.assertEqual(len(sensitivity), 16)
            self.assertEqual({int(row["threshold_min_decisions_each"]) for row in sensitivity}, {0, 20, 50, 100})
            self.assertEqual({row["method"] for row in sensitivity}, {
                "Paired t-test", "Wilcoxon signed-rank", "Pearson correlation", "Spearman correlation",
            })
            self.assertEqual([int(row["included_pairs"]) for row in counts], sorted(
                [int(row["included_pairs"]) for row in counts], reverse=True))
            threshold_100 = next(row for row in counts if row["threshold_min_decisions_each"] == "100")
            self.assertEqual(int(threshold_100["included_pairs"]), 54)
            self.assertEqual(int(threshold_100["included_au_decisions"]), 729184)
            self.assertEqual(int(threshold_100["included_nz_decisions"]), 145192)
            self.assertEqual(len(models), 2)
            self.assertTrue(all(float(row["effect_estimate"]) > 0 for row in models))
            self.assertEqual(len(stability), 5)
            self.assertTrue(all(row["direction_stable"] == "true" for row in stability))
            baseline_spearman = next(row for row in sensitivity if row["method"] == "Spearman correlation" and row["threshold_min_decisions_each"] == "0")
            concordance = next(row for row in rows(ROOT / "data/results/concordance/approval_rate_concordance.csv") if row["method"] == "Spearman")
            self.assertEqual(baseline_spearman["effect_estimate"], concordance["coefficient"])
            self.assertEqual(baseline_spearman["ci_lower"], concordance["ci_lower"])
            self.assertEqual(baseline_spearman["ci_upper"], concordance["ci_upper"])


if __name__ == "__main__":
    unittest.main()
