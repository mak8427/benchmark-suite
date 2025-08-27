#!/bin/bash
set -e

if [ "$CI_PIPELINE_SOURCE" = "web" ] && [ "$MAJOR_RELEASE" = "true" ]; then
  PART="major"
elif [ "$CI_PIPELINE_SOURCE" = "merge_request_event" ]; then
  PART="minor"
else
  PART="patch"
fi

echo "Version part to bump: $PART"
echo "VERSION_PART=$PART" >> version.env
