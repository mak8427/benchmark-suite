from .utils.benchmarks_func import *

if __name__ == "__main__":
    run_slurm_job(bench_name="flops_matrix_mul",partition="scc-cpu")