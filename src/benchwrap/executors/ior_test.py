import argparse

from .utils.benchmarks_func import *


def main():

    try:
        p = argparse.ArgumentParser()
        p.add_argument("--partition", required=False)

        args = p.parse_args()
        run_slurm_job(bench_name="ior_test", partition=args.partition)

    except:
        print("No partition specified")
        run_slurm_job(bench_name="ior_test", partition="None")


if __name__ == "__main__":
    main()
