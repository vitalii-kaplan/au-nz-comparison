"""Shared deterministic I/O and validation helpers for research modules."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREPARED_COLUMNS = [
    "Country",
    "Number approved",
    "Number declined",
    "Total applications",
    "Approval rate",
]


def resolve_from_root(path: str | Path, root: Path = PROJECT_ROOT) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / candidate


def display_path(path: Path, root: Path = PROJECT_ROOT) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def read_prepared_table(path: Path) -> list[dict[str, Any]]:
    """Read and fully validate one five-column prepared decision table."""

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != PREPARED_COLUMNS:
            raise ValueError(
                f"{path}: expected columns {PREPARED_COLUMNS!r}, "
                f"found {reader.fieldnames!r}"
            )
        rows: list[dict[str, Any]] = []
        for line_number, source_row in enumerate(reader, start=2):
            country = source_row["Country"].strip()
            if not country:
                raise ValueError(f"{path}:{line_number}: empty Country")
            try:
                approved = int(source_row["Number approved"])
                declined = int(source_row["Number declined"])
                decisions = int(source_row["Total applications"])
                rate = float(source_row["Approval rate"])
            except ValueError as error:
                raise ValueError(
                    f"{path}:{line_number}: invalid numeric value"
                ) from error
            if min(approved, declined, decisions) < 0:
                raise ValueError(f"{path}:{line_number}: negative count")
            if decisions <= 0:
                raise ValueError(f"{path}:{line_number}: decision total must be positive")
            if decisions != approved + declined:
                raise ValueError(f"{path}:{line_number}: counts do not reconcile")
            if not 0.0 <= rate <= 1.0:
                raise ValueError(f"{path}:{line_number}: rate outside [0, 1]")
            if not math.isclose(
                rate, approved / decisions, rel_tol=0.0, abs_tol=1e-15
            ):
                raise ValueError(f"{path}:{line_number}: rate does not reconcile")
            rows.append(
                {
                    "Country": country,
                    "Number approved": approved,
                    "Number declined": declined,
                    "Total applications": decisions,
                    "Approval rate": rate,
                }
            )

    countries = [str(row["Country"]) for row in rows]
    if countries != sorted(countries):
        raise ValueError(f"{path}: Country keys are not sorted")
    if len(countries) != len(set(countries)):
        raise ValueError(f"{path}: duplicate Country key")
    return rows


def table_totals(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "number_approved": sum(int(row["Number approved"]) for row in rows),
        "number_declined": sum(int(row["Number declined"]) for row in rows),
        "decision_total": sum(int(row["Total applications"]) for row in rows),
    }


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"{path}: missing CSV header")
        return list(reader)


def require_columns(
    path: Path, rows: list[dict[str, str]], required: set[str]
) -> None:
    columns = set(rows[0]) if rows else set()
    missing = required.difference(columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")


def require_passed_blocking_checks(path: Path) -> list[dict[str, str]]:
    rows = read_csv_rows(path)
    require_columns(path, rows, {"status", "blocking"})
    failures = [
        row
        for row in rows
        if row["blocking"].strip().lower() == "true"
        and row["status"].strip().lower() != "passed"
    ]
    if failures:
        raise ValueError(f"{path}: {len(failures)} blocking validation checks failed")
    return rows


def quantile_type7(values: Iterable[float], probability: float) -> float:
    """Return the Hyndman-Fan type-7 sample quantile used by R and NumPy."""

    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("quantile requires at least one value")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("quantile probability must be between zero and one")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def sample_sd(values: Iterable[float]) -> float:
    numbers = [float(value) for value in values]
    if len(numbers) < 2:
        raise ValueError("sample standard deviation requires at least two values")
    return statistics.stdev(numbers)
