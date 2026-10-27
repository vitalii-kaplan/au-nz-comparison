"""Produce descriptive AU-NZ comparison artifacts (Methods Section 3)."""

from __future__ import annotations

import argparse
import math
import statistics
from pathlib import Path
from typing import Any

from .analysis_common import (
    PROJECT_ROOT,
    display_path,
    quantile_type7,
    read_csv_rows,
    require_columns,
    require_passed_blocking_checks,
    sample_sd,
    sha256,
    utc_timestamp,
    write_csv,
    write_json,
)


INPUT_COLUMNS = {
    "destination_code",
    "destination_country",
    "period",
    "country",
    "number_approved",
    "number_declined",
    "decision_total",
    "approval_rate",
}
SUMMARY_COLUMNS = [
    "destination_code",
    "destination_country",
    "period",
    "represented_countries",
    "number_approved",
    "number_declined",
    "decision_total",
    "aggregate_approval_rate",
]
DISTRIBUTION_COLUMNS = [
    "destination_code",
    "destination_country",
    "measure",
    "unit",
    "n",
    "minimum",
    "q1",
    "median",
    "q3",
    "maximum",
    "mean",
    "sample_sd",
    "iqr",
    "quantile_method",
]
APPROVAL_ECDF_COLUMNS = [
    "destination_code",
    "destination_country",
    "country",
    "approval_rate",
    "approval_rate_percent",
    "rank",
    "ecdf",
]
DECISION_ECDF_COLUMNS = [
    "destination_code",
    "destination_country",
    "country",
    "decision_total",
    "log10_decision_total",
    "rank",
    "ecdf",
]


