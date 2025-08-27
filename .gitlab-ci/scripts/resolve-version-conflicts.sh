#!/bin/bash
set -e

# Get versions from both branches
git fetch origin main
MAIN_VERSION=$(git show origin/main:.bumpversion.cfg | grep "current_version" | cut -d'=' -f2 | tr -d ' ')
DEV_VERSION=$(grep "current_version" .bumpversion.cfg | cut -d'=' -f2 | tr -d ' ')

echo "Main version: $MAIN_VERSION"
echo "Dev version: $DEV_VERSION"

# Use the higher version (mirrors GitHub logic)
if [[ "$MAIN_VERSION" > "$DEV_VERSION" ]]; then
  echo "Updating to main version: $MAIN_VERSION"
  sed -i "s/current_version = .*/current_version = $MAIN_VERSION/" .bumpversion.cfg

  # Update other files too
  if [ -f "pyproject.toml" ]; then
    sed -i "s/version = \".*\"/version = \"$MAIN_VERSION\"/" pyproject.toml
  fi

  if [ -f "README.md" ]; then
    sed -i "s/version: .*/version: $MAIN_VERSION/" README.md
  fi

  # Commit if there are changes
  if ! git diff --quiet; then
    git add .
    git commit -m "sync: resolve version conflict, use $MAIN_VERSION"
    git push
  fi
fi
