# Security controls and checks

| Area | Implementation | Verified by |
|---|---|---|
| Authentication | Argon2id (argon2-cffi defaults); constant-time dummy verify for unknown users; password policy ≥12 chars with letter+digit, ≠ username | `test_init_auth.py` |
| Sessions | Random 256-bit token in HttpOnly, SameSite=Strict cookie (`Secure` under HTTPS); only SHA-256 hash stored; rotated on login; revoked on logout, password change (other sessions), admin reset and user disable; idle 30 min / absolute 12 h | `test_ac_sec_006_*`, `test_ac_auth_self_*`, `test_disabled_user_*` |
| Authorization | Role→permission map (`fmpoc/permissions.py`) re-evaluated from the DB on every request; per-route `require(...)` dependencies; object lookups scoped to the caller's workspace (`get_scoped`); hidden `Multiple` entity returns 404 | `test_rbac.py`, `test_ac_sec_014_*` |
| CSRF | Global dependency: every non-GET `/api/` request needs `X-CSRF-Token` equal to the session token (pre-auth login/initialize use a double-submit token); cross-origin `Origin` rejected | `test_ac_sec_020_*` (enumerates every mutating route) |
| Input validation / mass assignment | Pydantic models with `extra="forbid"`, lengths, enums, patterns, date ranges; money parsed as ≤2-dp decimals with range limits | `test_ac_sec_012_*`, `test_ac_sec_013_*` |
| SQL | SQLAlchemy ORM/Core with bound parameters only; LIKE wildcards escaped; sort/direction/status via `Literal` allowlists | `test_ac_sec_009_*`, `test_ac_sec_010_*` |
| XSS | React escaped rendering only (no `dangerouslySetInnerHTML`, checked by test); CSP `script-src 'self'` without inline | `test_ac_sec_011_*`, E2E `window.__xss` check |
| Attachments | Streaming 5 MB limit + 6 MB body limit; extension allowlist **and** content inspection (PDF header/trailer, Pillow-verified PNG/JPEG, types must agree); random 32-hex storage names under `attachments/`, `O_EXCL` writes; served with `nosniff` and attachment CSP | `test_ac_att_*`, `test_ac_sec_015/016/017_*` |
| Account numbers | AES-256-GCM (random nonce, AAD) + HMAC-SHA256 fingerprint for uniqueness; fixed 10-char mask; reveal = Budget Manager only, audited without the value, `Cache-Control: no-store` | `test_ac_bank_002_003_*`, `test_ac_sec_008_*` |
| Audit | Same DB transaction as the mutation (flush inside the unit of work); `before/after` sanitized (`SENSITIVE_KEYS`); SQLite triggers make `audit_event` append-only | `test_ac_aud_*` |
| Errors & logs | Generic JSON errors with correlation id; validation errors never echo input; engine `hide_parameters=True`; logs record method/path/status only, plus a redaction filter | `test_ac_sec_018_*`, `test_ac_aud_005_ac_sec_019_*` |
| Headers | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, CSP, `Permissions-Policy`, COOP/CORP, `Cache-Control: no-store` on API; HSTS when configured over HTTPS | `test_ac_sec_021_*` |
| Secure defaults | Loopback bind in local mode; no default credentials; debug/docs/openapi disabled; plain-HTTP network warning | `test_ac_sec_022_*`, `test_settings_local_mode_*` |
| OS commands | None — no `subprocess`/`os.system`/`eval` in application code | `test_ac_sec_023_*` (static scan) |

## Dependency vulnerability checks (AC-SEC-024)

```bash
. .venv/bin/activate
bash scripts/security_check.sh          # writes build/security/{pip-audit,npm-audit,security-tests}.txt
# individually:
pip-audit -r backend/requirements.txt
npm --prefix frontend audit
```

Results recorded for this run (2026-09-28): `pip-audit 2.10.1` — *No known vulnerabilities found*;
`npm 10.9.7 audit` — *found 0 vulnerabilities*. During development `npm audit` reported advisories for
`react-router-dom@6.x` and `vite@6.4.1`; they were remediated by removing the router dependency (a 60-line
History-API router is used instead) and pinning `vite@6.4.3`.

## v1.2.0 additions

| Area | Control | Verified by |
|---|---|---|
| Reports (PDF) | All user-controlled text XML-escaped before reportlab paragraph markup (blocks `<img src=…>`/markup injection); attachments read only via generated storage keys and verified against stored SHA-256; malformed PDFs replaced by a placeholder; temp files deleted after the response; available to financial roles and Auditors only (Administrator 403); generation audited | `test_v12_reports.py` |
| Reports (CSV) | Cells beginning with `= + - @` are prefixed with `'` (spreadsheet formula injection) | `test_cr002_entity_activity_report` |
| Transfers | `transaction.manage` + CSRF; request model forbids client-supplied descriptions/fields; object-scoped accounts; closed/non-register accounts refused; legs voided atomically | `test_v12_transfers.py` |
| New dependencies | reportlab 5.0.1, pypdf 6.19.0, charset-normalizer (pinned); `pip-audit`: no known vulnerabilities (2026-09-29); `npm audit`: 0 | `scripts/security_check.sh` |
