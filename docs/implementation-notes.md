# Implementation notes

Authority order followed: business rules (03) → security (04) → acceptance criteria (08) → domain/workflow/
architecture/database (02, 05, 06, 07) → product requirements (01, 09). No specification file was modified.

## 1. Specification ambiguities and how they were resolved

None of the items below blocked implementation, but each required a choice the documents do not make. They are
listed so an evaluator (or the product owner) can confirm or overrule them. The first two involve two
requirements that pull against each other.

| # | Topic | Tension | Resolution chosen |
|---|---|---|---|
| A1 | **Administrator audit-log access vs. financial isolation** | docs/04 matrix and BR-003 grant Administrators the Audit Log, but BR-003/AC-SEC-003 forbid them financial content — and audit snapshots of budgets, transactions, etc. *are* financial content. | Administrators see every audit event's metadata (time, actor, action, object type/id, category) but `before/after` snapshots of financial object types are withheld (`snapshots_withheld: true`). Security/user events are shown in full. Auditors see everything. |
| A2 | **Zero `Other` hidden (BR-019) vs. history/roll-up (BR-026, AC-REG-011)** | If `Other` carried allocations and later becomes 0.00, hiding it would make parent roll-ups not reconcile with visible children. | A zero `Other` is always hidden from transaction selection and hidden from displays **unless it carries actual activity**, in which case it is shown (flagged `hidden_zero_other`) so totals reconcile. |
| A3 | Who resolves Fiscal Year review items | Not in the permission matrix. | Budget Manager (governance/closure owner) and Register User (transaction owner) may confirm; reassignment is a transaction edit (Register User). |
| A4 | Cross-FY allocation "may require review" (BR-059, AC-REG-004/006) | Unclear whether every confirmed cross-FY allocation creates a review item. | Every cross-FY or no-covering-FY allocation creates a `PENDING` review; it blocks closure of the budget FY and of the natural FY until confirmed or reassigned. Reviews on VOID transactions/removed allocations do not block. |
| A5 | Budget 0 | Must belong to a Fiscal Year (budget FK) and be usable by both Deposits and Withdrawals. | One protected Budget 0 per Fiscal Year (code `0`, stored type EXPENSE, exempt from the type rule). Automatic for zero-dollar VOID records; manual selection is offered in selectors but requires explicit `BUDGET_ZERO` confirmation. |
| A6 | Budgets added to an already Approved FY | Approval locks *existing* budgets; new ones are not addressed. | Created as `APPROVED` + unlocked (an amendment); the unlocked-budget closure blocker forces an explicit lock. |
| A7 | Lock/unlock granularity | `Other` is derived from parent and children; locking them independently would allow changing a locked `Other`. | Lock/unlock applies to a whole parent family (parent, explicit children, `Other`). |
| A8 | "Inactive" vs "Rejected" budgets | Both are listed statuses; only Rejected is defined (amount 0). | Inactivation behaves like rejection for amounts (allowed amount 0, requested amount retained, history preserved, no new allocations) but shows `–`/“Inactive” instead of `X`/“Rejected”. |
| A9 | Applicable uncleared transactions for closure | "applicable" undefined. | ACTIVE transactions with any live allocation to a budget of that Fiscal Year. |
| A10 | Quarterly activity for cross-FY allocations | A transaction dated outside the budget FY has no Q1–Q4 bucket. | Yearly actual includes it; an extra "Outside FY dates" column appears when non-zero (no silent re-bucketing). |
| A11 | Allocations removed while editing a split | BR-001/BR-026 forbid losing history. | Removed allocations are soft-removed (`removed_at`) and excluded from totals; pending reviews on them become `REASSIGNED`. |
| A12 | Closed-FY transactions | BR-057 freezes *financial* fields. | Append-only supporting notes and new attachments remain allowed (non-financial, audited); edits, voids and attachment removal are refused. |
| A13 | Opening balance changes | BR-093 forbids manually overriding a register balance to zero. | Opening balance/date and the Register-Enabled flag become immutable once any register transaction exists. |
| A14 | Auditor theme/password | Auditors "may not modify application data", but BR-SEC-SELF-001 and BR-UI-THEME-002 apply to *every* user. | Own password and own theme preference are treated as personal account settings, permitted for all domains. |
| A15 | Entity Number of the hidden `Multiple` entity | "Every Entity" receives a number. | `Multiple` is `ENT-000000`; user entities start at `ENT-000001`. |
| A16 | `Other` child code | Not specified. | Reserved child code `00`, so `Other` displays as `1000-00 Other`; users cannot create child `00` or parent `0`. |

