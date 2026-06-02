#!/usr/bin/env bash
set -euo pipefail

partition="${BENCHWRAP_CAMPAIGN_PARTITION:-medium}"
runs="${BENCHWRAP_CAMPAIGN_RUNS:-3}"
nodes="${BENCHWRAP_CAMPAIGN_NODES:-1}"
export BENCHWRAP_SLURM_TIME="${BENCHWRAP_SLURM_TIME:-00:10:00}"

benchmarks=(
  coremark_mini
  fft_1d_small
  flops_matrix_mul_mini
  npb_ep_small
  npb_is_small
  random_access_small
)

artifact_root="${BENCHWRAP_CAMPAIGN_ARTIFACTS:-campaign-artifacts}"
manifest="$artifact_root/manifest.jsonl"
mkdir -p "$artifact_root"
: > "$manifest"

echo "campaign_partition=$partition"
echo "campaign_runs=$runs"
echo "campaign_nodes=$nodes"
echo "campaign_time=$BENCHWRAP_SLURM_TIME"
sinfo || true

job_ids=()
for benchmark in "${benchmarks[@]}"; do
  for run in $(seq 1 "$runs"); do
    echo ":: submit benchmark=$benchmark run=$run/$runs"
    output="$(benchwrap run "$benchmark" --partition "$partition" --nodes "$nodes")"
    echo "$output"
    job_id="$(printf '%s\n' "$output" | sed -nE 's/.*Job n: ([0-9]+).*/\1/p' | tail -n 1)"
    if [ -z "$job_id" ]; then
      echo "Failed to parse Slurm job id for $benchmark run $run" >&2
      exit 1
    fi
    job_ids+=("$job_id")
    printf '{"benchmark":"%s","run":%s,"job_id":"%s","partition":"%s","nodes":%s,"state":"submitted"}\n' \
      "$benchmark" "$run" "$job_id" "$partition" "$nodes" >> "$manifest"
  done
done

echo ":: waiting for ${#job_ids[@]} job(s)"
for job_id in "${job_ids[@]}"; do
  while squeue -h -j "$job_id" | grep -q .; do
    sleep 10
  done
done

python .ci/scripts/validate-slurm-campaign.py "$manifest"
