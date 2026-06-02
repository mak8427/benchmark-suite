import importlib.resources as res


def test_packaged_benchmarks_include_runtime_files():
    root = res.files("benchwrap.benchmarks")
    expected = [
        "flops_matrix_mul_mini",
        "coremark_mini",
        "npb_ep_small",
        "npb_is_small",
        "fft_1d_small",
        "random_access_small",
    ]

    for benchmark in expected:
        benchmark_dir = root / benchmark
        assert (benchmark_dir / "job_start.sh").is_file(), benchmark
        assert (benchmark_dir / "description.txt").is_file(), benchmark
