# Changelog

## 1.5.0 — 2026-10-01
Polish of existing features and easier installation; nothing new in the data model except one per-user setting. Beta: test channel only.
- **Sign-in from a bookmarked page** (found testing 1.4.1): signing in — including two-step verification — now always
  happens on the dashboard address, so a bookmark such as `/about` or `/users` leads to sign-in, then two-step
  verification (or its setup), then the dashboard. A "two-step verification required" answer from the server shows the
  two-step screen instead of the login page.
- A page left open while the server is upgraded now reloads itself once to pick up the new version (API responses name
  the page build they belong to); the page itself is never cached.
- **HF-001** Right after setting up a new installation (or on a slow computer), the sign-in page could briefly appear
  and replace the security token of the new session, so the next action failed ("Missing or invalid CSRF token"). The
  page no longer flashes and a late sign-in token can no longer overwrite the session's token.
- **CR-028 Bank Accounts in two tables.** The Bank Accounts page shows *Checking & Savings* (CHECKING and SAVINGS
  accounts) and *Investments and Other* (every other type) as separate tables, each with a total of its active
  accounts. The dashboard's bank balances table uses the same two groups with a subtotal for each, then the total of
  all accounts.
- **CR-029 Preview the audit signature page.** With *Include audit review signature page* ticked, *Preview signature
  page* opens just that page as a PDF (with the chosen wording and signers) before the full report is generated.
- **CR-030 Charts fill the space.** Charts are placed in two columns that each fill from the top, so a short chart
  no longer leaves a gap next to a tall one (one column on narrow screens).
- **CR-032** The backup passphrase and its confirmation fields line up even when only one has a hint.
- **CR-031 Customize the dashboard.** Financial users and Auditors can choose which dashboard sections are shown and
  in what order: **Customize dashboard** → a checkbox and ↑/↓ buttons per section (Current Fiscal Year, Budget, Bank
  account balances, Attention, Charts and, for Auditors, Review summary). Saved for your account; **Reset to
  default** restores the standard layout. Database migration `0009` (one new column; existing users keep the
  standard layout).
- **CR-026 Windows: one file.** Every release has `Freedger-<version>-windows-x64.exe` — download and double-click
  (local mode, opens the browser; data stays in `%LOCALAPPDATA%\FinancialManagementPOC`). It is not code-signed, so
  SmartScreen may ask: *More info → Run anyway*. The portable .zip is still published. Before a release is published,
  the .exe and the .zip are started on a Windows machine and checked (health, version, web page, license).
- **CR-027 Linux: one command.** `curl -fsSL https://github.com/kretherford0983/Freeger/releases/latest/download/install.sh | sudo bash`
  installs or upgrades a server: it picks the newest production release (while in beta: the newest test
  pre-release, with a notice), verifies the checksums and runs that release's `install-server.sh` (same snapshot,
  rollback copy and untouched `config.toml` as before). `--channel`, `--version` and `--port` options; the port of an
  existing installation is read from its `config.toml`. See docs/deployment.md.
- **License: AGPL-3.0.** Freedger is now free software under the GNU Affero General Public License v3.0 (`LICENSE`).
  `THIRD-PARTY-NOTICES.txt` lists every bundled component with its license; both files are in every package. The
  sign-in page, My Account and System/About show the license and a *Source code* link to the exact commit of the
  build. Runtime dependencies, including indirect ones, are now pinned so packages contain exactly what the notices
  list (CI checks the notices are current).

## 1.4.1 — 2026-09-30
The rest of the 1.4 plan (decisions in docs/implementation-notes.md §1a). Beta: test channel only.
- **CR-016 Audit review signature page.** Reports → End of Year Audit → *Include audit review signature page* adds a
  last page with a blank date line, the wording and a signature line for up to five signers (individual Entities,
  each with an optional title, printed as "Jane Doe, Trustee"). Choose the built-in default wording, one of up to four
  saved wordings (shared by the organization, each with a Delete button) or new wording, which can be saved for future
  use. The variables {FY} (Fiscal Year dates), {ORG} (organization) and {FYE} (Fiscal Year end date) are filled in;
  unknown variables are refused. Saving and deleting wordings is recorded in the audit log.
- **CR-020 Dashboard charts.** The dashboard (financial roles and Auditors) has a *Charts* section for a chosen Fiscal
  Year: income by budget (donut), monthly expenses (bars) with income (line), expense budgets budgeted vs spent, bank
  balances at each month end (per account and total), expenses by budget (donut) and cumulative net. **Choose charts**
  shows or hides each chart; the choice is saved per user (default: the first three). Every chart has a tooltip on
  hover and a *Show data table* view. VOID transactions and transfers are left out; months follow the Fiscal Year.
- **CR-018 Two-step verification (MFA).** Sign-in asks for a 6-digit code from an authenticator app after the
  password. Setup shows a QR code and a key to type in by hand, then 10 one-time **recovery codes** (shown once; new
  ones only by setting it up again). **On a server install it is required for every user** — everyone is asked to set
  it up at their next sign-in; on a local (desktop) install it is optional. "Trust this browser for 30 days" skips the
  code on a private computer. My account → *Two-step verification*: change authenticator, remove trusted browsers.
  Users (Administrator): *Reset two-step* (reason required). A locked-out sole Administrator can be reset on the
  server with `FinancialManagementPOC reset-mfa --user NAME`. Passkeys follow in 1.6.
