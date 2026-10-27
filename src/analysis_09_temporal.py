"""Describe annual destination and matched-country differences (Section 9)."""

from __future__ import annotations

import argparse
import math
import random
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from .analysis_04_matched_comparison import (
    regularized_incomplete_beta,
    student_t_ppf,
    wilcoxon_signed_rank,
)
from .analysis_07_binomial_regression import read_gate
from .analysis_common import (
    PROJECT_ROOT,
    display_path,
    quantile_type7,
    read_csv_rows,
    read_json,
    require_columns,
    require_passed_blocking_checks,
    sample_sd,
    sha256,
    utc_timestamp,
    write_csv,
    write_json,
)


ANNUAL_SUMMARY_COLUMNS = [
    "year", "destination_code", "destination_country", "represented_countries",
    "number_approved", "number_declined", "decision_total", "aggregate_approval_rate",
    "median_country_approval_rate", "country_rate_q1", "country_rate_q3",
    "country_rate_iqr", "median_country_decisions",
]
MATCHED_DIFFERENCE_COLUMNS = [
    "country", "year", "au_number_approved", "au_number_declined",
    "au_decision_total", "au_approval_rate", "nz_number_approved",
    "nz_number_declined", "nz_decision_total", "nz_approval_rate",
    "rate_difference_au_minus_nz", "rate_difference_percentage_points",
    "difference_direction", "meets_20_both", "meets_50_both",
]
MATCHED_SUMMARY_COLUMNS = [
    "year", "n_pairs", "n_nonzero", "n_positive", "n_negative", "n_zero",
    "mean_difference", "mean_ci_lower", "mean_ci_upper", "median_difference",
    "median_bootstrap_ci_lower", "median_bootstrap_ci_upper", "sample_sd", "q1",
    "q3", "iqr", "minimum", "maximum", "wilcoxon_statistic",
    "wilcoxon_p_value", "paired_t_statistic", "paired_t_degrees_of_freedom",
    "paired_t_p_value", "confidence_level", "bootstrap_replicates", "bootstrap_seed",
]
DISTRIBUTION_COLUMNS = [
    "year", "destination_code", "destination_country", "measure", "n", "minimum",
    "q1", "median", "q3", "maximum", "mean", "sample_sd", "iqr",
]


