from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / "src" / "benchwrap" / "benchmarks"

EXCLUDED_BENCHMARKS = {"IO_500", "ior_test"}


def _job_script(name: str) -> str:
    return (BENCHMARKS / name / "job_start.sh").read_text(encoding="utf-8")


def test_active_benchmark_scripts_do_not_use_stale_local_paths() -> None:
    for script_path in BENCHMARKS.glob("*/job_start.sh"):
        if script_path.parent.name in EXCLUDED_BENCHMARKS:
            continue
        text = script_path.read_text(encoding="utf-8")
        assert "/home/davide.mattioli/energy" not in text, script_path
        assert "benchmarks/." not in text, script_path


def test_active_benchmark_scripts_do_not_submit_recursive_benchwrap_jobs() -> None:
    for script_path in BENCHMARKS.glob("*/job_start.sh"):
        if script_path.parent.name in EXCLUDED_BENCHMARKS:
            continue
        text = script_path.read_text(encoding="utf-8")
        assert "benchwrap run" not in text, script_path


def test_active_benchmark_scripts_do_not_use_unresolved_template_variables() -> None:
    for script_path in BENCHMARKS.glob("*/job_start.sh"):
        if script_path.parent.name in EXCLUDED_BENCHMARKS:
            continue
        text = script_path.read_text(encoding="utf-8")
        assert "${f}" not in text, script_path


def test_likwid_benchmarks_use_valid_likwid_group_option() -> None:
    for script_path in BENCHMARKS.glob("*/job_start.sh"):
        if script_path.parent.name in EXCLUDED_BENCHMARKS:
            continue
        text = script_path.read_text(encoding="utf-8")
        assert "0-24-g" not in text, script_path
        if "likwid-perfctr" in text:
            assert " -g FLOPS_DP" in text, script_path


def test_known_fixed_benchmarks_invoke_their_package_modules() -> None:
    expected_modules = {
        "avx512_fma": "benchwrap.benchmarks.avx512_fma.workload",
        "branchy_int": "benchwrap.benchmarks.branchy_int.workload",
        "cache_sweep": "benchwrap.benchmarks.cache_sweep.workload",
        "cache_test": "benchwrap.benchmarks.cache_test.workload",
        "mem_bandwidth": "benchwrap.benchmarks.mem_bandwidth.workload",
        "mixed_phase": "benchwrap.benchmarks.mixed_phase.workload",
        "stream_triad": "benchwrap.benchmarks.stream_triad.workload",
        "flops_matrix_mul": "benchwrap.benchmarks.flops_matrix_mul.workload",
        "flops_matrix_mul_mini": "benchwrap.benchmarks.flops_matrix_mul_mini.workload",
        "flops_matrix_mul_no_likwid": "benchwrap.benchmarks.flops_matrix_mul_no_likwid.workload",
        "coremark_mini": "benchwrap.benchmarks.coremark_mini.workload",
        "npb_ep_small": "benchwrap.benchmarks.npb_ep_small.workload",
        "npb_is_small": "benchwrap.benchmarks.npb_is_small.workload",
        "fft_1d_small": "benchwrap.benchmarks.fft_1d_small.workload",
        "random_access_small": "benchwrap.benchmarks.random_access_small.workload",
    }
    for name, module in expected_modules.items():
        assert f"python3 -u -m {module}" in _job_script(name)


def test_flops_matrix_mul_defines_dest_before_use() -> None:
    text = _job_script("flops_matrix_mul")
    assert "DEST=" in text
    assert text.index("DEST=") < text.index("$DEST")
