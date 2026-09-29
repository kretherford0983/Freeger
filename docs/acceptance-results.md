# Acceptance-criteria results

> **v1.2.1 update:** product-owner corrections to CR-002 (audit PDF layout with attachments rendered at page width),
> CR-003 (transfer Entity) and CR-005 (split documentation rule + per-allocation no-attachment flag, migration 0004);
> see implementation-notes.md §1a. Full regression: **138 backend tests and 12 E2E tests pass**; `pip-audit` and
> `npm audit` report no vulnerabilities. All baseline criteria keep their status.
>
> **v1.2.0 update:** change requests CR-002…CR-006 (reports, transfers, no-attachment flag, documentation review,
> searchable entity picker) added; see implementation-notes.md §1a. Full regression: **135 backend tests and 11 E2E
> tests pass** (E2E also passes against the portable and PyInstaller Linux packages). All baseline criteria keep
> their status. Note for AC-FY-012: closure warnings now also include documentation-review warnings.
>
> **v1.1.1 update:** change request CR-001 (correct the date of a VOID transaction) was added after the baseline run;
> see implementation-notes.md §1a. All criteria below were re-run: 119 backend tests and 8 E2E tests pass.
> AC-REG-015/016/017 remain Pass — VOID stays irreversible, has zero financial effect, and general editing is still refused.

Run date: 2026-09-28 · Environment: Linux x86-64 container, Python 3.11.15, Node 22.22, Chromium 141 (Playwright 1.56.1).

Evidence sources:
- **API** — `backend/tests/*.py` (pytest, 114 tests, **114 passed**). Test names embed AC IDs.
- **E2E** — `frontend/e2e/poc.spec.ts` (Playwright, 7 tests, **7 passed** against source *and* **7 passed** against the packaged Linux build).
- **PKG** — packaging runs recorded in this report.

Status legend: **Pass** · **Fail** · **Not Implemented** · **Manual Verification Required** (procedure in `manual-verification.md`).

## Summary

| Group | Total | Pass | Manual Verification Required | Fail / Not Implemented |
|---|---|---|---|---|
| Authentication & RBAC / Security (AC-SEC) | 25 | 25 | 0 | 0 |
| Fiscal Years (AC-FY) | 13 | 13 | 0 | 0 |
| Budgets (AC-BUD) | 11 | 11 | 0 | 0 |
| Entities (AC-ENT) | 6 | 6 | 0 | 0 |
| Bank Accounts (AC-BANK) | 11 | 11 | 0 | 0 |
| Register (AC-REG) | 19 | 19 | 0 | 0 |
| Attachments (AC-ATT) | 4 | 4 | 0 | 0 |
| Audit (AC-AUD) | 5 | 5 | 0 | 0 |
| Packaging & Deployment (AC-DEP) | 6 | 3 | 3 | 0 |
| Initialization (AC-INIT) | 8 | 8 | 0 | 0 |
| Self-service password (AC-AUTH-SELF) | 6 | 6 | 0 | 0 |
| Theme (AC-UI-THEME) | 3 | 3 | 0 | 0 |
| Draft FY visibility (AC-FY-VIS) | 11 | 11 | 0 | 0 |
| **Total** | **128** | **125** | **3** | **0** |

## Authentication, RBAC and security

