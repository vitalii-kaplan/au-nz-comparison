"""Compare applicant-origin shares and concentration (Methods Section 8)."""

from __future__ import annotations

import argparse
import math
import random
import statistics
from pathlib import Path
from typing import Any

from .analysis_05_concordance import (
    average_ranks, correlation_p_value, fisher_z_interval, pearson_correlation,
)
from .analysis_common import (
    PROJECT_ROOT, display_path, quantile_type7, read_csv_rows, read_json,
    require_columns, require_passed_blocking_checks, sha256, utc_timestamp,
    write_csv, write_json,
)


SHARE_COLUMNS = ["destination_code", "destination_country", "country", "decision_total", "destination_decision_total", "decision_share", "share_rank"]
CONCENTRATION_COLUMNS = ["destination_code", "destination_country", "represented_origins", "destination_decision_total", "top_1_share", "top_5_share", "top_10_share", "median_origin_share", "hhi_0_1", "gini"]
CONCORDANCE_COLUMNS = ["method", "coefficient", "n", "p_value", "ci_lower", "ci_upper", "confidence_level", "ci_method", "population"]
DISTANCE_COLUMNS = ["measure", "value", "log_base", "eligible", "assumptions", "skip_reason"]
RANK_COLUMNS = ["destination_code", "rank", "country", "decision_share"]
LORENZ_COLUMNS = ["destination_code", "cumulative_origin_fraction", "cumulative_decision_share", "point_index"]
SCATTER_COLUMNS = ["country", "au_decision_share", "nz_decision_share", "au_decision_total", "nz_decision_total"]


def gini(values: list[float]) -> float:
    if not values or any(value < 0 for value in values):
        raise ValueError("Gini requires non-negative values")
    ordered = sorted(values)
    total = sum(ordered)
    if total == 0:
        raise ValueError("Gini is undefined when all values are zero")
    n = len(ordered)
    return sum((2 * index - n - 1) * value for index, value in enumerate(ordered, start=1)) / (n * total)


def concentration(shares: list[float]) -> dict[str, float]:
    if not shares or not math.isclose(sum(shares), 1.0, abs_tol=1e-12):
        raise ValueError("shares must be non-empty and sum to one")
    ordered = sorted(shares, reverse=True)
    return {
        "top_1_share": sum(ordered[:1]), "top_5_share": sum(ordered[:5]),
        "top_10_share": sum(ordered[:10]), "median_origin_share": statistics.median(ordered),
        "hhi_0_1": sum(value * value for value in ordered), "gini": gini(ordered),
    }


