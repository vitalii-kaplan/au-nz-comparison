"""Compare matched AU-NZ country approval rates (Methods Section 4)."""

from __future__ import annotations

import argparse
import math
import random
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

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


INPUT_COLUMNS = {
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
}
DIFFERENCE_COLUMNS = [
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
    "rate_difference_percentage_points",
    "difference_direction",
    "meets_20_both",
    "meets_50_both",
]
SUMMARY_COLUMNS = [
    "period",
    "n_pairs",
    "n_nonzero",
    "n_positive",
    "n_negative",
    "n_zero",
    "mean_difference",
    "mean_ci_lower",
    "mean_ci_upper",
    "median_difference",
    "median_bootstrap_ci_lower",
    "median_bootstrap_ci_upper",
    "sample_sd",
    "q1",
    "q3",
    "iqr",
    "minimum",
    "maximum",
    "confidence_level",
    "bootstrap_replicates",
    "bootstrap_seed",
    "quantile_method",
]
TEST_COLUMNS = [
    "test_name",
    "role",
    "alternative",
    "n",
    "statistic",
    "positive_rank_sum",
    "negative_rank_sum",
    "degrees_of_freedom",
    "p_value",
    "p_value_method",
    "zero_policy",
]
BOOTSTRAP_COLUMNS = ["replicate", "median_difference"]


def regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    if a <= 0 or b <= 0 or not 0.0 <= x <= 1.0:
        raise ValueError("invalid incomplete-beta arguments")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0

    def continued_fraction(first: float, second: float, value: float) -> float:
        maximum_iterations = 300
        epsilon = 3.0e-14
        minimum = 1.0e-300
        qab = first + second
        qap = first + 1.0
        qam = first - 1.0
        c = 1.0
        d = 1.0 - qab * value / qap
        if abs(d) < minimum:
            d = minimum
        d = 1.0 / d
        result = d
        for iteration in range(1, maximum_iterations + 1):
            doubled = 2 * iteration
            numerator = iteration * (second - iteration) * value / (
                (qam + doubled) * (first + doubled)
            )
            d = 1.0 + numerator * d
            if abs(d) < minimum:
                d = minimum
            c = 1.0 + numerator / c
            if abs(c) < minimum:
                c = minimum
            d = 1.0 / d
            result *= d * c
            numerator = -(
                (first + iteration)
                * (qab + iteration)
                * value
                / ((first + doubled) * (qap + doubled))
            )
            d = 1.0 + numerator * d
            if abs(d) < minimum:
                d = minimum
            c = 1.0 + numerator / c
            if abs(c) < minimum:
                c = minimum
            d = 1.0 / d
            delta = d * c
            result *= delta
            if abs(delta - 1.0) < epsilon:
                return result
        raise ArithmeticError("incomplete-beta continued fraction did not converge")

    log_factor = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    factor = math.exp(log_factor)
    if x < (a + 1.0) / (a + b + 2.0):
        return factor * continued_fraction(a, b, x) / a
    return 1.0 - factor * continued_fraction(b, a, 1.0 - x) / b


def student_t_cdf(value: float, degrees_of_freedom: int) -> float:
    if degrees_of_freedom <= 0:
        raise ValueError("degrees of freedom must be positive")
    if value == 0.0:
        return 0.5
    x = degrees_of_freedom / (degrees_of_freedom + value * value)
    tail = 0.5 * regularized_incomplete_beta(degrees_of_freedom / 2.0, 0.5, x)
    return 1.0 - tail if value > 0 else tail