| AC | Status | Evidence |
|---|---|---|
| AC-SEC-001 | Pass | API `test_ac_init_001_008_fresh_install_requires_wizard` (default credential attempts rejected), `test_ac_init_003_to_007_bootstrap_admin`; E2E wizard test |
| AC-SEC-002 | Pass | API `test_ac_sec_002_domain_separation` (6 cross-domain combos rejected on create and role change; multi-Financial allowed) |
| AC-SEC-003 | Pass | API `test_ac_sec_003_admin_financial_isolation` (17 financial endpoints → 403; financial audit snapshots withheld); E2E direct URL shows "not authorized" |
| AC-SEC-004 | Pass | API `test_ac_sec_004_auditor_read_only` (views users, audit, inactive/rejected/void, attachments; 8 mutation attempts → 403) |
| AC-SEC-005 | Pass | API `test_ac_sec_005_permission_matrix_direct_api`; E2E nav contents per role |
| AC-SEC-006 | Pass | API `test_ac_sec_006_session_cookie_properties` (HttpOnly, SameSite, server-side invalidation), `test_ac_sec_006_session_rotation_on_login`, `test_no_localstorage_token_in_frontend` |
| AC-SEC-007 | Pass | API `test_ac_sec_007_financial_institution_maintenance` |
| AC-SEC-008 | Pass | API `test_ac_sec_008_reveal_only_budget_manager_audited` (4 roles denied; audit + log free of plaintext); E2E reveal in UI |
| AC-SEC-009 | Pass | API `test_ac_sec_009_sql_injection_resistance` (7 payloads across entity search, register search, audit filter; stored literally; wildcards escaped) |
| AC-SEC-010 | Pass | API `test_ac_sec_010_structural_allowlists` |
| AC-SEC-011 | Pass | API `test_ac_sec_011_script_payloads_stored_as_inert_text`; E2E `<img onerror>` entity rendered as text, `window.__xss` undefined |
| AC-SEC-012 | Pass | API `test_ac_sec_012_server_side_validation`, `test_budget_validation`, `test_fy_validation`, `test_ac_init_002_required_fields` |
| AC-SEC-013 | Pass | API `test_ac_sec_013_mass_assignment` (20 protected-field attempts incl. bank_account_id, total, locked, status, is_system, roles) |
| AC-SEC-014 | Pass | API `test_ac_sec_014_object_level_authorization` |
| AC-SEC-015 | Pass | API `test_ac_sec_015_ac_att_004_path_traversal` (7 hostile names; files only as `<32hex>.bin` under attachments/) |
| AC-SEC-016 | Pass | API `test_ac_sec_016_disguised_files_rejected` (PE/ELF/script/HTML/mismatched/truncated) |
| AC-SEC-017 | Pass | API `test_ac_att_002_ac_sec_017_rejected_formats_and_size`, `test_request_body_limit` |
| AC-SEC-018 | Pass | API `test_ac_sec_018_safe_error_responses` |
| AC-SEC-019 | Pass | API `test_ac_aud_005_ac_sec_019_sensitive_values_absent` (DB audit rows + log file scanned for passwords, hashes, session tokens/hashes, CSRF tokens, keys, account numbers) |
| AC-SEC-020 | Pass | API `test_ac_sec_020_csrf_rejection_no_mutation`, `test_ac_sec_020_every_mutating_route_requires_csrf` (all 36 mutating API routes enumerated) |
| AC-SEC-021 | Pass | API `test_ac_sec_021_security_headers`, `test_ac_sec_021_hsts_when_https_configured`; PKG headers observed on packaged build (curl) |
| AC-SEC-022 | Pass | API `test_ac_sec_022_no_debug_or_docs_exposed`, fresh-install tests; packaged build started with `debug=False`, no docs routes |
| AC-SEC-023 | Pass | API `test_ac_sec_023_no_shell_command_construction` (static scan: no subprocess/os.system/eval/exec) |
| AC-SEC-024 | Pass | `scripts/security_check.sh`: pip-audit 2.10.1 "No known vulnerabilities found"; npm audit "found 0 vulnerabilities" (2026-09-28) |
| AC-SEC-025 | Pass | Security negative tests in `test_attachments_audit_security.py`, `test_rbac.py`, `test_init_auth.py` (all passing) |

## Fiscal Years

