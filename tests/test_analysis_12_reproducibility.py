"""Tests for the Step 12 reproducibility consolidator."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.analysis_12_reproducibility import run


ROOT = Path(__file__).resolve().parents[1]


class ReproducibilityTest(unittest.TestCase):
    def test_registers_verified_results_and_publication_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            for source in (ROOT / "data/results/manifests").glob("*.json"):
                if source.name[:2].isdigit() and int(source.name[:2]) <= 11:
                    (target / source.name).write_bytes(source.read_bytes())
            outputs = run(
                manifest_dir=target,
                table_dir=ROOT / "article/tables",
                figure_dir=ROOT / "article/figures",
            )
            with outputs["artifact_manifest"].open(newline="", encoding="utf-8") as handle:
                artifacts = list(csv.DictReader(handle))
            self.assertGreaterEqual(len(artifacts), 64)
            self.assertTrue(all(row["status"] == "verified" for row in artifacts))
            self.assertEqual(
                sum(row["artifact_type"].startswith("publication_") for row in artifacts),
                14,
            )
            self.assertIn("data/results/models/binomial_model_coefficients.csv", {row["path"] for row in artifacts})
            self.assertIn("article/tables/comparability_coverage.tex", {row["path"] for row in artifacts})
            self.assertEqual(outputs["reproducibility_issues"].read_text(encoding="utf-8").count("\n"), 1)
            self.assertIn("Rscript", outputs["software_versions"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
