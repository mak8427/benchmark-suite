#!/bin/bash
set -e

if [ "$CI_PIPELINE_SOURCE" = "merge_request_event" ] && [ "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME" = "main" ]; then
  echo "Syncing version bump back to dev..."
  git fetch origin dev
  git checkout dev
  if ! git merge --ff-only main; then
    echo "Fast-forward merge failed, attempting regular merge..."
    git merge --no-ff -m "Sync version bump from main" main
  fi
  git push origin dev
fi