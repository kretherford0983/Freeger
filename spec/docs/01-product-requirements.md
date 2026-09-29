# Financial Management Application — Product Requirements

**Status:** Draft baseline for review  
**Purpose:** Authoritative product-level requirements for the POC.  
**Audience:** Product owner, developers, autonomous software-engineering agents, reviewers.

## 1. Product Summary

Create a secure, web-based financial management application for individuals or teams. The application manages fiscal years, income and expense budgets, entities, bank accounts, continuous account registers, transaction allocations/splits, supporting attachments, users/roles, and immutable audit history.

The POC is a cash/register and budget-management system. It is not intended to be a full general-ledger, accrual, accounts-receivable, accounts-payable, or double-entry accounting platform.

The same application must support:

1. **Local installation** on Windows or Linux, accessed from a browser on localhost and requiring no separately installed Python, Node.js, Docker, or database server.
2. **Server installation** on Windows or Linux, accessed by multiple users over a network. Docker may be supported but cannot be a runtime prerequisite.

## 2. POC Goals

The POC must implement the complete core workflow for:

- Authentication and role-based access control.
- User administration.
- Fiscal Years.
- Income and Expense Budgets, including hierarchical sub-budgets.
- Entities and Financial Institutions.
- Bank Accounts.
- Continuous account Registers.
- Deposits and Withdrawals.
- Single-allocation and split transactions.
- Cross-fiscal-year budget allocation.
- Attachments.
- Transaction voiding and correction rules.
- Fiscal-year approval and closure.
- Immutable audit logging.
- Simple role-aware dashboards.
- Self-contained Windows and Linux application packaging.

## 3. Users and Security Domains

A user account belongs to exactly one high-level security domain. Security domains may not be combined on one account.

### 3.1 Administrator

Administrators manage users and roles and may view audit logs. Administrators may not view or modify financial data.

### 3.2 Financial User

Financial users may hold one or more of these roles:

- **Budget Manager** — manages Fiscal Years, Budgets, Bank Accounts, and Financial Institution Entities; may view Register data but may not create/edit/void transactions.
- **Budget User** — read-only access to permitted financial information; may not modify financial records.
- **Register User** — maintains Register transactions and ordinary Entities; may create Financial Institution Entities but may not modify or inactivate them after creation.

### 3.3 Auditor

Auditors are the global read-only users of the application. They may view all financial data, users/roles, attachments, inactive/rejected/voided records, and audit logs, but may not modify application data.

## 4. Fiscal Years

A Fiscal Year contains:

- Identifier entered by the user, with `FY` automatically prepended for display/name.
- Start Date.
- End Date.
- Status: `DRAFT`, `APPROVED`, or `CLOSED`.
- Creation, approval, and closure audit metadata.
- One or more supporting attachments.

Fiscal Years normally must be consecutive and non-overlapping. Creation/editing must detect gaps and overlaps and warn the Budget Manager. Intentional exceptions require explicit confirmation.

Fiscal quarters are four consecutive three-month periods relative to the Fiscal Year's Start Date.

A Draft Fiscal Year may receive transactions. Approval locks all active budgets. A Closed Fiscal Year is immutable.

At least one supporting attachment is required before closure.

## 5. Budgets

Budgets are specific to a Fiscal Year and are either `INCOME` or `EXPENSE`.

Every budget is conceptually hierarchical. A parent budget always has a system-managed `Other` child. When `Other` is the only child, the UI presents the parent as the selectable/displayed budget. When explicit sub-budgets exist, the parent becomes a roll-up and transactions may only select leaf budgets.

Budget identifiers use:

- Parent only in the simple case: `1000 <Budget Name>`, for example `1000 Operations`.
- Parent and child when explicit sub-budgets exist: `<Parent ID>-<Child ID> <Budget Name>`, for example `1000-01 Travel`.

The sum of explicit sub-budget amounts plus `Other` must always equal the parent amount. `Other` is calculated automatically and cannot be manually edited. If `Other` equals zero, it remains stored but is hidden from normal display and transaction selection.

Budgets may be Draft, Approved/Active, Rejected, or Inactive as appropriate. Rejected budgets have an allowed amount of zero and preserve historical transactions for audit/review.

Budget exhaustion or overage never prevents transaction allocation. Remaining amounts may become negative.

## 6. Bank Accounts

Bank Accounts contain:

- Account Name.
- Financial Institution Entity.
- Account Type.
- Optional subtype.
- Full account number, encrypted at rest.
- Register Enabled flag.
- Primary flag for register-enabled accounts.
- Optional current interest rate.
- Opening Balance and Opening Balance Date where applicable.
- Current balance.
- Status.
- Notes.

