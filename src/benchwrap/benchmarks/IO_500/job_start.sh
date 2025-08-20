#!/bin/bash
#SBATCH --job-name=IO_5ẞẞ
#SBATCH --nodes=4
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1

set -euo pipefail
salloc -N4
module load mpi

DEST="$HOME/.local/share/benchwrap/job_${SLURM_JOB_ID}"
mkdir -p "$DEST"


IO500="$HOME/.local/share/benchwrap/benchmarks/io500"

mpirun -np 4 "$IO500/io500.sh" "$IO500/config-minimal.ini"

echo "$(ls)"



