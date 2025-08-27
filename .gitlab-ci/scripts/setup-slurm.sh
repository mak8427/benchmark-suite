#!/bin/bash
set -e

# Install SLURM client (mirrors GitHub koesterlab/setup-slurm-action)
apt-get update
apt-get install -y wget gnupg lsb-release
apt-get update && apt-get install -y --no-install-recommends slurm-client && rm -rf /var/lib/apt/lists/*