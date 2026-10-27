"""Estimate country-specific AU-NZ effects and tests (Methods Section 6)."""

from __future__ import annotations

import argparse
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from .analysis_04_matched_comparison import validate_and_parse
from .analysis_common import PROJECT_ROOT, display_path, read_json, require_passed_blocking_checks, sha256, utc_timestamp, write_csv, write_json


EFFECT_COLUMNS = ["country", "period", "au_number_approved", "au_number_declined", "au_decision_total", "au_approval_rate", "nz_number_approved", "nz_number_declined", "nz_decision_total", "nz_approval_rate", "rate_difference_au_minus_nz", "rate_difference_ci_lower", "rate_difference_ci_upper", "risk_ratio", "risk_ratio_ci_lower", "risk_ratio_ci_upper", "odds_ratio", "odds_ratio_ci_lower", "odds_ratio_ci_upper", "minimum_expected_count", "selected_test", "test_statistic", "p_value", "bh_q_value", "fdr_significant", "continuity_correction", "meets_20_both", "meets_50_both", "warning_flags"]
SUMMARY_COLUMNS = ["metric", "value"]
FOREST_COLUMNS = ["country", "rate_difference_au_minus_nz", "rate_difference_ci_lower", "rate_difference_ci_upper", "bh_q_value", "fdr_significant", "au_decision_total", "nz_decision_total", "eligible_for_display", "displayed", "display_rank", "display_rule"]


def wilson_interval(successes: int, total: int, z: float) -> tuple[float, float]:
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2.0 * total)) / denominator
    half = z * math.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total)) / denominator
    return centre - half, centre + half


def newcombe_difference_interval(a: int, n1: int, c: int, n0: int, z: float) -> tuple[float, float]:
    p1, p0 = a / n1, c / n0
    l1, u1 = wilson_interval(a, n1, z)
    l0, u0 = wilson_interval(c, n0, z)
    difference = p1 - p0
    lower = difference - math.sqrt((p1 - l1) ** 2 + (u0 - p0) ** 2)
    upper = difference + math.sqrt((u1 - p1) ** 2 + (p0 - l0) ** 2)
    return max(-1.0, lower), min(1.0, upper)


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    row_one, row_two, column_one = a + b, c + d, a + c
    total = row_one + row_two
    low, high = max(0, column_one - row_two), min(row_one, column_one)
    def log_probability(value: int) -> float:
        return (math.lgamma(row_one + 1) - math.lgamma(value + 1) - math.lgamma(row_one - value + 1) + math.lgamma(row_two + 1) - math.lgamma(column_one - value + 1) - math.lgamma(row_two - column_one + value + 1) - math.lgamma(total + 1) + math.lgamma(column_one + 1) + math.lgamma(total - column_one + 1))
    observed = log_probability(a)
    return min(1.0, sum(math.exp(log_probability(value)) for value in range(low, high + 1) if log_probability(value) <= observed + 1e-12))


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    count = len(p_values)
    ordered = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [0.0] * count
    running = 1.0
    for rank_index in range(count - 1, -1, -1):
        original_index, p_value = ordered[rank_index]
        rank = rank_index + 1
        running = min(running, p_value * count / rank)
        adjusted[original_index] = min(1.0, running)
    return adjusted


def effect_ratios(a: int, b: int, c: int, d: int, z: float) -> tuple[float, float, float, float, float, float, str]:
    correction = "none"
    aa, bb, cc, dd = map(float, (a, b, c, d))
    if 0 in (a, b, c, d):
        aa, bb, cc, dd = (value + 0.5 for value in (aa, bb, cc, dd))
        correction = "Haldane-Anscombe: 0.5 added to all four cells"
    n1, n0 = aa + bb, cc + dd
    rr = (aa / n1) / (cc / n0)
    rr_se = math.sqrt(1.0 / aa - 1.0 / n1 + 1.0 / cc - 1.0 / n0)
    rr_lower, rr_upper = math.exp(math.log(rr) - z * rr_se), math.exp(math.log(rr) + z * rr_se)
    odds = aa * dd / (bb * cc)
    odds_se = math.sqrt(1.0 / aa + 1.0 / bb + 1.0 / cc + 1.0 / dd)
    odds_lower, odds_upper = math.exp(math.log(odds) - z * odds_se), math.exp(math.log(odds) + z * odds_se)
    return rr, rr_lower, rr_upper, odds, odds_lower, odds_upper, correction


