"""Define and verify the machine-readable analysis contract (Methods Section 1)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .analysis_common import (
    PREPARED_COLUMNS,
    PROJECT_ROOT,
    display_path,
    read_json,
    read_prepared_table,
    resolve_from_root,
    sha256,
    table_totals,
    utc_timestamp,
    write_csv,
    write_json,
)


CONTRACT_COLUMNS = [
    "contract_item",
    "item_type",
    "symbol",
    "definition",
    "unit",
    "weighting",
    "formula",
    "direction",
    "interpretation",
]
INPUT_REGISTRY_COLUMNS = [
    "destination_code",
    "destination_country",
    "period",
    "input_file",
    "sha256",
    "row_count",
    "country_count",
    "number_approved",
    "number_declined",
    "decision_total",
    "minimum_country_decisions",
    "maximum_country_decisions",
]


def contract_rows(config: dict[str, Any]) -> list[dict[str, str]]:
    direction = str(config["rate_difference_direction"])
    interpretation = str(config["interpretation_scope"])
    return [
        {
            "contract_item": "origin_country",
            "item_type": "index",
            "symbol": "i",
            "definition": "Normalized applicant origin country or reviewed exception",
            "unit": "country",
            "weighting": "not applicable",
            "formula": "not applicable",
            "direction": "not applicable",
            "interpretation": interpretation,
        },
        {
            "contract_item": "destination",
            "item_type": "index",
            "symbol": "j",
            "definition": "Visa destination",
            "unit": "AU or NZ",
            "weighting": "not applicable",
            "formula": "not applicable",
            "direction": "AU compared with NZ",
            "interpretation": interpretation,
        },
        {
            "contract_item": "calendar_year",
            "item_type": "index",
            "symbol": "t",
            "definition": "Calendar year of recorded decision",
            "unit": "year",
            "weighting": "not applicable",
            "formula": "2022, 2023, 2024, or 2025",
            "direction": "not applicable",
            "interpretation": interpretation,
        },
        {
            "contract_item": "approved",
            "item_type": "measure",
            "symbol": "A_ijt",
            "definition": "Approvals for NZ or grants for AU",
            "unit": "recorded decisions",
            "weighting": "count",
            "formula": "source approved or granted count",
            "direction": "higher is more approvals or grants",
            "interpretation": interpretation,
        },
        {
            "contract_item": "declined",
            "item_type": "measure",
            "symbol": "D_ijt",
            "definition": "Declines for NZ or refusals for AU",
            "unit": "recorded decisions",
            "weighting": "count",
            "formula": "source declined or refused count",
            "direction": "higher is more declines or refusals",
            "interpretation": interpretation,
        },
        {
            "contract_item": "decision_total",
            "item_type": "measure",
            "symbol": "N_ijt",
            "definition": "Observed two-outcome decision denominator",
            "unit": "recorded decisions",
            "weighting": "count",
            "formula": "A_ijt + D_ijt",
            "direction": "higher is more recorded decisions",
            "interpretation": "Not official application or lodgement volume",
        },
        {
            "contract_item": "approval_proportion",
            "item_type": "estimand",
            "symbol": "p_ijt",
            "definition": "Approval or grant proportion among observed decisions",
            "unit": "proportion",
            "weighting": "decision denominator",
            "formula": "A_ijt / N_ijt",
            "direction": "higher is a larger approved share",
            "interpretation": interpretation,
        },
        {
            "contract_item": "matched_rate_difference",
            "item_type": "estimand",
            "symbol": "Delta_i",
            "definition": "Matched-country AU minus NZ approval-rate difference",
            "unit": "proportion; report as percentage points",
            "weighting": "country-weighted unless otherwise stated",
            "formula": "p_i,AU - p_i,NZ",
            "direction": direction,
            "interpretation": "Positive means AU higher; negative means NZ higher",
        },
        {
            "contract_item": "decision_weighted_perspective",
            "item_type": "weighting",
            "symbol": "P_j",
            "definition": "Typical recorded decision within a destination",
            "unit": "destination",
            "weighting": "decision-weighted",
            "formula": "sum_i(A_ij) / sum_i(N_ij)",
            "direction": "destination-specific",
            "interpretation": interpretation,
        },
        {
            "contract_item": "country_weighted_perspective",
            "item_type": "weighting",
            "symbol": "country",
            "definition": "Typical represented origin country",
            "unit": "country",
            "weighting": "each country contributes once",
            "formula": "summary across country-level values",
            "direction": direction,
            "interpretation": interpretation,
        },
        {
            "contract_item": "country_year_perspective",
            "item_type": "weighting",
            "symbol": "country-year",
            "definition": "Temporal observation for an origin and destination",
            "unit": "country-year",
            "weighting": "each observed country-year contributes once unless modelled by counts",
            "formula": "one row per destination-country-year",
            "direction": direction,
            "interpretation": interpretation,
        },
    ]


def validate_schema(schema_path: Path) -> None:
    schema = read_json(schema_path)
    required = schema.get("items", {}).get("required")
    column_order = schema.get("x-table", {}).get("column_order")
    if required != PREPARED_COLUMNS or column_order != PREPARED_COLUMNS:
        raise ValueError(
            f"{schema_path}: prepared schema does not match {PREPARED_COLUMNS!r}"
        )


def run(
    *,
    config_path: Path,
    schema_path: Path,
    validation_dir: Path,
    manifest_dir: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Path]:
    config = read_json(config_path)
    validate_schema(schema_path)

    destinations = config.get("destinations")
    if not isinstance(destinations, dict) or set(destinations) != {"AU", "NZ"}:
        raise ValueError("Configuration must define exactly AU and NZ destinations")
    if config.get("rate_difference_direction") != "AU - NZ":
        raise ValueError("Rate-difference direction must be AU - NZ")
    if config.get("years") != [2022, 2023, 2024, 2025]:
        raise ValueError("Analysis years must be 2022-2025")

    registry_rows: list[dict[str, Any]] = []
    input_manifest: list[dict[str, Any]] = []
    for code in ("AU", "NZ"):
        settings = destinations[code]
        input_path = resolve_from_root(settings["pooled_file"], project_root)
        rows = read_prepared_table(input_path)
        totals = table_totals(rows)
        decisions = [int(row["Total applications"]) for row in rows]
        registry_rows.append(
            {
                "destination_code": code,
                "destination_country": settings["name"],
                "period": config["period"],
                "input_file": display_path(input_path, project_root),
                "sha256": sha256(input_path),
                "row_count": len(rows),
                "country_count": len({row["Country"] for row in rows}),
                **totals,
                "minimum_country_decisions": min(decisions),
                "maximum_country_decisions": max(decisions),
            }
        )
        input_manifest.append(
            {
                "destination_code": code,
                "path": display_path(input_path, project_root),
                "sha256": sha256(input_path),
                "rows": len(rows),
            }
        )

    contract_path = validation_dir / "analysis_contract.csv"
    registry_path = validation_dir / "input_registry.csv"
    manifest_path = manifest_dir / "01_analysis_contract.json"
    write_csv(contract_path, CONTRACT_COLUMNS, contract_rows(config))
    write_csv(registry_path, INPUT_REGISTRY_COLUMNS, registry_rows)

    manifest = {
        "module": "src.analysis_01_define_contract",
        "status": "passed",
        "analysis_timestamp_utc": utc_timestamp(),
        "config_file": display_path(config_path, project_root),
        "config_sha256": sha256(config_path),
        "schema_file": display_path(schema_path, project_root),
        "schema_sha256": sha256(schema_path),
        "inputs": input_manifest,
        "outputs": [
            {
                "path": display_path(contract_path, project_root),
                "sha256": sha256(contract_path),
                "rows": len(contract_rows(config)),
            },
            {
                "path": display_path(registry_path, project_root),
                "sha256": sha256(registry_path),
                "rows": len(registry_rows),
            },
        ],
        "validation": {
            "prepared_schema_matches": True,
            "destinations_are_au_and_nz": True,
            "years_are_2022_to_2025": True,
            "difference_direction_is_au_minus_nz": True,
            "pooled_inputs_pass_table_validation": True,
        },
    }
    write_json(manifest_path, manifest)
    return {
        "contract": contract_path,
        "input_registry": registry_path,
        "manifest": manifest_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=PROJECT_ROOT / "src/analysis_config.json"
    )
    parser.add_argument(
        "--schema", type=Path, default=PROJECT_ROOT / "data/schema.json"
    )
    parser.add_argument(
        "--validation-dir",
        type=Path,
        default=PROJECT_ROOT / "data/results/validation",
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=PROJECT_ROOT / "data/results/manifests",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = run(
        config_path=args.config,
        schema_path=args.schema,
        validation_dir=args.validation_dir,
        manifest_dir=args.manifest_dir,
    )
    print("Analysis contract verified and written:")
    for path in outputs.values():
        print(f"- {display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
