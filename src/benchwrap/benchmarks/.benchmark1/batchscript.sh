#!/bin/bash
#SBATCH -N 1
#SBATCH --exclusive
#SBATCH --time=00:03:00

# some payload for the benchmark
echo "HI"
sleep 20