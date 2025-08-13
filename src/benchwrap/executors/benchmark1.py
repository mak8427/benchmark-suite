from .utils.benchmarks_func import *

# Usage:
if __name__ == "__main__":
    cmd1 = "srun --exclusive --profile=all --partition=scc-cpu --acctg-freq=1 benchmarks/.benchmark1/batchscript.sh"
    cmd2 = "sh5util -j"
    run_slurm_job(cmd1, cmd2)
