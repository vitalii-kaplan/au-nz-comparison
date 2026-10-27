"""Estimate cross-destination approval-rate concordance (Methods Section 5)."""

from __future__ import annotations

import argparse
import math
import random
import statistics
from pathlib import Path
from typing import Any

from .analysis_04_matched_comparison import regularized_incomplete_beta
from .analysis_common import (
    PROJECT_ROOT, display_path, quantile_type7, read_json,
    require_passed_blocking_checks, sha256, utc_timestamp, write_csv, write_json,
)
from .analysis_04_matched_comparison import validate_and_parse


RESULT_COLUMNS = ["method", "coefficient", "n", "p_value", "ci_lower", "ci_upper", "confidence_level", "ci_method", "p_value_method"]
POINT_COLUMNS = ["country", "au_approval_rate", "nz_approval_rate", "au_decision_total", "nz_decision_total", "rate_difference_au_minus_nz"]
DIAGNOSTIC_COLUMNS = ["diagnostic", "value", "interpretation"]


def average_ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        rank = ((start + 1) + end) / 2.0
        for position in range(start, end):
            ranks[ordered[position][0]] = rank
        start = end
    return ranks


def pearson_correlation(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 3:
        raise ValueError("correlation requires equally sized samples of at least three")
    mx, my = statistics.fmean(x), statistics.fmean(y)
    numerator = sum((a - mx) * (b - my) for a, b in zip(x, y))
    denominator = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    if denominator == 0:
        raise ValueError("correlation is undefined for a constant variable")
    return numerator / denominator


def correlation_p_value(coefficient: float, n: int) -> float:
    if abs(coefficient) >= 1.0:
        return 0.0
    statistic = coefficient * math.sqrt((n - 2) / (1.0 - coefficient * coefficient))
    return regularized_incomplete_beta((n - 2) / 2.0, 0.5, (n - 2) / ((n - 2) + statistic * statistic))


def fisher_z_interval(coefficient: float, n: int, confidence: float) -> tuple[float, float]:
    critical = statistics.NormalDist().inv_cdf(0.5 + confidence / 2.0)
    transformed = math.atanh(max(-1 + 1e-15, min(1 - 1e-15, coefficient)))
    half_width = critical / math.sqrt(n - 3)
    return math.tanh(transformed - half_width), math.tanh(transformed + half_width)


def run(*, config_path: Path, input_path: Path, validation_checks_path: Path, output_dir: Path, manifest_dir: Path, project_root: Path = PROJECT_ROOT) -> dict[str, Path]:
    config = read_json(config_path)
    confidence = float(config["confidence_level"])
    seed = int(config["bootstrap_seed"])
    replicates = int(config["bootstrap_replicates"])
    thresholds = sorted(int(value) for value in config["small_denominator_thresholds"])
    require_passed_blocking_checks(validation_checks_path)
    rows = validate_and_parse(input_path, thresholds)
    au = [float(row["au_approval_rate"]) for row in rows]
    nz = [float(row["nz_approval_rate"]) for row in rows]
    n = len(rows)
    pearson = pearson_correlation(au, nz)
    spearman = pearson_correlation(average_ranks(au), average_ranks(nz))
    pearson_ci = fisher_z_interval(pearson, n, confidence)

    generator = random.Random(seed)
    bootstrapped: list[float] = []
    for _ in range(replicates):
        indices = [generator.randrange(n) for _ in range(n)]
        bx = [au[index] for index in indices]
        by = [nz[index] for index in indices]
        try:
            bootstrapped.append(pearson_correlation(average_ranks(bx), average_ranks(by)))
        except ValueError:
            continue
    alpha = 1.0 - confidence
    spearman_ci = (quantile_type7(bootstrapped, alpha / 2.0), quantile_type7(bootstrapped, 1.0 - alpha / 2.0))
    result_rows = [
        {"method": "Pearson", "coefficient": pearson, "n": n, "p_value": correlation_p_value(pearson, n), "ci_lower": pearson_ci[0], "ci_upper": pearson_ci[1], "confidence_level": confidence, "ci_method": "Fisher z transformation", "p_value_method": "t distribution with n-2 degrees of freedom"},
        {"method": "Spearman", "coefficient": spearman, "n": n, "p_value": correlation_p_value(spearman, n), "ci_lower": spearman_ci[0], "ci_upper": spearman_ci[1], "confidence_level": confidence, "ci_method": f"percentile bootstrap ({len(bootstrapped)} replicates; seed {seed})", "p_value_method": "t approximation applied to rank correlation"},
    ]
    points = [{column: row[column] for column in POINT_COLUMNS} for row in rows]
    diagnostics = [
        {"diagnostic": "matched_country_count", "value": n, "interpretation": "countries included in both correlations"},
        {"diagnostic": "au_unique_rates", "value": len(set(au)), "interpretation": "distinct Australian country approval rates"},
        {"diagnostic": "nz_unique_rates", "value": len(set(nz)), "interpretation": "distinct New Zealand country approval rates"},
        {"diagnostic": "au_boundary_rates", "value": sum(value in (0.0, 1.0) for value in au), "interpretation": "Australian rates equal to zero or one"},
        {"diagnostic": "nz_boundary_rates", "value": sum(value in (0.0, 1.0) for value in nz), "interpretation": "New Zealand rates equal to zero or one"},
        {"diagnostic": "spearman_bootstrap_replicates_used", "value": len(bootstrapped), "interpretation": "non-degenerate seeded resamples used for the interval"},
    ]
    outputs = {
        "concordance": output_dir / "approval_rate_concordance.csv",
        "scatter_points": output_dir / "approval_rate_scatter_points.csv",
        "diagnostics": output_dir / "concordance_diagnostics.csv",
        "manifest": manifest_dir / "05_concordance.json",
    }
    write_csv(outputs["concordance"], RESULT_COLUMNS, result_rows)
    write_csv(outputs["scatter_points"], POINT_COLUMNS, points)
    write_csv(outputs["diagnostics"], DIAGNOSTIC_COLUMNS, diagnostics)
    manifest_outputs = [{"name": name, "path": display_path(path, project_root), "sha256": sha256(path)} for name, path in outputs.items() if name != "manifest"]
    write_json(outputs["manifest"], {"module": "src.analysis_05_concordance", "status": "passed", "analysis_timestamp_utc": utc_timestamp(), "configuration": {"confidence_level": confidence, "bootstrap_seed": seed, "bootstrap_replicates": replicates}, "inputs": [{"path": display_path(path, project_root), "sha256": sha256(path)} for path in (input_path, validation_checks_path, config_path)], "outputs": manifest_outputs, "results": result_rows, "interpretation_warning": "Correlation measures association, not agreement."})
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "src/analysis_config.json")
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "data/prepared/comparison/matched_country_2022-2025.csv")
    parser.add_argument("--validation-checks", type=Path, default=PROJECT_ROOT / "data/results/validation/data_validation_checks.csv")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/results/concordance")
    parser.add_argument("--manifest-dir", type=Path, default=PROJECT_ROOT / "data/results/manifests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = run(config_path=args.config, input_path=args.input, validation_checks_path=args.validation_checks, output_dir=args.output_dir, manifest_dir=args.manifest_dir)
    print("Concordance artifacts written:")
    for path in outputs.values(): print(f"- {display_path(path)}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
