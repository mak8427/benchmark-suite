#!/bin/bash
#SBATCH --job-name=swarm_manager
#SBATCH --nodes=1
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1

set -euo pipefail

DEST="$HOME/.local/share/benchwrap/job_${SLURM_JOB_ID}"
mkdir -p "$DEST"

cd "$DEST"
/home/davide.mattioli/energy//bin/python3 -u -m benchwrap.benchmarks.ior_test.launcher 1>&2

echo "$(ls)"



