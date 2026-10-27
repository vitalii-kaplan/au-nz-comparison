"""Validate prepared inputs and build comparison tables (Methods Section 2)."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

from .analysis_common import (
    PROJECT_ROOT,
    display_path,
    read_json,
    read_prepared_table,
    resolve_from_root,
    sha256,
    utc_timestamp,
    write_csv,
    write_json,
)


DESTINATION_COUNTRY_COLUMNS = [
    "destination_code",
    "destination_country",
    "period",
    "country",
    "number_approved",
    "number_declined",
    "decision_total",
    "approval_rate",
]
MATCHED_COUNTRY_COLUMNS = [
    "country",
    "period",
    "au_number_approved",
    "au_number_declined",
    "au_decision_total",
    "au_approval_rate",
    "nz_number_approved",
    "nz_number_declined",
    "nz_decision_total",
    "nz_approval_rate",
    "rate_difference_au_minus_nz",
]
DESTINATION_COUNTRY_YEAR_COLUMNS = [
    "destination_code",
    "destination_country",
    "year",
    "country",
    "number_approved",
    "number_declined",
    "decision_total",
    "approval_rate",
]
MATCHED_COUNTRY_YEAR_COLUMNS = [
    "country",
    "year",
    "au_number_approved",
    "au_number_declined",
    "au_decision_total",
    "au_approval_rate",
    "nz_number_approved",
    "nz_number_declined",
    "nz_decision_total",
    "nz_approval_rate",
    "rate_difference_au_minus_nz",
]
VALIDATION_COLUMNS = [
    "check_id",
    "scope",
    "destination_code",
    "year",
    "status",
    "blocking",
    "observed",
    "expected",
    "message",
]
COVERAGE_COLUMNS = [
    "scope",
    "year",
    "country",
    "in_au",
    "in_nz",
    "coverage_status",
    "au_decision_total",
    "nz_decision_total",
]
SMALL_DENOMINATOR_COLUMNS = [
    "scope",
    "year",
    "destination_code",
    "destination_country",
    "country",
    "decision_total",
    "meets_20",
    "meets_50",
]
ISSUE_COLUMNS = [
    "record_type",
    "scope",
    "destination_code",
    "year",
    "country_or_label",
    "decision_total",
    "status",
    "reason",
    "analysis_handling",
    "source",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def indexed(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["Country"]): row for row in rows}


def sum_annual(
    annual: dict[int, list[dict[str, Any]]],
) -> dict[str, tuple[int, int]]:
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for rows in annual.values():
        for row in rows:
            country = str(row["Country"])
            totals[country][0] += int(row["Number approved"])
            totals[country][1] += int(row["Number declined"])
    return {country: (values[0], values[1]) for country, values in totals.items()}


def add_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    scope: str,
    status: bool,
    observed: Any,
    expected: Any,
    message: str,
    destination_code: str = "",
    year: int | str = "",
    blocking: bool = True,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "scope": scope,
            "destination_code": destination_code,
            "year": year,
            "status": "passed" if status else "failed",
            "blocking": str(blocking).lower(),
            "observed": observed,
            "expected": expected,
            "message": message,
        }
    )
    if blocking and not status:
        raise ValueError(f"{check_id}: {message}; observed={observed}, expected={expected}")


def make_long_row(
    code: str,
    name: str,
    period_or_year: str | int,
    row: dict[str, Any],
    *,
    annual: bool,
) -> dict[str, Any]:
    result = {
        "destination_code": code,
        "destination_country": name,
        "country": row["Country"],
        "number_approved": row["Number approved"],
        "number_declined": row["Number declined"],
        "decision_total": row["Total applications"],
        "approval_rate": row["Approval rate"],
    }
    result["year" if annual else "period"] = period_or_year
    return result


def matched_row(
    country: str,
    period_or_year: str | int,
    au: dict[str, Any],
    nz: dict[str, Any],
    *,
    annual: bool,
) -> dict[str, Any]:
    result = {
        "country": country,
        "au_number_approved": au["Number approved"],
        "au_number_declined": au["Number declined"],
        "au_decision_total": au["Total applications"],
        "au_approval_rate": au["Approval rate"],
        "nz_number_approved": nz["Number approved"],
        "nz_number_declined": nz["Number declined"],
        "nz_decision_total": nz["Total applications"],
        "nz_approval_rate": nz["Approval rate"],
        "rate_difference_au_minus_nz": (
            float(au["Approval rate"]) - float(nz["Approval rate"])
        ),
    }
    result["year" if annual else "period"] = period_or_year
    return result


def validate_contract(contract_path: Path, registry_path: Path) -> dict[str, str]:
    contract = read_csv_rows(contract_path)
    difference = [
        row for row in contract if row.get("contract_item") == "matched_rate_difference"
    ]
    if len(difference) != 1 or difference[0].get("direction") != "AU - NZ":
        raise ValueError("Analysis contract does not define AU - NZ matched differences")
    registry = read_csv_rows(registry_path)
    if {row.get("destination_code") for row in registry} != {"AU", "NZ"}:
        raise ValueError("Input registry does not contain exactly AU and NZ")
    return {str(row["destination_code"]): str(row["sha256"]) for row in registry}


def run(
    *,
    config_path: Path,
    contract_path: Path,
    registry_path: Path,
    m49_path: Path,
    harmonization_report_path: Path,
    comparison_dir: Path,
    validation_dir: Path,
    manifest_dir: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Path]:
    config = read_json(config_path)
    registry_hashes = validate_contract(contract_path, registry_path)
    years = [int(year) for year in config["years"]]
    destinations = config["destinations"]
    thresholds = sorted(int(value) for value in config["small_denominator_thresholds"])
    if thresholds != [20, 50]:
        raise ValueError("Small-denominator thresholds must be [20, 50]")

    with m49_path.open("r", encoding="utf-8-sig", newline="") as handle:
        m49_names = {row["Country or Area"] for row in csv.DictReader(handle)}
    allowed_non_m49 = {
        code: set(config["retained_non_m49"].get(code, [])) for code in ("AU", "NZ")
    }
    excluded_labels = set(config["excluded_non_country_labels"])

    checks: list[dict[str, Any]] = []
    pooled: dict[str, list[dict[str, Any]]] = {}
    annual: dict[str, dict[int, list[dict[str, Any]]]] = {"AU": {}, "NZ": {}}
    input_manifest: list[dict[str, Any]] = []

    for code in ("AU", "NZ"):
        settings = destinations[code]
        pooled_path = resolve_from_root(settings["pooled_file"], project_root)
        pooled[code] = read_prepared_table(pooled_path)
        add_check(
            checks,
            check_id="pooled_prepared_table_contract",
            scope="pooled",
            destination_code=code,
            status=True,
            observed=len(pooled[code]),
            expected="valid rows",
            message=(
                "Schema, sorted unique keys, non-negative reconciled counts, and "
                "rates all passed"
            ),
        )
        add_check(
            checks,
            check_id="pooled_input_hash",
            scope="pooled",
            destination_code=code,
            status=sha256(pooled_path) == registry_hashes[code],
            observed=sha256(pooled_path),
            expected=registry_hashes[code],
            message="Pooled input matches the Section 1 registry",
        )
        input_manifest.append(
            {
                "path": display_path(pooled_path, project_root),
                "sha256": sha256(pooled_path),
                "rows": len(pooled[code]),
            }
        )
        pooled_names = {str(row["Country"]) for row in pooled[code]}
        pooled_unexpected = sorted(
            pooled_names - m49_names - allowed_non_m49[code]
        )
        add_check(
            checks,
            check_id="pooled_country_names",
            scope="pooled",
            destination_code=code,
            status=not pooled_unexpected,
            observed=";".join(pooled_unexpected),
            expected="M49 names or reviewed exceptions",
            message="Pooled country names satisfy the harmonization contract",
        )
        pooled_excluded = sorted(pooled_names & excluded_labels)
        add_check(
            checks,
            check_id="pooled_excluded_labels_absent",
            scope="pooled",
            destination_code=code,
            status=not pooled_excluded,
            observed=";".join(pooled_excluded),
            expected="none",
            message="Excluded non-country labels are absent from the pooled table",
        )

        for year in years:
            annual_path = resolve_from_root(
                settings["annual_pattern"].format(year=year), project_root
            )
            annual[code][year] = read_prepared_table(annual_path)
            add_check(
                checks,
                check_id="annual_prepared_table_contract",
                scope="annual",
                destination_code=code,
                year=year,
                status=True,
                observed=len(annual[code][year]),
                expected="valid rows",
                message=(
                    "Schema, sorted unique keys, non-negative reconciled counts, "
                    "and rates all passed"
                ),
            )
            input_manifest.append(
                {
                    "path": display_path(annual_path, project_root),
                    "sha256": sha256(annual_path),
                    "rows": len(annual[code][year]),
                }
            )
            names = {str(row["Country"]) for row in annual[code][year]}
            unexpected = sorted(names - m49_names - allowed_non_m49[code])
            add_check(
                checks,
                check_id="annual_country_names",
                scope="annual",
                destination_code=code,
                year=year,
                status=not unexpected,
                observed=";".join(unexpected),
                expected="M49 names or reviewed exceptions",
                message="Annual country names satisfy the harmonization contract",
            )
            present_excluded = sorted(names & excluded_labels)
            add_check(
                checks,
                check_id="excluded_labels_absent",
                scope="annual",
                destination_code=code,
                year=year,
                status=not present_excluded,
                observed=";".join(present_excluded),
                expected="none",
                message="Excluded non-country labels are absent",
            )

        add_check(
            checks,
            check_id="annual_year_coverage",
            scope="annual",
            destination_code=code,
            status=set(annual[code]) == set(years),
            observed=";".join(str(year) for year in sorted(annual[code])),
            expected=";".join(str(year) for year in years),
            message="All configured calendar years are present",
        )

        annual_totals = sum_annual(annual[code])
        pooled_totals = {
            str(row["Country"]): (
                int(row["Number approved"]),
                int(row["Number declined"]),
            )
            for row in pooled[code]
        }
        add_check(
            checks,
            check_id="pooled_equals_annual_sum",
            scope="pooled_vs_annual",
            destination_code=code,
            status=pooled_totals == annual_totals,
            observed=len(pooled_totals),
            expected=len(annual_totals),
            message="Pooled counts equal the country-level sum of annual tables",
        )

    pooled_long = [
        make_long_row(code, destinations[code]["name"], config["period"], row, annual=False)
        for code in ("AU", "NZ")
        for row in pooled[code]
    ]
    pooled_long.sort(key=lambda row: (str(row["destination_code"]), str(row["country"])))

    annual_long = [
        make_long_row(code, destinations[code]["name"], year, row, annual=True)
        for code in ("AU", "NZ")
        for year in years
        for row in annual[code][year]
    ]
    annual_long.sort(
        key=lambda row: (
            str(row["destination_code"]),
            int(row["year"]),
            str(row["country"]),
        )
    )

    pooled_index = {code: indexed(pooled[code]) for code in ("AU", "NZ")}
    common_pooled = sorted(set(pooled_index["AU"]) & set(pooled_index["NZ"]))
    matched_pooled = [
        matched_row(
            country,
            config["period"],
            pooled_index["AU"][country],
            pooled_index["NZ"][country],
            annual=False,
        )
        for country in common_pooled
    ]

    matched_annual: list[dict[str, Any]] = []
    common_by_year: dict[int, int] = {}
    for year in years:
        au_index = indexed(annual["AU"][year])
        nz_index = indexed(annual["NZ"][year])
        common = sorted(set(au_index) & set(nz_index))
        common_by_year[year] = len(common)
        matched_annual.extend(
            matched_row(
                country, year, au_index[country], nz_index[country], annual=True
            )
            for country in common
        )
    matched_annual.sort(key=lambda row: (int(row["year"]), str(row["country"])))

    coverage_rows: list[dict[str, Any]] = []
    coverage_scopes: list[tuple[str, int | str, dict[str, dict[str, Any]], dict[str, dict[str, Any]]]] = [
        ("pooled", "", pooled_index["AU"], pooled_index["NZ"])
    ]
    for year in years:
        coverage_scopes.append(
            ("annual", year, indexed(annual["AU"][year]), indexed(annual["NZ"][year]))
        )
    for scope, year, au_index, nz_index in coverage_scopes:
        for country in sorted(set(au_index) | set(nz_index)):
            in_au = country in au_index
            in_nz = country in nz_index
            coverage_rows.append(
                {
                    "scope": scope,
                    "year": year,
                    "country": country,
                    "in_au": int(in_au),
                    "in_nz": int(in_nz),
                    "coverage_status": (
                        "both" if in_au and in_nz else "australia_only" if in_au else "new_zealand_only"
                    ),
                    "au_decision_total": (
                        au_index[country]["Total applications"] if in_au else ""
                    ),
                    "nz_decision_total": (
                        nz_index[country]["Total applications"] if in_nz else ""
                    ),
                }
            )

    small_rows: list[dict[str, Any]] = []
    for row in pooled_long:
        if int(row["decision_total"]) < max(thresholds):
            small_rows.append(
                {
                    "scope": "pooled",
                    "year": "",
                    "destination_code": row["destination_code"],
                    "destination_country": row["destination_country"],
                    "country": row["country"],
                    "decision_total": row["decision_total"],
                    "meets_20": int(int(row["decision_total"]) >= 20),
                    "meets_50": int(int(row["decision_total"]) >= 50),
                }
            )
    for row in annual_long:
        if int(row["decision_total"]) < max(thresholds):
            small_rows.append(
                {
                    "scope": "annual",
                    "year": row["year"],
                    "destination_code": row["destination_code"],
                    "destination_country": row["destination_country"],
                    "country": row["country"],
                    "decision_total": row["decision_total"],
                    "meets_20": int(int(row["decision_total"]) >= 20),
                    "meets_50": int(int(row["decision_total"]) >= 50),
                }
            )
    small_rows.sort(
        key=lambda row: (
            str(row["scope"]),
            str(row["destination_code"]),
            int(row["year"]) if row["year"] != "" else 0,
            int(row["decision_total"]),
            str(row["country"]),
        )
    )

    harmonization = read_json(harmonization_report_path)
    issue_rows: list[dict[str, Any]] = []
    for code in ("AU", "NZ"):
        destination_name = destinations[code]["name"]
        report = harmonization["destinations"][destination_name]
        for year in years:
            for item in report["annual"][str(year)]["excluded_or_unmatched"]:
                issue_rows.append(
                    {
                        "record_type": "source_label_exclusion",
                        "scope": "annual",
                        "destination_code": code,
                        "year": year,
                        "country_or_label": item["source_label"],
                        "decision_total": item["decisions"],
                        "status": item["normalization_status"],
                        "reason": item["notes"],
                        "analysis_handling": "excluded from normalized data",
                        "source": display_path(harmonization_report_path, project_root),
                    }
                )
    for row in coverage_rows:
        if row["scope"] != "pooled" or row["coverage_status"] == "both":
            continue
        present_code = "AU" if row["in_au"] else "NZ"
        decision_total = (
            row["au_decision_total"] if row["in_au"] else row["nz_decision_total"]
        )
        issue_rows.append(
            {
                "record_type": "paired_analysis_exclusion",
                "scope": "pooled",
                "destination_code": present_code,
                "year": "",
                "country_or_label": row["country"],
                "decision_total": decision_total,
                "status": row["coverage_status"],
                "reason": "Country is not represented in both destination tables",
                "analysis_handling": "retained for destination summaries; excluded from paired analysis",
                "source": "country_coverage.csv",
            }
        )
    issue_rows.sort(
        key=lambda row: (
            str(row["record_type"]),
            str(row["destination_code"]),
            int(row["year"]) if row["year"] != "" else 0,
            str(row["country_or_label"]),
        )
    )

    add_check(
        checks,
        check_id="pooled_common_country_count",
        scope="cross_destination",
        status=len(common_pooled)
        == int(harmonization["cross_destination"]["common_output_names"]),
        observed=len(common_pooled),
        expected=harmonization["cross_destination"]["common_output_names"],
        message="Common pooled-country count agrees with harmonization audit",
    )
    add_check(
        checks,
        check_id="blocking_validation_failures",
        scope="all",
        status=not any(row["status"] == "failed" and row["blocking"] == "true" for row in checks),
        observed=0,
        expected=0,
        message="No unresolved blocking validation failures",
    )

    output_paths = {
        "destination_country": comparison_dir / "destination_country_2022-2025.csv",
        "matched_country": comparison_dir / "matched_country_2022-2025.csv",
        "destination_country_year": comparison_dir / "destination_country_year.csv",
        "matched_country_year": comparison_dir / "matched_country_year.csv",
        "validation_checks": validation_dir / "data_validation_checks.csv",
        "country_coverage": validation_dir / "country_coverage.csv",
        "small_denominators": validation_dir / "small_denominators.csv",
        "issues_and_exclusions": validation_dir / "data_issues_and_exclusions.csv",
    }
    write_csv(output_paths["destination_country"], DESTINATION_COUNTRY_COLUMNS, pooled_long)
    write_csv(output_paths["matched_country"], MATCHED_COUNTRY_COLUMNS, matched_pooled)
    write_csv(
        output_paths["destination_country_year"],
        DESTINATION_COUNTRY_YEAR_COLUMNS,
        annual_long,
    )
    write_csv(
        output_paths["matched_country_year"], MATCHED_COUNTRY_YEAR_COLUMNS, matched_annual
    )
    write_csv(output_paths["validation_checks"], VALIDATION_COLUMNS, checks)
    write_csv(output_paths["country_coverage"], COVERAGE_COLUMNS, coverage_rows)
    write_csv(
        output_paths["small_denominators"], SMALL_DENOMINATOR_COLUMNS, small_rows
    )
    write_csv(output_paths["issues_and_exclusions"], ISSUE_COLUMNS, issue_rows)

    row_counts = {
        "destination_country": len(pooled_long),
        "matched_country": len(matched_pooled),
        "destination_country_year": len(annual_long),
        "matched_country_year": len(matched_annual),
        "validation_checks": len(checks),
        "country_coverage": len(coverage_rows),
        "small_denominators": len(small_rows),
        "issues_and_exclusions": len(issue_rows),
    }
    manifest_path = manifest_dir / "02_data_validation_and_tables.json"
    manifest = {
        "module": "src.analysis_02_build_tables",
        "status": "passed",
        "analysis_timestamp_utc": utc_timestamp(),
        "config_file": display_path(config_path, project_root),
        "config_sha256": sha256(config_path),
        "contract_file": display_path(contract_path, project_root),
        "contract_sha256": sha256(contract_path),
        "input_registry_file": display_path(registry_path, project_root),
        "input_registry_sha256": sha256(registry_path),
        "inputs": input_manifest,
        "outputs": [
            {
                "artifact": key,
                "path": display_path(path, project_root),
                "sha256": sha256(path),
                "rows": row_counts[key],
            }
            for key, path in output_paths.items()
        ],
        "summary": {
            "pooled_rows": len(pooled_long),
            "pooled_matched_countries": len(matched_pooled),
            "country_year_rows": len(annual_long),
            "matched_country_year_rows": len(matched_annual),
            "matched_countries_by_year": {
                str(year): common_by_year[year] for year in years
            },
            "small_denominator_rows": len(small_rows),
            "issue_and_exclusion_rows": len(issue_rows),
            "blocking_validation_failures": 0,
        },
    }
    write_json(manifest_path, manifest)
    output_paths["manifest"] = manifest_path
    return output_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=PROJECT_ROOT / "src/analysis_config.json"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=PROJECT_ROOT / "data/results/validation/analysis_contract.csv",
    )
    parser.add_argument(
        "--input-registry",
        type=Path,
        default=PROJECT_ROOT / "data/results/validation/input_registry.csv",
    )
    parser.add_argument(
        "--m49",
        type=Path,
        default=PROJECT_ROOT / "data/original/reference/un-m49.csv",
    )
    parser.add_argument(
        "--harmonization-report",
        type=Path,
        default=PROJECT_ROOT / "data/support/country-name-harmonization.json",
    )
    parser.add_argument(
        "--comparison-dir",
        type=Path,
        default=PROJECT_ROOT / "data/prepared/comparison",
    )
    parser.add_argument(
        "--validation-dir",
        type=Path,
        default=PROJECT_ROOT / "data/results/validation",
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=PROJECT_ROOT / "data/results/manifests",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = run(
        config_path=args.config,
        contract_path=args.contract,
        registry_path=args.input_registry,
        m49_path=args.m49,
        harmonization_report_path=args.harmonization_report,
        comparison_dir=args.comparison_dir,
        validation_dir=args.validation_dir,
        manifest_dir=args.manifest_dir,
    )
    print("Validated inputs and wrote comparison artifacts:")
    for path in outputs.values():
        print(f"- {display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
