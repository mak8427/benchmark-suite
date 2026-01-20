import argparse

from .utils.benchmarks_func import (check_io500, check_ior, get_ior, get_io500,
                                    run_slurm_job)


def main():

    if check_ior() == False:
        if check_io500() == False:
            get_io500()
        get_ior()
        assert check_ior() == True

    p = argparse.ArgumentParser(
        description="Run IO_500 benchmark via SLURM."
    )
    p.add_argument(
        "--partition",
        default=None,
        help="SLURM partition to submit the job to (default: scc-cpu).",
    )

    p.add_argument(
        "--nodes",
        "--n",
        "-n",
        dest="nodes",
        type=int,
        default=1,
        help="Number of nodes to request (default: 1).",
    )
    p.add_argument(
        "--exclusive",
        action="store_true",
        help="Request exclusive node access.",
    )
    args = p.parse_args()

    run_slurm_job(
        bench_name="IO_500",
        partition=args.partition,
        nodes=args.nodes,
        exclusive=args.exclusive,
    )


if __name__ == "__main__":
    main()
