from .utils.benchmarks_func import *

if __name__ == "__main__":
    run_slurm_job(bench_name="mem_bandwidth", partition="scc-cpu")
