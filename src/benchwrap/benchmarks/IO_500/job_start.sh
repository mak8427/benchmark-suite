#!/bin/bash
#SBATCH --job-name=IO_500


# Define paths
DEST="$HOME/.local/share/benchwrap/jobs/job_${SLURM_JOB_ID}"
IO500_DIR="$HOME/.local/share/benchwrap/benchmarks/io500"
IO500_SCRIPT="$IO500_DIR/io500.sh"
CONFIG_FILE="$IO500_DIR/config-minimal.ini"

# Change to the destination directory
cd "$DEST"

# Ensure the script is executable
chmod +x "$IO500_SCRIPT"

# Execute the script using srun
srun "$IO500_SCRIPT" "$CONFIG_FILE"

# List the files in the directory to verify output
echo "Listing files in the job directory:"
ls -l