Checking and Savings default to Register Enabled. Investment accounts default to not Register Enabled, but defaults may be overridden.

Exactly zero or one active register-enabled account may be Primary. The Primary account is the default Register selection.

Register-enabled account balances are derived from opening balance plus non-void Register activity. Non-register accounts may have a manually updated current balance, with all updates audited.

Bank Accounts cannot be deleted. They may be closed/inactivated only when no uncleared transactions remain and current balance is exactly `0.00`. For register-enabled accounts, the zero balance must be achieved through a final register transaction; it cannot be manually overridden. For non-register accounts, the manually maintained balance must be explicitly updated to `0.00` and audited before closure.

## 7. Entities

Entity types visible to users are:

- Individual.
- Organization.

Individual requires Primary Contact/Person Name. Organization requires Organization Name. Other contact fields are optional.

Entities may be flagged as Financial Institutions. Bank Account institution selectors only show Financial Institution Entities, while Financial Institutions remain valid Register entities.

A hidden protected `Multiple` Entity is created during application initialization and is used by the system for applicable split transactions. It is never displayed in Entity management or normal Entity selectors.

Entities are never hard-deleted. They may become inactive and may be restored through controlled, audited workflows.

The system generates an immutable unique Entity Number (for example `ENT-000001`) to distinguish legitimate duplicate names. Duplicate-name detection is non-blocking and must present existing possible matches before allowing creation.

## 8. Register and Transactions

Each register-enabled Bank Account has a continuous Register across its lifetime. Fiscal Year selection filters the continuous Register by Transaction Date; it does not create separate physical registers.

A Register Transaction contains bank/cash-level information and one or more Transaction Allocations. A normal transaction has exactly one allocation; a split transaction has multiple allocations.

The parent transaction amount is always derived from the sum of its allocation amounts.

Transaction types are:

- Deposit.
- Withdrawal.

Deposits may only allocate to Income budgets. Withdrawals may only allocate to Expense budgets.

Transaction dates include:

- **Transaction Date** — user-editable, defaults to current date.
- **Entry Timestamp** — system-generated and immutable.
- **Clear/Post Date** — nullable; null means uncleared.

Cleared transactions remain editable until an affected Fiscal Year is Closed, but editing a cleared transaction requires blocking confirmation and is fully audited.

A transaction may never move between Bank Accounts after creation. An incorrectly entered account requires voiding the original and creating a new transaction in the correct account.

## 9. Transaction Allocations and Fiscal-Year Assignment

Each Transaction Allocation references a specific Budget primary key. The Budget determines the allocation's Fiscal Year; Fiscal Year is not redundantly persisted on the allocation when it can be derived through the Budget.

The transaction form presents a Fiscal Year selector before the Budget selector. The Fiscal Year defaults to the Fiscal Year covering the Transaction Date. The selected Fiscal Year filters available budgets.

A transaction may allocate to a budget from a different Fiscal Year than the Transaction Date when legitimate. This requires explicit confirmation and may require Fiscal Year review.

If no Fiscal Year covers the Transaction Date, the application warns the user and identifies the closest configured Fiscal Year without silently treating it as correct. Such allocations are flagged for later review when an appropriate Fiscal Year is created.

If an intentional Fiscal Year overlap causes more than one Fiscal Year to cover a Transaction Date, the application must not silently choose one; the user must explicitly select the intended Fiscal Year.

## 10. Split Transactions

Only the parent Register Transaction affects the Bank Account balance. Allocations affect budget actuals.

### 10.1 Split Withdrawal

A Withdrawal has one parent payee/entity. Allocation children may independently contain:

- Fiscal Year/Budget.
- Invoice Number.
- Description.
- Amount.
- Notes.
- One or more attachments.

The Entity is inherited from the parent and cannot vary between Withdrawal allocations.

### 10.2 Split Deposit

A Deposit may represent multiple payments deposited together. Allocation children may independently contain:

- Entity.
- Fiscal Year/Budget.
- Description.
- Amount.
- Notes.
- Attachments.

The parent uses the hidden `Multiple` Entity where appropriate.

## 11. Attachments

POC attachment formats:

- PDF.
- JPG/JPEG.
- PNG.

Maximum size is 5 MB **per file**. Multiple attachments are permitted. The UI must allow users to navigate between attachments when viewing a record.

Attachments are stored on the filesystem; metadata and associations are stored in the database.

## 12. Transaction Voiding

Transactions are never deleted. The user action analogous to deletion is Void.

Void rules:

