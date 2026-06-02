"""Smoke tests for benchmark workload output contracts."""

from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

WORKLOADS = [
    (
        "benchwrap.benchmarks.coremark_mini.workload",
        {
            "COREMARK_MINI_SIZE": "1024",
            "COREMARK_MINI_ITERS": "1",
            "COREMARK_MINI_SECONDS": "0.01",
        },
        [r"coremark_mini size=1024", r"digest=\d+", r"score=[0-9.]+ ops/s"],
    ),
    (
        "benchwrap.benchmarks.fft_1d_small.workload",
        {"FFT_SIZE": "1024", "FFT_ITERS": "1", "FFT_SECONDS": "0.01"},
        [r"fft_1d_small size=1024", r"checksum=[0-9.]+", r"estimated_gflops="],
    ),
    (
        "benchwrap.benchmarks.flops_matrix_mul_mini.workload",
        {"FLOPS_MATRIX_MUL_MINI_N": "64"},
        [r"Allocating two 64x64 matrices", r"GEMM done in", r"Frobenius ="],
    ),
    (
        "benchwrap.benchmarks.npb_ep_small.workload",
        {
            "NPB_EP_PAIRS": "2048",
            "NPB_EP_CHUNKS": "2",
            "NPB_EP_SECONDS": "0.01",
        },
        [r"npb_ep_small pairs=2048", r"checksum=", r"pairs_per_s="],
    ),
    (
        "benchwrap.benchmarks.npb_is_small.workload",
        {
            "NPB_IS_KEYS": "1024",
            "NPB_IS_ITERS": "1",
            "NPB_IS_MAX_KEY": "256",
            "NPB_IS_SECONDS": "0.01",
        },
        [r"npb_is_small keys=1024", r"checksum=\d+", r"keys_per_s="],
    ),
    (
        "benchwrap.benchmarks.random_access_small.workload",
        {
            "RANDOM_ACCESS_SIZE": "1024",
            "RANDOM_ACCESS_UPDATES": "2048",
            "RANDOM_ACCESS_CHUNK": "512",
            "RANDOM_ACCESS_SECONDS": "0.01",
        },
        [r"random_access_small size=1024", r"checksum=\d+", r"updates_per_s="],
    ),
]


@pytest.mark.parametrize(("module", "extra_env", "patterns"), WORKLOADS)
def test_quick_benchmark_workloads_emit_expected_output(
    module, extra_env, patterns
) -> None:
    """CI-sized workloads should run and emit stable success signatures."""
    env = {
        **os.environ,
        **extra_env,
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "PYTHONUNBUFFERED": "1",
    }

    result = subprocess.run(
        [sys.executable, "-m", module],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert not result.stderr.strip()
    for pattern in patterns:
        assert re.search(pattern, result.stdout), result.stdout