| AC | Status | Evidence |
|---|---|---|
| AC-FY-001 | Pass | `test_ac_fy_001_naming` |
| AC-FY-002 | Pass | `test_ac_fy_002_relative_quarters`, `test_ac_fy_002_quarter_activity_by_transaction_date` |
| AC-FY-003 | Pass | `test_ac_fy_003_consecutive_no_warning` |
| AC-FY-004 | Pass | `test_ac_fy_004_gap_warning`; E2E gap confirmation dialog |
| AC-FY-005 | Pass | `test_ac_fy_005_overlap_warning_with_readiness` |
| AC-FY-006 | Pass | `test_ac_fy_006_ambiguous_overlapping_date` |
| AC-FY-007 | Pass | `test_ac_fy_007_copy_prior_budgets` (selected parents + hierarchy + amounts as Draft; removed budget not copied) |
| AC-FY-008 | Pass | `test_ac_fy_008_draft_accepts_transactions` |
| AC-FY-009 | Pass | `test_ac_fy_009_approval` |
| AC-FY-010 | Pass | `test_ac_fy_010_011_closure_blockers_each_independently`, `test_ac_fy_010_invalid_allocation_state_blocks` |
| AC-FY-011 | Pass | `test_ac_fy_010_011_closure_blockers_each_independently` (attachment removal re-blocks) |
| AC-FY-012 | Pass | `test_ac_fy_012_closure_warnings_budget0_not_warning`, `test_ac_fy_012_rejected_budget_activity_warning` |
| AC-FY-013 | Pass | `test_ac_fy_013_closed_immutability` |

## Budgets

| AC | Status | Evidence |
|---|---|---|
| AC-BUD-001 | Pass | `test_ac_bud_001_automatic_other` |
| AC-BUD-002 | Pass | `test_ac_bud_002_child_and_other_recalc`; E2E (Other = $75,000.00) |
| AC-BUD-003 | Pass | `test_ac_bud_003_children_cannot_exceed_parent` |
| AC-BUD-004 | Pass | `test_ac_bud_004_005_zero_other_hidden_then_reappears`, `test_ac_bud_004_zero_other_rejected_for_new_allocation` |
| AC-BUD-005 | Pass | `test_ac_bud_004_005_zero_other_hidden_then_reappears` |
| AC-BUD-006 | Pass | `test_ac_bud_006_rollup_parent_not_selectable` |
| AC-BUD-007 | Pass | `test_ac_bud_007_display_identifier`; E2E |
| AC-BUD-008 | Pass | `test_ac_bud_008_overage_allowed_negative_remaining` |
| AC-BUD-009 | Pass | `test_ac_bud_009_unlock_requires_reason_and_audits` |
| AC-BUD-010 | Pass | `test_ac_bud_010_rejected_budget` (API state `X`/red/"Rejected"; UI row class `bg-red` + icon + text) |
| AC-BUD-011 | Pass | `test_ac_bud_011_status_indicators`; E2E screenshots show icon + text + background |

## Entities

| AC | Status | Evidence |
|---|---|---|
| AC-ENT-001 | Pass | `test_ac_ent_001_002_required_names` |
| AC-ENT-002 | Pass | `test_ac_ent_001_002_required_names` |
| AC-ENT-003 | Pass | `test_ac_ent_003_register_display` |
| AC-ENT-004 | Pass | `test_ac_ent_004_005_duplicates_and_numbers` |
| AC-ENT-005 | Pass | `test_ac_ent_004_005_duplicates_and_numbers` (UI selectors append Entity Number for duplicate names) |
| AC-ENT-006 | Pass | `test_ac_ent_006_inactivation_preserves_history` |

## Bank Accounts

| AC | Status | Evidence |
|---|---|---|
| AC-BANK-001 | Pass | `test_ac_bank_001_financial_institution_filtering` |
| AC-BANK-002 | Pass | `test_ac_bank_002_003_uniqueness_and_encryption` (formatting-insensitive, randomized ciphertext) |
| AC-BANK-003 | Pass | `test_ac_bank_002_003_uniqueness_and_encryption` (raw SQLite + audit rows inspected) |
| AC-BANK-004 | Pass | `test_ac_bank_004_masking` (lengths 4–12; all roles) |
| AC-BANK-005 | Pass | `test_ac_bank_005_primary`, `test_register_defaults` |
| AC-BANK-006 | Pass | `test_ac_bank_006_register_balance` |
| AC-BANK-007 | Pass | `test_ac_bank_007_transaction_cannot_move_account` |
| AC-BANK-008 | Pass | `test_ac_bank_008_009_010_closure_rules` |
| AC-BANK-009 | Pass | `test_ac_bank_008_009_010_closure_rules` |
| AC-BANK-010 | Pass | `test_ac_bank_008_009_010_closure_rules` (manual override and opening-balance change refused; final transaction to exactly 0.00) |
| AC-BANK-011 | Pass | `test_ac_bank_011_non_register_zeroing` |

