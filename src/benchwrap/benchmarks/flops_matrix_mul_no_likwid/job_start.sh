#!/bin/bash
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1

set -euo pipefail

/home/davide.mattioli/energy//bin/python3 -u -m benchwrap.benchmarks.flops_matrix_mul.workload 1>&2

python3 -u -m benchwrap.benchmarks.flops_matrix_mul_mini.workload 1>&2