def run(*, config_path: Path, input_path: Path, validation_checks_path: Path, output_dir: Path, manifest_dir: Path, project_root: Path = PROJECT_ROOT) -> dict[str, Path]:
    config = read_json(config_path)
    confidence = float(config["confidence_level"])
    threshold = float(config["minimum_expected_count_for_asymptotic_test"])
    fdr_level = float(config["fdr_level"])
    maximum = int(config["forest_plot_max_countries"])
    thresholds = sorted(int(value) for value in config["small_denominator_thresholds"])
    z = statistics.NormalDist().inv_cdf(0.5 + confidence / 2.0)
    require_passed_blocking_checks(validation_checks_path)
    source = validate_and_parse(input_path, thresholds)
    effects: list[dict[str, Any]] = []
    for row in source:
        a, b = int(row["au_number_approved"]), int(row["au_number_declined"])
        c, d = int(row["nz_number_approved"]), int(row["nz_number_declined"])
        n1, n0 = a + b, c + d
        total, approved, declined = n1 + n0, a + c, b + d
        expected = [n1 * approved / total, n1 * declined / total, n0 * approved / total, n0 * declined / total]
        minimum_expected = min(expected)
        if minimum_expected >= threshold:
            chi_square = sum((observed - exp) ** 2 / exp for observed, exp in zip((a, b, c, d), expected))
            selected_test, statistic, p_value = "Pearson chi-square (df=1; no continuity correction)", chi_square, math.erfc(math.sqrt(chi_square / 2.0))
        else:
            selected_test, statistic, p_value = "Fisher exact (two-sided)", "", fisher_exact_two_sided(a, b, c, d)
        lower, upper = newcombe_difference_interval(a, n1, c, n0, z)
        rr, rr_l, rr_u, odds, odds_l, odds_u, correction = effect_ratios(a, b, c, d, z)
        warning_flags = []
        if minimum_expected < threshold: warning_flags.append("sparse_expected_counts")
        if min(n1, n0) < 20: warning_flags.append("below_20_in_at_least_one_destination")
        elif min(n1, n0) < 50: warning_flags.append("below_50_in_at_least_one_destination")
        if correction != "none": warning_flags.append("zero_cell_effect_correction")
        effects.append({
            "country": row["country"], "period": row["period"], "au_number_approved": a, "au_number_declined": b, "au_decision_total": n1, "au_approval_rate": a / n1, "nz_number_approved": c, "nz_number_declined": d, "nz_decision_total": n0, "nz_approval_rate": c / n0, "rate_difference_au_minus_nz": a / n1 - c / n0, "rate_difference_ci_lower": lower, "rate_difference_ci_upper": upper, "risk_ratio": rr, "risk_ratio_ci_lower": rr_l, "risk_ratio_ci_upper": rr_u, "odds_ratio": odds, "odds_ratio_ci_lower": odds_l, "odds_ratio_ci_upper": odds_u, "minimum_expected_count": minimum_expected, "selected_test": selected_test, "test_statistic": statistic, "p_value": min(1.0, p_value), "bh_q_value": 0.0, "fdr_significant": 0, "continuity_correction": correction, "meets_20_both": row["meets_20_both"], "meets_50_both": row["meets_50_both"], "warning_flags": ";".join(warning_flags) or "none",
        })
    q_values = benjamini_hochberg([float(row["p_value"]) for row in effects])
    for row, q_value in zip(effects, q_values):
        row["bh_q_value"] = q_value
        row["fdr_significant"] = int(q_value <= fdr_level)

    tests = Counter(str(row["selected_test"]) for row in effects)
    directions = Counter("AU higher" if row["rate_difference_au_minus_nz"] > 0 else "NZ higher" if row["rate_difference_au_minus_nz"] < 0 else "equal" for row in effects)
    summary = [
        {"metric": "countries_tested", "value": len(effects)},
        {"metric": "chi_square_tests", "value": tests["Pearson chi-square (df=1; no continuity correction)"]},
        {"metric": "fisher_exact_tests", "value": tests["Fisher exact (two-sided)"]},
        {"metric": "fdr_significant_at_0.05", "value": sum(int(row["fdr_significant"]) for row in effects)},
        {"metric": "au_higher", "value": directions["AU higher"]}, {"metric": "nz_higher", "value": directions["NZ higher"]}, {"metric": "equal", "value": directions["equal"]},
        {"metric": "meets_20_both", "value": sum(int(row["meets_20_both"]) for row in effects)}, {"metric": "meets_50_both", "value": sum(int(row["meets_50_both"]) for row in effects)},
        {"metric": "zero_cell_corrections", "value": sum(row["continuity_correction"] != "none" for row in effects)},
    ]
    eligible = sorted((row for row in effects if int(row["meets_50_both"])), key=lambda row: (-abs(float(row["rate_difference_au_minus_nz"])), str(row["country"])))
    selected = {str(row["country"]): rank for rank, row in enumerate(eligible[:maximum], start=1)}
    display_rule = f"largest {maximum} absolute rate differences among countries with at least 50 decisions in each destination"
    forest = [{"country": row["country"], "rate_difference_au_minus_nz": row["rate_difference_au_minus_nz"], "rate_difference_ci_lower": row["rate_difference_ci_lower"], "rate_difference_ci_upper": row["rate_difference_ci_upper"], "bh_q_value": row["bh_q_value"], "fdr_significant": row["fdr_significant"], "au_decision_total": row["au_decision_total"], "nz_decision_total": row["nz_decision_total"], "eligible_for_display": int(row in eligible), "displayed": int(str(row["country"]) in selected), "display_rank": selected.get(str(row["country"]), ""), "display_rule": display_rule} for row in effects]
    outputs = {"effects": output_dir / "country_specific_effects_and_tests.csv", "summary": output_dir / "country_test_summary.csv", "forest_selection": output_dir / "forest_plot_selection.csv", "manifest": manifest_dir / "06_country_differences.json"}
    write_csv(outputs["effects"], EFFECT_COLUMNS, effects); write_csv(outputs["summary"], SUMMARY_COLUMNS, summary); write_csv(outputs["forest_selection"], FOREST_COLUMNS, forest)
    manifest_outputs = [{"name": name, "path": display_path(path, project_root), "sha256": sha256(path)} for name, path in outputs.items() if name != "manifest"]
    write_json(outputs["manifest"], {"module": "src.analysis_06_country_differences", "status": "passed", "analysis_timestamp_utc": utc_timestamp(), "configuration": {"confidence_level": confidence, "minimum_expected_count": threshold, "fdr_level": fdr_level, "difference_interval": "Newcombe hybrid score", "zero_cell_effect_rule": "Haldane-Anscombe 0.5 to all four cells", "forest_display_rule": display_rule}, "inputs": [{"path": display_path(path, project_root), "sha256": sha256(path)} for path in (input_path, validation_checks_path, config_path)], "outputs": manifest_outputs, "summary": {row["metric"]: row["value"] for row in summary}})
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "src/analysis_config.json"); parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "data/prepared/comparison/matched_country_2022-2025.csv"); parser.add_argument("--validation-checks", type=Path, default=PROJECT_ROOT / "data/results/validation/data_validation_checks.csv"); parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/results/country_tests"); parser.add_argument("--manifest-dir", type=Path, default=PROJECT_ROOT / "data/results/manifests"); return parser.parse_args()


def main() -> int:
    args = parse_args(); outputs = run(config_path=args.config, input_path=args.input, validation_checks_path=args.validation_checks, output_dir=args.output_dir, manifest_dir=args.manifest_dir)
    print("Country-specific artifacts written:")
    for path in outputs.values(): print(f"- {display_path(path)}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
