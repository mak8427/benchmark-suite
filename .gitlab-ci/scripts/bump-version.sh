#!/bin/bash
set -e

source version.env || echo "No version.env file found, using default version part"
VERSION_PART=${VERSION_PART:-patch}

if [ "$CI_PIPELINE_SOURCE" = "push" ] && [ "$CI_COMMIT_BRANCH" = "dev" ]; then
  echo "Bumping $VERSION_PART version for dev push..."

  # Checkout the branch explicitly instead of working in detached HEAD
  git fetch origin dev
  git checkout -B dev origin/dev

  # Check if this is a mirror from GitHub
  if git remote -v | grep -q github; then
    echo "Detected GitHub mirror repository - skipping version bump to avoid conflicts with GitHub Actions"
    echo "The version will be bumped by GitHub Actions workflows instead."
    exit 0
  fi

  # Proceed with version bump
  bump2version $VERSION_PART
  git push origin dev --follow-tags

elif [ "$CI_PIPELINE_SOURCE" = "merge_request_event" ] && [ "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME" = "main" ]; then
  echo "Bumping $VERSION_PART version for main merge..."

  # Checkout the target branch explicitly
  git fetch origin main
  git checkout -B main origin/main

  # Check if this is a mirror from GitHub
  if git remote -v | grep -q github; then
    echo "Detected GitHub mirror repository - skipping version bump to avoid conflicts with GitHub Actions"
    echo "The version will be bumped by GitHub Actions workflows instead."
    exit 0
  fi

  # Proceed with version bump
  bump2version $VERSION_PART
  git push origin main --follow-tags
fi