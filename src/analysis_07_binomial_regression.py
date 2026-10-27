"""Fit destination binomial regressions with country fixed effects (Section 7)."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .analysis_common import (
    PROJECT_ROOT, display_path, read_csv_rows, read_json, require_columns,
    require_passed_blocking_checks, sha256, utc_timestamp, write_csv, write_json,
)


COEFFICIENT_COLUMNS = ["model", "term", "estimate", "standard_error", "ci_lower", "ci_upper", "p_value", "odds_ratio", "odds_ratio_ci_lower", "odds_ratio_ci_upper", "covariance_method"]
CONTRAST_COLUMNS = ["model", "au_standardized_probability", "au_ci_lower", "au_ci_upper", "nz_standardized_probability", "nz_ci_lower", "nz_ci_upper", "au_minus_nz_probability_contrast", "contrast_standard_error", "contrast_ci_lower", "contrast_ci_upper", "standardization_population"]
FIT_COLUMNS = ["model", "observations", "countries", "matched_units", "decisions", "parameters", "log_likelihood", "aic", "residual_deviance", "residual_degrees_of_freedom", "pearson_chi_square", "pearson_dispersion"]
DIAGNOSTIC_COLUMNS = ["model", "diagnostic", "value", "interpretation"]
INFLUENCE_COLUMNS = ["model", "rank", "country", "year", "destination_code", "number_approved", "number_declined", "decision_total", "fitted_probability", "deviance_residual", "leverage", "cooks_distance"]


def read_gate(path: Path) -> dict[str, bool]:
    rows = read_csv_rows(path)
    require_columns(path, rows, {"analysis_component", "eligible"})
    return {row["analysis_component"]: row["eligible"].lower() == "true" for row in rows}


def validate_matched(path: Path, annual: bool) -> None:
    rows = read_csv_rows(path)
    required = {"country", "au_number_approved", "au_number_declined", "nz_number_approved", "nz_number_declined"}
    if annual:
        required.add("year")
    require_columns(path, rows, required)
    if not rows:
        raise ValueError(f"{path}: no matched rows")
    keys = [(row["country"], row.get("year", "")) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{path}: duplicate matched keys")
    for row in rows:
        for prefix in ("au", "nz"):
            approved = int(row[f"{prefix}_number_approved"])
            declined = int(row[f"{prefix}_number_declined"])
            if approved < 0 or declined < 0 or approved + declined <= 0:
                raise ValueError(f"{path}: invalid counts for {row['country']}")


def _rows_with_columns(path: Path, columns: list[str]) -> list[dict[str, str]]:
    rows = read_csv_rows(path)
    require_columns(path, rows, set(columns))
    return [{column: row[column] for column in columns} for row in rows]


def run(
    *,
    config_path: Path,
    pooled_input_path: Path,
    annual_input_path: Path,
    validation_checks_path: Path,
    comparability_path: Path,
    output_dir: Path,
    manifest_dir: Path,
    r_backend_path: Path = PROJECT_ROOT / "src/fit_binomial_models.R",
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Path]:
    config = read_json(config_path)
    require_passed_blocking_checks(validation_checks_path)
    gates = read_gate(comparability_path)
    if not gates.get("pooled_country_fixed_effect_binomial_model", False):
        raise ValueError("comparability gate rejected the pooled binomial model")
    if not gates.get("country_year_binomial_model", False):
        raise ValueError("comparability gate rejected the country-year binomial model")
    validate_matched(pooled_input_path, annual=False)
    validate_matched(annual_input_path, annual=True)
    confidence = float(config["confidence_level"])
    reference = str(config["reference_destination"])
    if reference != "NZ" or config.get("comparison_destination") != "AU":
        raise ValueError("Section 7 requires NZ as reference and AU as comparison")

    coefficients: list[dict[str, str]] = []
    contrasts: list[dict[str, str]] = []
    fit_statistics: list[dict[str, str]] = []
    diagnostics: list[dict[str, str]] = []
    influence: list[dict[str, str]] = []
    r_version = subprocess.run(["Rscript", "--version"], text=True, capture_output=True, check=True).stderr.strip() or subprocess.run(["Rscript", "--version"], text=True, capture_output=True, check=True).stdout.strip()
    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        for name, source in (("pooled_country_fixed_effects", pooled_input_path), ("country_year_fixed_effects", annual_input_path)):
            subprocess.run(
                ["Rscript", str(r_backend_path), str(source), name, str(temporary_path), str(confidence), reference],
                check=True,
            )
            coefficients.extend(_rows_with_columns(temporary_path / f"{name}_coefficients.csv", COEFFICIENT_COLUMNS))
            contrasts.extend(_rows_with_columns(temporary_path / f"{name}_contrasts.csv", CONTRAST_COLUMNS))
            fit_statistics.extend(_rows_with_columns(temporary_path / f"{name}_fit.csv", FIT_COLUMNS))
            diagnostics.extend(_rows_with_columns(temporary_path / f"{name}_diagnostics.csv", DIAGNOSTIC_COLUMNS))
            influence.extend(_rows_with_columns(temporary_path / f"{name}_influence.csv", INFLUENCE_COLUMNS))

    destination_terms = [row for row in coefficients if row["term"] == "destinationAU"]
    if len(destination_terms) != 2:
        raise ValueError("destination coefficient missing from fitted models")
    outputs = {
        "coefficients": output_dir / "binomial_model_coefficients.csv",
        "contrasts": output_dir / "destination_probability_contrasts.csv",
        "fit": output_dir / "model_fit_statistics.csv",
        "diagnostics": output_dir / "model_diagnostics.csv",
        "influence": output_dir / "influential_observations.csv",
        "manifest": manifest_dir / "07_binomial_regression.json",
    }
    write_csv(outputs["coefficients"], COEFFICIENT_COLUMNS, coefficients)
    write_csv(outputs["contrasts"], CONTRAST_COLUMNS, contrasts)
    write_csv(outputs["fit"], FIT_COLUMNS, fit_statistics)
    write_csv(outputs["diagnostics"], DIAGNOSTIC_COLUMNS, diagnostics)
    write_csv(outputs["influence"], INFLUENCE_COLUMNS, influence)
    input_paths = (config_path, pooled_input_path, annual_input_path, validation_checks_path, comparability_path, r_backend_path)
    write_json(outputs["manifest"], {
        "module": "src.analysis_07_binomial_regression", "status": "passed",
        "analysis_timestamp_utc": utc_timestamp(),
        "configuration": {"reference_destination": reference, "comparison_destination": "AU", "confidence_level": confidence, "pooled_covariance": "country-cluster-robust sandwich (CR1)", "annual_covariance": "country-cluster-robust sandwich (CR1)", "r_version": r_version},
        "inputs": [{"path": display_path(path, project_root), "sha256": sha256(path)} for path in input_paths],
        "outputs": [{"name": name, "path": display_path(path, project_root), "sha256": sha256(path)} for name, path in outputs.items() if name != "manifest"],
        "destination_terms": destination_terms,
        "interpretation_warning": "Destination coefficients are conditional observational associations, not causal effects.",
    })
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "src/analysis_config.json")
    parser.add_argument("--pooled-input", type=Path, default=PROJECT_ROOT / "data/prepared/comparison/matched_country_2022-2025.csv")
    parser.add_argument("--annual-input", type=Path, default=PROJECT_ROOT / "data/prepared/comparison/matched_country_year.csv")
    parser.add_argument("--validation-checks", type=Path, default=PROJECT_ROOT / "data/results/validation/data_validation_checks.csv")
    parser.add_argument("--comparability", type=Path, default=PROJECT_ROOT / "data/results/validation/comparability_decisions.csv")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/results/models")
    parser.add_argument("--manifest-dir", type=Path, default=PROJECT_ROOT / "data/results/manifests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = run(config_path=args.config, pooled_input_path=args.pooled_input, annual_input_path=args.annual_input, validation_checks_path=args.validation_checks, comparability_path=args.comparability, output_dir=args.output_dir, manifest_dir=args.manifest_dir)
    print("Binomial-model artifacts written:")
    for path in outputs.values():
        print(f"- {display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
