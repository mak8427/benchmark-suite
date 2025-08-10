#!/bin/bash
#SBATCH --job-name=likwid-flops
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --output=likwid-%j.out
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1


module load likwid
source activate energy
srun likwid-perfctr -C 0-3 -g FLOPS_DP -t 1000ms -O \
    -o timeline_${SLURM_JOB_ID}.csv \
    python3 -u benchmarks/.cache_test/workload.py

# python3 -u benchmarks/.cache_test/workload.py

echo "LIKWID output saved to flops_${SLURM_JOB_ID}.csv"

