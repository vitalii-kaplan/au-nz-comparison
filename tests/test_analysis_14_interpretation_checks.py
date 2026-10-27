"""Tests for the Step 14 interpretation-boundary audit."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.analysis_14_interpretation_checks import run


ROOT = Path(__file__).resolve().parents[1]


class InterpretationBoundaryTest(unittest.TestCase):
    def arguments(self, target: Path, text_files: list[Path] | None = None) -> dict[str, object]:
        return {"contract_path": ROOT / "data/results/validation/analysis_contract.csv", "registry_path": ROOT / "data/results/manifests/result_table_registry.csv", "step13_manifest": ROOT / "data/results/manifests/13_validate_outputs.json", "manifest_dir": ROOT / "data/results/manifests", "output_path": target / "checks.csv", "text_files": text_files or []}

    def test_all_registered_results_have_reporting_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            outputs = run(**self.arguments(target))
            with outputs["checks"].open(newline="", encoding="utf-8") as handle:
                checks = list(csv.DictReader(handle))
            self.assertGreaterEqual(len(checks), 60)
            self.assertTrue(all(row["status"] == "passed" for row in checks))

    def test_rejects_unsupported_machine_generated_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            text = target / "summary.txt"
            text.write_text("These results prove that Australia is fairer.", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "interpretation-boundary"):
                run(**self.arguments(target, [text]))


if __name__ == "__main__":
    unittest.main()
