"""Tests for the Step 13 minimum-output validator."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.analysis_13_validate_outputs import run


ROOT = Path(__file__).resolve().parents[1]


class OutputValidationTest(unittest.TestCase):
    def test_validates_required_inventory_and_documented_skip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outputs = run(
                step12_manifest=ROOT / "data/results/manifests/12_reproducibility.json",
                artifact_manifest=ROOT / "data/results/manifests/artifact_manifest.csv",
                output_dir=Path(temporary),
            )
            with outputs["checklist"].open(newline="", encoding="utf-8") as handle:
                checks = list(csv.DictReader(handle))
            self.assertEqual(len(checks), 17)
            self.assertEqual(sum(row["status"] == "passed" for row in checks), 16)
            self.assertEqual(sum(row["status"] == "skipped" for row in checks), 1)
            with outputs["result_registry"].open(newline="", encoding="utf-8") as handle:
                registry = list(csv.DictReader(handle))
            self.assertEqual(len(registry), 9)
            self.assertTrue(all(row["interpretation_scope"].endswith("not causal") for row in registry))


if __name__ == "__main__":
    unittest.main()