## Register transactions and allocations

| AC | Status | Evidence |
|---|---|---|
| AC-REG-001 | Pass | `test_ac_reg_001_parent_allocation_model`; E2E |
| AC-REG-002 | Pass | `test_ac_reg_002_dates` |
| AC-REG-003 | Pass | `test_ac_reg_003_budget_type_filtering` (incl. Budget 0 exception with confirmation) |
| AC-REG-004 | Pass | `test_ac_reg_004_006_cross_fy_confirmation_and_review` |
| AC-REG-005 | Pass | `test_ac_reg_005_missing_natural_fiscal_year` |
| AC-REG-006 | Pass | `test_ac_reg_004_006_cross_fy_confirmation_and_review`, `test_review_reassignment_resolves` |
| AC-REG-007 | Pass | `test_ac_reg_007_split_withdrawal` |
| AC-REG-008 | Pass | `test_ac_reg_008_split_deposit_multiple` |
| AC-REG-009 | Pass | `test_ac_reg_009_010_011_derived_total_and_single_count` ($600+$400=$1,000 → $1,100) |
| AC-REG-010 | Pass | same test (balance −$1,100 exactly) |
| AC-REG-011 | Pass | same test (per-budget actuals, parent roll-up) |
| AC-REG-012 | Pass | `test_ac_reg_012_cleared_edit_confirmation` |
| AC-REG-013 | Pass | `test_ac_reg_013_type_change_protected` |
| AC-REG-014 | Pass | `test_ac_reg_014_no_hard_delete` |
| AC-REG-015 | Pass | `test_ac_reg_015_016_017_void`; E2E void dialog (reason + typed confirmation) |
| AC-REG-016 | Pass | `test_ac_reg_015_016_017_void` |
| AC-REG-017 | Pass | `test_ac_reg_015_016_017_void` |
| AC-REG-018 | Pass | `test_ac_reg_018_void_attachments` |
| AC-REG-019 | Pass | `test_ac_reg_019_zero_dollar_void` |

## Attachments

| AC | Status | Evidence |
|---|---|---|
| AC-ATT-001 | Pass | `test_ac_att_001_003_allowed_formats_and_multiple` (PDF/PNG/JPG/JPEG, exactly 5 MiB accepted) |
| AC-ATT-002 | Pass | `test_ac_att_002_ac_sec_017_rejected_formats_and_size` |
| AC-ATT-003 | Pass | `test_ac_att_001_003_allowed_formats_and_multiple`; UI viewer has Previous/Next navigation (`components.tsx` `Attachments`) |
| AC-ATT-004 | Pass | `test_ac_sec_015_ac_att_004_path_traversal` |

## Audit

| AC | Status | Evidence |
|---|---|---|
| AC-AUD-001 | Pass | `test_ac_aud_001_002_snapshots` |
| AC-AUD-002 | Pass | `test_ac_aud_001_002_snapshots`, `test_ac_reg_012_cleared_edit_confirmation` |
| AC-AUD-003 | Pass | `test_ac_aud_003_atomic_rollback` (audit writer failure), `test_ac_aud_003_db_level_audit_failure_rolls_back` (DB-level failure) |
| AC-AUD-004 | Pass | `test_ac_aud_004_append_only` (no API routes; SQLite triggers abort UPDATE/DELETE) |
| AC-AUD-005 | Pass | `test_ac_aud_005_ac_sec_019_sensitive_values_absent`, `test_ac_bank_002_003_uniqueness_and_encryption` |

## Packaging and deployment

