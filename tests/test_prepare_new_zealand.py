"""Integration tests for the New Zealand data-preparation script."""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts/prepare_new_zealand.py"
INPUT_DIR = PROJECT_ROOT / "data/original/new-zealand"
SCHEMA = PROJECT_ROOT / "data/schema.json"
REFERENCE = (
    PROJECT_ROOT / "tests/data/inz_student_visa_decisions_2022-2025.csv"
)
RETAINED_COLUMNS = [
    "Country",
    "Number approved",
    "Number declined",
    "Total applications",
    "Approval rate",
]
INTEGER_COLUMNS = [
    "Number approved",
    "Number declined",
    "Total applications",
]


def read_rows(path: Path, *, reference: bool = False) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        expected_columns = RETAINED_COLUMNS + (["Applications_log10"] if reference else [])
        assert reader.fieldnames == expected_columns
        rows: list[dict[str, object]] = []
        for row in reader:
            typed: dict[str, object] = {"Country": row["Country"]}
            for column in INTEGER_COLUMNS:
                typed[column] = int(row[column])
            typed["Approval rate"] = float(row["Approval rate"])
            rows.append(typed)
    return rows


def _assert_prepared_nz_matches_previous_article(tmp_path: Path) -> None:
    """The rebuilt five-column table must equal the previous article dataset."""

    output_dir = tmp_path / "prepared"
    combined_output = output_dir / "inz_student_visa_decisions_2022-2025.csv"
    report_path = tmp_path / "new-zealand-reference-comparison.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input-dir",
            str(INPUT_DIR),
            "--schema",
            str(SCHEMA),
            "--output-dir",
            str(output_dir),
            "--output",
            str(combined_output),
            "--reference",
            str(REFERENCE),
            "--report",
            str(report_path),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    actual = read_rows(combined_output)
    expected = read_rows(REFERENCE, reference=True)
    assert len(actual) == len(expected)
    assert [row["Country"] for row in actual] == [
        row["Country"] for row in expected
    ]

    for actual_row, expected_row in zip(actual, expected, strict=True):
        assert actual_row["Country"] == expected_row["Country"]
        for column in INTEGER_COLUMNS:
            assert actual_row[column] == expected_row[column]
        assert math.isclose(
            float(actual_row["Approval rate"]),
            float(expected_row["Approval rate"]),
            rel_tol=0.0,
            abs_tol=1e-15,
        )

    for year in (2022, 2023, 2024, 2025):
        assert (output_dir / f"student_visa_decisions_{year}.csv").is_file()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["output_validation"][
        "combined_counts_equal_sum_of_annual_tables"
    ]
    assert report["reference_comparison"]["semantic_equal"]
    assert report["reference_comparison"]["difference_count"] == 0
    assert report["reference_comparison"]["reference_rows"] == len(expected)
    assert report["reference_comparison"]["prepared_rows"] == len(actual)


class PrepareNewZealandRegressionTest(unittest.TestCase):
    """Regression coverage for the New Zealand preparation entry point."""

    def test_combined_table_matches_previous_article(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            _assert_prepared_nz_matches_previous_article(Path(temporary_directory))


if __name__ == "__main__":
    unittest.main()
