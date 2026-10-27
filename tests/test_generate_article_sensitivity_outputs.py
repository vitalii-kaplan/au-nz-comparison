"""Tests for the article's denominator-sensitivity publication outputs."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.generate_article_sensitivity_outputs import generate_outputs


class ArticleSensitivityOutputsTest(unittest.TestCase):
    def test_outputs_use_verified_threshold_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = generate_outputs(
                table_dir=root / "tables", figure_dir=root / "figures"
            )
            self.assertEqual(set(outputs), {"table", "figure"})
            table = outputs["table"].read_text(encoding="utf-8")
            figure = outputs["figure"].read_text(encoding="utf-8")
            self.assertIn("Threshold 0 includes every pooled matched origin", table)
            self.assertEqual(table.count(r"\begin{table}"), 2)
            self.assertIn(r"\label{tab:sensitivity-paired}", table)
            self.assertIn(r"\label{tab:sensitivity-concordance}", table)
            self.assertIn("100 & 54", table)
            self.assertIn("16.3 (12.7, 19.9)", table)
            self.assertIn("0.629 (0.529, 0.711)", table)
            self.assertNotIn("year fixed effects", table)
            self.assertNotIn("country-year", table)
            self.assertEqual(figure.count(r"xtick={0,20,50,100}"), 2)


if __name__ == "__main__":
    unittest.main()
