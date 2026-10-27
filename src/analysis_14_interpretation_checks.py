"""Enforce descriptive, associational, and non-causal reporting boundaries (Step 14)."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any

from .analysis_common import PROJECT_ROOT, display_path, read_json, sha256, utc_timestamp, write_csv, write_json


CHECK_COLUMNS = ["check_id", "artifact_id", "requirement", "observed", "expected", "status", "blocking", "message"]
RESULT_MANIFESTS = (
    "03_descriptive.json", "04_matched_comparison.json", "05_concordance.json",
    "06_country_differences.json", "07_binomial_regression.json",
    "08_origin_composition.json", "09_temporal.json", "10_sensitivity.json",
)
FORBIDDEN_PATTERNS = {
    "comparative_fairness": re.compile(r"\bfairer\b", re.IGNORECASE),
    "nationality_discrimination": re.compile(r"\bdiscriminat(?:e|es|ed|ing|ion|ory)\b", re.IGNORECASE),
    "individual_causal_effect": re.compile(r"causally\s+changes", re.IGNORECASE),
    "applicant_quality": re.compile(r"applicant\s+quality", re.IGNORECASE),
}


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def add_check(checks: list[dict[str, Any]], *, check_id: str, artifact_id: str,
              requirement: str, observed: str, expected: str, passed: bool,
              message: str) -> None:
    checks.append({"check_id": check_id, "artifact_id": artifact_id, "requirement": requirement, "observed": observed, "expected": expected, "status": "passed" if passed else "failed", "blocking": "true", "message": message})


def verify_step13(manifest_path: Path, registry_path: Path) -> None:
    manifest = read_json(manifest_path)
    if manifest.get("module") != "src.analysis_13_validate_outputs" or manifest.get("status") != "passed":
        raise ValueError(f"{manifest_path}: Step 13 did not pass")
    registered = next((row for row in manifest["outputs"] if row["name"] == "result_registry"), None)
    if not registered or registered["sha256"] != sha256(registry_path):
        raise ValueError(f"{registry_path}: hash does not match Step 13")


def run(
    *,
    contract_path: Path,
    registry_path: Path,
    step13_manifest: Path,
    manifest_dir: Path,
    output_path: Path,
    text_files: list[Path] | None = None,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Path]:
    verify_step13(step13_manifest, registry_path)
    checks: list[dict[str, Any]] = []
    contract = {row["contract_item"]: row for row in csv_rows(contract_path)}
    contract_requirements = {
        "decision_total": ("unit", "recorded decisions"),
        "matched_rate_difference": ("direction", "AU - NZ"),
        "decision_weighted_perspective": ("weighting", "decision-weighted"),
        "country_weighted_perspective": ("weighting", "each country contributes once"),
    }
    for item, (field, expected) in contract_requirements.items():
        observed = contract.get(item, {}).get(field, "")
        add_check(checks, check_id=f"contract_{item}_{field}", artifact_id="analysis_contract", requirement=field, observed=observed, expected=expected, passed=observed == expected, message="analysis contract reporting boundary")

    registry = csv_rows(registry_path)
    required_metadata = ("grain", "unit", "weighting", "denominator", "direction", "interpretation_scope")
    expected_scope = "descriptive and associational; not causal"
    for row in registry:
        table_id = row["table_id"]
        for field in required_metadata:
            observed = row.get(field, "").strip()
            expected = expected_scope if field == "interpretation_scope" else "non-empty"
            passed = observed == expected_scope if field == "interpretation_scope" else bool(observed)
            add_check(checks, check_id=f"{table_id}_{field}", artifact_id=table_id, requirement=field, observed=observed, expected=expected, passed=passed, message="article-facing result metadata")

    manifest_inputs: list[dict[str, str]] = [
        {"path": display_path(contract_path, project_root), "sha256": sha256(contract_path)},
        {"path": display_path(registry_path, project_root), "sha256": sha256(registry_path)},
        {"path": display_path(step13_manifest, project_root), "sha256": sha256(step13_manifest)},
    ]
    for name in RESULT_MANIFESTS:
        path = manifest_dir / name
        value = read_json(path)
        module = str(value.get("module", name))
        passed = value.get("status") == "passed" and bool(value.get("inputs")) and bool(value.get("outputs"))
        add_check(checks, check_id=f"manifest_{name[:2]}", artifact_id=module, requirement="passed manifest with inputs and outputs", observed=str(value.get("status", "")), expected="passed", passed=passed, message="result provenance and status")
        manifest_inputs.append({"path": display_path(path, project_root), "sha256": sha256(path)})

    for text_path in text_files or []:
        text = text_path.read_text(encoding="utf-8")
        for boundary, pattern in FORBIDDEN_PATTERNS.items():
            match = pattern.search(text)
            add_check(checks, check_id=f"text_{text_path.stem}_{boundary}", artifact_id=display_path(text_path, project_root), requirement=f"no unsupported {boundary} claim", observed=match.group(0) if match else "none", expected="none", passed=match is None, message="optional machine-generated text boundary scan")
        manifest_inputs.append({"path": display_path(text_path, project_root), "sha256": sha256(text_path)})

    write_csv(output_path, CHECK_COLUMNS, checks)
    failures = [row for row in checks if row["status"] == "failed"]
    if failures:
        raise ValueError(f"interpretation-boundary audit found {len(failures)} failure(s)")
    manifest_path = manifest_dir / "14_interpretation_checks.json"
    write_json(manifest_path, {"module": "src.analysis_14_interpretation_checks", "status": "passed", "analysis_timestamp_utc": utc_timestamp(), "inputs": manifest_inputs, "outputs": [{"name": "interpretation_checks", "path": display_path(output_path, project_root), "sha256": sha256(output_path), "rows": len(checks)}], "summary": {"checks_passed": len(checks), "checks_failed": 0, "registered_result_tables": len(registry), "optional_text_files_checked": len(text_files or [])}, "interpretation_scope": expected_scope})
    return {"checks": output_path, "manifest": manifest_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=PROJECT_ROOT / "data/results/validation/analysis_contract.csv")
    parser.add_argument("--registry", type=Path, default=PROJECT_ROOT / "data/results/manifests/result_table_registry.csv")
    parser.add_argument("--step13-manifest", type=Path, default=PROJECT_ROOT / "data/results/manifests/13_validate_outputs.json")
    parser.add_argument("--manifest-dir", type=Path, default=PROJECT_ROOT / "data/results/manifests")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data/results/manifests/interpretation_boundary_checks.csv")
    parser.add_argument("--text-file", type=Path, action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = run(contract_path=args.contract, registry_path=args.registry, step13_manifest=args.step13_manifest, manifest_dir=args.manifest_dir, output_path=args.output, text_files=args.text_file)
    print("Interpretation-boundary artifacts written:")
    for path in outputs.values():
        print(f"- {display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
