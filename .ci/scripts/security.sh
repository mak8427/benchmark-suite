#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install pip-audit bandit

pip-audit -r src/requirements.txt
bandit -r src -ll
