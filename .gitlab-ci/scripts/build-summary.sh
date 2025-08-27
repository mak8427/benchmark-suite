#!/bin/bash
set -e

echo "Build Summary"
echo "============="

if [ -d "dist" ] && [ -n "$(ls -A dist)" ]; then
  echo "Build Status: SUCCESS"
  echo "Files created:"
  for file in dist/*; do
    if [ -f "$file" ]; then
      SIZE=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo "unknown")
      echo "  - $(basename "$file") (${SIZE} bytes)"
    fi
  done
else
  echo "Build Status: FAILED - No distribution files created"
fi

echo "Build completed at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"