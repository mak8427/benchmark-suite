from .utils.benchmarks_func import *

if __name__ == "__main__":
    cmd1 = "sbatch -p scc-cpu benchmarks/.benchmark2/batchscript.sh"
    cmd2 = "sh5util -j"
    run_slurm_job(cmd1, cmd2)
