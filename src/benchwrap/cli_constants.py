"""Shared constants for the Benchwrap CLI commands."""

from __future__ import annotations

import os
import pathlib

BENCH_PKG = "benchwrap.benchmarks"
EXECUTORS_PKG = "benchwrap.executors"
DATA_DIR = (
    pathlib.Path(os.getenv("XDG_DATA_HOME", pathlib.Path.home() / ".local/share"))
    / "benchwrap"
)
TOK_FILE = DATA_DIR / "tokens"
USER_ROOT = (
    pathlib.Path(os.getenv("XDG_DATA_HOME", pathlib.Path.home() / ".local/share"))
    / "benchwrap/benchmarks"
)
JOBS_DEFAULT = DATA_DIR / "jobs"
BENCH_ROOT = pathlib.Path(__file__).parent.parent / "src/benchmarks"
BASE_URL = "http://141.5.110.112:7800"
