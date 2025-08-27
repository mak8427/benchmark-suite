#!/bin/bash
set -e

echo "Running linting (warn-only)..."
PY_FILES="$(git ls-files '*.py' || true)"
if [ -n "$PY_FILES" ]; then
  pre-commit run --all-files --show-diff-on-failure || echo "Linting completed with warnings"
fi