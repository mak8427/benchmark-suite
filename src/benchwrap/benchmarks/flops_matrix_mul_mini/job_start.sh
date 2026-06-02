#!/bin/bash
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1


set -euo pipefail
BENCH_NAME="flops_matrix_mul_mini"
DEST="$HOME/.local/share/benchwrap/jobs/${BENCH_NAME}/job_${SLURM_JOB_ID}"
LIKWID_RAW="$DEST/likwid_${SLURM_JOB_ID}.raw"
LIKWID_CSV="$DEST/likwid_${SLURM_JOB_ID}.csv"
mkdir -p "$DEST"
if command -v module >/dev/null 2>&1; then
  module load likwid || true
fi
if command -v conda >/dev/null 2>&1; then
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate energy || true
fi

if command -v likwid-perfctr >/dev/null 2>&1; then
  srun --cpu-bind=cores \
    likwid-perfctr -g FLOPS_DP -t 1s \
    python3 -u -m benchwrap.benchmarks.flops_matrix_mul_mini.workload 2>&1 \
    | tee "$LIKWID_RAW" >&2
  python3 -m benchwrap.executors.utils.likwid_csv "$LIKWID_RAW" "$LIKWID_CSV" || true
else
  srun --cpu-bind=cores python3 -u -m benchwrap.benchmarks.flops_matrix_mul_mini.workload 1>&2
fi

echo "LIKWID output saved to $LIKWID_CSV"
