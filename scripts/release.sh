#!/usr/bin/env bash
# Release script for forage
# Usage: ./scripts/release.sh [patch|minor|major]

set -e

VERSION_TYPE=${1:-patch}

if [[ ! "$VERSION_TYPE" =~ ^(patch|minor|major)$ ]]; then
    echo "Usage: $0 [patch|minor|major]"
    exit 1
fi

# Ensure we're on master and up to date
git fetch origin
if [[ $(git rev-parse HEAD) != $(git rev-parse origin/master) ]]; then
    echo "Error: Not up to date with origin/master"
    exit 1
fi

# Get current version from pyproject.toml
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)
echo "Current version: $CURRENT_VERSION"

# Calculate new version
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"
case "$VERSION_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
esac
NEW_VERSION="$MAJOR.$MINOR.$PATCH"
echo "New version: $NEW_VERSION"

# Update version in pyproject.toml
sed -i '' "s/^version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml

# Update version in __init__.py
sed -i '' "s/__version__ = \"$CURRENT_VERSION\"/__version__ = \"$NEW_VERSION\"/" src/forage/__init__.py

# Generate changelog entry from git log
echo ""
echo "Recent commits to include in changelog:"
git log --oneline v${CURRENT_VERSION}..HEAD 2>/dev/null || git log --oneline -20

echo ""
echo "Please update CHANGELOG.md with the new version entry."
echo "Then run:"
echo "  git add -A"
echo "  git commit -m 'chore: release v$NEW_VERSION'"
echo "  git tag v$NEW_VERSION"
echo "  git push origin master --tags"
