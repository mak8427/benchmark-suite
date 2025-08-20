#!/bin/bash
#SBATCH --job-name=swarm_manager
#SBATCH --nodes=2
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1

set -euo pipefail
salloc -N2 --exclusive
module load mpi

DEST="$HOME/.local/share/benchwrap/job_${SLURM_JOB_ID}"
mkdir -p "$DEST"


IO500="$HOME/.local/share/benchwrap/benchmarks/io500"

mpirun -np 2 "$IO500/io500.sh" -f "$IO500/config-minimal.ini"

echo "$(ls)"



