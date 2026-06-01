import argparse

from .utils.benchmarks_func import run_slurm_job


def main():
    p = argparse.ArgumentParser(description="Run npb_is_small benchmark via SLURM.")
    p.add_argument(
        "--partition", default=None, help="SLURM partition to submit the job to."
    )
    p.add_argument(
        "--nodes",
        "--n",
        "-n",
        dest="nodes",
        type=int,
        default=1,
        help="Number of nodes to request.",
    )
    p.add_argument(
        "--exclusive", action="store_true", help="Request exclusive node access."
    )
    args = p.parse_args()
    run_slurm_job("npb_is_small", args.partition, args.nodes, args.exclusive)


if __name__ == "__main__":
    main()
