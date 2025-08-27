#!/bin/bash
set -e

if [ -s outdated.txt ]; then
  echo "⚠️ Outdated dependencies found:"
  cat outdated.txt
  echo ""
  echo "Please consider updating these dependencies."

  # Create GitLab issue (mirrors GitHub issue creation)
  echo "Creating GitLab issue for outdated dependencies..."
  echo "Issue creation placeholder - would create issue with outdated dependencies"

  exit 1
else
  echo "✅ All dependencies are up to date!"
fi