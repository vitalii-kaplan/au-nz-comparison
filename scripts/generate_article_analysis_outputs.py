#!/usr/bin/env python3
"""Generate article tables and charts for Methods Sections 3 and 4."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESCRIPTIVE_DIR = PROJECT_ROOT / "data/results/descriptive"
PAIRED_DIR = PROJECT_ROOT / "data/results/paired"
MANIFEST_DIR = PROJECT_ROOT / "data/results/manifests"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descriptive-dir", type=Path, default=DESCRIPTIVE_DIR)
    parser.add_argument("--paired-dir", type=Path, default=PAIRED_DIR)
    parser.add_argument("--manifest-dir", type=Path, default=MANIFEST_DIR)
    parser.add_argument(
        "--table-dir", type=Path, default=PROJECT_ROOT / "article/tables"
    )
    parser.add_argument(
        "--figure-dir", type=Path, default=PROJECT_ROOT / "article/figures"
    )
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"{path}: missing CSV header")
        return list(reader)


def require_columns(path: Path, rows: list[dict[str, str]], required: set[str]) -> None:
    columns = set(rows[0]) if rows else set()
    missing = required.difference(columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(manifest_path: Path, expected_module: str) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("module") != expected_module or manifest.get("status") != "passed":
        raise ValueError(f"{manifest_path}: analysis did not pass")
    for output in manifest.get("outputs", []):
        path = PROJECT_ROOT / output["path"]
        if not path.exists() or sha256(path) != output["sha256"]:
            raise ValueError(f"{manifest_path}: output hash mismatch for {path}")


def percent(value: str | float, digits: int = 1) -> str:
    return f"{float(value) * 100.0:.{digits}f}"


def percentage_points(value: str | float, digits: int = 2) -> str:
    return f"{float(value) * 100.0:.{digits}f}"


def format_integer(value: str | float | int) -> str:
    return f"{int(float(value)):,}"


def format_count_statistic(value: str | float) -> str:
    number = float(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.1f}"


def format_p(value: str | float) -> str:
    number = float(value)
    return "$p<0.001$" if number < 0.001 else f"$p={number:.3f}$"


def collect_inputs(
    descriptive_dir: Path, paired_dir: Path, manifest_dir: Path
) -> dict[str, Any]:
    verify_manifest(manifest_dir / "03_descriptive.json", "src.analysis_03_descriptive")
    verify_manifest(
        manifest_dir / "04_matched_comparison.json",
        "src.analysis_04_matched_comparison",
    )
    paths = {
        "summary": descriptive_dir / "dataset_summary_by_destination.csv",
        "distributions": descriptive_dir / "country_level_distribution_statistics.csv",
        "approval_ecdf": descriptive_dir / "approval_rate_ecdf_points.csv",
        "decision_ecdf": descriptive_dir / "decision_volume_ecdf_points.csv",
        "matched_summary": paired_dir / "matched_difference_summary.csv",
        "tests": paired_dir / "paired_test_results.csv",
        "differences": paired_dir / "matched_country_differences.csv",
    }
    rows = {name: read_rows(path) for name, path in paths.items()}
    require_columns(
        paths["summary"],
        rows["summary"],
        {"destination_code", "represented_countries", "decision_total", "aggregate_approval_rate"},
    )
    require_columns(
        paths["distributions"],
        rows["distributions"],
        {
            "destination_code",
            "measure",
            "minimum",
            "q1",
            "median",
            "q3",
            "maximum",
            "mean",
            "sample_sd",
            "iqr",
        },
    )
    require_columns(
        paths["approval_ecdf"],
        rows["approval_ecdf"],
        {"destination_code", "approval_rate_percent", "ecdf"},
    )
    require_columns(
        paths["decision_ecdf"],
        rows["decision_ecdf"],
        {"destination_code", "decision_total", "log10_decision_total", "ecdf"},
    )
    require_columns(
        paths["matched_summary"],
        rows["matched_summary"],
        {
            "n_pairs",
            "n_positive",
            "n_negative",
            "n_zero",
            "mean_difference",
            "mean_ci_lower",
            "mean_ci_upper",
            "median_difference",
            "median_bootstrap_ci_lower",
            "median_bootstrap_ci_upper",
            "sample_sd",
            "q1",
            "q3",
            "minimum",
            "maximum",
        },
    )
    require_columns(
        paths["tests"], rows["tests"], {"test_name", "statistic", "p_value", "n"}
    )
    require_columns(
        paths["differences"],
        rows["differences"],
        {"country", "rate_difference_percentage_points"},
    )
    if len(rows["summary"]) != 2 or len(rows["matched_summary"]) != 1:
        raise ValueError("Unexpected descriptive or matched summary row count")
    return rows


def descriptive_table(data: dict[str, Any]) -> str:
    summary = {row["destination_code"]: row for row in data["summary"]}
    distributions = {
        (row["destination_code"], row["measure"]): row
        for row in data["distributions"]
    }
    lines = [
        "% Generated by scripts/generate_article_analysis_outputs.py. Do not edit.",
        "\\begin{table}[H]",
        "\\caption{Descriptive comparison of destination-level and country-level outcomes, 2022--2025}",
        "\\label{tab:descriptive-comparison}",
        "\\centering",
        "\\small",
        "Panel A: Decision-weighted destination summaries\\par\\smallskip",
        "\\begin{tabular}{l|rrr}",
        "\\toprule",
        "Destination & Origins & Decisions & Aggregate approval (\\%) \\\\",
        "\\midrule",
    ]
    for code in ("AU", "NZ"):
        row = summary[code]
        lines.append(
            f"{row['destination_country']} & {row['represented_countries']} & "
            f"{format_integer(row['decision_total'])} & {percent(row['aggregate_approval_rate'])} \\\\"
        )
    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
            "",
            "\\medskip",
            "Panel B: Country-weighted distributions\\par\\smallskip",
            "\\begin{tabular}{l|rr|rr}",
            "\\toprule",
            "Statistic & AU approval (\\%) & NZ approval (\\%) & AU decisions & NZ decisions \\\\",
            "\\midrule",
        ]
    )
    for label, field in (
        ("Minimum", "minimum"),
        ("First quartile", "q1"),
        ("Median", "median"),
        ("Third quartile", "q3"),
        ("Maximum", "maximum"),
        ("Mean", "mean"),
        ("Standard deviation", "sample_sd"),
        ("Interquartile range", "iqr"),
    ):
        lines.append(
            f"{label} & "
            f"{percent(distributions[('AU', 'approval_rate')][field])} & "
            f"{percent(distributions[('NZ', 'approval_rate')][field])} & "
            f"{format_count_statistic(distributions[('AU', 'decision_total')][field])} & "
            f"{format_count_statistic(distributions[('NZ', 'decision_total')][field])} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}", ""])
    return "\n".join(lines)


def paired_table(data: dict[str, Any]) -> str:
    summary = data["matched_summary"][0]
    tests = {row["test_name"]: row for row in data["tests"]}
    wilcoxon = tests["Wilcoxon signed-rank"]
    paired_t = tests["Paired t-test"]
    return f"""% Generated by scripts/generate_article_analysis_outputs.py. Do not edit.