| AC | Status | Evidence |
|---|---|---|
| AC-DEP-001 | Manual Verification Required | Artifact built: `dist/FinancialManagementPOC-windows-x64.zip` (relocatable CPython 3.12.12 + win_amd64 wheels, no install needed). Not executable in this Linux environment. `build_windows.ps1` and CI job `build-windows` (build + smoke test on windows-latest) provided. Procedure MV-1. |
| AC-DEP-002 | Pass | PKG: PyInstaller bundle started with `env -i PATH=/nonexistent` (no Python/Node/SQLite on PATH), fresh data dir, migrations applied; **full E2E suite (7/7) passed against the bundle** |
| AC-DEP-003 | Manual Verification Required | Loopback default verified (`test_settings_local_mode_binds_loopback`; packaged build unreachable on the container's non-loopback IP). Browser auto-open needs a desktop session → MV-2. |
| AC-DEP-004 | Pass | `test_settings_local_mode_binds_loopback` (server mode host override); PKG: container run with `FM_MODE=server FM_HOST=0.0.0.0` served via published port, with plain-HTTP security warning |
| AC-DEP-005 | Pass | `packaging/docker/Dockerfile` + compose/Caddy provided; bundle-based image built with `build_bundle_image.sh` and run successfully; native builds do not use Docker |
| AC-DEP-006 | Manual Verification Required | `test_ac_dep_006_portable_data_set` (copied data set → new installation decrypts), `test_portable_key_required` (missing key refused). Key file is OS-neutral JSON. Actual Windows↔Linux move → MV-3. |

## Benchmark v1.1 criteria

| AC | Status | Evidence |
|---|---|---|
| AC-INIT-001 | Pass | `test_ac_init_001_008_fresh_install_requires_wizard`; E2E wizard auto-presented |
| AC-INIT-002 | Pass | `test_ac_init_002_required_fields`; E2E |
| AC-INIT-003 | Pass | `test_ac_init_003_to_007_bootstrap_admin` (key file, roles, Multiple, admin role) |
| AC-INIT-004 | Pass | same; E2E sign-out/sign-in |
| AC-INIT-005 | Pass | same; E2E admin nav/dashboard/users/audit |
| AC-INIT-006 | Pass | same; E2E user list row |
| AC-INIT-007 | Pass | same; E2E `/fiscal-years` not authorized |
| AC-INIT-008 | Pass | `test_ac_init_001_008_*` (empty migrated DB), `test_ac_init_008_partial_workspace_row_does_not_suppress_wizard` |
| AC-AUTH-SELF-001 | Pass | `test_ac_auth_self_001_to_006_password_change`, `test_ac_auth_self_all_domains_can_change_password`; E2E |
| AC-AUTH-SELF-002 | Pass | same |
| AC-AUTH-SELF-003 | Pass | same |
| AC-AUTH-SELF-004 | Pass | same; E2E old password rejected / new accepted |
| AC-AUTH-SELF-005 | Pass | same |
| AC-AUTH-SELF-006 | Pass | same |
| AC-UI-THEME-001 | Pass | E2E theme toggle; `test_ac_ui_theme_001_002_persistence` |
| AC-UI-THEME-002 | Pass | E2E across navigation + logout/login; API persistence test |
| AC-UI-THEME-003 | Pass | E2E captures 12 full-page screenshots (6 core screens × 2 themes) — reviewed visually; all E2E flows also executed with dark theme active for `bm1` |
| AC-FY-VIS-001 | Pass | `test_ac_fy_vis_001_to_011_draft_visibility`; E2E |
| AC-FY-VIS-002 | Pass | same; E2E detail route immediately after create |
| AC-FY-VIS-003 | Pass | same; E2E Budget FY filter shows "FY2027 — Draft" |
| AC-FY-VIS-004 | Pass | E2E Create Budget selector shows "FY2027 — Draft" |
| AC-FY-VIS-005 | Pass | API + E2E budget created in Draft FY |
| AC-FY-VIS-006 | Pass | API + E2E Register User allocation to Draft-year budget |
| AC-FY-VIS-007 | Pass | labels `FY2027 — Draft` everywhere; status never used alone |
| AC-FY-VIS-008 | Pass | `test_ac_fy_vis_001_to_011_draft_visibility` (same id/route/name after approval) |
| AC-FY-VIS-009 | Pass | `test_ac_fy_013_closed_immutability` |
| AC-FY-VIS-010 | Pass | list/selectable endpoints return Draft FYs (API test) |
| AC-FY-VIS-011 | Pass | Draft detail returns 200 for every financial role |
