#!/bin/bash
#SBATCH --job-name=flops_matrix_mul
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
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

#Trap And start Jobs
# 1) Save LIKWID timeline to CSV; 2) send your app's stdout to stderr so it doesn't mix
trap 'rsync -a timeline_*.csv "$DEST/" 2>/dev/null || true' EXIT

outfile="timeline_${SLURM_JOB_ID}.csv"
srun --cpu-bind=cores \
  likwid-perfctr -g FLOPS_DP -t 200ms \
  python3 -u -m benchwrap.benchmarks.flops_matrix_mul.workload 1>&2 \
  | tee "$outfile" >/dev/null

echo "Results -> $DEST"



