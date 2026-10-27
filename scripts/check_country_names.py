#!/usr/bin/env python3
"""Normalize NZ and AU country labels to M49 names plus reviewed exceptions."""

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
DEFAULT_M49 = PROJECT_ROOT / "data/original/reference/un-m49.csv"
DEFAULT_ALIASES = (
    PROJECT_ROOT / "data/reference/country_aliases.csv"
)
DEFAULT_REPORT = PROJECT_ROOT / "data/support/country-name-harmonization.json"
OUTPUT_COLUMNS = [
    "Country",
    "Number approved",
    "Number declined",
    "Total applications",
    "Approval rate",
]
TARGET_YEARS = (2022, 2023, 2024, 2025)
DESTINATIONS = {
    "New Zealand": {
        "input_dir": PROJECT_ROOT / "data/prepared/new-zealand",
        "output_dir": PROJECT_ROOT / "data/prepared/new-zealand",
    },
    "Australia": {
        "input_dir": PROJECT_ROOT / "data/prepared/australia",
        "output_dir": PROJECT_ROOT / "data/prepared/australia",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m49", type=Path, default=DEFAULT_M49)
    parser.add_argument("--aliases", type=Path, default=DEFAULT_ALIASES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_m49(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"Country or Area", "M49 Code", "ISO-alpha2 Code", "ISO-alpha3 Code"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing M49 columns: {sorted(missing)}")
        records: dict[str, dict[str, str]] = {}
        for row in reader:
            name = row["Country or Area"].strip()
            if not name or name in records:
                raise ValueError(f"{path}: empty or duplicate M49 name: {name!r}")
            records[name] = {
                "m49_code": row["M49 Code"].strip(),
                "iso_alpha2": row["ISO-alpha2 Code"].strip(),
                "iso_alpha3": row["ISO-alpha3 Code"].strip(),
            }
    return records


def read_aliases(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    aliases: dict[tuple[str, str], dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "destination_country",
            "source_label",
            "canonical_country",
            "normalization_status",
            "notes",
        }
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing alias columns: {sorted(missing)}")
        for row in reader:
            destination = row["destination_country"].strip()
            source_label = row["source_label"].strip()
            key = (destination, source_label)
            if not source_label or key in aliases:
                raise ValueError(f"{path}: empty or duplicate alias key: {key!r}")
            aliases[key] = {
                "canonical_country": row["canonical_country"].strip(),
                "normalization_status": row["normalization_status"].strip(),
                "notes": row["notes"].strip(),
            }
    return aliases


def resolve_label(
    destination: str,
    source_label: str,
    m49: dict[str, dict[str, str]],
    aliases: dict[tuple[str, str], dict[str, str]],
) -> dict[str, str]:
    if source_label in m49:
        return {
            "canonical_country": source_label,
            "normalization_status": "matched",
            "notes": "Exact UN M49 English-name match",
        }
    alias = aliases.get((destination, source_label)) or aliases.get(("", source_label))
    if alias is None:
        return {
            "canonical_country": "",
            "normalization_status": "unmatched",
            "notes": "No exact UN M49 match or reviewed alias",
        }
    canonical = alias["canonical_country"]
    status = alias["normalization_status"]
    if canonical and canonical not in m49 and status != "non_m49_retained":
        raise ValueError(
            f"Alias for {destination}/{source_label!r} resolves to non-M49 name "
            f"{canonical!r}"
        )
    if status == "non_m49_retained" and not canonical:
        raise ValueError(
            f"Retained non-M49 label for {destination}/{source_label!r} "
            "must have an output name"
        )
    return alias


def read_prepared(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != OUTPUT_COLUMNS:
            raise ValueError(f"{path}: expected columns {OUTPUT_COLUMNS!r}")
        rows: list[dict[str, Any]] = []
        for line_number, row in enumerate(reader, start=2):
            try:
                approved = int(row["Number approved"])
                declined = int(row["Number declined"])
                decisions = int(row["Total applications"])
                rate = float(row["Approval rate"])
            except ValueError as error:
                raise ValueError(f"{path}:{line_number}: invalid numeric value") from error
            if min(approved, declined, decisions) < 0 or decisions != approved + declined:
                raise ValueError(f"{path}:{line_number}: counts do not reconcile")
            if not math.isclose(rate, approved / decisions, rel_tol=0.0, abs_tol=1e-15):
                raise ValueError(f"{path}:{line_number}: approval rate does not reconcile")
            rows.append(
                {
                    "Country": row["Country"],
                    "Number approved": approved,
                    "Number declined": declined,
                    "Total applications": decisions,
                    "Approval rate": rate,
                }
            )
    return rows


def write_prepared(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_NONNUMERIC, lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        for row in rows:
            values = [row[column] for column in OUTPUT_COLUMNS]
            values = [
                int(value) if isinstance(value, float) and value.is_integer() else value
                for value in values
            ]
            writer.writerow(values)


def normalize_destination_year(
    destination: str,
    year: int,
    input_path: Path,
    output_path: Path,
    m49: dict[str, dict[str, str]],
    aliases: dict[tuple[str, str], dict[str, str]],
) -> dict[str, Any]:
    source_rows = read_prepared(input_path)
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    mappings: list[dict[str, Any]] = []
    status_counts: dict[str, int] = defaultdict(int)
    excluded_decisions = 0

    for row in source_rows:
        source_label = str(row["Country"])
        resolution = resolve_label(destination, source_label, m49, aliases)
        canonical = resolution["canonical_country"]
        status = resolution["normalization_status"]
        status_counts[status] += 1
        mapping = {
            "year": year,
            "source_label": source_label,
            "canonical_country": canonical or None,
            "normalization_status": status,
            "m49_code": m49[canonical]["m49_code"] if canonical in m49 else None,
            "decisions": int(row["Total applications"]),
            "notes": resolution["notes"],
        }
        mappings.append(mapping)
        if not canonical:
            excluded_decisions += int(row["Total applications"])
            continue
        totals[canonical][0] += int(row["Number approved"])
        totals[canonical][1] += int(row["Number declined"])

    normalized: list[dict[str, Any]] = []
    for country in sorted(totals):
        approved, declined = totals[country]
        decisions = approved + declined
        normalized.append(
            {
                "Country": country,
                "Number approved": approved,
                "Number declined": declined,
                "Total applications": decisions,
                "Approval rate": approved / decisions,
            }
        )
    retained_non_m49 = {
        mapping["canonical_country"]
        for mapping in mappings
        if mapping["normalization_status"] == "non_m49_retained"
    }
    if any(
        row["Country"] not in m49 and row["Country"] not in retained_non_m49
        for row in normalized
    ):
        raise ValueError(
            f"{destination}: normalized output contains an unreviewed non-M49 name"
        )
    if len({row["Country"] for row in normalized}) != len(normalized):
        raise ValueError(f"{destination}: normalized output keys are not unique")

    write_prepared(normalized, output_path)
    source_decisions = sum(int(row["Total applications"]) for row in source_rows)
    included_decisions = sum(int(row["Total applications"]) for row in normalized)
    if source_decisions != included_decisions + excluded_decisions:
        raise ValueError(f"{destination}: normalization does not conserve decisions")

    return {
        "year": year,
        "input_file": display_path(input_path),
        "output_file": display_path(output_path),
        "source_rows": len(source_rows),
        "normalized_rows": len(normalized),
        "status_counts": dict(sorted(status_counts.items())),
        "source_decisions": source_decisions,
        "included_decisions": included_decisions,
        "excluded_decisions": excluded_decisions,
        "excluded_or_unmatched": [
            mapping for mapping in mappings if mapping["canonical_country"] is None
        ],
        "retained_non_m49": [
            mapping
            for mapping in mappings
            if mapping["normalization_status"] == "non_m49_retained"
        ],
        "renamed": [
            mapping
            for mapping in mappings
            if mapping["canonical_country"]
            and mapping["canonical_country"] != mapping["source_label"]
        ],
        "mappings": mappings,
        "output_sha256": sha256(output_path),
    }


def combine_annual_rows(
    annual_rows: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for year in TARGET_YEARS:
        for row in annual_rows[year]:
            country = str(row["Country"])
            totals[country][0] += int(row["Number approved"])
            totals[country][1] += int(row["Number declined"])

    combined: list[dict[str, Any]] = []
    for country in sorted(totals):
        approved, declined = totals[country]
        decisions = approved + declined
        combined.append(
            {
                "Country": country,
                "Number approved": approved,
                "Number declined": declined,
                "Total applications": decisions,
                "Approval rate": approved / decisions,
            }
        )
    return combined


def prepare_destination(
    destination: str,
    input_dir: Path,
    output_dir: Path,
    m49: dict[str, dict[str, str]],
    aliases: dict[tuple[str, str], dict[str, str]],
) -> dict[str, Any]:
    annual_reports: dict[str, dict[str, Any]] = {}
    annual_rows: dict[int, list[dict[str, Any]]] = {}

    for year in TARGET_YEARS:
        input_path = input_dir / f"student_visa_decisions_{year}.csv"
        output_path = output_dir / f"student_visa_decisions_{year}-m49.csv"
        annual_reports[str(year)] = normalize_destination_year(
            destination,
            year,
            input_path,
            output_path,
            m49,
            aliases,
        )
        annual_rows[year] = read_prepared(output_path)

    combined_rows = combine_annual_rows(annual_rows)
    combined_path = output_dir / "student_visa_decisions_2022-2025-m49.csv"
    write_prepared(combined_rows, combined_path)

    annual_included_decisions = sum(
        report["included_decisions"] for report in annual_reports.values()
    )
    combined_decisions = sum(
        int(row["Total applications"]) for row in combined_rows
    )
    if combined_decisions != annual_included_decisions:
        raise ValueError(
            f"{destination}: combined normalized table does not conserve annual counts"
        )

    status_counts: dict[str, int] = defaultdict(int)
    excluded_or_unmatched: list[dict[str, Any]] = []
    retained_non_m49: list[dict[str, Any]] = []
    renamed: list[dict[str, Any]] = []
    for report in annual_reports.values():
        for status, count in report["status_counts"].items():
            status_counts[status] += count
        excluded_or_unmatched.extend(report["excluded_or_unmatched"])
        retained_non_m49.extend(report["retained_non_m49"])
        renamed.extend(report["renamed"])

    source_decisions = sum(
        report["source_decisions"] for report in annual_reports.values()
    )
    excluded_decisions = sum(
        report["excluded_decisions"] for report in annual_reports.values()
    )
    if source_decisions != combined_decisions + excluded_decisions:
        raise ValueError(
            f"{destination}: combined normalization does not conserve source counts"
        )

    return {
        "annual": annual_reports,
        "source_country_year_rows": sum(
            report["source_rows"] for report in annual_reports.values()
        ),
        "normalized_country_year_rows": sum(
            report["normalized_rows"] for report in annual_reports.values()
        ),
        "normalized_rows": len(combined_rows),
        "status_counts_by_country_year": dict(sorted(status_counts.items())),
        "source_decisions": source_decisions,
        "included_decisions": combined_decisions,
        "excluded_decisions": excluded_decisions,
        "excluded_or_unmatched": excluded_or_unmatched,
        "retained_non_m49": retained_non_m49,
        "renamed": renamed,
        "combined": {
            "period": "2022-2025",
            "construction": "sum of normalized annual tables",
            "output_file": display_path(combined_path),
            "normalized_rows": len(combined_rows),
            "included_decisions": combined_decisions,
            "output_sha256": sha256(combined_path),
        },
        "validation": {
            "annual_tables_normalized_before_combination": True,
            "combined_counts_equal_sum_of_normalized_annual_tables": True,
            "source_equals_included_plus_excluded_decisions": True,
        },
    }


def main() -> int:
    args = parse_args()
    m49 = read_m49(args.m49)
    aliases = read_aliases(args.aliases)
    destination_reports: dict[str, Any] = {}
    normalized_names: dict[str, set[str]] = {}

    for destination, paths in DESTINATIONS.items():
        report = prepare_destination(
            destination,
            paths["input_dir"],
            paths["output_dir"],
            m49,
            aliases,
        )
        destination_reports[destination] = report
        combined_path = (
            paths["output_dir"] / "student_visa_decisions_2022-2025-m49.csv"
        )
        with combined_path.open("r", encoding="utf-8", newline="") as handle:
            normalized_names[destination] = {
                row["Country"] for row in csv.DictReader(handle)
            }

    m49_names = set(m49)
    common = normalized_names["New Zealand"] & normalized_names["Australia"]
    common_m49 = common & m49_names
    retained_non_m49_names = {
        destination: sorted(
            {
                mapping["canonical_country"]
                for mapping in destination_reports[destination]["retained_non_m49"]
            }
        )
        for destination in DESTINATIONS
    }
    report = {
        "status": "passed",
        "m49_reference_file": display_path(args.m49),
        "m49_reference_sha256": sha256(args.m49),
        "m49_country_or_area_rows": len(m49),
        "alias_file": display_path(args.aliases),
        "normalization_order": "normalize each annual table, then combine years",
        "target_years": list(TARGET_YEARS),
        "destinations": destination_reports,
        "cross_destination": {
            "common_output_names": len(common),
            "common_m49_names": len(common_m49),
            "new_zealand_only_output_names": sorted(
                normalized_names["New Zealand"] - normalized_names["Australia"]
            ),
            "australia_only_output_names": sorted(
                normalized_names["Australia"] - normalized_names["New Zealand"]
            ),
            "retained_non_m49_names": retained_non_m49_names,
            "all_output_names_are_exact_m49_names": all(
                names <= m49_names for names in normalized_names.values()
            ),
            "all_output_names_are_m49_or_reviewed_exceptions": all(
                names
                <= m49_names | set(retained_non_m49_names[destination])
                for destination, names in normalized_names.items()
            ),
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"Checked and normalized NZ/AU labels against {len(m49)} UN M49 "
        f"country or area names plus reviewed exceptions, then combined annual "
        f"outputs; {len(common)} names occur in both combined tables"
    )
    print(f"Audit report: {display_path(args.report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
