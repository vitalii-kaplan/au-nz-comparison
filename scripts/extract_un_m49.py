#!/usr/bin/env python3
"""Extract the English UN M49 table from a downloaded UNSD overview page."""

from __future__ import annotations

import argparse
import csv
from html.parser import HTMLParser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data/original/reference/un-m49-overview.html"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/original/reference/un-m49.csv"
EXPECTED_COLUMNS = [
    "Global Code",
    "Global Name",
    "Region Code",
    "Region Name",
    "Sub-region Code",
    "Sub-region Name",
    "Intermediate Region Code",
    "Intermediate Region Name",
    "Country or Area",
    "M49 Code",
    "ISO-alpha2 Code",
    "ISO-alpha3 Code",
    "Least Developed Countries (LDC)",
    "Land Locked Developing Countries (LLDC)",
    "Small Island Developing States (SIDS)",
]


class EnglishM49TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[str] | None = None
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and attributes.get("id") == "downloadTableEN":
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.current_row = []
        elif self.in_table and tag in {"td", "th"} and self.current_row is not None:
            self.in_cell = True
            self.current_cell = []

    def handle_data(self, data: str) -> None:
        if self.in_table and self.in_cell:
            self.current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.in_table and tag in {"td", "th"} and self.in_cell:
            value = " ".join("".join(self.current_cell).split())
            if value == "x":
                value = "x"
            assert self.current_row is not None
            self.current_row.append(value)
            self.in_cell = False
            self.current_cell = []
        elif self.in_table and tag == "tr" and self.current_row is not None:
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = None
        elif self.in_table and tag == "table":
            self.in_table = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    parser = EnglishM49TableParser()
    parser.feed(args.input.read_text(encoding="utf-8"))
    if not parser.rows:
        raise ValueError(f"No English M49 table found in {args.input}")
    header, *rows = parser.rows
    if header != EXPECTED_COLUMNS:
        raise ValueError(f"Unexpected M49 columns: {header!r}")
    if any(len(row) != len(header) for row in rows):
        raise ValueError("The downloaded M49 table contains a malformed row")
    if len(rows) < 240:
        raise ValueError(f"Expected at least 240 M49 country/area rows; found {len(rows)}")
    names = [row[header.index("Country or Area")] for row in rows]
    codes = [row[header.index("M49 Code")] for row in rows]
    if len(names) != len(set(names)) or len(codes) != len(set(codes)):
        raise ValueError("M49 country/area names or codes are not unique")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    print(f"Extracted {len(rows)} UN M49 country/area rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
