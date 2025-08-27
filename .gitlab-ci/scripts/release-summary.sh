#!/bin/bash
set -e

source release.env

echo "Release Summary"
echo "==============="
echo "Version: $RELEASE_VERSION"
echo "Tag: v$RELEASE_VERSION"
echo "Triggered by: $CI_PIPELINE_SOURCE"
echo "Files included:"
ls -la dist/
