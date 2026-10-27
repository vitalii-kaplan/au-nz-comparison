"""Tests for Methods Section 1 analysis-contract implementation."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.analysis_01_define_contract import run


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT_ROOT / "src/analysis_config.json"
SCHEMA = PROJECT_ROOT / "data/schema.json"


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class AnalysisContractTest(unittest.TestCase):
    def test_contract_and_input_registry_are_generated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            outputs = run(
                config_path=CONFIG,
                schema_path=SCHEMA,
                validation_dir=root / "validation",
                manifest_dir=root / "manifests",
            )

            contract = csv_rows(outputs["contract"])
            registry = csv_rows(outputs["input_registry"])
            manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))

            self.assertEqual(len(contract), 11)
            difference = next(
                row
                for row in contract
                if row["contract_item"] == "matched_rate_difference"
            )
            self.assertEqual(difference["direction"], "AU - NZ")
            self.assertIn("percentage points", difference["unit"])

            by_destination = {row["destination_code"]: row for row in registry}
            self.assertEqual(set(by_destination), {"AU", "NZ"})
            self.assertEqual(int(by_destination["AU"]["row_count"]), 192)
            self.assertEqual(int(by_destination["NZ"]["row_count"]), 179)
            self.assertEqual(int(by_destination["AU"]["decision_total"]), 737424)
            self.assertEqual(int(by_destination["NZ"]["decision_total"]), 148746)
            self.assertEqual(manifest["status"], "passed")
            self.assertTrue(
                manifest["validation"]["pooled_inputs_pass_table_validation"]
            )

    def test_wrong_difference_direction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config = json.loads(CONFIG.read_text(encoding="utf-8"))
            config["rate_difference_direction"] = "NZ - AU"
            invalid_config = root / "invalid-config.json"
            invalid_config.write_text(json.dumps(config), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "AU - NZ"):
                run(
                    config_path=invalid_config,
                    schema_path=SCHEMA,
                    validation_dir=root / "validation",
                    manifest_dir=root / "manifests",
                )


if __name__ == "__main__":
    unittest.main()
