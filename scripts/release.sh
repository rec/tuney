#!/usr/bin/env bash
set -euxo pipefail

part="${1:-patch}"

if [[ "$part" != "patch" && "$part" != "minor" && "$part" != "major" ]]; then
  echo "usage: scripts/release [patch|minor|major]" >&2
  exit 2
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "release requires a clean working tree" >&2
  exit 1
fi

branch="$(git branch --show-current)"
if [[ "$branch" != "main" ]]; then
  echo "release must run from main, not $branch" >&2
  exit 1
fi

uv version --bump "$part" --no-sync
version="$(uv version --short)"
tag="v$version"

if git rev-parse --verify --quiet "$tag" >/dev/null; then
  echo "tag already exists: $tag" >&2
  exit 1
fi

git add pyproject.toml uv.lock
git commit -m "Release $tag"
git push
git tag "$tag"
git push origin "$tag"
