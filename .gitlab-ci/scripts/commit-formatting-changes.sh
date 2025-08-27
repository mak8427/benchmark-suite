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

    # Determine which branch to push to
    BRANCH_NAME=${CI_COMMIT_BRANCH:-${CI_MERGE_REQUEST_SOURCE_BRANCH_NAME:-main}}
    echo "Target branch for pushing changes: $BRANCH_NAME"

    # Check if branch exists remotely
    if ! git ls-remote --heads origin $BRANCH_NAME | grep -q $BRANCH_NAME; then
      echo "Warning: Branch $BRANCH_NAME doesn't exist remotely. Defaulting to main branch."
      BRANCH_NAME="main"

      # Make sure we're on the main branch
      git fetch origin $BRANCH_NAME
      git checkout $BRANCH_NAME || git checkout -b $BRANCH_NAME origin/$BRANCH_NAME
    fi

    # Push changes (mirrors GitHub push logic)
    echo "Attempting to push to branch: $BRANCH_NAME"
    for i in {1..3}; do
      echo "Attempt $i to push changes..."

      # Pull latest changes to avoid conflicts
      git fetch origin $BRANCH_NAME

      if [ "$i" -gt 1 ]; then
        # For retries, merge the latest changes
        if ! git merge --ff-only origin/$BRANCH_NAME; then
          echo "Fast-forward merge failed, attempting regular merge..."
          git merge --no-ff -m "Merge remote changes before auto-formatting" origin/$BRANCH_NAME || {
            echo "Merge failed. Stashing our changes and retrying..."
            git merge --abort || true
            git stash
            git pull --rebase origin $BRANCH_NAME
            git stash pop || true
          }
        fi
      fi

      if git push origin HEAD:$BRANCH_NAME; then
        echo "Successfully pushed formatting changes!"
        break
      elif [ $i -eq 3 ]; then
        echo "Failed to push after 3 attempts"
        echo "Changes have been committed locally but not pushed."
        echo "You may need to manually push these changes later."
        # Don't exit with error, as the formatting itself succeeded
        break
      else
        echo "Push failed, will sync and retry..."
        sleep 1
      fi
    done
  else
    echo "No changes to commit after excluding CI files"
  fi
else
  echo "No formatting changes needed"
fi
