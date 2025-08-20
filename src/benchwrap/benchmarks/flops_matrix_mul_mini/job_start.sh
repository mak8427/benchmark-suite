#!/bin/bash
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1

set -euo pipefail
module load likwid
source activate energy

#Trap And start Job


srun --cpu-bind=cores \
  likwid-perfctr -g FLOPS_DP -t 1s \
  python3 -u -m benchwrap.benchmarks.flops_matrix_mul_mini.workload 1>&2 \

benchwrap run flops_matrix_mul scc-cpu

echo "Results -> $DEST"



