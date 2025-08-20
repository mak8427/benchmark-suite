#!/bin/bash
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1

set -euo pipefail
module load likwid
source activate energy
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}

#Create job dir
DEST="$HOME/.local/share/benchwrap/job_${SLURM_JOB_ID}"
mkdir -p "$DEST"

#Trap And start Job


srun --cpu-bind=cores \
  likwid-perfctr -g FLOPS_DP -t 1s \
  python3 -u -m benchwrap.benchmarks.flops_matrix_mul_mini.workload 1>&2 \

benchwrap run flops_matrix_mul scc-cpu

echo "Results -> $DEST"



