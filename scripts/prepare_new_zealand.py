#!/usr/bin/env python3
"""Build and verify annual and combined New Zealand decision tables."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data/original/new-zealand"
DEFAULT_SCHEMA = PROJECT_ROOT / "data/schema.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data/prepared/new-zealand"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "data/prepared/new-zealand/inz_student_visa_decisions_2022-2025.csv"
)
DEFAULT_REFERENCE = (
    PROJECT_ROOT
    / "tests/data/inz_student_visa_decisions_2022-2025.csv"
)
DEFAULT_REPORT = (
    PROJECT_ROOT / "data/support/new-zealand-reference-comparison.json"
)

SOURCE_FILES = {
    2022: "student_visa_decisions_2022.csv",
    2023: "student_visa_decisions_2023.csv",
    2024: "student_visa_decisions_2024.csv",
    2025: "student_visa_decisions_2025.csv",
}
SOURCE_COUNTRY = "country_territory_special_administrative_region"
SOURCE_APPROVED = "number_approved"
SOURCE_DECLINED = "number_declined"
OUTPUT_COLUMNS = [
    "Country",
    "Number approved",
    "Number declined",
    "Total applications",
    "Approval rate",
]
REFERENCE_ONLY_COLUMNS = ["Applications_log10"]
INTEGER_COLUMNS = [
    "Number approved",
    "Number declined",
    "Total applications",
]
FLOAT_COLUMNS = ["Approval rate"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--skip-reference-check",
        action="store_true",
        help="Build and validate the output without comparing it to the reference CSV.",
    )
    return parser.parse_args()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def parse_nonnegative_integer(value: str, *, field: str, source: Path, line: int) -> int:
    normalized = value.strip().replace(",", "")
    try:
        result = int(normalized)
    except ValueError as error:
        raise ValueError(f"{source}:{line}: invalid integer in {field}: {value!r}") from error
    if result < 0:
        raise ValueError(f"{source}:{line}: negative value in {field}: {result}")
    return result


def validate_schema(schema_path: Path) -> dict[str, Any]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = schema.get("items", {}).get("required")
    column_order = schema.get("x-table", {}).get("column_order")
    if required != OUTPUT_COLUMNS or column_order != OUTPUT_COLUMNS:
        raise ValueError(
            f"{schema_path}: required fields and x-table.column_order must equal "
            f"{OUTPUT_COLUMNS!r}"
        )
    return schema


def make_prepared_rows(totals: dict[str, list[int]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for country in sorted(totals):
        approved, declined = totals[country]
        decisions = approved + declined
        if decisions <= 0:
            raise ValueError(f"{country}: decision total must be positive")
        prepared.append(
            {
                "Country": country,
                "Number approved": approved,
                "Number declined": declined,
                "Total applications": decisions,
                "Approval rate": approved / decisions,
            }
        )
    validate_prepared(prepared)
    return prepared


def collect_rows(
    input_dir: Path,
) -> tuple[dict[int, list[dict[str, Any]]], list[dict[str, Any]]]:
    annual_rows: dict[int, list[dict[str, Any]]] = {}
    source_audit: list[dict[str, Any]] = []

    for expected_year, filename in SOURCE_FILES.items():
        totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        source = input_dir / filename
        detail_rows = 0
        detail_approvals = 0
        detail_declines = 0
        published_total: dict[str, int] | None = None
        seen_countries: set[str] = set()

        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"year", SOURCE_COUNTRY, SOURCE_APPROVED, SOURCE_DECLINED}
            missing = required.difference(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{source}: missing required columns: {sorted(missing)}")

            for line_number, row in enumerate(reader, start=2):
                year = parse_nonnegative_integer(
                    row["year"], field="year", source=source, line=line_number
                )
                if year != expected_year:
                    raise ValueError(
                        f"{source}:{line_number}: expected year {expected_year}, found {year}"
                    )

                country = row[SOURCE_COUNTRY].strip()
                if not country:
                    raise ValueError(f"{source}:{line_number}: empty country label")
                approved = parse_nonnegative_integer(
                    row[SOURCE_APPROVED],
                    field=SOURCE_APPROVED,
                    source=source,
                    line=line_number,
                )
                declined = parse_nonnegative_integer(
                    row[SOURCE_DECLINED],
                    field=SOURCE_DECLINED,
                    source=source,
                    line=line_number,
                )

                if country == "Total":
                    if published_total is not None:
                        raise ValueError(f"{source}:{line_number}: duplicate Total row")
                    published_total = {
                        "approved": approved,
                        "declined": declined,
                        "decisions": approved + declined,
                    }
                    continue

                if country in seen_countries:
                    raise ValueError(
                        f"{source}:{line_number}: duplicate country within year: {country}"
                    )
                seen_countries.add(country)
                detail_rows += 1
                detail_approvals += approved
                detail_declines += declined
                totals[country][0] += approved
                totals[country][1] += declined

        prepared = make_prepared_rows(totals)
        annual_rows[expected_year] = prepared
        source_audit.append(
            {
                "year": expected_year,
                "source_file": display_path(source),
                "detail_rows": detail_rows,
                "detail_approvals": detail_approvals,
                "detail_declines": detail_declines,
                "detail_decisions": detail_approvals + detail_declines,
                "prepared_rows": len(prepared),
                "excluded_total_rows": 1 if published_total is not None else 0,
                "published_total": published_total,
            }
        )

    return annual_rows, source_audit


def combine_annual_rows(
    annual_rows: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for year in SOURCE_FILES:
        for row in annual_rows[year]:
            country = str(row["Country"])
            totals[country][0] += int(row["Number approved"])
            totals[country][1] += int(row["Number declined"])
    return make_prepared_rows(totals)


def validate_prepared(rows: list[dict[str, Any]]) -> None:
    countries = [str(row["Country"]) for row in rows]
    if countries != sorted(countries):
        raise ValueError("Prepared rows are not sorted by Country")
    if len(countries) != len(set(countries)):
        raise ValueError("Prepared Country values are not unique")

    for row in rows:
        if list(row) != OUTPUT_COLUMNS:
            raise ValueError(f"Unexpected prepared column order for {row.get('Country')}")
        approved = int(row["Number approved"])
        declined = int(row["Number declined"])
        decisions = int(row["Total applications"])
        if decisions != approved + declined:
            raise ValueError(f"Decision total does not reconcile for {row['Country']}")
        if not math.isclose(
            float(row["Approval rate"]), approved / decisions, rel_tol=0.0, abs_tol=1e-15
        ):
            raise ValueError(f"Approval rate does not reconcile for {row['Country']}")


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(
            handle,
            quoting=csv.QUOTE_NONNUMERIC,
            lineterminator="\n",
        )
        writer.writerow(OUTPUT_COLUMNS)
        for row in rows:
            values = [row[column] for column in OUTPUT_COLUMNS]
            # KNIME serialized mathematically integral rates as integers
            # (for example 1 rather than 1.0).
            values = [
                int(value) if isinstance(value, float) and value.is_integer() else value
                for value in values
            ]
            writer.writerow(values)


def read_typed_csv(
    path: Path, *, permitted_extra_columns: list[str] | None = None
) -> list[dict[str, Any]]:
    permitted_extra_columns = permitted_extra_columns or []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        expected_columns = OUTPUT_COLUMNS + permitted_extra_columns
        if reader.fieldnames != expected_columns:
            raise ValueError(
                f"{path}: expected columns {expected_columns!r}, found {reader.fieldnames!r}"
            )
        rows: list[dict[str, Any]] = []
        for line_number, row in enumerate(reader, start=2):
            typed: dict[str, Any] = {"Country": row["Country"]}
            for field in INTEGER_COLUMNS:
                typed[field] = parse_nonnegative_integer(
                    row[field], field=field, source=path, line=line_number
                )
            for field in FLOAT_COLUMNS:
                try:
                    typed[field] = float(row[field])
                except ValueError as error:
                    raise ValueError(
                        f"{path}:{line_number}: invalid float in {field}: {row[field]!r}"
                    ) from error
            rows.append(typed)
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_with_reference(output: Path, reference: Path) -> dict[str, Any]:
    actual = read_typed_csv(output)
    expected = read_typed_csv(
        reference, permitted_extra_columns=REFERENCE_ONLY_COLUMNS
    )
    differences: list[dict[str, Any]] = []
    max_float_difference = 0.0

    for index in range(max(len(actual), len(expected))):
        if index >= len(actual) or index >= len(expected):
            differences.append(
                {
                    "row": index + 2,
                    "field": "row",
                    "prepared": actual[index] if index < len(actual) else None,
                    "reference": expected[index] if index < len(expected) else None,
                }
            )
            continue
        for field in OUTPUT_COLUMNS:
            actual_value = actual[index][field]
            expected_value = expected[index][field]
            if field in FLOAT_COLUMNS:
                difference = abs(float(actual_value) - float(expected_value))
                max_float_difference = max(max_float_difference, difference)
                equal = difference <= 1e-15
            else:
                equal = actual_value == expected_value
            if not equal:
                differences.append(
                    {
                        "row": index + 2,
                        "field": field,
                        "prepared": actual_value,
                        "reference": expected_value,
                    }
                )

    return {
        "reference_file": display_path(reference),
        "prepared_file": display_path(output),
        "reference_rows": len(expected),
        "prepared_rows": len(actual),
        "semantic_equal": not differences,
        "compared_columns": OUTPUT_COLUMNS,
        "reference_only_columns_ignored": REFERENCE_ONLY_COLUMNS,
        "maximum_absolute_float_difference": max_float_difference,
        "difference_count": len(differences),
        "differences": differences[:100],
        "reference_sha256": sha256(reference),
        "prepared_sha256": sha256(output),
    }


def main() -> int:
    args = parse_args()
    validate_schema(args.schema)
    annual_rows, source_audit = collect_rows(args.input_dir)
    rows = combine_annual_rows(annual_rows)

    outputs: list[dict[str, Any]] = []
    for year in SOURCE_FILES:
        annual_output = args.output_dir / f"student_visa_decisions_{year}.csv"
        write_csv(annual_rows[year], annual_output)
        outputs.append(
            {
                "period": str(year),
                "file": display_path(annual_output),
                "rows": len(annual_rows[year]),
                "sha256": sha256(annual_output),
            }
        )

    write_csv(rows, args.output)
    outputs.append(
        {
            "period": "2022-2025",
            "file": display_path(args.output),
            "rows": len(rows),
            "sha256": sha256(args.output),
        }
    )

    annual_approved = sum(
        int(row["Number approved"])
        for year in SOURCE_FILES
        for row in annual_rows[year]
    )
    annual_declined = sum(
        int(row["Number declined"])
        for year in SOURCE_FILES
        for row in annual_rows[year]
    )
    if annual_approved != sum(int(row["Number approved"]) for row in rows):
        raise ValueError("Combined approvals do not reconcile to annual tables")
    if annual_declined != sum(int(row["Number declined"]) for row in rows):
        raise ValueError("Combined declines do not reconcile to annual tables")

    report: dict[str, Any] = {
        "status": "passed",
        "schema_file": display_path(args.schema),
        "period": "2022-2025",
        "prepared_rows": len(rows),
        "source_audit": source_audit,
        "outputs": outputs,
        "output_validation": {
            "columns_match_schema": True,
            "countries_unique": True,
            "countries_sorted": True,
            "counts_nonnegative": True,
            "decision_totals_reconcile": True,
            "rates_reconcile": True,
            "combined_counts_equal_sum_of_annual_tables": True,
        },
    }

    if not args.skip_reference_check:
        comparison = compare_with_reference(args.output, args.reference)
        report["reference_comparison"] = comparison
        if not comparison["semantic_equal"]:
            report["status"] = "failed"

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(
        f"Prepared {len(SOURCE_FILES)} annual tables and {len(rows)} combined "
        f"country rows: {display_path(args.output)}"
    )
    if "reference_comparison" in report:
        comparison = report["reference_comparison"]
        print(
            "Reference comparison: "
            f"retained_columns_equal={str(comparison['semantic_equal']).lower()}"
        )
    print(f"Audit report: {display_path(args.report)}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
