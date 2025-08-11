#!/bin/bash
#SBATCH --job-name=flops_matrix_mul
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --output=likwid-%j.out
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1
#SBATCH --exclusive

module load likwid
conda activate energy

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}
srun --cpu-bind=cores likwid-perfctr \
     -g FLOPS_DP -t 200ms -O \
     -o timeline_${SLURM_JOB_ID}.csv \
     python3 -u benchmarks/.flops_matrix_mul/workload.py

echo "LIKWID output saved to timeline_${SLURM_JOB_ID}.csv"