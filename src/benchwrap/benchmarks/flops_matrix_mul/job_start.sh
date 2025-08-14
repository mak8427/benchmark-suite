#!/bin/bash
#SBATCH --job-name=flops_matrix_mul
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
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

srun --cpu-bind=cores \
  likwid-perfctr -g FLOPS_DP -t 1s \
  python3 -u -m benchwrap.benchmarks.flops_matrix_mul.workload 1>&2


echo "Results -> $DEST"



