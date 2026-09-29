#!/usr/bin/env bash
# Reproducible dependency-vulnerability checks (BR-106 / AC-SEC-024) + security-focused test run.
# Usage (repo root, dev venv active):  bash scripts/security_check.sh  -> reports in build/security/
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/build/security"; mkdir -p "$OUT"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
status=0
echo "== Python dependencies (pip-audit $(pip-audit --version 2>/dev/null)) $STAMP"
pip-audit -r "$ROOT/backend/requirements.txt" --desc 2>&1 | tee "$OUT/pip-audit.txt" || status=1
echo "== JavaScript dependencies (npm $(npm --version)) $STAMP"
(cd "$ROOT/frontend" && npm audit --audit-level=low 2>&1) | tee "$OUT/npm-audit.txt" || status=1
echo "== Security negative tests (AC-SEC-*)"
(cd "$ROOT/backend" && python -m pytest -q -p no:warnings tests/test_attachments_audit_security.py tests/test_rbac.py \
   tests/test_init_auth.py 2>&1 | grep -vE "^(INFO|WARNING)" | tail -3) | tee "$OUT/security-tests.txt"
exit $status
