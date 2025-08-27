#!/bin/bash
set -e

WHEEL_FILE=$(find dist -name "*.whl" | head -1)

if [ -z "$WHEEL_FILE" ]; then
  echo "Error: No wheel file found for testing"
  exit 1
fi

echo "Installing wheel: $WHEEL_FILE"
pip install "$WHEEL_FILE"

python -c "
import sys
print('Package installed successfully')
print('Python version:', sys.version)
"
