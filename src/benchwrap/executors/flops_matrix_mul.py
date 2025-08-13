import argparse

from .utils.benchmarks_func import *


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--partition", required=False)

    args = p.parse_args()
    run_slurm_job(bench_name="flops_matrix_mul", partition=args.partition)


if __name__ == "__main__":
    main()
