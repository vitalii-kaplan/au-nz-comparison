#!/usr/bin/env python3
"""Generate article table and bar-chart source from verified validation CSVs."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = PROJECT_ROOT / "data/results/validation/input_registry.csv"
DEFAULT_COVERAGE = PROJECT_ROOT / "data/results/validation/country_coverage.csv"
DEFAULT_CHECKS = PROJECT_ROOT / "data/results/validation/data_validation_checks.csv"
DEFAULT_TABLE = PROJECT_ROOT / "article/tables/dataset_scale_and_coverage.tex"
DEFAULT_FIGURE = PROJECT_ROOT / "article/figures/data_coverage_overview.tex"
EXPECTED_YEARS = (2022, 2023, 2024, 2025)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--country-coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--validation-checks", type=Path, default=DEFAULT_CHECKS)
    parser.add_argument("--table-output", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--figure-output", type=Path, default=DEFAULT_FIGURE)
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
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


def collect_summary(
    registry_path: Path,
    coverage_path: Path,
    checks_path: Path,
) -> dict[str, object]:
    registry = read_rows(registry_path)
    coverage = read_rows(coverage_path)
    checks = read_rows(checks_path)
    require_columns(
        registry_path,
        registry,
        {
            "destination_code",
            "destination_country",
            "country_count",
            "number_approved",
            "number_declined",
            "decision_total",
        },
    )
    require_columns(
        coverage_path,
        coverage,
        {"scope", "year", "country", "coverage_status"},
    )
    require_columns(checks_path, checks, {"status", "blocking"})

    failed_blocking = [
        row
        for row in checks
        if row["blocking"].strip().lower() == "true"
        and row["status"].strip().lower() != "passed"
    ]
    if failed_blocking:
        raise ValueError(
            f"{checks_path}: {len(failed_blocking)} blocking validation checks failed"
        )

    by_destination = {row["destination_code"]: row for row in registry}
    if set(by_destination) != {"AU", "NZ"} or len(registry) != 2:
        raise ValueError(f"{registry_path}: expected one AU row and one NZ row")

    destinations: dict[str, dict[str, int | str]] = {}
    for code in ("AU", "NZ"):
        row = by_destination[code]
        values = {
            "destination_country": row["destination_country"],
            "country_count": int(row["country_count"]),
            "number_approved": int(row["number_approved"]),
            "number_declined": int(row["number_declined"]),
            "decision_total": int(row["decision_total"]),
        }
        if values["number_approved"] + values["number_declined"] != values["decision_total"]:
            raise ValueError(f"{registry_path}: {code} counts do not reconcile")
        destinations[code] = values

    pooled_rows = [row for row in coverage if row["scope"] == "pooled"]
    pooled_statuses = Counter(row["coverage_status"] for row in pooled_rows)
    expected_statuses = {"both", "australia_only", "new_zealand_only"}
    if set(pooled_statuses) != expected_statuses:
        raise ValueError(
            f"{coverage_path}: unexpected pooled coverage statuses "
            f"{sorted(pooled_statuses)}"
        )

    annual_both: dict[int, int] = {}
    for year in EXPECTED_YEARS:
        annual_both[year] = sum(
            1
            for row in coverage
            if row["scope"] == "annual"
            and int(row["year"]) == year
            and row["coverage_status"] == "both"
        )
        if annual_both[year] == 0:
            raise ValueError(f"{coverage_path}: no matched countries for {year}")

    if (
        pooled_statuses["both"] + pooled_statuses["australia_only"]
        != destinations["AU"]["country_count"]
    ):
        raise ValueError(f"{coverage_path}: AU pooled coverage does not reconcile")
    if (
        pooled_statuses["both"] + pooled_statuses["new_zealand_only"]
        != destinations["NZ"]["country_count"]
    ):
        raise ValueError(f"{coverage_path}: NZ pooled coverage does not reconcile")

    return {
        "destinations": destinations,
        "pooled_coverage": dict(pooled_statuses),
        "annual_matched": annual_both,
        "validation_checks": len(checks),
    }


def format_integer(value: int) -> str:
    return f"{value:,}"


def render_table(summary: dict[str, object]) -> str:
    destinations = summary["destinations"]
    coverage = summary["pooled_coverage"]
    assert isinstance(destinations, dict)
    assert isinstance(coverage, dict)
    au = destinations["AU"]
    nz = destinations["NZ"]
    assert isinstance(au, dict)
    assert isinstance(nz, dict)

    return f"""% Generated by scripts/generate_article_validation_outputs.py. Do not edit.
