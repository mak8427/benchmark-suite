#!/bin/bash
set -e

source release.env

echo "Generating release notes..."

cat > release_notes.md << EOF
## Release $RELEASE_VERSION

### Build Information
- **Python Version**: $PYTHON_VERSION
- **Built on**: $(date -u '+%Y-%m-%d %H:%M:%S UTC')
- **Commit**: $CI_COMMIT_SHA
- **Branch**: $CI_COMMIT_BRANCH
- **Pipeline**: $CI_PIPELINE_ID
- **Triggered by**: $CI_PIPELINE_SOURCE

### Distribution Files
EOF

for file in dist/*; do
  if [ -f "$file" ]; then
    SIZE=$(stat -c%s "$file" 2>/dev/null || echo "unknown")
    echo "- $(basename "$file") (${SIZE} bytes)" >> release_notes.md
  fi
done