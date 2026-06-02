"""Tests for LIKWID CSV artifact conversion."""

from __future__ import annotations

from benchwrap.executors.utils.likwid_csv import convert, parse_likwid_rows

TEXT = """
# GID|MetricsCount|CpuCount|Total runtime [s]|Clock [MHz]|CPI|DP [MFLOP/s]
1 10 1 1.000 2880.0 0.42 123.4
coremark_mini digest=1 score=2
"""


def test_parse_likwid_rows_ignores_benchmark_output() -> None:
    headers, rows = parse_likwid_rows(TEXT)

    assert headers == [
        "GID",
        "MetricsCount",
        "CpuCount",
        "Total runtime [s]",
        "Clock [MHz]",
        "CPI",
        "DP [MFLOP/s]",
    ]
    assert rows == [["1", "10", "1", "1.000", "2880.0", "0.42", "123.4"]]


def test_convert_writes_csv(tmp_path) -> None:
    src = tmp_path / "likwid.out"
    dst = tmp_path / "likwid.csv"
    src.write_text(TEXT, encoding="utf-8")

    assert convert(src, dst) == 0
    assert dst.read_text(encoding="utf-8").splitlines() == [
        "GID,MetricsCount,CpuCount,Total runtime [s],Clock [MHz],CPI,DP [MFLOP/s]",
        "1,10,1,1.000,2880.0,0.42,123.4",
    ]
