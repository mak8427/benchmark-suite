#!/bin/bash
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1

set -euo pipefail
source activate energy

python3 -u -m benchwrap.benchmarks.flops_matrix_mul_no_likwid.workload 1>&2

echo "Slurm energy profile saved for job ${SLURM_JOB_ID}."
