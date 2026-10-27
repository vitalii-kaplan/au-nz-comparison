"""Tests for publication outputs based on Methods Sections 5 and 6."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.generate_article_concordance_country_outputs import generate_outputs


class ArticleConcordanceCountryOutputsTest(unittest.TestCase):
    def test_outputs_use_verified_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = generate_outputs(table_dir=root / "tables", figure_dir=root / "figures")
            concordance = outputs["concordance_table"].read_text(encoding="utf-8")
            scatter = outputs["concordance_figure"].read_text(encoding="utf-8")
            country = outputs["country_table"].read_text(encoding="utf-8")
            forest = outputs["forest_figure"].read_text(encoding="utf-8")
            self.assertIn("0.629", concordance); self.assertIn("0.472", concordance)
            self.assertIn("(0.529, 0.711)", concordance)
            self.assertIn("axis equal image", scatter); self.assertNotIn("regression", scatter)
            self.assertIn("xlabel={New Zealand approval rate (\\%)}", scatter)
            self.assertIn("ylabel={Australian approval rate (\\%)}", scatter)
            self.assertIn("complete table contains all 173", country)
            self.assertIn("48.4 (38.8, 56.9)", country)
            self.assertEqual(forest.count("+= ("), 20)
            self.assertEqual(forest.count("-= ("), 20)
            self.assertIn("at least 50 decisions", country)


if __name__ == "__main__": unittest.main()
