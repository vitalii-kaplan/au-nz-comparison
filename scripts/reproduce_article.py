#!/usr/bin/env python3
"""Reproduce the article from the selectively extracted source data."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_INITIAL_INPUTS = (
    ROOT / "data/original/australia/student_visa_grant_rates_2005_2026-02-28.csv",
    ROOT / "data/original/new-zealand/student_visa_decisions_2022.csv",
    ROOT / "data/original/new-zealand/student_visa_decisions_2023.csv",
    ROOT / "data/original/new-zealand/student_visa_decisions_2024.csv",
    ROOT / "data/original/new-zealand/student_visa_decisions_2025.csv",
    ROOT / "data/original/reference/un-m49-overview.html",
    ROOT / "data/reference/country_aliases.csv",
)
PREPARATION_MODULES = (
    "scripts.prepare_new_zealand",
    "scripts.prepare_australia",
    "scripts.extract_un_m49",
    "scripts.check_country_names",
)


def require_initial_inputs() -> None:
    missing = [path.relative_to(ROOT) for path in REQUIRED_INITIAL_INPUTS if not path.exists()]
    if missing:
        listing = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(
            "Required source inputs are missing. Follow data/README.md to download "
            f"and selectively extract them:\n{listing}"
        )


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-preparation",
        action="store_true",
        help="reuse existing prepared inputs and begin with the analysis pipeline",
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="run the complete unittest suite after reproducing the outputs",
    )
    parser.add_argument(
        "--build-pdf",
        action="store_true",
        help="compile article/article.pdf with latexmk after reproducing the outputs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.skip_preparation:
        require_initial_inputs()
        for module in PREPARATION_MODULES:
            run([sys.executable, "-m", module])

    run([sys.executable, "-m", "src.analysis_15_run_pipeline"])

    if args.run_tests:
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    if args.build_pdf:
        run(
            [
                "latexmk",
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "article.tex",
            ],
            cwd=ROOT / "article",
        )

    print("Article reproduction completed successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        print(f"Reproduction failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
