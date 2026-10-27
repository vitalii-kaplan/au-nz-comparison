"""Run pre-specified threshold and method sensitivity analyses (Section 10)."""

from __future__ import annotations

import argparse
import math
import random
import statistics
from pathlib import Path
from typing import Any

from .analysis_04_matched_comparison import (
    regularized_incomplete_beta,
    student_t_ppf,
    validate_and_parse,
    wilcoxon_signed_rank,
)
from .analysis_05_concordance import (
    average_ranks,
    correlation_p_value,
    fisher_z_interval,
    pearson_correlation,
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


SENSITIVITY_COLUMNS = [
    "method", "population", "threshold_min_decisions_each", "n", "effect_name",
    "effect_estimate", "ci_lower", "ci_upper", "confidence_level", "p_value",
    "q_value", "direction", "interval_excludes_null", "significant_0_05",
    "ci_method", "p_value_method",
]
COUNT_COLUMNS = [
    "population", "threshold_min_decisions_each", "included_pairs", "excluded_pairs",
    "included_au_decisions", "included_nz_decisions", "minimum_au_decisions",
    "minimum_nz_decisions",
]
MODEL_COLUMNS = [
    "model", "analysis_unit", "n_countries", "n_matched_units", "n_decisions",
    "effect_name", "effect_estimate", "ci_lower", "ci_upper", "standard_error",
    "direction", "interval_excludes_null", "difference_from_pooled_model",
]
STABILITY_COLUMNS = [
    "comparison_family", "method", "levels_compared", "direction_stable",
    "interval_exclusion_stable", "significance_stable", "minimum_effect",
    "maximum_effect", "absolute_effect_range", "interpretation",
]


def bootstrap_interval(
    x: list[float], y: list[float] | None, *, statistic: str,
    replicates: int, seed: int, confidence: float,
) -> tuple[float, float, int]:
    generator = random.Random(seed)
    values: list[float] = []
    n = len(x)
    for _ in range(replicates):
        indices = [generator.randrange(n) for _ in range(n)]
        if statistic == "median":
            values.append(quantile_type7((x[index] for index in indices), 0.5))
        elif statistic == "spearman":
            if y is None:
                raise ValueError("Spearman bootstrap requires two variables")
            bx = [x[index] for index in indices]
            by = [y[index] for index in indices]
            try:
                values.append(pearson_correlation(average_ranks(bx), average_ranks(by)))
            except ValueError:
                continue
        else:
            raise ValueError(f"unsupported bootstrap statistic: {statistic}")
    if not values:
        raise ValueError("all bootstrap resamples were degenerate")
    alpha = 1.0 - confidence
    return (quantile_type7(values, alpha / 2.0),
            quantile_type7(values, 1.0 - alpha / 2.0), len(values))


def direction(value: float) -> str:
    return "positive" if value > 0 else "negative" if value < 0 else "null"


def result_row(
    *, method: str, threshold: int, n: int, effect_name: str, estimate: float,
    lower: float, upper: float, confidence: float, p_value: float,
    ci_method: str, p_value_method: str,
) -> dict[str, Any]:
    return {
        "method": method, "population": "pooled matched origins",
        "threshold_min_decisions_each": threshold, "n": n, "effect_name": effect_name,
        "effect_estimate": estimate, "ci_lower": lower, "ci_upper": upper,
        "confidence_level": confidence, "p_value": p_value, "q_value": "",
        "direction": direction(estimate),
        "interval_excludes_null": str(lower > 0 or upper < 0).lower(),
        "significant_0_05": str(p_value < 0.05).lower(), "ci_method": ci_method,
        "p_value_method": p_value_method,
    }


def analyze_population(
    rows: list[dict[str, Any]], *, threshold: int, confidence: float,
    replicates: int, seed: int,
) -> list[dict[str, Any]]:
    differences = [float(row["rate_difference_au_minus_nz"]) for row in rows]
    au = [float(row["au_approval_rate"]) for row in rows]
    nz = [float(row["nz_approval_rate"]) for row in rows]
    n = len(rows)
    if n < 4:
        raise ValueError("sensitivity population requires at least four pairs")
    sd = sample_sd(differences)
    se = sd / math.sqrt(n)
    df = n - 1
    critical = student_t_ppf(0.5 + confidence / 2.0, df)
    mean = statistics.fmean(differences)
    t_statistic = mean / se if se else 0.0
    t_p = regularized_incomplete_beta(df / 2.0, 0.5, df / (df + t_statistic**2))
    median = quantile_type7(differences, 0.5)
    median_ci = bootstrap_interval(differences, None, statistic="median",
                                   replicates=replicates, seed=seed, confidence=confidence)
    wilcoxon = wilcoxon_signed_rank(differences)
    pearson = pearson_correlation(au, nz)
    pearson_ci = fisher_z_interval(pearson, n, confidence)
    spearman = pearson_correlation(average_ranks(au), average_ranks(nz))
    spearman_ci = bootstrap_interval(au, nz, statistic="spearman",
                                     replicates=replicates, seed=seed,
                                     confidence=confidence)
    return [
        result_row(method="Paired t-test", threshold=threshold, n=n,
                   effect_name="mean AU-minus-NZ rate difference", estimate=mean,
                   lower=mean - critical * se, upper=mean + critical * se,
                   confidence=confidence, p_value=t_p, ci_method="Student t interval",
                   p_value_method="Student t distribution"),
        result_row(method="Wilcoxon signed-rank", threshold=threshold, n=int(wilcoxon["n"]),
                   effect_name="median AU-minus-NZ rate difference", estimate=median,
                   lower=median_ci[0], upper=median_ci[1], confidence=confidence,
                   p_value=float(wilcoxon["p_value"]),
                   ci_method=f"percentile bootstrap ({median_ci[2]} replicates)",
                   p_value_method="normal approximation with tie adjustment and continuity correction"),
        result_row(method="Pearson correlation", threshold=threshold, n=n,
                   effect_name="approval-rate correlation", estimate=pearson,
                   lower=pearson_ci[0], upper=pearson_ci[1], confidence=confidence,
                   p_value=correlation_p_value(pearson, n),
                   ci_method="Fisher z transformation",
                   p_value_method="t distribution with n-2 degrees of freedom"),
        result_row(method="Spearman correlation", threshold=threshold, n=n,
                   effect_name="approval-rate rank correlation", estimate=spearman,
                   lower=spearman_ci[0], upper=spearman_ci[1], confidence=confidence,
                   p_value=correlation_p_value(spearman, n),
                   ci_method=f"percentile bootstrap ({spearman_ci[2]} replicates)",
                   p_value_method="t approximation applied to rank correlation"),
    ]


def stability_rows(sensitivity: list[dict[str, Any]], models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    thresholds = sorted({int(row["threshold_min_decisions_each"]) for row in sensitivity})
    threshold_label = ", ".join(str(value) for value in thresholds)
    for method in ("Paired t-test", "Wilcoxon signed-rank", "Pearson correlation", "Spearman correlation"):
        rows = [row for row in sensitivity if row["method"] == method]
        estimates = [float(row["effect_estimate"]) for row in rows]
        direction_stable = len({row["direction"] for row in rows}) == 1
        interval_stable = len({row["interval_excludes_null"] for row in rows}) == 1
        significance_stable = len({row["significant_0_05"] for row in rows}) == 1
        output.append({
            "comparison_family": "denominator thresholds", "method": method,
            "levels_compared": f"{threshold_label} minimum decisions in each destination",
            "direction_stable": str(direction_stable).lower(),
            "interval_exclusion_stable": str(interval_stable).lower(),
            "significance_stable": str(significance_stable).lower(),
            "minimum_effect": min(estimates), "maximum_effect": max(estimates),
            "absolute_effect_range": max(estimates) - min(estimates),
            "interpretation": "descriptive stability flag; not a preferred-result rule",
        })
    model_estimates = [float(row["effect_estimate"]) for row in models]
    output.append({
        "comparison_family": "binomial model specification",
        "method": "standardized AU-minus-NZ probability contrast",
        "levels_compared": "pooled country FE; country and year FE",
        "direction_stable": str(len({row["direction"] for row in models}) == 1).lower(),
        "interval_exclusion_stable": str(len({row["interval_excludes_null"] for row in models}) == 1).lower(),
        "significance_stable": "not_applicable",
        "minimum_effect": min(model_estimates), "maximum_effect": max(model_estimates),
        "absolute_effect_range": max(model_estimates) - min(model_estimates),
        "interpretation": "comparison of pre-specified adjusted model contrasts",
    })
    return output


def run(
    *, config_path: Path, matched_path: Path, validation_checks_path: Path,
    comparability_path: Path, model_contrasts_path: Path, model_fit_path: Path,
    temporal_summary_path: Path, output_dir: Path, manifest_dir: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Path]:
    config = read_json(config_path)
    require_passed_blocking_checks(validation_checks_path)
    if not read_gate(comparability_path).get("pooled_paired_analysis", False):
        raise ValueError("comparability gate rejected pooled paired analysis")
    thresholds = [int(value) for value in config["sensitivity_denominator_thresholds"]]
    if thresholds != [0, 20, 50, 100]:
        raise ValueError("Section 10 requires thresholds 0, 20, 50, and 100")
    rows = validate_and_parse(matched_path, thresholds[1:])
    confidence = float(config["confidence_level"])
    replicates = int(config["bootstrap_replicates"])
    base_seed = int(config["bootstrap_seed"])
    sensitivity: list[dict[str, Any]] = []
    counts: list[dict[str, Any]] = []
    for threshold in thresholds:
        included = [row for row in rows if threshold == 0 or (
            int(row["au_decision_total"]) >= threshold and int(row["nz_decision_total"]) >= threshold
        )]
        sensitivity.extend(analyze_population(
            included, threshold=threshold, confidence=confidence,
            replicates=replicates, seed=base_seed + threshold * 10,
        ))
        counts.append({
            "population": "pooled matched origins", "threshold_min_decisions_each": threshold,
            "included_pairs": len(included), "excluded_pairs": len(rows) - len(included),
            "included_au_decisions": sum(int(row["au_decision_total"]) for row in included),
            "included_nz_decisions": sum(int(row["nz_decision_total"]) for row in included),
            "minimum_au_decisions": min(int(row["au_decision_total"]) for row in included),
            "minimum_nz_decisions": min(int(row["nz_decision_total"]) for row in included),
        })

    contrast_rows = read_csv_rows(model_contrasts_path)
    fit_rows = read_csv_rows(model_fit_path)
    require_columns(model_contrasts_path, contrast_rows, {
        "model", "au_minus_nz_probability_contrast", "contrast_standard_error",
        "contrast_ci_lower", "contrast_ci_upper",
    })
    require_columns(model_fit_path, fit_rows, {"model", "countries", "matched_units", "decisions"})
    fit_by_model = {row["model"]: row for row in fit_rows}
    pooled_estimate = next(float(row["au_minus_nz_probability_contrast"])
                           for row in contrast_rows if row["model"] == "pooled_country_fixed_effects")
    models: list[dict[str, Any]] = []
    units = {"pooled_country_fixed_effects": "matched origin",
             "country_year_fixed_effects": "matched origin-year"}
    for row in contrast_rows:
        model = row["model"]
        fit = fit_by_model[model]
        estimate = float(row["au_minus_nz_probability_contrast"])
        lower = float(row["contrast_ci_lower"])
        upper = float(row["contrast_ci_upper"])
        models.append({
            "model": model, "analysis_unit": units[model],
            "n_countries": fit["countries"], "n_matched_units": fit["matched_units"],
            "n_decisions": fit["decisions"],
            "effect_name": "standardized AU-minus-NZ probability contrast",
            "effect_estimate": estimate, "ci_lower": lower, "ci_upper": upper,
            "standard_error": row["contrast_standard_error"], "direction": direction(estimate),
            "interval_excludes_null": str(lower > 0 or upper < 0).lower(),
            "difference_from_pooled_model": estimate - pooled_estimate,
        })
    temporal_rows = read_csv_rows(temporal_summary_path)
    require_columns(temporal_summary_path, temporal_rows, {"year", "mean_difference", "median_difference"})
    if len(temporal_rows) != len(config["years"]):
        raise ValueError("temporal summary does not cover every configured year")
    stability = stability_rows(sensitivity, models)

    outputs = {
        "sensitivity_analysis_summary": output_dir / "sensitivity_analysis_summary.csv",
        "threshold_population_counts": output_dir / "threshold_population_counts.csv",
        "model_sensitivity_comparison": output_dir / "model_sensitivity_comparison.csv",
        "result_stability_flags": output_dir / "result_stability_flags.csv",
        "manifest": manifest_dir / "10_sensitivity.json",
    }
    write_csv(outputs["sensitivity_analysis_summary"], SENSITIVITY_COLUMNS, sensitivity)
    write_csv(outputs["threshold_population_counts"], COUNT_COLUMNS, counts)
    write_csv(outputs["model_sensitivity_comparison"], MODEL_COLUMNS, models)
    write_csv(outputs["result_stability_flags"], STABILITY_COLUMNS, stability)
    input_paths = (config_path, matched_path, validation_checks_path, comparability_path,
                   model_contrasts_path, model_fit_path, temporal_summary_path)
    write_json(outputs["manifest"], {
        "module": "src.analysis_10_sensitivity", "status": "passed",
        "analysis_timestamp_utc": utc_timestamp(),
        "configuration": {"thresholds": thresholds, "confidence_level": confidence,
                          "bootstrap_replicates": replicates, "bootstrap_seed": base_seed,
                          "selection_policy": "pre-specified; no significance search"},
        "inputs": [{"path": display_path(path, project_root), "sha256": sha256(path)} for path in input_paths],
        "outputs": [{"name": name, "path": display_path(path, project_root), "sha256": sha256(path)}
                    for name, path in outputs.items() if name != "manifest"],
        "row_counts": {"sensitivity_analysis_summary": len(sensitivity),
                       "threshold_population_counts": len(counts),
                       "model_sensitivity_comparison": len(models),
                       "result_stability_flags": len(stability)},
        "interpretation_warning": "Sensitivity flags describe stability and do not select a preferred result.",
    })
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "src/analysis_config.json")
    parser.add_argument("--matched", type=Path, default=PROJECT_ROOT / "data/prepared/comparison/matched_country_2022-2025.csv")
    parser.add_argument("--validation-checks", type=Path, default=PROJECT_ROOT / "data/results/validation/data_validation_checks.csv")
    parser.add_argument("--comparability", type=Path, default=PROJECT_ROOT / "data/results/validation/comparability_decisions.csv")
    parser.add_argument("--model-contrasts", type=Path, default=PROJECT_ROOT / "data/results/models/destination_probability_contrasts.csv")
    parser.add_argument("--model-fit", type=Path, default=PROJECT_ROOT / "data/results/models/model_fit_statistics.csv")
    parser.add_argument("--temporal-summary", type=Path, default=PROJECT_ROOT / "data/results/temporal/annual_matched_difference_summary.csv")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/results/robustness")
    parser.add_argument("--manifest-dir", type=Path, default=PROJECT_ROOT / "data/results/manifests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = run(config_path=args.config, matched_path=args.matched,
                  validation_checks_path=args.validation_checks, comparability_path=args.comparability,
                  model_contrasts_path=args.model_contrasts, model_fit_path=args.model_fit,
                  temporal_summary_path=args.temporal_summary, output_dir=args.output_dir,
                  manifest_dir=args.manifest_dir)
    print("Sensitivity artifacts written:")
    for path in outputs.values():
        print(f"- {display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
