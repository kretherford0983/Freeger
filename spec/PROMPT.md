# PROMPT.md — Financial Management POC Implementation Task

Implement the complete Financial Management POC described by this repository.

This is a greenfield implementation and may be used as a comparative benchmark across autonomous software-engineering agents. Your output should therefore be a working, testable implementation rather than a requirements rewrite or architectural proposal.

## Required First Step

Read, in full:
- `AGENT.md`;
- all documents under `docs/`;
- `evaluation/clarifications.md`.

Treat those materials as the authoritative specification. Do not invent accounting, security, lifecycle, or permission rules where the repository already defines them.

## Implementation Goal

Deliver the POC with the documented modules and cross-cutting controls, including:
- authentication and role separation;
- Fiscal Years and lifecycle rules;
- hierarchical Income/Expense Budgets with system-managed Other behavior;
- Entities and Financial Institutions;
- Bank Accounts and encrypted account-number handling;
- continuous Registers;
- normal and split Transactions/Allocations;
- cross-Fiscal-Year allocation/review handling;
- attachments;
- void/inactivation/history behavior;
- immutable audit logging;
- Fiscal Year approval/closure;
- role-aware UI/navigation and the specified POC dashboard;
- secure coding controls and adversarial/negative tests;
- self-contained Windows and Linux packaging approach plus optional Docker server deployment.

## Technical Baseline

Use the architecture specified in `docs/06-technical-architecture.md`: React + TypeScript frontend, Python + FastAPI backend, SQLAlchemy, Alembic, SQLite for the POC, filesystem attachment storage, server-side sessions, and portable application-level encryption for sensitive account numbers.

## Execution Strategy

Implement incrementally in a dependency-aware order. A recommended sequence is:

1. **Foundation** — repository structure, configuration, SQLite/Alembic, first-run initialization, authentication, RBAC, sessions/CSRF, audit infrastructure, encryption/key handling, secure request/error/logging foundations.
2. **Financial Structure** — Fiscal Years, Budgets, Entities, Bank Accounts, lifecycle validation and permissions.
3. **Register** — Register UI/API, Transactions, Allocations, splits, dates, balances, attachments, cross-FY review, void behavior.
4. **Governance** — approval, lock/unlock/rejection, Fiscal Year closure checks and attachments, closed immutability.
5. **UI Completion** — dashboards, role-aware navigation, holistic Fiscal Year/Budget views, filters, accessible state indicators, audit views.
6. **Security Verification** — injection/XSS/mass-assignment/object-authorization/upload/path/CSRF/error/logging/security-header tests and dependency checks.
7. **Packaging** — production React build served by FastAPI, self-contained Windows/Linux builds, local/server modes, optional Docker server packaging.
8. **Acceptance Verification** — execute/document all acceptance criteria and produce a results report.

You may adjust internal sequencing when dependencies require it, but do not reduce scope.

## Definition of Done

The task is complete only when:
- the application can be run and exercised;
- required database migrations exist;
- backend business/security rules are enforced independently of the UI;
- automated tests cover the documented acceptance criteria wherever practical;
- security negative tests are present and pass;
- no known POC requirement is silently omitted;
- setup/build/deployment instructions are documented;
- acceptance results identify the status of every criterion;
- any unavoidable limitations are clearly documented rather than hidden.

Do not implement deferred Day-2 functionality merely to add polish. Prioritize correctness, auditability, security, data integrity, testability, and compliance with the canonical specification.
