#!/bin/bash
set -e

if [ "$CI_PIPELINE_SOURCE" = "merge_request_event" ] && [ "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME" = "main" ]; then
  echo "Syncing version bump back to dev..."

  # Check if this is a mirror from GitHub
  if git remote -v | grep -q github; then
    echo "Detected GitHub mirror repository - skipping version sync to avoid conflicts with GitHub Actions"
    echo "The version sync will be handled by GitHub Actions workflows instead."
    exit 0
  fi

  # Make sure we're on main before checking out dev
  git fetch origin main
  git checkout -B main origin/main

  # Now checkout dev and merge from main
  git fetch origin dev
  git checkout -B dev origin/dev

  if ! git merge --ff-only main; then
    echo "Fast-forward merge failed, attempting regular merge..."
    git merge --no-ff -m "Sync version bump from main" main
  fi

  git push origin dev
fi
