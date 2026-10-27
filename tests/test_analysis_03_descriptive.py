"""Tests for Methods Section 3 descriptive comparison."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.analysis_03_descriptive import run
from src.analysis_common import quantile_type7


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT = PROJECT_ROOT / "data/prepared/comparison/destination_country_2022-2025.csv"
CHECKS = PROJECT_ROOT / "data/results/validation/data_validation_checks.csv"


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class DescriptiveAnalysisTest(unittest.TestCase):
    def test_type7_quantiles(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0]
        self.assertEqual(quantile_type7(values, 0.0), 1.0)
        self.assertEqual(quantile_type7(values, 0.25), 1.75)
        self.assertEqual(quantile_type7(values, 0.50), 2.5)
        self.assertEqual(quantile_type7(values, 0.75), 3.25)
        self.assertEqual(quantile_type7(values, 1.0), 4.0)

    def test_descriptive_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            outputs = run(
                input_path=INPUT,
                validation_checks_path=CHECKS,
                output_dir=root / "descriptive",
                manifest_dir=root / "manifests",
            )
            summary = {row["destination_code"]: row for row in csv_rows(outputs["dataset_summary"])}
            distributions = csv_rows(outputs["distribution_statistics"])
            rate_points = csv_rows(outputs["approval_rate_ecdf"])
            volume_points = csv_rows(outputs["decision_volume_ecdf"])
            manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))

            self.assertEqual(len(summary), 2)
            self.assertEqual(int(summary["AU"]["represented_countries"]), 192)
            self.assertEqual(int(summary["NZ"]["represented_countries"]), 179)
            self.assertEqual(int(summary["AU"]["decision_total"]), 737424)
            self.assertEqual(int(summary["NZ"]["decision_total"]), 148746)
            self.assertAlmostEqual(
                float(summary["AU"]["aggregate_approval_rate"]),
                639078 / 737424,
                places=15,
            )
            self.assertEqual(len(distributions), 4)
            self.assertEqual(len(rate_points), 371)
            self.assertEqual(len(volume_points), 371)
            self.assertEqual(rate_points[-1]["destination_code"], "NZ")
            self.assertEqual(float(rate_points[-1]["ecdf"]), 1.0)
            self.assertEqual(manifest["status"], "passed")


if __name__ == "__main__":
    unittest.main()
