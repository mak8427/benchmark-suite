#!/bin/bash
#SBATCH --job-name=swarm_manager
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1

set -euo pipefail
salloc -N2 --exclusive
module load mpi

DEST="$HOME/.local/share/benchwrap/job_${SLURM_JOB_ID}"
mkdir -p "$DEST"

cd "$DEST"
/home/davide.mattioli/energy//bin/python3 -u -m benchwrap.benchmarks.ior_test.launcher 1>&2


CONF_DIR="$DEST/ior_inis"
echo "$(findmnt -T . -o TARGET,FSTYPE,SOURCE)"


for cfg in "$CONF_DIR"/*.ini; do
  mpirun -np 2 "$HOME/.local/share/benchwrap/benchmarks/io500/bin/ior" -f "$cfg"
done


echo "$(ls)"



