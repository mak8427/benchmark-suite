#!/bin/bash
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1

set -euo pipefail
module load likwid
source activate energy

srun --cpu-bind=cores \
  likwid-perfctr -g FLOPS_DP -t 1s \
  python3 -u -m benchwrap.benchmarks.random_access_small.workload 1>&2

echo "LIKWID output saved to timeline_${SLURM_JOB_ID}.csv"
