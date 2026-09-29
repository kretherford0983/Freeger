# Comparative Implementation Results

## Run Metadata

- Agent/system: Claude (Cowork mode)
- Model/version: claude-opus-5-5 (configured model identifier)
- Date: 2026-09-28
- Starting repository/version: empty `Freedger` folder + benchmark package v1.1 (placed unchanged in `spec/`)
- Time/resource constraints: single session; Linux x86-64 cloud container; Docker Hub and python.org blocked by network policy
- Human interventions: none
- Clarifications supplied: none (ambiguities resolved and documented in implementation-notes.md §1)

## Build and Startup

- Source build: **Pass** (frontend `tsc` + Vite build; backend starts, migrations applied)
- Windows self-contained build: **Built, Not Tested on Windows** (`FinancialManagementPOC-windows-x64.zip`; PyInstaller script + CI job provided) — MV-1
- Linux self-contained build: **Pass** (PyInstaller onedir; started with empty environment; E2E 7/7 against it)
- Optional Docker deployment: **Pass** (bundle-based image built and run in server mode; standard Dockerfile provided but not built — registry blocked)

## Automated Tests

- Total: 121 (114 backend API + 7 E2E UI; E2E additionally re-run against the Linux package)
- Passed: 121
- Failed: 0
- Skipped: 0

## Acceptance Criteria

- Total evaluated: 128
- Passed: 125
- Failed: 0
- Not implemented: 0
- Unable to test (Manual Verification Required): 3 — AC-DEP-001, AC-DEP-003 (browser launch), AC-DEP-006 (cross-OS)

## Security/RBAC

- Result summary: all 25 AC-SEC criteria pass with direct API negative tests; pip-audit and npm audit clean.
- Direct API authorization checks: permission matrix exercised per role; all 36 mutating routes enumerated for CSRF; object-ID substitution tests.
- Sensitive account-number handling: AES-256-GCM ciphertext + HMAC fingerprint; masked 10-char display; Budget-Manager-only reveal, audited without value; raw DB/audit/log scans.
- Session/CSRF observations: HttpOnly SameSite=Strict cookie, hashed server-side sessions, rotation on login, revocation on logout/password change/disable, per-session CSRF token, Origin check.

## Data Integrity

- Fiscal Year lifecycle: Draft operational; irreversible approval (locks budgets) and closure (6 blockers, warnings, confirmation, attachment).
- Budget hierarchy/calculations: system Other recalculated in the same transaction; children ≤ parent enforced; zero Other hidden/reappears; roll-ups derived.
- Register/allocation calculations: totals derived from allocations; balance counts parents once; running and FY-start balances derived.
- Void/closed-year behavior: irreversible void with reason; zero-dollar VOID on Budget 0; closed-year transactions immutable.
- Audit integrity: atomic with mutations (verified by injected failures); append-only enforced by DB triggers; sanitized snapshots.

## Human Review Observations

- UX/usability: role-aware navigation; structured confirmation dialogs; expandable register rows; attachment viewer with navigation.
- Accessibility: labelled controls, icon + text status, keyboard-dismissable dialogs; no formal audit.
- Code organization: routers (HTTP) / services (rules) / schemas (contracts) / security modules.
- Maintainability: Alembic migrations, typed frontend, AC-named tests.
- Documentation: README + docs/ (configuration, deployment, security, implementation notes, acceptance results, manual procedures).
- Visual polish: functional, consistent light/dark palette; intentionally modest.
- Unexpected behavior: none known.

## Known Defects / Missing Scope

- Windows package and cross-OS data move not executed in this environment (procedures provided).
- Specification ambiguities A1–A16 resolved by documented choices pending product-owner confirmation.
