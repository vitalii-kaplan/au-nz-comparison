#!/usr/bin/env python3
"""Prepare annual and combined Australian student-visa decision tables."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "data/original/australia/student_visa_grant_rates_2005_2026-02-28.csv"
)
DEFAULT_SCHEMA = PROJECT_ROOT / "data/schema.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data/prepared/australia"
DEFAULT_REPORT = PROJECT_ROOT / "data/support/australia-preparation-audit.json"

TARGET_YEARS = (2022, 2023, 2024, 2025)
FILTERS = {
    "client_location": "Outside Australia",
    "applicant_type": "Primary",
    "sector": "Higher Education Sector",
}
OUTPUT_COLUMNS = [
    "Country",
    "Number approved",
    "Number declined",
    "Total applications",
    "Approval rate",
]
REQUIRED_SOURCE_COLUMNS = {
    "financial_year_of_decision",
    "month",
    "client_location",
    "sector",
    "applicant_type",
    "citizenship_country",
    "grant_total",
    "refused_total",
    "total",
    "computed_grant_rate",
}
FINANCIAL_YEAR_PATTERN = re.compile(r"^(?P<start>\d{4})-\d{2}(?:\s+to\s+.+)?$")
MONTH_PATTERN = re.compile(r"^M(?P<number>0[1-9]|1[0-2])\s+\S+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def parse_nonnegative_integer(value: str, *, field: str, line: int) -> int:
    normalized = value.strip().replace(",", "")
    try:
        result = int(normalized)
    except ValueError as error:
        raise ValueError(f"line {line}: invalid integer in {field}: {value!r}") from error
    if result < 0:
        raise ValueError(f"line {line}: negative value in {field}: {result}")
    return result


def calendar_year(financial_year: str, month: str, *, line: int) -> int:
    year_match = FINANCIAL_YEAR_PATTERN.fullmatch(financial_year.strip())
    if year_match is None:
        raise ValueError(f"line {line}: invalid financial year: {financial_year!r}")
    month_match = MONTH_PATTERN.match(month.strip())
    if month_match is None:
        raise ValueError(f"line {line}: invalid month label: {month!r}")
    start_year = int(year_match.group("start"))
    financial_month = int(month_match.group("number"))
    return start_year if financial_month <= 6 else start_year + 1


def validate_schema(schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = schema.get("items", {}).get("required")
    column_order = schema.get("x-table", {}).get("column_order")
    if required != OUTPUT_COLUMNS or column_order != OUTPUT_COLUMNS:
        raise ValueError(
            f"{schema_path}: required fields and x-table.column_order must equal "
            f"{OUTPUT_COLUMNS!r}"
        )


def make_prepared_rows(totals: dict[str, list[int]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for country in sorted(totals):
        approved, declined, source_total = totals[country]
        decision_total = approved + declined
        if decision_total <= 0:
            raise ValueError(f"{country}: decision total must be positive")
        if decision_total != source_total:
            raise ValueError(
                f"{country}: grants plus refusals ({decision_total}) do not equal "
                f"summed source total ({source_total})"
            )
        prepared.append(
            {
                "Country": country,
                "Number approved": approved,
                "Number declined": declined,
                "Total applications": decision_total,
                "Approval rate": approved / decision_total,
            }
        )
    validate_prepared(prepared)
    return prepared


def validate_prepared(rows: list[dict[str, Any]]) -> None:
    countries = [str(row["Country"]) for row in rows]
    if countries != sorted(countries):
        raise ValueError("Prepared rows are not sorted by Country")
    if len(countries) != len(set(countries)):
        raise ValueError("Prepared Country values are not unique")
    for row in rows:
        if list(row) != OUTPUT_COLUMNS:
            raise ValueError(f"Unexpected column order for {row.get('Country')}")
        approved = int(row["Number approved"])
        declined = int(row["Number declined"])
        decision_total = int(row["Total applications"])
        if min(approved, declined, decision_total) < 0:
            raise ValueError(f"Negative prepared count for {row['Country']}")
        if decision_total != approved + declined:
            raise ValueError(f"Decision total does not reconcile for {row['Country']}")
        if not math.isclose(
            float(row["Approval rate"]),
            approved / decision_total,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError(f"Approval rate does not reconcile for {row['Country']}")


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(
            handle, quoting=csv.QUOTE_NONNUMERIC, lineterminator="\n"
        )
        writer.writerow(OUTPUT_COLUMNS)
        for row in rows:
            values = [row[column] for column in OUTPUT_COLUMNS]
            values = [
                int(value) if isinstance(value, float) and value.is_integer() else value
                for value in values
            ]
            writer.writerow(values)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(input_path: Path) -> tuple[dict[int, list[dict[str, Any]]], dict[str, Any]]:
    annual_totals: dict[int, dict[str, list[int]]] = {
        year: defaultdict(lambda: [0, 0, 0]) for year in TARGET_YEARS
    }
    funnel = {
        "source_rows": 0,
        "outside_australia_rows": 0,
        "outside_primary_rows": 0,
        "outside_primary_higher_education_rows": 0,
        "selected_calendar_year_rows": 0,
    }
    source_reconciliation_failures = 0
    selected_rate_failures = 0
    selected_months: dict[int, set[str]] = {year: set() for year in TARGET_YEARS}
    selected_financial_years: dict[int, set[str]] = {
        year: set() for year in TARGET_YEARS
    }
    year_source_sums: dict[int, list[int]] = {
        year: [0, 0, 0] for year in TARGET_YEARS
    }
    selected_rows_by_year = {year: 0 for year in TARGET_YEARS}

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_SOURCE_COLUMNS.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{input_path}: missing required columns: {sorted(missing)}")

        for line_number, row in enumerate(reader, start=2):
            funnel["source_rows"] += 1
            approved = parse_nonnegative_integer(
                row["grant_total"], field="grant_total", line=line_number
            )
            declined = parse_nonnegative_integer(
                row["refused_total"], field="refused_total", line=line_number
            )
            source_total = parse_nonnegative_integer(
                row["total"], field="total", line=line_number
            )
            if approved + declined != source_total:
                source_reconciliation_failures += 1

            if row["client_location"] != FILTERS["client_location"]:
                continue
            funnel["outside_australia_rows"] += 1
            if row["applicant_type"] != FILTERS["applicant_type"]:
                continue
            funnel["outside_primary_rows"] += 1
            if row["sector"] != FILTERS["sector"]:
                continue
            funnel["outside_primary_higher_education_rows"] += 1

            year = calendar_year(
                row["financial_year_of_decision"], row["month"], line=line_number
            )
            if year not in annual_totals:
                continue
            funnel["selected_calendar_year_rows"] += 1
            selected_rows_by_year[year] += 1

            country = row["citizenship_country"].strip()
            if not country:
                raise ValueError(f"line {line_number}: empty citizenship_country")
            if source_total <= 0:
                raise ValueError(f"line {line_number}: selected source total is not positive")

            if "computed_grant_rate" in row and row["computed_grant_rate"].strip():
                source_rate = float(row["computed_grant_rate"])
                if not math.isclose(
                    source_rate,
                    approved / source_total,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                ):
                    selected_rate_failures += 1

            totals = annual_totals[year][country]
            totals[0] += approved
            totals[1] += declined
            totals[2] += source_total
            year_source_sums[year][0] += approved
            year_source_sums[year][1] += declined
            year_source_sums[year][2] += source_total
            selected_months[year].add(row["month"])
            selected_financial_years[year].add(row["financial_year_of_decision"])

    if source_reconciliation_failures:
        raise ValueError(
            f"Found {source_reconciliation_failures} source rows where grants plus "
            "refusals do not equal total"
        )
    if selected_rate_failures:
        raise ValueError(
            f"Found {selected_rate_failures} selected rows with inconsistent source rates"
        )

    annual_rows = {
        year: make_prepared_rows(annual_totals[year]) for year in TARGET_YEARS
    }
    annual_audit = []
    for year in TARGET_YEARS:
        rows = annual_rows[year]
        approved = sum(int(row["Number approved"]) for row in rows)
        declined = sum(int(row["Number declined"]) for row in rows)
        decisions = sum(int(row["Total applications"]) for row in rows)
        if [approved, declined, decisions] != year_source_sums[year]:
            raise ValueError(f"{year}: aggregation does not conserve source counts")
        annual_audit.append(
            {
                "calendar_year": year,
                "selected_source_rows": selected_rows_by_year[year],
                "country_rows": len(rows),
                "number_approved": approved,
                "number_declined": declined,
                "total_applications_legacy_decision_total": decisions,
                "financial_years_used": sorted(selected_financial_years[year]),
                "months_used": sorted(selected_months[year]),
            }
        )

    audit = {
        "source_file": display_path(input_path),
        "source_sha256": sha256(input_path),
        "filters": FILTERS,
        "calendar_year_rule": {
            "M01_M06": "financial-year starting year (July-December)",
            "M07_M12": "financial-year starting year plus one (January-June)",
        },
        "target_calendar_years": list(TARGET_YEARS),
        "filter_funnel": funnel,
        "source_reconciliation_failures": source_reconciliation_failures,
        "selected_source_rate_failures": selected_rate_failures,
        "annual": annual_audit,
    }
    return annual_rows, audit


def combine_annual_rows(
    annual_rows: dict[int, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for year in TARGET_YEARS:
        for row in annual_rows[year]:
            country_totals = totals[str(row["Country"])]
            country_totals[0] += int(row["Number approved"])
            country_totals[1] += int(row["Number declined"])
            country_totals[2] += int(row["Total applications"])
    return make_prepared_rows(totals)


def main() -> int:
    args = parse_args()
    validate_schema(args.schema)
    annual_rows, audit = extract(args.input)
    combined_rows = combine_annual_rows(annual_rows)

    output_files: list[dict[str, Any]] = []
    for year in TARGET_YEARS:
        path = args.output_dir / f"student_visa_decisions_{year}.csv"
        write_csv(annual_rows[year], path)
        output_files.append(
            {"period": str(year), "file": display_path(path), "sha256": sha256(path)}
        )

    combined_path = args.output_dir / "student_visa_decisions_2022-2025.csv"
    write_csv(combined_rows, combined_path)
    output_files.append(
        {
            "period": "2022-2025",
            "file": display_path(combined_path),
            "sha256": sha256(combined_path),
        }
    )

    combined_approved = sum(int(row["Number approved"]) for row in combined_rows)
    combined_declined = sum(int(row["Number declined"]) for row in combined_rows)
    combined_decisions = sum(int(row["Total applications"]) for row in combined_rows)
    annual_decisions = sum(
        int(entry["total_applications_legacy_decision_total"])
        for entry in audit["annual"]
    )
    if combined_decisions != annual_decisions:
        raise ValueError("Combined table does not conserve annual decision totals")

    audit.update(
        {
            "status": "passed",
            "schema_file": display_path(args.schema),
            "outputs": output_files,
            "combined": {
                "country_rows": len(combined_rows),
                "number_approved": combined_approved,
                "number_declined": combined_declined,
                "total_applications_legacy_decision_total": combined_decisions,
            },
            "validation": {
                "source_counts_reconcile": True,
                "source_rates_reconcile": True,
                "annual_aggregation_conserves_counts": True,
                "combined_aggregation_conserves_annual_counts": True,
                "output_columns_match_schema": True,
                "country_keys_unique_within_each_output": True,
                "country_keys_sorted": True,
                "prepared_rates_recalculated_from_aggregated_counts": True,
            },
        }
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")

    print(
        f"Prepared {len(TARGET_YEARS)} annual tables and {len(combined_rows)} "
        f"combined country rows in {display_path(args.output_dir)}"
    )
    print(f"Audit report: {display_path(args.report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