def student_t_ppf(probability: float, degrees_of_freedom: int) -> float:
    if not 0.5 < probability < 1.0:
        raise ValueError("this implementation requires 0.5 < probability < 1")
    lower = 0.0
    upper = 1.0
    while student_t_cdf(upper, degrees_of_freedom) < probability:
        upper *= 2.0
    for _ in range(100):
        midpoint = (lower + upper) / 2.0
        if student_t_cdf(midpoint, degrees_of_freedom) < probability:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def wilcoxon_signed_rank(differences: list[float]) -> dict[str, float | int]:
    nonzero = [value for value in differences if value != 0.0]
    if not nonzero:
        raise ValueError("Wilcoxon test requires a nonzero paired difference")
    ordered = sorted(enumerate(nonzero), key=lambda item: abs(item[1]))
    ranks = [0.0] * len(nonzero)
    tie_sizes: list[int] = []
    index = 0
    while index < len(ordered):
        end = index + 1
        absolute_value = abs(ordered[index][1])
        while end < len(ordered) and abs(ordered[end][1]) == absolute_value:
            end += 1
        average_rank = ((index + 1) + end) / 2.0
        for position in range(index, end):
            ranks[ordered[position][0]] = average_rank
        tie_sizes.append(end - index)
        index = end
    positive = sum(rank for rank, value in zip(ranks, nonzero) if value > 0)
    negative = sum(rank for rank, value in zip(ranks, nonzero) if value < 0)
    n = len(nonzero)
    expected = n * (n + 1) / 4.0
    variance = n * (n + 1) * (2 * n + 1) / 24.0
    variance -= sum(size**3 - size for size in tie_sizes) / 48.0
    if variance <= 0:
        raise ValueError("Wilcoxon variance is not positive")
    corrected_distance = max(0.0, abs(positive - expected) - 0.5)
    z_value = corrected_distance / math.sqrt(variance)
    p_value = math.erfc(z_value / math.sqrt(2.0))
    return {
        "n": n,
        "n_zero": len(differences) - n,
        "positive_rank_sum": positive,
        "negative_rank_sum": negative,
        "statistic": min(positive, negative),
        "z_value": z_value,
        "p_value": min(1.0, p_value),
    }


