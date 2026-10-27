"""Tests for Methods Section 5 concordance analysis."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.analysis_05_concordance import average_ranks, pearson_correlation, run
from src.analysis_common import sha256

ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle: return list(csv.DictReader(handle))


class ConcordanceTest(unittest.TestCase):
    def test_rank_and_correlation_helpers(self) -> None:
        self.assertEqual(average_ranks([3, 1, 1, 2]), [4.0, 1.5, 1.5, 3.0])
        self.assertAlmostEqual(pearson_correlation([1, 2, 3], [2, 4, 6]), 1.0)
        self.assertAlmostEqual(pearson_correlation([1, 2, 3], [6, 4, 2]), -1.0)

    def test_outputs_are_complete_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            kwargs = {"config_path": ROOT / "src/analysis_config.json", "input_path": ROOT / "data/prepared/comparison/matched_country_2022-2025.csv", "validation_checks_path": ROOT / "data/results/validation/data_validation_checks.csv"}
            first = run(**kwargs, output_dir=base / "first", manifest_dir=base / "mf")
            second = run(**kwargs, output_dir=base / "second", manifest_dir=base / "ms")
            results = rows(first["concordance"])
            self.assertEqual([row["method"] for row in results], ["Pearson", "Spearman"])
            self.assertEqual({int(row["n"]) for row in results}, {173})
            self.assertEqual(len(rows(first["scatter_points"])), 173)
            for key in ("concordance", "scatter_points", "diagnostics"):
                self.assertEqual(sha256(first[key]), sha256(second[key]))


if __name__ == "__main__": unittest.main()
