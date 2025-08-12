#!/bin/bash
#SBATCH --job-name=flops_matrix_mul
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1

set -euo pipefail
module load likwid
conda activate energy
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}
DEST="$HOME/.local/share/likwid/${SLURM_JOB_ID}"
mkdir -p "$DEST"
cd "${SLURM_TMPDIR:?need SLURM_TMPDIR}"


trap 'rsync -a timeline_*.csv "$DEST/" 2>/dev/null || true' EXIT
srun --cpu-bind=cores likwid-perfctr -g FLOPS_DP -t 200ms -O -o "timeline_${SLURM_JOB_ID}.csv" \
  python3 -u "$SLURM_SUBMIT_DIR/benchmarks/.flops_matrix_mul/workload.py"
echo "Results -> $DEST"
