#!/bin/bash
set -e

source version.env

if [ "$CI_PIPELINE_SOURCE" = "push" ] && [ "$CI_COMMIT_BRANCH" = "dev" ]; then
  echo "Bumping $VERSION_PART version for dev push..."
  bump2version $VERSION_PART
  git push --follow-tags
elif [ "$CI_PIPELINE_SOURCE" = "merge_request_event" ] && [ "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME" = "main" ]; then
  echo "Bumping $VERSION_PART version for main merge..."
  bump2version $VERSION_PART
  git push --follow-tags
fi