def run(
    *,
    config_path: Path,
    long_input_path: Path,
    matched_input_path: Path,
    validation_checks_path: Path,
    comparability_path: Path,
    output_dir: Path,
    manifest_dir: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Path]:
    config = read_json(config_path)
    require_passed_blocking_checks(validation_checks_path)
    long_rows = read_csv_rows(long_input_path)
    matched_rows = read_csv_rows(matched_input_path)
    decisions = read_csv_rows(comparability_path)
    require_columns(long_input_path, long_rows, {"destination_code", "destination_country", "country", "decision_total"})
    require_columns(matched_input_path, matched_rows, {"country", "au_decision_total", "nz_decision_total"})
    require_columns(comparability_path, decisions, {"analysis_component", "eligible", "evidence", "caveat"})
    gate = {row["analysis_component"]: row for row in decisions}
    if "zero_filled_composition_distance" not in gate:
        raise ValueError("comparability decision for composition distance is missing")
    confidence = float(config["confidence_level"])
    seed = int(config["bootstrap_seed"])
    replicates = int(config["bootstrap_replicates"])

    by_destination: dict[str, list[dict[str, str]]] = {}
    for row in long_rows:
        total = int(row["decision_total"])
        if total <= 0:
            raise ValueError(f"{long_input_path}: non-positive decision total")
        by_destination.setdefault(row["destination_code"], []).append(row)
    if set(by_destination) != {"AU", "NZ"}:
        raise ValueError("composition input must contain AU and NZ")

    shares: list[dict[str, Any]] = []
    concentrations: list[dict[str, Any]] = []
    ranked_points: list[dict[str, Any]] = []
    lorenz_points: list[dict[str, Any]] = []
    share_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for code in ("AU", "NZ"):
        source = by_destination[code]
        destination_total = sum(int(row["decision_total"]) for row in source)
        ranked = sorted(source, key=lambda row: (-int(row["decision_total"]), row["country"]))
        code_shares: list[float] = []
        for rank, row in enumerate(ranked, start=1):
            value = int(row["decision_total"]) / destination_total
            item = {
                "destination_code": code, "destination_country": row["destination_country"],
                "country": row["country"], "decision_total": row["decision_total"],
                "destination_decision_total": destination_total, "decision_share": value,
                "share_rank": rank,
            }
            shares.append(item); share_lookup[(code, row["country"])] = item; code_shares.append(value)
            ranked_points.append({"destination_code": code, "rank": rank, "country": row["country"], "decision_share": value})
        metrics = concentration(code_shares)
        concentrations.append({
            "destination_code": code, "destination_country": source[0]["destination_country"],
            "represented_origins": len(source), "destination_decision_total": destination_total,
            **metrics,
        })
        ascending = sorted(code_shares)
        cumulative = 0.0
        lorenz_points.append({"destination_code": code, "cumulative_origin_fraction": 0.0, "cumulative_decision_share": 0.0, "point_index": 0})
        for index, value in enumerate(ascending, start=1):
            cumulative += value
            lorenz_points.append({"destination_code": code, "cumulative_origin_fraction": index / len(ascending), "cumulative_decision_share": cumulative, "point_index": index})

    scatter: list[dict[str, Any]] = []
    for row in matched_rows:
        country = row["country"]
        au, nz = share_lookup[("AU", country)], share_lookup[("NZ", country)]
        scatter.append({
            "country": country, "au_decision_share": au["decision_share"],
            "nz_decision_share": nz["decision_share"], "au_decision_total": row["au_decision_total"],
            "nz_decision_total": row["nz_decision_total"],
        })
    au_values = [float(row["au_decision_share"]) for row in scatter]
    nz_values = [float(row["nz_decision_share"]) for row in scatter]
    n = len(scatter)
    pearson = pearson_correlation(au_values, nz_values)
    spearman = pearson_correlation(average_ranks(au_values), average_ranks(nz_values))
    pearson_ci = fisher_z_interval(pearson, n, confidence)
    generator = random.Random(seed)
    bootstrapped: list[float] = []
    for _ in range(replicates):
        indices = [generator.randrange(n) for _ in range(n)]
        x = [au_values[index] for index in indices]
        y = [nz_values[index] for index in indices]
        try:
            bootstrapped.append(pearson_correlation(average_ranks(x), average_ranks(y)))
        except ValueError:
            continue
    alpha = 1.0 - confidence
    concordance = [
        {"method": "Spearman", "coefficient": spearman, "n": n, "p_value": correlation_p_value(spearman, n), "ci_lower": quantile_type7(bootstrapped, alpha / 2), "ci_upper": quantile_type7(bootstrapped, 1 - alpha / 2), "confidence_level": confidence, "ci_method": f"percentile bootstrap ({len(bootstrapped)} replicates; seed {seed})", "population": "origins represented in both destinations; shares use full destination totals"},
        {"method": "Pearson", "coefficient": pearson, "n": n, "p_value": correlation_p_value(pearson, n), "ci_lower": pearson_ci[0], "ci_upper": pearson_ci[1], "confidence_level": confidence, "ci_method": "Fisher z transformation", "population": "origins represented in both destinations; shares use full destination totals"},
    ]
    distance_gate = gate["zero_filled_composition_distance"]
    eligible = distance_gate["eligible"].lower() == "true"
    if eligible:
        raise ValueError("Jensen-Shannon implementation requires an explicit true-zero policy; current project contract does not provide one")
    distance = [{
        "measure": "Jensen-Shannon divergence", "value": "", "log_base": 2,
        "eligible": "false", "assumptions": "requires union support and valid zero assignment for absent origins",
        "skip_reason": f"{distance_gate['evidence']}; {distance_gate['caveat']}",
    }]
    shares.sort(key=lambda row: (row["destination_code"], int(row["share_rank"])))
    scatter.sort(key=lambda row: row["country"])

    outputs = {
        "shares": output_dir / "origin_shares.csv",
        "concentration": output_dir / "concentration_statistics.csv",
        "concordance": output_dir / "share_concordance.csv",
        "distance": output_dir / "composition_distance.csv",
        "ranked": output_dir / "ranked_share_points.csv",
        "lorenz": output_dir / "lorenz_curve_points.csv",
        "scatter": output_dir / "share_scatter_points.csv",
        "manifest": manifest_dir / "08_origin_composition.json",
    }
    write_csv(outputs["shares"], SHARE_COLUMNS, shares)
    write_csv(outputs["concentration"], CONCENTRATION_COLUMNS, concentrations)
    write_csv(outputs["concordance"], CONCORDANCE_COLUMNS, concordance)
    write_csv(outputs["distance"], DISTANCE_COLUMNS, distance)
    write_csv(outputs["ranked"], RANK_COLUMNS, ranked_points)
    write_csv(outputs["lorenz"], LORENZ_COLUMNS, lorenz_points)
    write_csv(outputs["scatter"], SCATTER_COLUMNS, scatter)
    write_json(outputs["manifest"], {
        "module": "src.analysis_08_origin_composition", "status": "passed",
        "analysis_timestamp_utc": utc_timestamp(),
        "configuration": {"confidence_level": confidence, "bootstrap_seed": seed, "bootstrap_replicates": replicates, "hhi_scale": "0-1"},
        "inputs": [{"path": display_path(path, project_root), "sha256": sha256(path)} for path in (config_path, long_input_path, matched_input_path, validation_checks_path, comparability_path)],
        "outputs": [{"name": name, "path": display_path(path, project_root), "sha256": sha256(path)} for name, path in outputs.items() if name != "manifest"],
        "summary": {"destinations": 2, "matched_origins": n, "jsd_status": "skipped_ineligible"},
    })
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "src/analysis_config.json")
    parser.add_argument("--long-input", type=Path, default=PROJECT_ROOT / "data/prepared/comparison/destination_country_2022-2025.csv")
    parser.add_argument("--matched-input", type=Path, default=PROJECT_ROOT / "data/prepared/comparison/matched_country_2022-2025.csv")
    parser.add_argument("--validation-checks", type=Path, default=PROJECT_ROOT / "data/results/validation/data_validation_checks.csv")
    parser.add_argument("--comparability", type=Path, default=PROJECT_ROOT / "data/results/validation/comparability_decisions.csv")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/results/composition")
    parser.add_argument("--manifest-dir", type=Path, default=PROJECT_ROOT / "data/results/manifests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = run(config_path=args.config, long_input_path=args.long_input, matched_input_path=args.matched_input, validation_checks_path=args.validation_checks, comparability_path=args.comparability, output_dir=args.output_dir, manifest_dir=args.manifest_dir)
    print("Composition artifacts written:")
    for path in outputs.values():
        print(f"- {display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
