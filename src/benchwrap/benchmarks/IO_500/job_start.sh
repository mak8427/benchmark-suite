#!/bin/bash
#SBATCH -n 64
#SBATCH --job-name=IO_500
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1s


module purge
module load openmpi
module load mpi


DEST="$HOME/.local/share/benchwrap/jobs/job_${SLURM_JOB_ID}"
IO500="$HOME/.local/share/benchwrap/benchmarks/io500"
cd "$DEST"

srun "$IO500/io500.sh" "$IO500/config-minimal.ini"

echo "$(ls)"



