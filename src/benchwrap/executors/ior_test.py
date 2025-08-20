import argparse
import os

from .utils.benchmarks_func import *


def main():

    if check_ior() == False:
        if check_io500() == False:
            get_io500()
        get_ior()
        assert check_ior() == True

    p = argparse.ArgumentParser(description="Run FLOPS matrix multiplication benchmark via SLURM.")
    p.add_argument(
        "--partition",
        default=None,
        help="SLURM partition to submit the job to (default: scc-cpu).",
    )

    p.add_argument(
        "--nodes", "--n", "-n",
        dest="nodes",
        type=int,
        default=1,
        help="Number of nodes to request (default: 1).",
    )
    args = p.parse_args()


    run_slurm_job(
        bench_name="ior_test",
        partition=args.partition,
        nodes=args.nodes,
    )


if __name__ == "__main__":
    main()