\\begin{{table}}[H]
\\caption{{Matched-country AU-minus-NZ approval-rate comparison, 2022--2025}}
\\label{{tab:matched-country-comparison}}
\\centering
\\small
\\begin{{tabular}}{{lr}}
\\toprule
Quantity & Result \\\\
\\midrule
Matched countries & {summary['n_pairs']} \\\\
AU higher / NZ higher / equal & {summary['n_positive']} / {summary['n_negative']} / {summary['n_zero']} \\\\
Mean difference, percentage points (95\\% CI) & {percentage_points(summary['mean_difference'])} ({percentage_points(summary['mean_ci_lower'])}, {percentage_points(summary['mean_ci_upper'])}) \\\\
Median difference, percentage points (bootstrap 95\\% CI) & {percentage_points(summary['median_difference'])} ({percentage_points(summary['median_bootstrap_ci_lower'])}, {percentage_points(summary['median_bootstrap_ci_upper'])}) \\\\
Standard deviation, percentage points & {percentage_points(summary['sample_sd'])} \\\\
First / third quartile, percentage points & {percentage_points(summary['q1'])} / {percentage_points(summary['q3'])} \\\\
Range, percentage points & {percentage_points(summary['minimum'])} to {percentage_points(summary['maximum'])} \\\\
Wilcoxon signed-rank, $W$ ($n={wilcoxon['n']}$) & {float(wilcoxon['statistic']):.1f}; {format_p(wilcoxon['p_value'])} \\\\
Paired $t$ sensitivity, $t({paired_t['degrees_of_freedom']})$ & {float(paired_t['statistic']):.2f}; {format_p(paired_t['p_value'])} \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}
"""


def coordinates(rows: list[dict[str, str]], code: str, x: str, y: str) -> str:
    return " ".join(
        f"({float(row[x]):.12g},{float(row[y]):.12g})"
        for row in rows
        if row["destination_code"] == code
    )


def descriptive_figure(data: dict[str, Any]) -> str:
    au_rate = coordinates(data["approval_ecdf"], "AU", "ecdf", "approval_rate_percent")
    nz_rate = coordinates(data["approval_ecdf"], "NZ", "ecdf", "approval_rate_percent")
    au_volume = coordinates(data["decision_ecdf"], "AU", "ecdf", "log10_decision_total")
    nz_volume = coordinates(data["decision_ecdf"], "NZ", "ecdf", "log10_decision_total")
    return f"""% Generated by scripts/generate_article_analysis_outputs.py. Do not edit.
