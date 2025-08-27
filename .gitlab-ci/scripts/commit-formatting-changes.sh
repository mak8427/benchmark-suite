#!/bin/bash
set -e

# Check for changes (mirrors GitHub step)
CHANGED_FILES=$(git status --porcelain | grep -v "^.* \.gitlab-ci.yml" || true)

if [ -n "$CHANGED_FILES" ]; then
  echo "Files were auto-formatted:"
  echo "$CHANGED_FILES"

  # Stage all changes first
  git add .
  # Remove CI files from staging (like GitHub excludes workflows)
  git reset -- .gitlab-ci.yml

  if ! git diff --cached --quiet; then
    git commit -m "style: auto-format code (excluding CI config) [skip ci]"

    # Push changes (mirrors GitHub push logic)
    for i in {1..3}; do
      echo "Attempt $i to push changes..."
      if git push origin $CI_COMMIT_BRANCH; then
        echo "Successfully pushed formatting changes!"
        break
      elif [ $i -eq 3 ]; then
        echo "Failed to push after 3 attempts"
        exit 1
      else
        echo "Push failed, syncing and retrying..."
        git fetch origin $CI_COMMIT_BRANCH
        git rebase origin/$CI_COMMIT_BRANCH || git merge origin/$CI_COMMIT_BRANCH --no-edit
        sleep 1
      fi
    done
  else
    echo "No changes to commit after excluding CI files"
  fi
else
  echo "No formatting changes needed"
fi