- **CR-023 Backup.** System/About → *Backup / Restore* (Administrators): one encrypted `.fmbak` file with the
  database, all attachments and the encryption key (not `config.toml`), protected by a passphrase you choose.
- **CR-025 Restore.** Upload a backup, enter its passphrase, your password and `RESTORE`: the current data is replaced,
  kept as a safety copy in `pre-restore/`, the application reloads itself and everyone signs in again with the
  accounts from the backup. Progress is shown step by step; any failure leaves (or puts back) the current data.
- **CR-024 Restore when setting up.** The initialization wizard offers *Restore from a backup instead*, to move an
  installation to a new server. See docs/backup-restore.md.

Upgrade notes: database migrations `0006` (table `signature_template`), `0007` (column `app_user.dashboard_charts`)
and `0008` (tables `user_mfa`, `mfa_recovery_code`, `trusted_device`; column `auth_session.mfa_pending`) are
additive. Users already signed in stay signed in; on a server install each user sets up two-step verification at their
next sign-in (have your phone ready when you first sign in after the upgrade). New folders in the data directory:
`backup-work/` (temporary) and `pre-restore/` (safety copy after a restore).

## 1.4.0 — 2026-09-30
Change requests CR-017, CR-019, CR-021 and CR-022 (decisions recorded in docs/implementation-notes.md §1a). The rest of
the 1.4 plan — audit signature page (CR-016), MFA (CR-018), dashboard charts (CR-020) and backup/restore
(CR-023 … CR-025) — follows in **1.4.1**. Beta: pre-release on the test channel only (no production release is
planned before 1.6).
- **CR-017 Documentation review.** A transaction (or split allocation) marked "no attachment will be provided" **with a
  reason** now counts as documented: it no longer appears in the Fiscal Year documentation review, the closing
  warnings or the dashboard count. A mark without a reason is still listed. Transfers (which carry the reason
  "Internal transfer between accounts") are no longer listed.
- **CR-019 Income budgets.** An income budget that received more than budgeted shows **+$X above budget** in green
  (Budgets page, dashboard, budget selector and the PDF reports) instead of a negative remaining amount, and is no
  longer an "over budget" closing warning. Expense budgets are unchanged.
