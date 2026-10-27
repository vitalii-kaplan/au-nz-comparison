"""Tests for Methods Section 2 validation and comparison-table construction."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.analysis_01_define_contract import run as run_contract
from src.analysis_02_build_tables import run as run_tables
from src.analysis_common import read_prepared_table


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT_ROOT / "src/analysis_config.json"
SCHEMA = PROJECT_ROOT / "data/schema.json"
M49 = PROJECT_ROOT / "data/original/reference/un-m49.csv"
HARMONIZATION = PROJECT_ROOT / "data/support/country-name-harmonization.json"


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class AnalysisTableTest(unittest.TestCase):
    def test_comparison_and_validation_artifacts_are_generated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            validation_dir = root / "validation"
            manifest_dir = root / "manifests"
            contract_outputs = run_contract(
                config_path=CONFIG,
                schema_path=SCHEMA,
                validation_dir=validation_dir,
                manifest_dir=manifest_dir,
            )
            outputs = run_tables(
                config_path=CONFIG,
                contract_path=contract_outputs["contract"],
                registry_path=contract_outputs["input_registry"],
                m49_path=M49,
                harmonization_report_path=HARMONIZATION,
                comparison_dir=root / "comparison",
                validation_dir=validation_dir,
                manifest_dir=manifest_dir,
            )

            pooled = csv_rows(outputs["destination_country"])
            matched = csv_rows(outputs["matched_country"])
            country_year = csv_rows(outputs["destination_country_year"])
            matched_year = csv_rows(outputs["matched_country_year"])
            checks = csv_rows(outputs["validation_checks"])
            issues = csv_rows(outputs["issues_and_exclusions"])
            manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))

            self.assertEqual(len(pooled), 371)
            self.assertEqual(len(matched), 173)
            self.assertEqual(len(country_year), 1276)
            self.assertEqual(len(matched_year), 564)
            self.assertTrue(all(row["status"] == "passed" for row in checks))
            self.assertEqual(len(issues), 30)
            self.assertEqual(
                sum(row["record_type"] == "source_label_exclusion" for row in issues),
                5,
            )
            self.assertEqual(
                sum(row["record_type"] == "paired_analysis_exclusion" for row in issues),
                25,
            )

            afghanistan = next(row for row in matched if row["country"] == "Afghanistan")
            expected_difference = float(afghanistan["au_approval_rate"]) - float(
                afghanistan["nz_approval_rate"]
            )
            self.assertAlmostEqual(
                float(afghanistan["rate_difference_au_minus_nz"]),
                expected_difference,
                places=15,
            )
            self.assertEqual(
                manifest["summary"]["matched_countries_by_year"],
                {"2022": 139, "2023": 142, "2024": 139, "2025": 144},
            )
            self.assertEqual(manifest["summary"]["blocking_validation_failures"], 0)

    def test_invalid_prepared_counts_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            invalid = Path(temporary_directory) / "invalid.csv"
            invalid.write_text(
                '"Country","Number approved","Number declined",'
                '"Total applications","Approval rate"\n'
                '"Example",4,3,8,0.5\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "counts do not reconcile"):
                read_prepared_table(invalid)


if __name__ == "__main__":
    unittest.main()
