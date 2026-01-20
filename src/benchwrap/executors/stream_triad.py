import argparse
import sys

from .utils.benchmarks_func import run_slurm_job


def main():
    # Parse CLI arguments
    p = argparse.ArgumentParser(description="Run stream_triad benchmark via SLURM.")
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
        bench_name="stream_triad",
        partition=args.partition,
        nodes=args.nodes,
        exclusive=args.exclusive,
    )


if __name__ == "__main__":
    main()
