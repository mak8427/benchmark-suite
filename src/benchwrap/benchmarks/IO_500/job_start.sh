#!/bin/bash
#SBATCH --job-name=IO_500
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1s

set -euo pipefail
module load mpi




IO500="$HOME/.local/share/benchwrap/benchmarks/io500"
cd "$DEST"

srun "$IO500/io500.sh" "$IO500/config-minimal.ini"

echo "$(ls)"



