#!/bin/bash
set -e

if [ -n "$PACKAGE_VERSION" ]; then
  VERSION="$PACKAGE_VERSION"
else
  # Fallback version detection
  VERSION=$(grep "current_version" .bumpversion.cfg | cut -d'=' -f2 | tr -d ' ' || echo "0.0.0")
fi
echo "Release version: $VERSION"
echo "RELEASE_VERSION=$VERSION" >> release.env