- **CR-021** The dashboard's bank account balances show a **Total** of all listed accounts.
- **CR-022** **My account → About** shows the application version and build (e.g. *test build #12*) to every user.
  System/About (Administrators) shows the same plus the bind address; other users no longer receive the bind address
  and port from the About API.

## 1.3.0 — 2026-09-29
Change requests CR-007 … CR-015 (decisions recorded in docs/implementation-notes.md §1a):
- **CR-007 Fiscal Year document types.** Fiscal Year documents are *Approval document*, *Audit Signoff* or *Other*.
  Approving a Fiscal Year needs an Approval document — or the "No approval document" mark (strong warning, optional
  reason), which is then a Fiscal Year review warning. Closing needs an Audit Signoff (an "other" document no longer
  counts) and an Approval document unless the mark is set. Budget Managers can change a document's type while the
  year is open (audited); uploading an Approval document clears the mark automatically.
- **CR-008 Fiscal Year Close report.** New PDF on the Reports page: the audit report with the Fiscal Year documents
  placed after the Fiscal Year review and before the budgets and transactions. A copy is generated automatically when
  the year is closed and kept as a permanent, system-generated Fiscal Year document (if it cannot be produced the
  closing is not performed). The End of Year Audit report no longer includes the Fiscal Year documents.
- **CR-009** Split-allocation attachment lists and PDF captions are labelled "<Entity> - <Budget>"
  (e.g. "Bob Smith - 4000 Donations"; the transaction's entity is used when the allocation has none).
- **CR-010** Files can be attached while entering or editing a transaction — for the transaction and for each split
  allocation. They upload right after saving; any file that fails is named and can be added again from the register.
- **CR-011 Duplicate protection.** Every form is locked with "Saving…" while it saves; each create form sends a
  one-time request key so a repeated submit returns the record already created; a *possible duplicate* confirmation
  appears for a transaction with the same account, date, type, amount and entity. A check number can be used only once
  per account — voided checks keep their number. A wrongly entered number on a VOID record is fixed with
  **Correct check number…** (clear or change, reason required, audited, noted on the record).
- **CR-012 Missing check review.** Register → Fiscal Year reviews lists gaps in each account's check sequence (from
  the lowest to the highest recorded number; VOID records count as recorded). Resolve by entering the transaction,
  recording a zero-dollar VOID for the number, or "Confirm not missing" with a note. Gaps are a closing warning only.
  Check numbers repeated before 1.3 are listed for clean-up.
- **CR-013** The top bar and left navigation stay in place; only the page content scrolls.
- **CR-014** The left navigation collapses to icons («/»); the choice is remembered per user.
- **CR-015** The register header (title, account, buttons, filters, balances) and the column headings stay on screen
  while scrolling (normal scrolling on very small windows).

Upgrade notes: database migration `0005` is additive (new tables `request_key`, `check_number_acknowledgement`; new
columns on `attachment`, `fiscal_year`, `app_user`). Existing Fiscal Year documents become "Other": before closing an
open Fiscal Year, mark its signoff document as **Audit Signoff** (and its approval document as **Approval**).
`config.toml`, the key and attachments are not touched. See docs/upgrade.md.

## 1.2.1 — 2026-09-29
Corrections requested by the product owner after reviewing 1.2.0:
- **CR-002 — End of Year Audit PDF layout.** Page 1 is a title page; page 2 is the *Fiscal Year Review*
  introduction (activity summary per account, closure readiness, documentation review); pages 3–n list the budgets;
  then **every transaction gets at least one page** with its headline fields at the top — *Transaction date, Entity,
  Transaction type, Amount, Description, Clear Date, Notes* — and **each attachment reproduced underneath, scaled to
  the 8.5×11 page width** (images drawn; PDF attachments embedded page by page as vector content, landscape/legal
  pages scaled to fit). Every page of the report is US Letter. The transaction index page was removed. The Entity
  activity report and its CSV are unchanged.
- **CR-003 — Transfers.** The transfer form has an **Entity** field; the generated descriptions read
  `Transfer to|from <masked account> for <selected Entity>` (the organization/workspace name when no Entity is chosen),
  and the Entity is recorded on both legs. Legs remain locked together (voiding one voids both) as before.
- **CR-005 — Split documentation rule** is now exactly: if the transaction (parent) has **no** attachment **and** is
  not marked "no attachment", every allocation (child) needs an attachment **or its own "no attachment" mark**;
  if the parent has an attachment or the mark, the allocations need neither and are not reviewed.
  Split allocations therefore get their own **"No attachment will be provided for this allocation"** checkbox
  (with the same warning and optional reason); uploading a file to that allocation clears it automatically.

Upgrade notes: database migration `0004` **adds** four columns to `transaction_allocation` (per-allocation
no-attachment flag, reason, who/when); existing rows are not changed. `config.toml`, the key and attachments are
untouched. See docs/upgrade.md.

## 1.2.0 — 2026-09-29
New features (change requests CR-002 … CR-006):
- **Reports** (new menu item for all financial roles and Auditors):
  - *End of Year Audit report* — one printable PDF: Fiscal Year budget (Q1–Q4, actuals, remaining), closure/review
    summary, transaction index, then **every transaction of the year on its own page followed immediately by its
    attachments** (images rendered, PDF attachments merged page-for-page, SHA-256 verified), then the Fiscal Year
    supporting documents. Options: one account or all, include/exclude VOID. Generation is audited.
  - *Entity activity report* — deposits and withdrawals per entity for an account (or all accounts) and date range,
    with per-transaction detail, print view and CSV export. Transfers are shown separately.
- **Transfers** — "Transfer…" button in the Register records a withdrawal in the source account and a deposit in the
  destination account (linked; descriptions generated as `Transfer to|from <masked account> for <organization>`;
  Budget 0, so budgets are unaffected). Voiding either side voids both; per-side clear date and notes stay editable.
- **Searchable entity picker** in the transaction form (type to filter by name or Entity Number; keyboard friendly).
- **"No attachment will be provided" checkbox** on transactions, with a warning when ticked and an optional reason.
  Adding an attachment later clears the mark automatically (audited).
- **Documentation review** on the Fiscal Year page, in closure-readiness warnings, on the dashboard and in the audit
  report: transactions without supporting attachments and transactions marked "no attachment". Warnings only —
  never a blocker for approval or closure.
- Budget 0 is now shown as inflows/outflows (transfers post both directions).

Upgrade notes: database migration `0003` adds columns only (existing rows untouched). New runtime libraries:
reportlab, pypdf (bundled in the packages). See docs/upgrade.md.

## 1.1.1 — 2026-09-28
- **CR-001 (change request): correct the Transaction Date of a VOID transaction.** Register Users can use
  **Register → expand a VOID row → Correct date…** (API `POST /api/transactions/{id}/void-date`). Only the date changes;
  the record stays VOID with zero balance/budget effect and the change is audited (`TRANSACTION_VOID_DATE_CORRECTED`).
  For a zero-dollar VOID accountability record, its protected Budget 0 allocation follows the new date's Fiscal Year.
  Closed Fiscal Years stay immutable (a record in a closed year cannot be changed, and a record cannot be moved into one).
- Zero-dollar VOID records dated inside a Closed Fiscal Year are now refused instead of attaching to the nearest open year.
- New portable Linux build (`packaging/build_linux_portable.sh`, glibc ≥ 2.27) and server installer
  (`packaging/linux/install-server.sh`).
- No database schema change (no new migration); existing data, `config.toml` and the encryption key are untouched by the upgrade.

## 1.1.0 — 2026-09-28
- Initial implementation of the benchmark v1.1 POC.
