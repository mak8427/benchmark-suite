#!/usr/bin/env bash
set -euo pipefail

partition="${BENCHWRAP_CI_SLURM_PARTITION:-}"
if [ -z "$partition" ]; then
  partition="$(sinfo -h -o '%P' | head -n 1 | tr -d '*')"
fi

if [ -z "$partition" ]; then
  echo "Could not detect a Slurm partition" >&2
  exit 1
fi

export BENCHWRAP_SLURM_TIME="${BENCHWRAP_SLURM_TIME:-00:02:00}"

echo "Using Slurm partition: $partition"
echo "Using BENCHWRAP_SLURM_TIME=$BENCHWRAP_SLURM_TIME"
sinfo
squeue || true

python -m pytest tests/test_slurm.py -v --tb=short

output="$(benchwrap run coremark_mini -p "$partition" -n 1 2>&1)"
printf '%s\n' "$output"
job_id="$(printf '%s\n' "$output" | sed -n 's/.*Job n: \([0-9][0-9]*\).*/\1/p' | tail -n 1)"
if [ -z "$job_id" ]; then
  echo "Could not parse benchwrap Slurm job id" >&2
  exit 1
fi

deadline=$((SECONDS + 180))
while squeue -h -j "$job_id" | grep -q "$job_id"; do
  if [ "$SECONDS" -gt "$deadline" ]; then
    echo "Timed out waiting for Slurm job $job_id" >&2
    squeue -j "$job_id" || true
    exit 1
  fi
  sleep 3
done

state="$(sacct -X -n -j "$job_id" --format=State -P | head -n 1 | tr -d '[:space:]')"
echo "benchwrap coremark_mini job $job_id state: ${state:-unknown}"
test "$state" = "COMPLETED"