def parse_annual_destination(path: Path, years: list[int]) -> list[dict[str, Any]]:
    rows = read_csv_rows(path)
    require_columns(path, rows, {
        "destination_code", "destination_country", "year", "country",
        "number_approved", "number_declined", "decision_total", "approval_rate",
    })
    parsed: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()
    for line_number, row in enumerate(rows, start=2):
        code = row["destination_code"]
        year = int(row["year"])
        key = (code, year, row["country"])
        if code not in {"AU", "NZ"} or year not in years or not row["country"] or key in seen:
            raise ValueError(f"{path}:{line_number}: invalid or duplicate annual key")
        seen.add(key)
        approved = int(row["number_approved"])
        declined = int(row["number_declined"])
        total = int(row["decision_total"])
        rate = float(row["approval_rate"])
        if min(approved, declined) < 0 or total <= 0 or approved + declined != total:
            raise ValueError(f"{path}:{line_number}: invalid decision counts")
        if not math.isclose(rate, approved / total, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError(f"{path}:{line_number}: approval rate does not reconcile")
        parsed.append({**row, "year": year, "number_approved": approved,
                       "number_declined": declined, "decision_total": total,
                       "approval_rate": rate})
    expected = {(code, year) for code in ("AU", "NZ") for year in years}
    if {(row["destination_code"], row["year"]) for row in parsed} != expected:
        raise ValueError(f"{path}: incomplete destination-year coverage")
    return parsed


def parse_matched_annual(path: Path, years: list[int], thresholds: list[int]) -> list[dict[str, Any]]:
    rows = read_csv_rows(path)
    require_columns(path, rows, {
        "country", "year", "au_number_approved", "au_number_declined",
        "au_decision_total", "au_approval_rate", "nz_number_approved",
        "nz_number_declined", "nz_decision_total", "nz_approval_rate",
        "rate_difference_au_minus_nz",
    })
    parsed: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for line_number, row in enumerate(rows, start=2):
        year = int(row["year"])
        key = (row["country"], year)
        if not row["country"] or year not in years or key in seen:
            raise ValueError(f"{path}:{line_number}: invalid or duplicate matched key")
        seen.add(key)
        values: dict[str, Any] = {**row, "year": year}
        for prefix in ("au", "nz"):
            approved = int(row[f"{prefix}_number_approved"])
            declined = int(row[f"{prefix}_number_declined"])
            total = int(row[f"{prefix}_decision_total"])
            rate = float(row[f"{prefix}_approval_rate"])
            if min(approved, declined) < 0 or total <= 0 or approved + declined != total:
                raise ValueError(f"{path}:{line_number}: invalid {prefix.upper()} counts")
            if not math.isclose(rate, approved / total, rel_tol=0.0, abs_tol=1e-15):
                raise ValueError(f"{path}:{line_number}: invalid {prefix.upper()} rate")
            values[f"{prefix}_number_approved"] = approved
            values[f"{prefix}_number_declined"] = declined
            values[f"{prefix}_decision_total"] = total
            values[f"{prefix}_approval_rate"] = rate
        difference = values["au_approval_rate"] - values["nz_approval_rate"]
        if not math.isclose(float(row["rate_difference_au_minus_nz"]), difference,
                            rel_tol=0.0, abs_tol=1e-15):
            raise ValueError(f"{path}:{line_number}: invalid AU-minus-NZ difference")
        values["rate_difference_au_minus_nz"] = difference
        values["rate_difference_percentage_points"] = difference * 100.0
        values["difference_direction"] = (
            "AU higher" if difference > 0 else "NZ higher" if difference < 0 else "equal"
        )
        for threshold in thresholds:
            values[f"meets_{threshold}_both"] = int(
                values["au_decision_total"] >= threshold
                and values["nz_decision_total"] >= threshold
            )
        parsed.append(values)
    if {row["year"] for row in parsed} != set(years):
        raise ValueError(f"{path}: incomplete matched year coverage")
    return parsed


def distribution_summary(values: list[float]) -> dict[str, float | int]:
    if len(values) < 2:
        raise ValueError("distribution summary requires at least two observations")
    q1 = quantile_type7(values, 0.25)
    q3 = quantile_type7(values, 0.75)
    return {
        "n": len(values), "minimum": min(values), "q1": q1,
        "median": quantile_type7(values, 0.5), "q3": q3, "maximum": max(values),
        "mean": statistics.fmean(values), "sample_sd": sample_sd(values), "iqr": q3 - q1,
    }


def summarize_differences(
    differences: list[float], *, year: int, confidence: float,
    bootstrap_replicates: int, bootstrap_seed: int,
) -> dict[str, Any]:
    if len(differences) < 2:
        raise ValueError("paired-difference summary requires at least two pairs")
    n = len(differences)
    mean = statistics.fmean(differences)
    sd = sample_sd(differences)
    se = sd / math.sqrt(n)
    df = n - 1
    critical = student_t_ppf(0.5 + confidence / 2.0, df)
    t_statistic = mean / se if se else 0.0
    t_p = regularized_incomplete_beta(df / 2.0, 0.5, df / (df + t_statistic**2))
    wilcoxon = wilcoxon_signed_rank(differences)
    generator = random.Random(bootstrap_seed)
    medians = [
        quantile_type7((generator.choice(differences) for _ in range(n)), 0.5)
        for _ in range(bootstrap_replicates)
    ]
    alpha = 1.0 - confidence
    q1 = quantile_type7(differences, 0.25)
    q3 = quantile_type7(differences, 0.75)
    signs = Counter("positive" if value > 0 else "negative" if value < 0 else "zero"
                    for value in differences)
    return {
        "year": year, "n_pairs": n, "n_nonzero": wilcoxon["n"],
        "n_positive": signs["positive"], "n_negative": signs["negative"],
        "n_zero": signs["zero"], "mean_difference": mean,
        "mean_ci_lower": mean - critical * se, "mean_ci_upper": mean + critical * se,
        "median_difference": quantile_type7(differences, 0.5),
        "median_bootstrap_ci_lower": quantile_type7(medians, alpha / 2.0),
        "median_bootstrap_ci_upper": quantile_type7(medians, 1.0 - alpha / 2.0),
        "sample_sd": sd, "q1": q1, "q3": q3, "iqr": q3 - q1,
        "minimum": min(differences), "maximum": max(differences),
        "wilcoxon_statistic": wilcoxon["statistic"],
        "wilcoxon_p_value": wilcoxon["p_value"], "paired_t_statistic": t_statistic,
        "paired_t_degrees_of_freedom": df, "paired_t_p_value": t_p,
        "confidence_level": confidence, "bootstrap_replicates": bootstrap_replicates,
        "bootstrap_seed": bootstrap_seed,
    }


def run(
    *, config_path: Path, destination_year_path: Path, matched_year_path: Path,
    validation_checks_path: Path, comparability_path: Path, output_dir: Path,
    manifest_dir: Path, project_root: Path = PROJECT_ROOT,
) -> dict[str, Path]:
    config = read_json(config_path)
    years = [int(value) for value in config["years"]]
    thresholds = sorted(int(value) for value in config["small_denominator_thresholds"])
    if thresholds != [20, 50] or config.get("rate_difference_direction") != "AU - NZ":
        raise ValueError("Section 9 requires thresholds [20, 50] and AU - NZ direction")
    require_passed_blocking_checks(validation_checks_path)
    if not read_gate(comparability_path).get("annual_paired_analysis", False):
        raise ValueError("comparability gate rejected annual paired analysis")
    destinations = parse_annual_destination(destination_year_path, years)
    matched = parse_matched_annual(matched_year_path, years, thresholds)
    confidence = float(config["confidence_level"])
    replicates = int(config["bootstrap_replicates"])
    base_seed = int(config["bootstrap_seed"])

    annual_summary: list[dict[str, Any]] = []
    distribution_rows: list[dict[str, Any]] = []
    for year in years:
        for code in ("AU", "NZ"):
            group = [row for row in destinations if row["year"] == year and row["destination_code"] == code]
            approved = sum(row["number_approved"] for row in group)
            declined = sum(row["number_declined"] for row in group)
            total = approved + declined
            rates = [row["approval_rate"] for row in group]
            decisions = [float(row["decision_total"]) for row in group]
            rate_stats = distribution_summary(rates)
            annual_summary.append({
                "year": year, "destination_code": code,
                "destination_country": group[0]["destination_country"],
                "represented_countries": len(group), "number_approved": approved,
                "number_declined": declined, "decision_total": total,
                "aggregate_approval_rate": approved / total,
                "median_country_approval_rate": rate_stats["median"],
                "country_rate_q1": rate_stats["q1"], "country_rate_q3": rate_stats["q3"],
                "country_rate_iqr": rate_stats["iqr"],
                "median_country_decisions": quantile_type7(decisions, 0.5),
            })
            for measure, values in (("approval_rate", rates), ("decision_total", decisions)):
                distribution_rows.append({
                    "year": year, "destination_code": code,
                    "destination_country": group[0]["destination_country"],
                    "measure": measure, **distribution_summary(values),
                })

    matched_summary = []
    for year in years:
        differences = [row["rate_difference_au_minus_nz"] for row in matched if row["year"] == year]
        matched_summary.append(summarize_differences(
            differences, year=year, confidence=confidence,
            bootstrap_replicates=replicates, bootstrap_seed=base_seed + year,
        ))
    matched_output = [{column: row[column] for column in MATCHED_DIFFERENCE_COLUMNS} for row in matched]

    outputs = {
        "annual_destination_summary": output_dir / "annual_destination_summary.csv",
        "annual_matched_difference_summary": output_dir / "annual_matched_difference_summary.csv",
        "matched_country_year_differences": output_dir / "matched_country_year_differences.csv",
        "annual_distribution_statistics": output_dir / "annual_distribution_statistics.csv",
        "manifest": manifest_dir / "09_temporal.json",
    }
    write_csv(outputs["annual_destination_summary"], ANNUAL_SUMMARY_COLUMNS, annual_summary)
    write_csv(outputs["annual_matched_difference_summary"], MATCHED_SUMMARY_COLUMNS, matched_summary)
    write_csv(outputs["matched_country_year_differences"], MATCHED_DIFFERENCE_COLUMNS, matched_output)
    write_csv(outputs["annual_distribution_statistics"], DISTRIBUTION_COLUMNS, distribution_rows)
    input_paths = (config_path, destination_year_path, matched_year_path,
                   validation_checks_path, comparability_path)
    write_json(outputs["manifest"], {
        "module": "src.analysis_09_temporal", "status": "passed",
        "analysis_timestamp_utc": utc_timestamp(),
        "configuration": {"years": years, "difference_direction": "AU - NZ",
                          "confidence_level": confidence, "bootstrap_replicates": replicates,
                          "bootstrap_seed_rule": "analysis seed plus calendar year"},
        "inputs": [{"path": display_path(path, project_root), "sha256": sha256(path)} for path in input_paths],
        "outputs": [{"name": name, "path": display_path(path, project_root), "sha256": sha256(path)}
                    for name, path in outputs.items() if name != "manifest"],
        "row_counts": {"annual_destination_summary": len(annual_summary),
                       "annual_matched_difference_summary": len(matched_summary),
                       "matched_country_year_differences": len(matched_output),
                       "annual_distribution_statistics": len(distribution_rows)},
        "interpretation_warning": "Annual results are descriptive or associational and use observed matched pairs only.",
    })
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "src/analysis_config.json")
    parser.add_argument("--destination-year", type=Path, default=PROJECT_ROOT / "data/prepared/comparison/destination_country_year.csv")
    parser.add_argument("--matched-year", type=Path, default=PROJECT_ROOT / "data/prepared/comparison/matched_country_year.csv")
    parser.add_argument("--validation-checks", type=Path, default=PROJECT_ROOT / "data/results/validation/data_validation_checks.csv")
    parser.add_argument("--comparability", type=Path, default=PROJECT_ROOT / "data/results/validation/comparability_decisions.csv")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/results/temporal")
    parser.add_argument("--manifest-dir", type=Path, default=PROJECT_ROOT / "data/results/manifests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = run(config_path=args.config, destination_year_path=args.destination_year,
                  matched_year_path=args.matched_year, validation_checks_path=args.validation_checks,
                  comparability_path=args.comparability, output_dir=args.output_dir,
                  manifest_dir=args.manifest_dir)
    print("Temporal artifacts written:")
    for path in outputs.values():
        print(f"- {display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
