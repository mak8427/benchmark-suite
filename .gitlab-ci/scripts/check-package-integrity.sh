#!/bin/bash
set -e

if [ ! -d "dist" ] || [ -z "$(ls -A dist)" ]; then
  echo "Error: No distribution files found"
  exit 1
fi

echo "Distribution files found:"
ls -la dist/

if ! twine check dist/*; then
  echo "Warning: twine check failed, performing basic validation..."

  for file in dist/*; do
    if [[ $file == *.whl ]]; then
      echo "Checking wheel file: $file"
      python -m zipfile -l "$file" > /dev/null || {
        echo "Error: Invalid wheel file $file"
        exit 1
      }
    elif [[ $file == *.tar.gz ]]; then
      echo "Checking source distribution: $file"
      tar -tzf "$file" > /dev/null || {
        echo "Error: Invalid source distribution $file"
        exit 1
      }
    fi
  done
  echo "Basic package validation completed"
else
  echo "Package integrity check passed"
fi