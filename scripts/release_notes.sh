#!/usr/bin/env bash
# Prints the CHANGELOG.md section for a version (used as GitHub release notes).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
awk -v v="$1" '
  $0 ~ "^## " v " " || $0 == "## " v { on=1; next }
  on && /^## / { exit }
  on { print }' "$ROOT/CHANGELOG.md"
