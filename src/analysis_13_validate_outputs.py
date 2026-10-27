"""Validate the minimum result-table and figure inventory (Step 13)."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from .analysis_common import PROJECT_ROOT, display_path, read_json, sha256, utc_timestamp, write_csv, write_json


CHECKLIST_COLUMNS = [
    "output_id", "category", "description", "path", "required", "status",
    "row_count", "required_columns", "key_fields", "registered_sha256",
    "current_sha256", "message",
]
REGISTRY_COLUMNS = [
    "table_id", "source_csv", "grain", "key_fields", "unit", "weighting",
    "denominator", "direction", "interpretation_scope", "intended_results_subsection",
]


TABLE_REQUIREMENTS = [
    ("dataset_summary", "Dataset summary by destination", "data/results/descriptive/dataset_summary_by_destination.csv", {"destination_code", "decision_total", "aggregate_approval_rate"}, ("destination_code",)),
    ("country_descriptives", "Country-level descriptive statistics", "data/results/descriptive/country_level_distribution_statistics.csv", {"destination_code", "measure", "median", "iqr"}, ("destination_code", "measure")),
    ("matched_differences", "Matched-country differences", "data/results/paired/matched_difference_summary.csv", {"period", "n_pairs", "mean_difference", "median_difference"}, ("period",)),
    ("approval_concordance", "Pearson and Spearman concordance", "data/results/concordance/approval_rate_concordance.csv", {"method", "coefficient", "n", "ci_lower", "ci_upper"}, ("method",)),
    ("country_effects", "Complete country-specific effects and FDR tests", "data/results/country_tests/country_specific_effects_and_tests.csv", {"country", "rate_difference_au_minus_nz", "bh_q_value", "fdr_significant"}, ("country",)),
    ("binomial_regression", "Binomial regression coefficients", "data/results/models/binomial_model_coefficients.csv", {"model", "term", "estimate", "standard_error", "p_value"}, ("model", "term")),
    ("origin_concentration", "Applicant-origin concentration statistics", "data/results/composition/concentration_statistics.csv", {"destination_code", "top_1_share", "hhi_0_1", "gini"}, ("destination_code",)),
    ("annual_statistics", "Annual destination statistics", "data/results/temporal/annual_destination_summary.csv", {"year", "destination_code", "decision_total", "aggregate_approval_rate"}, ("year", "destination_code")),
    ("sensitivity_summary", "Sensitivity-analysis summary", "data/results/robustness/sensitivity_analysis_summary.csv", {"method", "threshold_min_decisions_each", "effect_estimate", "direction"}, ("method", "threshold_min_decisions_each")),
]
FIGURE_REQUIREMENTS = [
    ("data_coverage", "Dataset scale and coverage", "article/figures/data_coverage_overview.tex"),
    ("comparability_audit", "Pooled and annual comparability audit", "article/figures/comparability_audit.tex"),
    ("decision_volume_distribution", "AU/NZ decision-volume distributions", "article/figures/decision_volume_log10_bins.tex"),
    ("approval_rate_distribution", "AU/NZ approval-rate distributions", "article/figures/descriptive_ecdfs.tex"),
    ("paired_difference_distribution", "Paired-difference distribution", "article/figures/matched_difference_distribution.tex"),
    ("approval_rate_scatter", "AU-vs-NZ approval-rate scatterplot", "article/figures/approval_rate_concordance.tex"),
    ("country_forest_plot", "Selected country-difference forest plot", "article/figures/country_difference_forest.tex"),
    ("pooled_standardized_probabilities", "Pooled standardized destination probabilities", "article/figures/pooled_standardized_probabilities.tex"),
    ("threshold_sensitivity", "Minimum-denominator sensitivity", "article/figures/threshold_sensitivity.tex"),
]
TABLE_METADATA = {
    "dataset_summary": ("destination", "destination_code", "counts and proportions", "decision-weighted", "approved or granted plus declined or refused decisions", "destination-specific", "descriptive and associational; not causal", "Destination scale and country-level distributions"),
    "country_descriptives": ("destination by measure", "destination_code;measure", "proportion or recorded decisions", "country-weighted", "observed two-outcome decisions", "destination-specific", "descriptive and associational; not causal", "Destination scale and country-level distributions"),
    "matched_differences": ("pooled matched-country population", "period", "proportion", "each matched origin once", "observed decisions in each destination", "AU minus NZ", "descriptive and associational; not causal", "Matched-country approval-rate differences"),
    "approval_concordance": ("correlation method", "method", "correlation coefficient", "each matched origin once", "observed decisions in each destination", "association, not agreement", "descriptive and associational; not causal", "Cross-destination concordance"),
    "country_effects": ("matched origin country", "country", "proportion and relative effects", "country-specific decision counts", "observed decisions in each destination", "AU minus NZ for rate differences", "descriptive and associational; not causal", "Country-specific differences"),
    "binomial_regression": ("model term", "model;term", "log odds and odds ratio", "grouped binomial decision counts", "approved versus declined decisions", "AU relative to NZ", "descriptive and associational; not causal", "Adjusted destination association"),
    "origin_concentration": ("destination", "destination_code", "decision share and concentration index", "recorded decisions", "all destination-specific decisions", "destination-specific", "descriptive and associational; not causal", "Applicant-origin composition"),
    "annual_statistics": ("destination-year", "year;destination_code", "counts and proportions", "decision- and country-weighted summaries kept separate", "observed annual decisions", "destination-specific", "descriptive and associational; not causal", "Temporal comparison"),
    "sensitivity_summary": ("method and denominator threshold", "method;threshold_min_decisions_each", "method-specific effect", "matched origins meeting threshold", "observed decisions in both destinations", "AU minus NZ where applicable", "descriptive and associational; not causal", "Sensitivity analyses"),
}


def csv_contract(path: Path, required: set[str], keys: tuple[str, ...]) -> tuple[int, str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = required - fields
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path}: result table is empty")
    observed = [tuple(row[key] for key in keys) for row in rows]
    if len(observed) != len(set(observed)):
        raise ValueError(f"{path}: duplicate key for {keys}")
    return len(rows), ";".join(sorted(required))


def verify_step12(manifest_path: Path, artifact_path: Path, project_root: Path) -> dict[str, dict[str, str]]:
    manifest = read_json(manifest_path)
    if manifest.get("module") != "src.analysis_12_reproducibility" or manifest.get("status") != "passed":
        raise ValueError(f"{manifest_path}: Step 12 did not pass")
    registered_output = next((row for row in manifest["outputs"] if row["name"] == "artifact_manifest"), None)
    if not registered_output or sha256(artifact_path) != registered_output["sha256"]:
        raise ValueError(f"{artifact_path}: hash does not match Step 12")
    with artifact_path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["path"]: row for row in csv.DictReader(handle)}


def run(
    *,
    step12_manifest: Path,
    artifact_manifest: Path,
    output_dir: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Path]:
    registered = verify_step12(step12_manifest, artifact_manifest, project_root)
    checklist: list[dict[str, Any]] = []
    registry: list[dict[str, str]] = []

    for output_id, description, relative, required, keys in TABLE_REQUIREMENTS:
        path = project_root / relative
        row_count, required_text = csv_contract(path, required, keys)
        current_hash = sha256(path)
        registration = registered.get(relative)
        status = "passed" if registration and registration["sha256"] == current_hash else "failed"
        checklist.append({"output_id": output_id, "category": "table", "description": description, "path": relative, "required": "true", "status": status, "row_count": row_count, "required_columns": required_text, "key_fields": ";".join(keys), "registered_sha256": registration["sha256"] if registration else "", "current_sha256": current_hash, "message": "schema, key, content, and registration verified" if status == "passed" else "missing or stale artifact registration"})
        metadata = TABLE_METADATA[output_id]
        registry.append(dict(zip(REGISTRY_COLUMNS, (output_id, relative, *metadata))))

    for output_id, description, relative in FIGURE_REQUIREMENTS:
        path = project_root / relative
        if not path.exists() or path.stat().st_size == 0:
            raise ValueError(f"{path}: required figure is missing or empty")
        current_hash = sha256(path)
        registration = registered.get(relative)
        status = "passed" if registration and registration["sha256"] == current_hash else "failed"
        checklist.append({"output_id": output_id, "category": "figure", "description": description, "path": relative, "required": "true", "status": status, "row_count": "", "required_columns": "", "key_fields": "", "registered_sha256": registration["sha256"] if registration else "", "current_sha256": current_hash, "message": "non-empty publication source and registration verified" if status == "passed" else "missing or stale artifact registration"})

    optional_relative = "data/results/composition/composition_distance.csv"
    optional_path = project_root / optional_relative
    with optional_path.open(encoding="utf-8-sig", newline="") as handle:
        optional_rows = list(csv.DictReader(handle))
    documented_skip = len(optional_rows) == 1 and optional_rows[0].get("eligible") == "false" and bool(optional_rows[0].get("skip_reason"))
    registration = registered.get(optional_relative)
    optional_hash = sha256(optional_path)
    optional_status = "skipped" if documented_skip and registration and registration["sha256"] == optional_hash else "failed"
    checklist.append({"output_id": "jensen_shannon_distance", "category": "optional_table", "description": "Union-based composition distance", "path": optional_relative, "required": "false", "status": optional_status, "row_count": len(optional_rows), "required_columns": "eligible;skip_reason", "key_fields": "measure", "registered_sha256": registration["sha256"] if registration else "", "current_sha256": optional_hash, "message": "explicitly skipped with a recorded comparability reason" if optional_status == "skipped" else "optional output is neither produced nor validly skipped"})

    failures = [row for row in checklist if row["status"] == "failed"]
    checklist_path = output_dir / "minimum_output_checklist.csv"
    registry_path = output_dir / "result_table_registry.csv"
    write_csv(checklist_path, CHECKLIST_COLUMNS, checklist)
    write_csv(registry_path, REGISTRY_COLUMNS, registry)
    if failures:
        raise ValueError(f"minimum-output validation found {len(failures)} failure(s)")
    outputs = {"checklist": checklist_path, "result_registry": registry_path}
    manifest_path = output_dir / "13_validate_outputs.json"
    write_json(manifest_path, {"module": "src.analysis_13_validate_outputs", "status": "passed", "analysis_timestamp_utc": utc_timestamp(), "inputs": [{"path": display_path(step12_manifest, project_root), "sha256": sha256(step12_manifest)}, {"path": display_path(artifact_manifest, project_root), "sha256": sha256(artifact_manifest)}], "outputs": [{"name": name, "path": display_path(path, project_root), "sha256": sha256(path), "rows": len(checklist) if name == "checklist" else len(registry)} for name, path in outputs.items()], "summary": {"required_outputs_passed": sum(row["required"] == "true" for row in checklist), "optional_outputs_skipped": sum(row["status"] == "skipped" for row in checklist), "failures": 0}})
    outputs["manifest"] = manifest_path
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step12-manifest", type=Path, default=PROJECT_ROOT / "data/results/manifests/12_reproducibility.json")
    parser.add_argument("--artifact-manifest", type=Path, default=PROJECT_ROOT / "data/results/manifests/artifact_manifest.csv")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/results/manifests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = run(step12_manifest=args.step12_manifest, artifact_manifest=args.artifact_manifest, output_dir=args.output_dir)
    print("Minimum-output validation artifacts written:")
    for path in outputs.values():
        print(f"- {display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