- Void is irreversible through the UI.
- A required Void Reason must be supplied.
- Strong confirmation is required.
- The transaction remains permanently visible as `VOID`.
- It no longer affects Bank Account balances or Budget actuals.
- Existing allocations and attachments remain for history.
- Existing attachments cannot be removed after voiding.
- Additional supporting attachments and notes may be added after voiding.
- A transaction affecting a Closed Fiscal Year cannot be voided.

Zero-dollar transactions are permitted only when created as VOID records for accountability purposes, such as documenting a physically damaged unused check. They use protected Budget 0 and require an appropriate Void Reason/documentation.

## 13. Fiscal-Year Approval and Closure

Approval is performed by a Budget Manager and is irreversible through the UI. Approval automatically locks active budgets. Approved budgets may later be explicitly unlocked by a Budget Manager for an authorized amendment; unlocking requires a reason and is audited.

Closure is performed only by a Budget Manager and is irreversible in the POC.

Closure blockers include at least:

- Fiscal Year is not Approved.
- One or more budgets are unlocked.
- One or more applicable transactions are uncleared.
- Unresolved Fiscal Year review items exist.
- Invalid/incomplete transaction allocation state exists.
- Fewer than one Fiscal Year supporting attachment exists.

Warnings may include rejected-budget activity, over-budget conditions, reviewed cross-FY allocations, and voided transactions. Budget 0 activity is valid and is not inherently a closure warning.

The Budget Manager must explicitly confirm that the Fiscal Year has been reviewed and is approved for closure. Formal Auditor sign-off is a future enhancement.

## 14. UI / Navigation

Unauthorized modules are hidden and backend authorization independently prevents access.

### Administrator Navigation

- Users.
- Audit Log.
- System/About.

### Financial Navigation

- Dashboard.
- Fiscal Years.
- Budgets.
- Bank Accounts.
- Register.
- Entities.

Visible actions depend on Financial roles.

### Auditor Navigation

- Dashboard.
- Fiscal Years.
- Budgets.
- Bank Accounts.
- Register.
- Entities.
- Users.
- Audit Log.

## 15. Fiscal-Year and Budget Views

Fiscal Year detail presents holistic Income and Expense budget information, separated by type and showing Q1-Q4 activity and yearly totals.

Budget state indicators include:

- Closed padlock — Approved and Locked.
- Open padlock — Approved and Unlocked.
- `?` — Draft/Unapproved.
- `X` — Rejected.

Rows also contain textual status; color/iconography cannot be the only status indicator.

Suggested visual background indicators:

- Approved — light green.
- Draft — light yellow.
- Rejected — light red.

The Budget screen presents similar information but adds editing controls for authorized Budget Managers.

## 16. Register UI

The Register defaults to the Primary register-enabled Bank Account and provides an account selector at the top.

Account display uses Account Name plus a masked account number.

The Register supports filtering by Fiscal Year, transaction type, cleared/uncleared/void status, date, and search. Rows show or provide access to Transaction Date, Clear Date, Entity, Check Number, Invoice Number, Description, Deposit/Withdrawal amount, running balance, attachments, allocations, and other stored metadata.

Rows may be expandable to preserve a readable table while exposing detailed metadata.

## 17. Audit Logging

Audit history is append-only and cannot be modified or deleted through the application.

Auditable mutations record:

- Actor.
- Timestamp.
- Action.
- Object type.
- Object ID.
- Before snapshot.
- After snapshot.

Create events have a null before state. Sensitive fields are sanitized/masked before audit snapshots are persisted.

Financial changes and their audit events must commit atomically. If audit persistence fails, the financial change must roll back.

Revealing a full Bank Account number is itself audit logged, but the revealed number is never written to the audit event.

## 18. Simple POC Dashboard

The POC dashboard is intentionally modest.

Financial users may see current Fiscal Year status, Income/Expense summary information, permitted Bank Account balances, and attention items such as Fiscal Year review items.

Auditors may see Fiscal Year status and review-oriented counts/summaries.

Administrator landing content is limited to user/security-oriented information.

## 19. POC Non-Goals / Later Enhancements

The following are intentionally deferred unless needed to satisfy a core POC rule:

- AI/RAG/MCP functionality.
- Automated backup/restore and portable backup packages.
- Automated attachment compression.
- WebP/TIFF attachments.
- Advanced bank reconciliation/cleared-balance calculations.
- Formal Auditor electronic sign-off for Fiscal Year closure.
- Advanced analytics/reporting/dashboarding.
- Missing-receipt highlighting.
- PostgreSQL deployment option.
- Advanced post-close correction workflows.
- Replacement-transaction relationships.
