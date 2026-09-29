# Changelog

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
