#!/bin/bash
set -e

VERSION=""

if [ -f "pyproject.toml" ]; then
  VERSION=$(grep -E '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/' | head -1)
elif [ -f "setup.py" ]; then
  VERSION=$(python setup.py --version 2>/dev/null || echo "")
fi

if [ -z "$VERSION" ]; then
  VERSION=$(git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//' || echo "")
fi

if [ -z "$VERSION" ] && [ -f ".bumpversion.cfg" ]; then
  VERSION=$(grep "current_version" .bumpversion.cfg | cut -d'=' -f2 | tr -d ' ')
fi

if [ -z "$VERSION" ]; then
  VERSION="$(date +%Y.%m.%d)-$(git rev-parse --short HEAD)"
fi

echo "Detected version: $VERSION"
echo "PACKAGE_VERSION=$VERSION" >> build.env