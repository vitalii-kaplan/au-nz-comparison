"""Tests for publication outputs based on Methods Sections 3 and 4."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.generate_article_analysis_outputs import collect_inputs, generate_outputs


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ArticleAnalysisOutputsTest(unittest.TestCase):
    def test_generated_tables_and_figures_use_verified_results(self) -> None:
        data = collect_inputs(
            PROJECT_ROOT / "data/results/descriptive",
            PROJECT_ROOT / "data/results/paired",
            PROJECT_ROOT / "data/results/manifests",
        )
        self.assertEqual(len(data["approval_ecdf"]), 371)
        self.assertEqual(len(data["differences"]), 173)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            outputs = generate_outputs(
                table_dir=root / "tables",
                figure_dir=root / "figures",
            )
            descriptive_table = outputs["descriptive_table"].read_text(encoding="utf-8")
            paired_table = outputs["paired_table"].read_text(encoding="utf-8")
            descriptive_figure = outputs["descriptive_figure"].read_text(encoding="utf-8")
            decision_bin_figure = outputs["decision_bin_figure"].read_text(encoding="utf-8")
            paired_figure = outputs["paired_figure"].read_text(encoding="utf-8")

            self.assertIn("86.7", descriptive_table)
            self.assertIn("81.3", descriptive_table)
            self.assertIn("Standard deviation", descriptive_table)
            self.assertIn("22,142.8", descriptive_table)
            self.assertIn("Interquartile range", descriptive_table)
            self.assertIn("\\begin{tabular}{l|rrr}", descriptive_table)
            self.assertIn("\\begin{tabular}{l|rr|rr}", descriptive_table)
            self.assertIn("16.32", paired_table)
            self.assertIn("9.44", paired_table)
            self.assertIn("16.32 (12.71, 19.93)", paired_table)
            self.assertIn("9.44 (4.33, 14.53)", paired_table)
            self.assertEqual(paired_table.count("; $p<0.001$"), 2)
            self.assertIn("const plot", descriptive_figure)
            self.assertIn("xlabel={ECDF}, ylabel={Country approval rate (\\%)}", descriptive_figure)
            self.assertIn("xmin=0, xmax=1, ymin=0, ymax=100", descriptive_figure)
            self.assertIn("xlabel={ECDF}, ylabel={Log10 recorded decisions}", descriptive_figure)
            self.assertIn("xmin=0, xmax=1, ymin=0, ymax=5.5", descriptive_figure)
            self.assertEqual(descriptive_figure.count("red!80!black, thick, const plot"), 2)
            self.assertNotIn("orange!85!black", descriptive_figure)
            self.assertNotIn("thick, dashed, const plot", descriptive_figure)
            self.assertEqual(
                descriptive_figure.count(
                    "legend style={font=\\scriptsize, at={(0.97,0.03)}, anchor=south east, draw=none}"
                ),
                1,
            )
            self.assertEqual(
                descriptive_figure.count(
                    "legend style={font=\\scriptsize, at={(0.03,0.97)}, anchor=north west, draw=none}"
                ),
                1,
            )
            self.assertEqual(
                decision_bin_figure.count("xlabel={Log10 of recorded decisions}"),
                2,
            )
            self.assertNotIn("Discrete", decision_bin_figure)
            self.assertIn(
                "coordinates {(0,55) (1,69) (2,40) (3,17) (4,9) (5,2)}",
                decision_bin_figure,
            )
            self.assertIn(
                "coordinates {(0,61) (1,57) (2,38) (3,21) (4,2) (5,0)}",
                decision_bin_figure,
            )
            self.assertEqual(
                decision_bin_figure.count("ylabel={Number of origin countries}"),
                2,
            )
            self.assertEqual(paired_figure.count("mark=*"), 1)
            self.assertIn("xmax=173", paired_figure)


if __name__ == "__main__":
    unittest.main()
