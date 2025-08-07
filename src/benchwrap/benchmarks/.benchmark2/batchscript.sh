#!/bin/bash
#SBATCH --job-name=likwid-flops
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --cpus-per-task=4
#SBATCH --output=likwid-%j.out
#SBATCH --profile=all
#SBATCH --acctg-freq=1
#SBATCH --acctg-freq=energy=1
#SBATCH --exclusive

module load likwid
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4

likwid-perfctr -C 0-3 -g FLOPS_DP -t 1000ms -O \
  --output flops_${SLURM_JOB_ID}.csv \
  python3 -u my_workload.py


echo "LIKWID output saved to flops_<procid>_${SLURM_JOB_ID}.csv"
