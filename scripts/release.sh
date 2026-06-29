#!/usr/bin/env bash
set -euo pipefail

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

head="$(git rev-parse HEAD)"
origin_main="$(git rev-parse origin/main)"
if [[ "$head" != "$origin_main" ]]; then
  echo "release requires HEAD to equal origin/main" >&2
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
git tag "$tag"
git push origin "$tag"