## 1a. Change requests after the benchmark baseline

**CR-001 (requested by the product owner, v1.1.1): correct the Transaction Date of a VOID transaction.**
This deliberately relaxes BR-066/BR-069 and the docs/05 statement that voiding "prevents future financial edits"
for one field only. Rationale: a zero-dollar VOID accountability record created with the default (today's) date
could not otherwise be corrected. Scope and safeguards:

- Dedicated action `POST /api/transactions/{id}/void-date` (Register User, CSRF-protected); the request model accepts
  only `transaction_date`, optional `fiscal_year_id` (zero-dollar records, ambiguous overlap) and an optional `reason`.
- Applies to VOID transactions only; general PATCH editing of VOID transactions is still refused (AC-REG-017 unchanged).
  The record remains VOID; amounts, void reason, check number, allocations' figures and attachments are unchanged.
- Zero-dollar VOID records: Budget 0 allocation follows the Fiscal Year covering the new date (same rule as creation).
- Closed Fiscal Years remain immutable: a record in a Closed FY cannot be corrected and cannot be moved into one.
- Audited as `TRANSACTION_VOID_DATE_CORRECTED` with before/after snapshots and the reason.
- Tests: `backend/tests/test_cr001_void_date.py` (5 tests) and E2E "CR-001".

**v1.2.1 corrections (product owner review of 1.2.0).** These supersede the corresponding 1.2.0 rows below.

| CR | Correction | Implementation |
|---|---|---|
| CR-002 | Audit report layout | Page 1 title page; page 2 Fiscal Year Review introduction (activity summary per account, closure readiness, documentation review with transaction numbers); pages 3–n budgets; then ≥ 1 page per transaction: the seven headline fields (Transaction date, Entity, Transaction type, Amount, Description, Clear Date, Notes) at the top, secondary detail (status, check #, entry, void/transfer/documentation info, allocations) in small print, then every attachment **rendered** beneath within the Letter page width. Implementation: one reportlab build; images drawn with `drawImage`; each PDF attachment page reserves a box of its aspect ratio (`_Block`) and is merged afterwards with `pypdf.merge_transformed_page` (vector, scaled, rotation normalised) so it can sit directly under the transaction details. A box is shrunk to fit the rest of the current page when ≥ 60 % of full size fits, otherwise it starts the next page at full width. Description = the allocation description (numbered list with amounts for splits). The transaction index was removed; the FY supporting documents remain as a final section. Only the audit report changed (the entity report/CSV are as in 1.2.0, per the product owner). |
| CR-003 | Transfer entity | `POST /api/transfers` accepts optional `entity_id` (active, non-hidden entity). It is stored as the parent entity and allocation entity of both legs and names the organization in the descriptions `Transfer to|from <mask> for <Entity>`; without it the workspace (organization) name is used as in 1.2.0. Legs stay locked together (clarified by the product owner: no change). |
| CR-005 | Split documentation rule | Product-owner rule, implemented verbatim in `services/documentation.py: classify`: if the parent has an attachment or the parent no-attachment mark, the transaction is not reviewed for missing documentation (a parent mark is listed as "no attachment"); otherwise every child needs an attachment or its **own** no-attachment mark (migration `0004` adds `no_attachment`, `_reason`, `_set_at`, `_set_by_user_id` to `transaction_allocation`). Any child with neither → "Missing attachment"; all children documented but some only by a mark → "no attachment" item. An unsplit transaction is the same rule with one child. Changing allocation marks is not a financial edit (no cleared-edit confirmation). Uploading to an allocation clears that allocation's mark (`ALLOCATION_NO_ATTACHMENT_CLEARED`); uploading to the transaction clears the parent mark. |

**CR-002 … CR-006 (requested by the product owner, v1.2.0)**

| CR | Feature | Key decisions |
|---|---|---|
| CR-002 | Reports: End of Year Audit PDF; Entity activity | PDF built server-side (reportlab + pypdf) so image **and** PDF attachments are physically placed right after their transaction when printed. Transaction set = dated within the FY **or** allocated to its budgets (cross-FY), grouped by account then date; VOID included by default (option). Each transaction starts a new page; each PDF attachment gets a caption page with SHA-256 then its own pages; a PDF that cannot be parsed is replaced by a placeholder identifying the stored file. All user text is XML-escaped before reportlab markup (prevents `<img src=…>` file inclusion). Entity report credits split-deposit allocations to their own entities, groups transfers separately and excludes them from totals; CSV cells are protected against formula injection. Report generation writes a `REPORT_GENERATED` audit event. |
| CR-003 | Transfers | Two linked ACTIVE transactions (`transfer_group`): withdrawal in source, deposit in destination, same date/clear date/amount. Allocated to protected **Budget 0** of the FY covering the date (non-budget activity, no budget impact; closed FY refused; ambiguous overlap requires an explicit FY). Descriptions generated as `Transfer to|from <10-char masked number of the other account> for <workspace name>`. No entity. Void either leg → both voided. Only Clear Date, Notes and the no-attachment flag are editable per leg (banks may clear on different days); otherwise void and re-enter. Transfers are marked "no attachment will be provided" (reason "Internal transfer between accounts") so they appear once in the documentation review as marked items. |
| CR-004 | "No attachment will be provided" | Transaction-level flag + optional reason + who/when (migration 0003). UI shows a warning dialog before the box can be ticked. Setting/clearing it is not treated as a financial edit (no cleared-edit confirmation). Uploading an attachment to the transaction or one of its allocations clears the flag automatically (audited `TRANSACTION_NO_ATTACHMENT_CLEARED`). |
| CR-005 | Documentation review warnings | Applies to ACTIVE transactions with an allocation in the FY. Single allocation: warning when neither the transaction nor its allocation has an attachment. **Split: warning when (parent has 0 attachments and not every child has one) or (no child has one)** — i.e. every child documented is always sufficient; a parent document is sufficient only together with at least one child document. This follows the request text literally; the rule lives in one function (`services/documentation.py: split_is_documented`) if a looser reading (parent document alone suffices) is preferred. Marked transactions are listed as "no attachment" instead of "missing". Warnings appear in closure readiness, on the FY page, the dashboard and the audit report — never as blockers. VOID transactions are not listed. |
| CR-006 | Searchable entity picker | Accessible combobox (type to filter by name or Entity Number, arrow keys/Enter, "— none —"), used for the payee/payer and split-deposit allocation entities. |

## 2. Other implementation choices

- **Money** is stored as integer cents (SQLite has no exact decimal); API uses decimal strings with ≤2 places.
- **Confirmation protocol**: warning conditions (FY gap/overlap, duplicate entity, cross-FY, no covering FY, cleared
  edit, type change, Budget 0) return `409 CONFIRMATION_REQUIRED` with structured warnings; the client resubmits
  with `confirmations: [codes]`. The UI shows a blocking dialog with an explicit checkbox. Approve/close/void use
  explicit `confirm_*` booleans; the void dialog additionally requires typing `VOID`.
- **Ambiguous overlap (BR-008)**: when two open FYs cover the date the API rejects allocations lacking an explicit
  `fiscal_year_id` (`AMBIGUOUS_FISCAL_YEAR`), so the backend itself never chooses.
- **Split deposits**: parent entity becomes `Multiple` when allocation entities differ; a single-entity deposit keeps
  that entity. Withdrawal allocations inherit the payee; a different allocation entity is rejected.
- **Invoice numbers** are accepted on Withdrawal allocations only (docs/01 §10); check numbers on Withdrawals only.
- Fiscal Years are editable (identifier/dates, with continuity checks) only while Draft; budget codes are immutable
  after creation (name/amount/notes editable).
- A guard prevents disabling/demoting the last active Administrator.
- Theme preference changes are not audited (preference, not business data). All other mutations are audited.
- The login rate limiter is in-process; run one application process per data directory.
- Frontend routing uses a small built-in History-API router (removes the vulnerable `react-router` dependency chain).

## 3. Known limitations / not verified in this environment

| Item | Status |
|---|---|
| AC-DEP-001 Windows build | Windows artifacts are produced (`build_windows_portable.sh` built `FinancialManagementPOC-windows-x64.zip`; `build_windows.ps1` + CI job for PyInstaller) but could not be executed on Windows here → *Manual Verification Required* (procedure in manual-verification.md; CI smoke test provided). |
| AC-DEP-003 browser opening | Loopback binding verified; automatic browser opening requires a desktop session → manual. |
| AC-DEP-006 cross-OS move | Verified by relocating a data set to a new installation directory (same OS) and decrypting; the key/DB format is OS-neutral. Windows↔Linux transfer → manual. |
| Standard Dockerfile | Not built here (Docker Hub blocked by network policy); the bundle-based image was built and run in server mode. |
| Accessibility | Text + icon status, labelled controls, keyboard-closable dialogs; no formal WCAG audit. |
| Scale | SQLite single node; PostgreSQL is a documented Day-2 option (SQLAlchemy keeps the path open). |
