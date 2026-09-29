#!/usr/bin/env bash
# Prints the application version (backend/fmpoc/config.py). With --check, also verifies frontend/package.json matches.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY=$(sed -n 's/^VERSION = "\(.*\)"$/\1/p' "$ROOT/backend/fmpoc/config.py")
[ -n "$PY" ] || { echo "VERSION not found in backend/fmpoc/config.py" >&2; exit 1; }
if [ "${1:-}" = "--check" ]; then
  JS=$(sed -n 's/^  "version": "\(.*\)",$/\1/p' "$ROOT/frontend/package.json" | head -1)
  [ "$PY" = "$JS" ] || { echo "Version mismatch: config.py=$PY package.json=$JS" >&2; exit 1; }
  echo "version $PY (backend and frontend agree)"
else
  echo "$PY"
fi