def validate_and_parse(path: Path) -> list[dict[str, Any]]:
    source = read_csv_rows(path)
    require_columns(path, source, INPUT_COLUMNS)
    if not source:
        raise ValueError(f"{path}: no observations")
    parsed: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for line_number, row in enumerate(source, start=2):
        code = row["destination_code"]
        country = row["country"]
        key = (code, country)
        if code not in {"AU", "NZ"}:
            raise ValueError(f"{path}:{line_number}: unexpected destination {code!r}")
        if not country or key in seen:
            raise ValueError(f"{path}:{line_number}: empty or duplicate key {key!r}")
        seen.add(key)
        approved = int(row["number_approved"])
        declined = int(row["number_declined"])
        total = int(row["decision_total"])
        rate = float(row["approval_rate"])
        if min(approved, declined) < 0 or total <= 0 or approved + declined != total:
            raise ValueError(f"{path}:{line_number}: invalid decision counts")
        if not math.isclose(rate, approved / total, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError(f"{path}:{line_number}: approval rate does not reconcile")
        parsed.append(
            {
                **row,
                "number_approved": approved,
                "number_declined": declined,
                "decision_total": total,
                "approval_rate": rate,
            }
        )
    if {str(row["destination_code"]) for row in parsed} != {"AU", "NZ"}:
        raise ValueError(f"{path}: both AU and NZ must be present")
    return parsed


def distribution_row(
    *, code: str, name: str, measure: str, unit: str, values: list[float]
) -> dict[str, Any]:
    q1 = quantile_type7(values, 0.25)
    median = quantile_type7(values, 0.50)
    q3 = quantile_type7(values, 0.75)
    return {
        "destination_code": code,
        "destination_country": name,
        "measure": measure,
        "unit": unit,
        "n": len(values),
        "minimum": min(values),
        "q1": q1,
        "median": median,
        "q3": q3,
        "maximum": max(values),
        "mean": statistics.fmean(values),
        "sample_sd": sample_sd(values),
        "iqr": q3 - q1,
        "quantile_method": "Hyndman-Fan type 7",
    }


def run(
    *,
    input_path: Path,
    validation_checks_path: Path,
    output_dir: Path,
    manifest_dir: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Path]:
    require_passed_blocking_checks(validation_checks_path)
    rows = validate_and_parse(input_path)
    summary_rows: list[dict[str, Any]] = []
    distribution_rows: list[dict[str, Any]] = []
    approval_ecdf: list[dict[str, Any]] = []
    decision_ecdf: list[dict[str, Any]] = []

    for code in ("AU", "NZ"):
        group = [row for row in rows if row["destination_code"] == code]
        group.sort(key=lambda row: str(row["country"]))
        name = str(group[0]["destination_country"])
        period = str(group[0]["period"])
        if any(row["destination_country"] != name or row["period"] != period for row in group):
            raise ValueError(f"{input_path}: inconsistent destination metadata for {code}")
        approved = sum(int(row["number_approved"]) for row in group)
        declined = sum(int(row["number_declined"]) for row in group)
        total = approved + declined
        summary_rows.append(
            {
                "destination_code": code,
                "destination_country": name,
                "period": period,
                "represented_countries": len(group),
                "number_approved": approved,
                "number_declined": declined,
                "decision_total": total,
                "aggregate_approval_rate": approved / total,
            }
        )

        rates = [float(row["approval_rate"]) for row in group]
        decisions = [float(row["decision_total"]) for row in group]
        distribution_rows.extend(
            [
                distribution_row(
                    code=code,
                    name=name,
                    measure="approval_rate",
                    unit="proportion",
                    values=rates,
                ),
                distribution_row(
                    code=code,
                    name=name,
                    measure="decision_total",
                    unit="recorded decisions",
                    values=decisions,
                ),
            ]
        )

        rate_sorted = sorted(group, key=lambda row: (float(row["approval_rate"]), str(row["country"])))
        for rank, row in enumerate(rate_sorted, start=1):
            rate = float(row["approval_rate"])
            approval_ecdf.append(
                {
                    "destination_code": code,
                    "destination_country": name,
                    "country": row["country"],
                    "approval_rate": rate,
                    "approval_rate_percent": rate * 100.0,
                    "rank": rank,
                    "ecdf": rank / len(rate_sorted),
                }
            )

        decision_sorted = sorted(group, key=lambda row: (int(row["decision_total"]), str(row["country"])))
        for rank, row in enumerate(decision_sorted, start=1):
            total_value = int(row["decision_total"])
            decision_ecdf.append(
                {
                    "destination_code": code,
                    "destination_country": name,
                    "country": row["country"],
                    "decision_total": total_value,
                    "log10_decision_total": math.log10(total_value),
                    "rank": rank,
                    "ecdf": rank / len(decision_sorted),
                }
            )

    outputs = {
        "dataset_summary": output_dir / "dataset_summary_by_destination.csv",
        "distribution_statistics": output_dir / "country_level_distribution_statistics.csv",
        "approval_rate_ecdf": output_dir / "approval_rate_ecdf_points.csv",
        "decision_volume_ecdf": output_dir / "decision_volume_ecdf_points.csv",
        "manifest": manifest_dir / "03_descriptive.json",
    }
    write_csv(outputs["dataset_summary"], SUMMARY_COLUMNS, summary_rows)
    write_csv(outputs["distribution_statistics"], DISTRIBUTION_COLUMNS, distribution_rows)
    write_csv(outputs["approval_rate_ecdf"], APPROVAL_ECDF_COLUMNS, approval_ecdf)
    write_csv(outputs["decision_volume_ecdf"], DECISION_ECDF_COLUMNS, decision_ecdf)

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
            "module": "src.analysis_03_descriptive",
            "status": "passed",
            "analysis_timestamp_utc": utc_timestamp(),
            "inputs": [
                {"path": display_path(input_path, project_root), "sha256": sha256(input_path)},
                {"path": display_path(validation_checks_path, project_root), "sha256": sha256(validation_checks_path)},
            ],
            "outputs": manifest_outputs,
            "summary": {
                row["destination_code"]: {
                    "represented_countries": row["represented_countries"],
                    "decision_total": row["decision_total"],
                    "aggregate_approval_rate": row["aggregate_approval_rate"],
                }
                for row in summary_rows
            },
            "methods": {
                "aggregate_rate": "sum(approved) / sum(decisions)",
                "country_distribution_weighting": "one represented country per observation",
                "sample_sd_denominator": "n - 1",
                "quantile_method": "Hyndman-Fan type 7",
                "decision_volume_plot_transform": "log10 for positive decision totals only",
            },
        },
    )
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=PROJECT_ROOT / "data/prepared/comparison/destination_country_2022-2025.csv",
    )
    parser.add_argument(
        "--validation-checks",
        type=Path,
        default=PROJECT_ROOT / "data/results/validation/data_validation_checks.csv",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "data/results/descriptive"
    )
    parser.add_argument(
        "--manifest-dir", type=Path, default=PROJECT_ROOT / "data/results/manifests"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = run(
        input_path=args.input,
        validation_checks_path=args.validation_checks,
        output_dir=args.output_dir,
        manifest_dir=args.manifest_dir,
    )
    print("Descriptive artifacts written:")
    for path in outputs.values():
        print(f"- {display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
