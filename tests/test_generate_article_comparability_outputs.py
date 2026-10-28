"""Tests for Step 11 publication output generation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.generate_article_comparability_outputs import generate_outputs


ROOT = Path(__file__).resolve().parents[1]


class ComparabilityPublicationTest(unittest.TestCase):
    def test_generates_table_from_verified_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            outputs = generate_outputs(
                validation_dir=ROOT / "data/results/validation",
                manifest_dir=ROOT / "data/results/manifests",
                table_dir=target / "tables",
            )
            self.assertEqual(set(outputs), {"coverage_table"})
            for path in outputs.values():
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 100)

            coverage = outputs["coverage_table"].read_text(encoding="utf-8")
            self.assertIn("Pooled & 198 & 173 & 25 & 19 & 6 & 87.4\\%", coverage)
            self.assertIn("2023 & 182 & 142 & 40 & 25 & 15 & 78.0\\%", coverage)
            self.assertEqual(coverage.count(r"\begin{table}"), 1)


if __name__ == "__main__":
    unittest.main()
