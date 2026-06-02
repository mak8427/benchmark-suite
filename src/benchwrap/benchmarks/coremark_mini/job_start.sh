#!/bin/bash
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1

set -euo pipefail

if command -v module >/dev/null 2>&1; then
  module load likwid || true
fi

if command -v conda >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate energy || true
fi

if command -v likwid-perfctr >/dev/null 2>&1; then
  srun --cpu-bind=cores \
    likwid-perfctr -g FLOPS_DP -t 1s \
    python3 -u -m benchwrap.benchmarks.coremark_mini.workload 1>&2
else
  srun --cpu-bind=cores \
    python3 -u -m benchwrap.benchmarks.coremark_mini.workload 1>&2
fi

echo "LIKWID output saved to timeline_${SLURM_JOB_ID}.csv"
