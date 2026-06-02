#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install build twine

rm -rf dist
python -m build --wheel --sdist
twine check dist/*

wheel="$(find dist -maxdepth 1 -name '*.whl' | head -n 1)"
sdist="$(find dist -maxdepth 1 -name '*.tar.gz' | head -n 1)"

test -n "$wheel"
test -n "$sdist"
python -m zipfile -t "$wheel"
tar -tzf "$sdist" >/dev/null

rm -rf /tmp/benchwrap-wheel-venv
python -m venv /tmp/benchwrap-wheel-venv
/tmp/benchwrap-wheel-venv/bin/python -m pip install --upgrade pip
/tmp/benchwrap-wheel-venv/bin/python -m pip install "$wheel"
/tmp/benchwrap-wheel-venv/bin/python - <<'PY'
import importlib.resources as res
import subprocess

import benchwrap

benchmarks = res.files("benchwrap.benchmarks")
required = [
    "flops_matrix_mul_mini",
    "coremark_mini",
    "npb_ep_small",
    "npb_is_small",
    "fft_1d_small",
    "random_access_small",
]
missing = [name for name in required if not (benchmarks / name / "job_start.sh").is_file()]
if missing:
    raise SystemExit(f"missing benchmark job scripts in wheel: {missing}")

print("benchwrap imported from", benchwrap.__file__)
subprocess.run(["/tmp/benchwrap-wheel-venv/bin/benchwrap", "list"], check=True)
PY
