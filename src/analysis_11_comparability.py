"""Classify missingness and set analysis comparability gates (Methods Section 11)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .analysis_common import (
    PROJECT_ROOT,
    display_path,
    read_csv_rows,
    read_json,
    require_columns,
    require_passed_blocking_checks,
    sha256,
    utc_timestamp,
    write_csv,
    write_json,
)


CLASSIFICATION_COLUMNS = [
    "scope", "year", "destination_code", "country_or_label", "classification",
    "decision_total", "pair_status", "zero_assignment_allowed", "evidence",
]
DECISION_COLUMNS = [
    "analysis_component", "eligible", "evidence", "caveat", "required_handling",
]
PAIR_COLUMNS = [
    "scope", "year", "country", "included", "reason", "au_decision_total",
    "nz_decision_total",
]
ZERO_COLUMNS = ["status", "zero_assignment_allowed", "reason", "handling"]
PAIR_SUMMARY_COLUMNS = [
    "scope", "year", "union_origins", "matched_origins", "unmatched_origins",
    "au_only_origins", "nz_only_origins", "matched_share",
]
CLASSIFICATION_SUMMARY_COLUMNS = [
    "scope", "year", "destination_code", "classification", "record_count",
    "decision_total",
]


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def run(
    *,
    config_path: Path,
    coverage_path: Path,
    issues_path: Path,
    validation_checks_path: Path,
    output_dir: Path,
    manifest_dir: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Path]:
    config = read_json(config_path)
    require_passed_blocking_checks(validation_checks_path)
    coverage = read_csv_rows(coverage_path)
    issues = read_csv_rows(issues_path)
    require_columns(
        coverage_path,
        coverage,
        {"scope", "year", "country", "in_au", "in_nz", "coverage_status", "au_decision_total", "nz_decision_total"},
    )
    require_columns(
        issues_path,
        issues,
        {"record_type", "scope", "destination_code", "year", "country_or_label", "decision_total", "status", "reason"},
    )
    retained = {
        code: set(config["retained_non_m49"].get(code, [])) for code in ("AU", "NZ")
    }

    classifications: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    for row in coverage:
        pair_status = row["coverage_status"]
        included = pair_status == "both"
        pairs.append({
            "scope": row["scope"], "year": row["year"], "country": row["country"],
            "included": int(included),
            "reason": "valid observations in both destinations" if included else "origin absent from one destination table",
            "au_decision_total": row["au_decision_total"], "nz_decision_total": row["nz_decision_total"],
        })
        for code, present_field, total_field in (
            ("AU", "in_au", "au_decision_total"), ("NZ", "in_nz", "nz_decision_total")
        ):
            present = row[present_field] == "1"
            if present:
                classification = "reviewed_non_m49_label" if row["country"] in retained[code] else "observed_positive_decisions"
                evidence = "validated prepared row with a positive two-outcome decision total"
            else:
                classification = "absent_country"
                evidence = "no prepared row; source semantics do not establish that absence equals zero"
            classifications.append({
                "scope": row["scope"], "year": row["year"], "destination_code": code,
                "country_or_label": row["country"], "classification": classification,
                "decision_total": row[total_field], "pair_status": pair_status,
                "zero_assignment_allowed": "false", "evidence": evidence,
            })

    for row in issues:
        if row["record_type"] != "source_label_exclusion":
            continue
        classifications.append({
            "scope": row["scope"], "year": row["year"], "destination_code": row["destination_code"],
            "country_or_label": row["country_or_label"], "classification": "excluded_non_country_label",
            "decision_total": row["decision_total"], "pair_status": "not_applicable",
            "zero_assignment_allowed": "false", "evidence": row["reason"],
        })

    pooled_pairs = sum(row["scope"] == "pooled" and row["included"] == 1 for row in pairs)
    annual_pairs = sum(row["scope"] == "annual" and row["included"] == 1 for row in pairs)
    decisions = [
        {
            "analysis_component": "pooled_paired_analysis", "eligible": "true",
            "evidence": f"{pooled_pairs} origins have valid positive-decision observations in both destinations",
            "caveat": "destination source populations are aligned approximately, not identically",
            "required_handling": "use matched origins only; do not zero-fill destination-only origins",
        },
        {
            "analysis_component": "pooled_country_fixed_effect_binomial_model", "eligible": "true",
            "evidence": f"{pooled_pairs} matched pooled origins and all blocking validations passed",
            "caveat": "origins with no outcome variation cannot estimate finite fixed effects",
            "required_handling": "fit matched origins and report outcome-invariant exclusions",
        },
        {
            "analysis_component": "annual_paired_analysis", "eligible": "true",
            "evidence": f"{annual_pairs} matched country-year pairs; annual tables reconcile to pooled counts",
            "caveat": "coverage varies by origin and year",
            "required_handling": "use observed matched country-year pairs only",
        },
        {
            "analysis_component": "country_year_binomial_model", "eligible": "true",
            "evidence": f"{annual_pairs} matched country-year pairs over all configured years",
            "caveat": "repeated observations within origin country require dependence adjustment",
            "required_handling": "include country and year fixed effects; cluster standard errors by origin",
        },
        {
            "analysis_component": "zero_filled_composition_distance", "eligible": "false",
            "evidence": "destination-only origins exist and no source evidence establishes that absence means zero",
            "caveat": "zero filling could convert missing or unrepresented origins into invented observations",
            "required_handling": "skip Jensen-Shannon divergence and report the reason",
        },
    ]
    zero_policy = [
        {"status": "observed_positive_decisions", "zero_assignment_allowed": "false", "reason": "use the recorded positive decision count", "handling": "retain observed row"},
        {"status": "absent_country", "zero_assignment_allowed": "false", "reason": "absence is not documented as a true zero", "handling": "exclude from paired analyses; retain destination-specific observed rows"},
        {"status": "excluded_non_country_label", "zero_assignment_allowed": "false", "reason": "label is not an origin country", "handling": "exclude and audit"},
        {"status": "reviewed_non_m49_label", "zero_assignment_allowed": "false", "reason": "reviewed retained origin is observed, not missing", "handling": "retain unchanged where observed"},
        {"status": "suppressed_or_unresolved", "zero_assignment_allowed": "false", "reason": "zero cannot be inferred", "handling": "stop dependent analysis or exclude explicitly"},
    ]
    classifications.sort(key=lambda row: (row["scope"], str(row["year"]), row["destination_code"], row["country_or_label"], row["classification"]))
    pairs.sort(key=lambda row: (row["scope"], str(row["year"]), row["country"]))

    pair_summary: list[dict[str, Any]] = []
    scope_years = [("pooled", "")] + [("annual", str(year)) for year in config["years"]]
    for scope, year in scope_years:
        group = [row for row in pairs if row["scope"] == scope and str(row["year"]) == year]
        if not group:
            raise ValueError(f"missing pair coverage for {scope} {year}")
        matched = sum(row["included"] == 1 for row in group)
        au_only = sum(bool(row["au_decision_total"]) and not row["nz_decision_total"] for row in group)
        nz_only = sum(bool(row["nz_decision_total"]) and not row["au_decision_total"] for row in group)
        unmatched = len(group) - matched
        if unmatched != au_only + nz_only:
            raise ValueError(f"unmatched coverage does not reconcile for {scope} {year}")
        pair_summary.append({
            "scope": scope, "year": year, "union_origins": len(group),
            "matched_origins": matched, "unmatched_origins": unmatched,
            "au_only_origins": au_only, "nz_only_origins": nz_only,
            "matched_share": matched / len(group),
        })

    classification_summary: list[dict[str, Any]] = []
    classification_keys = sorted({
        (row["scope"], str(row["year"]), row["destination_code"], row["classification"])
        for row in classifications
    })
    for scope, year, destination_code, classification in classification_keys:
        group = [row for row in classifications if (
            row["scope"], str(row["year"]), row["destination_code"], row["classification"]
        ) == (scope, year, destination_code, classification)]
        classification_summary.append({
            "scope": scope, "year": year, "destination_code": destination_code,
            "classification": classification, "record_count": len(group),
            "decision_total": sum(int(row["decision_total"]) for row in group if row["decision_total"]),
        })

    outputs = {
        "classification": output_dir / "missingness_classification.csv",
        "decisions": output_dir / "comparability_decisions.csv",
        "pairs": output_dir / "pairwise_inclusion_exclusion.csv",
        "zero_policy": output_dir / "zero_assignment_policy.csv",
        "pair_summary": output_dir / "pairwise_coverage_summary.csv",
        "classification_summary": output_dir / "missingness_classification_summary.csv",
        "manifest": manifest_dir / "11_comparability.json",
    }
    write_csv(outputs["classification"], CLASSIFICATION_COLUMNS, classifications)
    write_csv(outputs["decisions"], DECISION_COLUMNS, decisions)
    write_csv(outputs["pairs"], PAIR_COLUMNS, pairs)
    write_csv(outputs["zero_policy"], ZERO_COLUMNS, zero_policy)
    write_csv(outputs["pair_summary"], PAIR_SUMMARY_COLUMNS, pair_summary)
    write_csv(outputs["classification_summary"], CLASSIFICATION_SUMMARY_COLUMNS, classification_summary)
    write_json(outputs["manifest"], {
        "module": "src.analysis_11_comparability", "status": "passed",
        "analysis_timestamp_utc": utc_timestamp(),
        "inputs": [{"path": display_path(path, project_root), "sha256": sha256(path)} for path in (config_path, coverage_path, issues_path, validation_checks_path)],
        "outputs": [{"name": name, "path": display_path(path, project_root), "sha256": sha256(path)} for name, path in outputs.items() if name != "manifest"],
        "summary": {"pooled_matched_origins": pooled_pairs, "matched_country_year_pairs": annual_pairs, "pair_summary_rows": len(pair_summary), "classification_summary_rows": len(classification_summary), "zero_filled_composition_distance_eligible": False},
    })
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "src/analysis_config.json")
    parser.add_argument("--coverage", type=Path, default=PROJECT_ROOT / "data/results/validation/country_coverage.csv")
    parser.add_argument("--issues", type=Path, default=PROJECT_ROOT / "data/results/validation/data_issues_and_exclusions.csv")
    parser.add_argument("--validation-checks", type=Path, default=PROJECT_ROOT / "data/results/validation/data_validation_checks.csv")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/results/validation")
    parser.add_argument("--manifest-dir", type=Path, default=PROJECT_ROOT / "data/results/manifests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = run(config_path=args.config, coverage_path=args.coverage, issues_path=args.issues, validation_checks_path=args.validation_checks, output_dir=args.output_dir, manifest_dir=args.manifest_dir)
    print("Comparability artifacts written:")
    for path in outputs.values():
        print(f"- {display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
