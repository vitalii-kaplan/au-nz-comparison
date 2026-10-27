"""Run the complete research pipeline in dependency order (Step 15)."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from .analysis_common import PROJECT_ROOT, display_path, read_csv_rows, read_json, sha256, utc_timestamp, write_csv, write_json


STAGES = (
    ("01", "src.analysis_01_define_contract"),
    ("02", "src.analysis_02_build_tables"),
    ("11", "src.analysis_11_comparability"),
    ("03", "src.analysis_03_descriptive"),
    ("04", "src.analysis_04_matched_comparison"),
    ("05", "src.analysis_05_concordance"),
    ("06", "src.analysis_06_country_differences"),
    ("07", "src.analysis_07_binomial_regression"),
    ("08", "src.analysis_08_origin_composition"),
    ("09", "src.analysis_09_temporal"),
    ("10", "src.analysis_10_sensitivity"),
    ("P01", "scripts.generate_article_validation_outputs"),
    ("P02", "scripts.generate_article_comparability_outputs"),
    ("P03", "scripts.generate_article_analysis_outputs"),
    ("P04", "scripts.generate_article_concordance_country_outputs"),
    ("P05", "scripts.generate_article_model_outputs"),
    ("P06", "scripts.generate_article_sensitivity_outputs"),
    ("12", "src.analysis_12_reproducibility"),
    ("13", "src.analysis_13_validate_outputs"),
    ("14", "src.analysis_14_interpretation_checks"),
)
STATUS_COLUMNS = [
    "sequence", "step", "module", "started_utc", "ended_utc",
    "duration_seconds", "status", "exit_code", "message",
]
Runner = Callable[[str], tuple[int, str]]


def gate_eligibility(path: Path) -> dict[str, bool]:
    rows = read_csv_rows(path)
    decisions = {row["analysis_component"]: row["eligible"].lower() == "true" for row in rows}
    required = {"country_year_binomial_model", "annual_paired_analysis"}
    if not required.issubset(decisions):
        raise ValueError(f"{path}: missing required gate decisions")
    return decisions


def subprocess_runner(module: str, project_root: Path = PROJECT_ROOT) -> tuple[int, str]:
    completed = subprocess.run(
        [sys.executable, "-m", module],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout + "\n" + completed.stderr).strip()
    message = output.splitlines()[-1] if output else "completed without console output"
    return completed.returncode, message


def execute_pipeline(
    *,
    status_path: Path,
    gate_path: Path,
    runner: Runner,
) -> tuple[bool, list[dict[str, str | int | float]]]:
    status_rows: list[dict[str, str | int | float]] = []
    gates: dict[str, bool] | None = None
    for sequence, (step, module) in enumerate(STAGES, start=1):
        skip_reason = ""
        if step == "07" and gates is not None and not gates["country_year_binomial_model"]:
            skip_reason = "comparability gate did not establish country-year model eligibility"
        if step == "09" and gates is not None and not gates["annual_paired_analysis"]:
            skip_reason = "comparability gate did not establish annual paired-analysis eligibility"
        started = utc_timestamp()
        clock = time.perf_counter()
        if skip_reason:
            row = {"sequence": sequence, "step": step, "module": module, "started_utc": started, "ended_utc": utc_timestamp(), "duration_seconds": round(time.perf_counter() - clock, 6), "status": "skipped", "exit_code": "", "message": skip_reason}
            status_rows.append(row)
            write_csv(status_path, STATUS_COLUMNS, status_rows)
            continue
        exit_code, message = runner(module)
        row = {"sequence": sequence, "step": step, "module": module, "started_utc": started, "ended_utc": utc_timestamp(), "duration_seconds": round(time.perf_counter() - clock, 6), "status": "passed" if exit_code == 0 else "failed", "exit_code": exit_code, "message": message}
        status_rows.append(row)
        write_csv(status_path, STATUS_COLUMNS, status_rows)
        if exit_code != 0:
            return False, status_rows
        if step == "11":
            gates = gate_eligibility(gate_path)
    return True, status_rows


def run(
    *,
    status_path: Path,
    gate_path: Path,
    manifest_dir: Path,
    project_root: Path = PROJECT_ROOT,
    runner: Runner | None = None,
) -> dict[str, Path]:
    active_runner = runner or (lambda module: subprocess_runner(module, project_root))
    passed, rows = execute_pipeline(status_path=status_path, gate_path=gate_path, runner=active_runner)
    if not passed:
        failed = next(row for row in rows if row["status"] == "failed")
        raise RuntimeError(f"pipeline stopped at Step {failed['step']}: {failed['message']}")
    step14_path = manifest_dir / "14_interpretation_checks.json"
    step14 = read_json(step14_path)
    if step14.get("status") != "passed":
        raise ValueError("final interpretation-boundary gate did not pass")
    pipeline_run_path = manifest_dir / "pipeline_run.json"
    if read_json(pipeline_run_path).get("status") != "passed":
        raise ValueError("reproducibility pipeline record did not pass")
    manifest_path = manifest_dir / "15_pipeline.json"
    write_json(manifest_path, {"module": "src.analysis_15_run_pipeline", "status": "passed", "analysis_timestamp_utc": utc_timestamp(), "execution_order": [step for step, _ in STAGES], "inputs": [{"path": display_path(gate_path, project_root), "sha256": sha256(gate_path)}, {"path": display_path(step14_path, project_root), "sha256": sha256(step14_path)}, {"path": display_path(pipeline_run_path, project_root), "sha256": sha256(pipeline_run_path)}], "outputs": [{"name": "pipeline_stage_status", "path": display_path(status_path, project_root), "sha256": sha256(status_path), "rows": len(rows)}], "summary": {"stages_passed": sum(row["status"] == "passed" for row in rows), "stages_skipped": sum(row["status"] == "skipped" for row in rows), "stages_failed": 0}})
    return {"stage_status": status_path, "pipeline_run": pipeline_run_path, "manifest": manifest_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-output", type=Path, default=PROJECT_ROOT / "data/results/manifests/pipeline_stage_status.csv")
    parser.add_argument("--gate", type=Path, default=PROJECT_ROOT / "data/results/validation/comparability_decisions.csv")
    parser.add_argument("--manifest-dir", type=Path, default=PROJECT_ROOT / "data/results/manifests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        outputs = run(status_path=args.status_output, gate_path=args.gate, manifest_dir=args.manifest_dir)
    except (RuntimeError, ValueError) as error:
        print(f"Pipeline failed: {error}", file=sys.stderr)
        return 1
    print("Research pipeline completed:")
    for path in outputs.values():
        print(f"- {display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
