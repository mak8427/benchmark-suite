"""Convert LIKWID text output into a CSV artifact."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_likwid_rows(text: str) -> tuple[list[str], list[list[str]]]:
    """Return LIKWID table headers and rows from text output."""
    headers: list[str] = []
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# GID|"):
            headers = [part.strip() for part in stripped[2:].split("|")]
            continue
        if not headers or not stripped or stripped.startswith("-"):
            continue
        values = stripped.split()
        if len(values) == len(headers):
            rows.append(values)
    return headers, rows


def convert(input_path: Path, output_path: Path) -> int:
    """Write parsed LIKWID rows from input_path to output_path."""
    headers, rows = parse_likwid_rows(input_path.read_text(errors="replace"))
    if not headers or not rows:
        return 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    return convert(args.input, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