\\begin{{minipage}}[t]{{0.48\\textwidth}}
\\centering
\\begin{{tikzpicture}}
\\begin{{axis}}[
  width=0.88\\linewidth,
  height=5.2cm,
  xmin=0, xmax=1, ymin=0, ymax=100,
  xlabel={{ECDF}}, ylabel={{Country approval rate (\\%)}},
  title={{(a) Country approval rates}},
  legend style={{font=\\scriptsize, at={{(0.97,0.03)}}, anchor=south east, draw=none}},
  tick label style={{font=\\small}}, label style={{font=\\small}}, title style={{font=\\small}},
]
\\addplot[blue!80!black, thick, const plot] coordinates {{{au_rate}}};
\\addlegendentry{{Australia}}
\\addplot[red!80!black, thick, const plot] coordinates {{{nz_rate}}};
\\addlegendentry{{New Zealand}}
\\end{{axis}}
\\end{{tikzpicture}}
\\end{{minipage}}%
\\hfill
\\begin{{minipage}}[t]{{0.48\\textwidth}}
\\centering
\\begin{{tikzpicture}}
\\begin{{axis}}[
  width=0.88\\linewidth,
  height=5.2cm,
  xmin=0, xmax=1, ymin=0, ymax=5.5,
  xlabel={{ECDF}}, ylabel={{Log10 recorded decisions}},
  title={{(b) Country decision volumes}},
  legend style={{font=\\scriptsize, at={{(0.03,0.97)}}, anchor=north west, draw=none}},
  tick label style={{font=\\small}}, label style={{font=\\small}}, title style={{font=\\small}},
]
\\addplot[blue!80!black, thick, const plot] coordinates {{{au_volume}}};
\\addlegendentry{{Australia}}
\\addplot[red!80!black, thick, const plot] coordinates {{{nz_volume}}};
\\addlegendentry{{New Zealand}}
\\end{{axis}}
\\end{{tikzpicture}}
\\end{{minipage}}
"""


def decision_volume_bin_figure(data: dict[str, Any]) -> str:
    bin_counts: dict[str, Counter[int]] = {"AU": Counter(), "NZ": Counter()}
    for row in data["decision_ecdf"]:
        total = int(row["decision_total"])
        if total <= 0:
            raise ValueError("Decision-volume figure requires positive decision totals")
        bin_counts[row["destination_code"]][len(str(total)) - 1] += 1

    maximum_bin = max(max(counts) for counts in bin_counts.values())
    bins = list(range(maximum_bin + 1))
    ticks = ",".join(str(value) for value in bins)
    au = " ".join(f"({value},{bin_counts['AU'][value]})" for value in bins)
    nz = " ".join(f"({value},{bin_counts['NZ'][value]})" for value in bins)

    def panel(title: str, colour: str, coordinates_text: str) -> str:
        return f"""\\begin{{minipage}}[t]{{0.48\\textwidth}}
