#!/bin/bash
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1

set -euo pipefail
module load likwid
source activate energy
DEST="$HOME/.local/share/benchwrap/jobs/flops_matrix_mul/job_${SLURM_JOB_ID}"

srun --cpu-bind=cores \
  likwid-perfctr -g FLOPS_DP -t 1s \
  python3 -u -m benchwrap.benchmarks.flops_matrix_mul.workload 1>&2


echo "Results -> $DEST"
echo "LIKWID output saved to timeline_${SLURM_JOB_ID}.csv"