\\begin{{table}}
\\caption{{Scale and pooled country coverage of the validated comparison data, 2022--2025}}
\\label{{tab:validated-scale-coverage}}
\\centering
\\small
Panel A: Destination-level scale\\par\\smallskip
\\begin{{tabular}}{{lrrrr}}
\\toprule
Destination & Origins & \\shortstack{{Approved\\\\or granted}} & \\shortstack{{Declined\\\\or refused}} & Decisions \\\\
\\midrule
Australia & {format_integer(int(au['country_count']))} & {format_integer(int(au['number_approved']))} & {format_integer(int(au['number_declined']))} & {format_integer(int(au['decision_total']))} \\\\
New Zealand & {format_integer(int(nz['country_count']))} & {format_integer(int(nz['number_approved']))} & {format_integer(int(nz['number_declined']))} & {format_integer(int(nz['decision_total']))} \\\\
\\bottomrule
\\end{{tabular}}

\\medskip
Panel B: Pooled origin-country coverage\\par\\smallskip
\\begin{{tabular}}{{lr}}
\\toprule
Coverage status & Origin countries \\\\
\\midrule
Represented in both destinations & {format_integer(int(coverage['both']))} \\\\
Australia only & {format_integer(int(coverage['australia_only']))} \\\\
New Zealand only & {format_integer(int(coverage['new_zealand_only']))} \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}
"""


def render_figure(summary: dict[str, object]) -> str:
    destinations = summary["destinations"]
    annual = summary["annual_matched"]
    assert isinstance(destinations, dict)
    assert isinstance(annual, dict)
    au = destinations["AU"]
    nz = destinations["NZ"]
    assert isinstance(au, dict)
    assert isinstance(nz, dict)
    annual_coordinates = " ".join(
        f"({year},{int(annual[year])})" for year in EXPECTED_YEARS
    )

    return f"""% Generated by scripts/generate_article_validation_outputs.py. Do not edit.
\\begin{{minipage}}[t]{{0.46\\textwidth}}
\\centering
\\begin{{tikzpicture}}
\\begin{{axis}}[
  width=0.80\\linewidth,
  height=5.2cm,
  ybar,
  bar width=20pt,
  symbolic x coords={{AU,NZ}},
  xtick=data,
  ymin=0,
  ylabel={{Recorded decisions}},
  title={{(a) Decision volume, 2022--2025}},
  scaled y ticks=false,
  yticklabel style={{/pgf/number format/fixed,/pgf/number format/1000 sep={{,}}}},
  enlarge x limits=0.45,
  tick label style={{font=\\small}},
  label style={{font=\\small}},
  title style={{font=\\small}},
]
\\addplot[fill=blue!65, draw=blue!80!black] coordinates {{(AU,{int(au['decision_total'])}) (NZ,{int(nz['decision_total'])})}};
\\end{{axis}}
\\end{{tikzpicture}}
\\end{{minipage}}%
\\hfill
\\begin{{minipage}}[t]{{0.46\\textwidth}}
\\centering
\\begin{{tikzpicture}}
\\begin{{axis}}[
  width=0.80\\linewidth,
  height=5.2cm,
  ybar,
  bar width=16pt,
  symbolic x coords={{2022,2023,2024,2025}},
  xtick=data,
  ymin=0,
  ymax=160,
  ylabel={{Matched origin countries}},
  title={{(b) Annual matched coverage}},
  nodes near coords,
  every node near coord/.append style={{font=\\scriptsize}},
  enlarge x limits=0.18,
  tick label style={{font=\\small}},
  label style={{font=\\small}},
  title style={{font=\\small}},
]
\\addplot[fill=gray!65, draw=black!75] coordinates {{{annual_coordinates}}};
\\end{{axis}}
\\end{{tikzpicture}}
\\end{{minipage}}
"""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_outputs(
    registry_path: Path = DEFAULT_REGISTRY,
    coverage_path: Path = DEFAULT_COVERAGE,
    checks_path: Path = DEFAULT_CHECKS,
    table_output: Path = DEFAULT_TABLE,
    figure_output: Path = DEFAULT_FIGURE,
) -> dict[str, Path]:
    summary = collect_summary(registry_path, coverage_path, checks_path)
    write_text(table_output, render_table(summary))
    write_text(figure_output, render_figure(summary))
    return {"table": table_output, "figure": figure_output}


def main() -> None:
    args = parse_args()
    outputs = generate_outputs(
        registry_path=args.input_registry,
        coverage_path=args.country_coverage,
        checks_path=args.validation_checks,
        table_output=args.table_output,
        figure_output=args.figure_output,
    )
    print(f"Wrote {outputs['table']}")
    print(f"Wrote {outputs['figure']}")


if __name__ == "__main__":
    main()