\\centering
\\begin{{tikzpicture}}
\\begin{{axis}}[
  width=0.88\\linewidth,
  height=5.2cm,
  xmin=-0.6, xmax={maximum_bin + 0.6}, ymin=0, ymax=80,
  xtick={{{ticks}}}, ytick={{0,10,...,80}},
  xlabel={{Log10 of recorded decisions}}, ylabel={{Number of origin countries}},
  title={{{title}}},
  ybar, bar width=12pt,
  nodes near coords,
  nodes near coords style={{font=\\scriptsize}},
  tick label style={{font=\\small}}, label style={{font=\\small}}, title style={{font=\\small}},
]
\\addplot[fill={colour}, draw=none] coordinates {{{coordinates_text}}};
\\end{{axis}}
\\end{{tikzpicture}}
\\end{{minipage}}"""

    return (
        "% Generated by scripts/generate_article_analysis_outputs.py. Do not edit.\n"
        + panel("(a) Australia", "blue!80!black", au)
        + "%\n\\hfill\n"
        + panel("(b) New Zealand", "red!80!black", nz)
        + "\n"
    )


def matched_figure(data: dict[str, Any]) -> str:
    ordered = sorted(
        (float(row["rate_difference_percentage_points"]), row["country"])
        for row in data["differences"]
    )
    summary = data["matched_summary"][0]
    mean = float(summary["mean_difference"]) * 100.0
    mean_lower = float(summary["mean_ci_lower"]) * 100.0
    mean_upper = float(summary["mean_ci_upper"]) * 100.0
    median = float(summary["median_difference"]) * 100.0
    median_lower = float(summary["median_bootstrap_ci_lower"]) * 100.0
    median_upper = float(summary["median_bootstrap_ci_upper"]) * 100.0
    points = " ".join(
        f"({rank},{value:.12g})" for rank, (value, _) in enumerate(ordered, start=1)
    )
    return f"""% Generated by scripts/generate_article_analysis_outputs.py. Do not edit.
\\begin{{tikzpicture}}
\\begin{{axis}}[
  width=0.92\\textwidth,
  height=12.0cm,
  xmin=1, xmax={len(ordered)},
  xlabel={{Countries ordered by AU-minus-NZ difference}},
  ylabel={{Approval-rate difference (percentage points)}},
  legend style={{font=\\scriptsize, at={{(0.03,0.97)}}, anchor=north west, draw=none, fill=white}},
  tick label style={{font=\\small}}, label style={{font=\\small}},
]
\\addplot[draw=none, fill=blue!14, forget plot] coordinates {{(1,{mean_lower:.12g}) ({len(ordered)},{mean_lower:.12g}) ({len(ordered)},{mean_upper:.12g}) (1,{mean_upper:.12g})}} \\closedcycle;
\\addplot[draw=none, fill=red!14, forget plot] coordinates {{(1,{median_lower:.12g}) ({len(ordered)},{median_lower:.12g}) ({len(ordered)},{median_upper:.12g}) (1,{median_upper:.12g})}} \\closedcycle;
\\addplot[gray!70, dashed, thick, domain=1:{len(ordered)}] {{0}};
\\addlegendentry{{Equality (zero difference)}}
\\addplot[only marks, mark=*, mark size=1.25pt, black!65] coordinates {{{points}}};
\\addlegendentry{{Country differences}}
\\addplot[blue!80!black, thick, domain=1:{len(ordered)}] {{{mean:.12g}}};
\\addlegendentry{{Mean (95\\% CI)}}
\\addplot[red!80!black, thick, densely dotted, domain=1:{len(ordered)}] {{{median:.12g}}};
\\addlegendentry{{Median (bootstrap 95\\% CI)}}
\\end{{axis}}
\\end{{tikzpicture}}
"""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_outputs(
    descriptive_dir: Path = DESCRIPTIVE_DIR,
    paired_dir: Path = PAIRED_DIR,
    manifest_dir: Path = MANIFEST_DIR,
    table_dir: Path = PROJECT_ROOT / "article/tables",
    figure_dir: Path = PROJECT_ROOT / "article/figures",
) -> dict[str, Path]:
    data = collect_inputs(descriptive_dir, paired_dir, manifest_dir)
    outputs = {
        "descriptive_table": table_dir / "descriptive_comparison.tex",
        "paired_table": table_dir / "matched_country_comparison.tex",
        "descriptive_figure": figure_dir / "descriptive_ecdfs.tex",
        "decision_bin_figure": figure_dir / "decision_volume_log10_bins.tex",
        "paired_figure": figure_dir / "matched_difference_distribution.tex",
    }
    write_text(outputs["descriptive_table"], descriptive_table(data))
    write_text(outputs["paired_table"], paired_table(data))
    write_text(outputs["descriptive_figure"], descriptive_figure(data))
    write_text(outputs["decision_bin_figure"], decision_volume_bin_figure(data))
    write_text(outputs["paired_figure"], matched_figure(data))
    return outputs


def main() -> None:
    args = parse_args()
    outputs = generate_outputs(
        descriptive_dir=args.descriptive_dir,
        paired_dir=args.paired_dir,
        manifest_dir=args.manifest_dir,
        table_dir=args.table_dir,
        figure_dir=args.figure_dir,
    )
    for path in outputs.values():
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
