"""Tests for the article's pooled-model publication outputs."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.generate_article_model_outputs import generate_outputs


class ArticleModelOutputsTest(unittest.TestCase):
    def test_outputs_use_verified_pooled_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = generate_outputs(
                table_dir=root / "tables", figure_dir=root / "figures"
            )
            self.assertEqual(set(outputs), {"table", "figure"})
            table = outputs["table"].read_text(encoding="utf-8")
            figure = outputs["figure"].read_text(encoding="utf-8")
            self.assertIn("885,588", table)
            self.assertIn("2.57 (1.77, 3.72)", table)
            self.assertIn("85.3 (83.8, 86.8)", table)
            self.assertIn("74.4 (71.6, 77.2)", table)
            self.assertIn("10.9 (6.6, 15.2)", table)
            self.assertEqual(figure.count(r"\begin{axis}"), 2)
            self.assertIn("Destination probabilities", figure)
            self.assertIn("Probability contrast", figure)


if __name__ == "__main__":
    unittest.main()