def validate_and_parse(path: Path, thresholds: list[int]) -> list[dict[str, Any]]:
    source = read_csv_rows(path)
    require_columns(path, source, INPUT_COLUMNS)
    if not source:
        raise ValueError(f"{path}: no matched observations")
    parsed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, row in enumerate(source, start=2):
        country = row["country"]
        if not country or country in seen:
            raise ValueError(f"{path}:{line_number}: empty or duplicate country")
        seen.add(country)
        values: dict[str, Any] = {**row}
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
        if not math.isclose(
            float(row["rate_difference_au_minus_nz"]),
            difference,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
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
    return parsed


def run(
    *,
    config_path: Path,
    input_path: Path,
    validation_checks_path: Path,
    output_dir: Path,
    manifest_dir: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Path]:
    config = read_json(config_path)
    if config.get("rate_difference_direction") != "AU - NZ":
        raise ValueError("Rate-difference direction must be AU - NZ")
    confidence = float(config["confidence_level"])
    if confidence != 0.95:
        raise ValueError("Matched comparison currently requires 95% confidence")
    thresholds = sorted(int(value) for value in config["small_denominator_thresholds"])
    if thresholds != [20, 50]:
        raise ValueError("Small-denominator thresholds must be [20, 50]")
    seed = int(config["bootstrap_seed"])
    replicates = int(config["bootstrap_replicates"])
    if replicates <= 0:
        raise ValueError("Bootstrap replicate count must be positive")
    require_passed_blocking_checks(validation_checks_path)
    rows = validate_and_parse(input_path, thresholds)
    differences = [float(row["rate_difference_au_minus_nz"]) for row in rows]
    n = len(differences)
    mean = statistics.fmean(differences)
    sd = sample_sd(differences)
    standard_error = sd / math.sqrt(n)
    degrees_of_freedom = n - 1
    critical = student_t_ppf(0.5 + confidence / 2.0, degrees_of_freedom)
    t_statistic = mean / standard_error if standard_error else 0.0
    t_p_value = regularized_incomplete_beta(
        degrees_of_freedom / 2.0,
        0.5,
        degrees_of_freedom / (degrees_of_freedom + t_statistic * t_statistic),
    )

    generator = random.Random(seed)
    bootstrap_medians = [
        quantile_type7((generator.choice(differences) for _ in range(n)), 0.5)
        for _ in range(replicates)
    ]
    alpha = 1.0 - confidence
    bootstrap_lower = quantile_type7(bootstrap_medians, alpha / 2.0)
    bootstrap_upper = quantile_type7(bootstrap_medians, 1.0 - alpha / 2.0)
    q1 = quantile_type7(differences, 0.25)
    median = quantile_type7(differences, 0.5)
    q3 = quantile_type7(differences, 0.75)
    signs = Counter(row["difference_direction"] for row in rows)
    wilcoxon = wilcoxon_signed_rank(differences)
    period_values = {str(row["period"]) for row in rows}
    if len(period_values) != 1:
        raise ValueError(f"{input_path}: inconsistent periods")
    period = period_values.pop()

    summary_rows = [
        {
            "period": period,
            "n_pairs": n,
            "n_nonzero": int(wilcoxon["n"]),
            "n_positive": signs["AU higher"],
            "n_negative": signs["NZ higher"],
            "n_zero": signs["equal"],
            "mean_difference": mean,
            "mean_ci_lower": mean - critical * standard_error,
            "mean_ci_upper": mean + critical * standard_error,
            "median_difference": median,
            "median_bootstrap_ci_lower": bootstrap_lower,
            "median_bootstrap_ci_upper": bootstrap_upper,
            "sample_sd": sd,
            "q1": q1,
            "q3": q3,
            "iqr": q3 - q1,
            "minimum": min(differences),
            "maximum": max(differences),
            "confidence_level": confidence,
            "bootstrap_replicates": replicates,
            "bootstrap_seed": seed,
            "quantile_method": "Hyndman-Fan type 7",
        }
    ]
    test_rows = [
        {
            "test_name": "Wilcoxon signed-rank",
            "role": "primary",
            "alternative": "two-sided",
            "n": wilcoxon["n"],
            "statistic": wilcoxon["statistic"],
            "positive_rank_sum": wilcoxon["positive_rank_sum"],
            "negative_rank_sum": wilcoxon["negative_rank_sum"],
            "degrees_of_freedom": "",
            "p_value": wilcoxon["p_value"],
            "p_value_method": "normal approximation with tie adjustment and continuity correction",
            "zero_policy": "discard zero differences (Wilcox method)",
        },
        {
            "test_name": "Paired t-test",
            "role": "sensitivity",
            "alternative": "two-sided",
            "n": n,
            "statistic": t_statistic,
            "positive_rank_sum": "",
            "negative_rank_sum": "",
            "degrees_of_freedom": degrees_of_freedom,
            "p_value": max(0.0, min(1.0, t_p_value)),
            "p_value_method": "Student t distribution",
            "zero_policy": "retain zero differences",
        },
    ]
    bootstrap_rows = [
        {"replicate": index, "median_difference": value}
        for index, value in enumerate(bootstrap_medians, start=1)
    ]

    outputs = {
        "matched_differences": output_dir / "matched_country_differences.csv",
        "difference_summary": output_dir / "matched_difference_summary.csv",
        "test_results": output_dir / "paired_test_results.csv",
        "bootstrap_distribution": output_dir / "median_bootstrap_distribution.csv",
        "manifest": manifest_dir / "04_matched_comparison.json",
    }
    write_csv(outputs["matched_differences"], DIFFERENCE_COLUMNS, rows)
    write_csv(outputs["difference_summary"], SUMMARY_COLUMNS, summary_rows)
    write_csv(outputs["test_results"], TEST_COLUMNS, test_rows)
    write_csv(outputs["bootstrap_distribution"], BOOTSTRAP_COLUMNS, bootstrap_rows)

    manifest_outputs = []
    for name, path in outputs.items():
        if name == "manifest":
            continue
        manifest_outputs.append(
            {"name": name, "path": display_path(path, project_root), "sha256": sha256(path)}
        )
    write_json(
        outputs["manifest"],
        {
            "module": "src.analysis_04_matched_comparison",
            "status": "passed",
            "analysis_timestamp_utc": utc_timestamp(),
            "configuration": {
                "difference_direction": "AU - NZ",
                "confidence_level": confidence,
                "bootstrap_seed": seed,
                "bootstrap_replicates": replicates,
                "zero_policy": "discard zero differences for Wilcoxon only",
            },
            "inputs": [
                {"path": display_path(input_path, project_root), "sha256": sha256(input_path)},
                {"path": display_path(validation_checks_path, project_root), "sha256": sha256(validation_checks_path)},
                {"path": display_path(config_path, project_root), "sha256": sha256(config_path)},
            ],
            "outputs": manifest_outputs,
            "summary": summary_rows[0],
            "tests": test_rows,
        },
    )
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "src/analysis_config.json")
    parser.add_argument(
        "--input",
        type=Path,
        default=PROJECT_ROOT / "data/prepared/comparison/matched_country_2022-2025.csv",
    )
    parser.add_argument(
        "--validation-checks",
        type=Path,
        default=PROJECT_ROOT / "data/results/validation/data_validation_checks.csv",
    )
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/results/paired")
    parser.add_argument("--manifest-dir", type=Path, default=PROJECT_ROOT / "data/results/manifests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = run(
        config_path=args.config,
        input_path=args.input,
        validation_checks_path=args.validation_checks,
        output_dir=args.output_dir,
        manifest_dir=args.manifest_dir,
    )
    print("Matched-country comparison artifacts written:")
    for path in outputs.values():
        print(f"- {display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
