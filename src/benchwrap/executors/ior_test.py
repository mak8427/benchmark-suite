import argparse
import os

from .utils.benchmarks_func import *


def main():

    if check_ior() == False:
        if check_io500() == False:
            get_io500()
        get_ior()
        assert check_ior() == True

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
