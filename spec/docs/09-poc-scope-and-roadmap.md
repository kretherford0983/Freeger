# 09 — POC Scope and Roadmap

## POC Required Scope

The POC is not a mock-up. It must implement the documented modules and core rules sufficiently for end-to-end use and objective acceptance testing.

Required:
- first-run initialization;
- authentication and role-based access control;
- Administrator, Budget Manager, Budget User, Register User and Auditor behavior;
- Fiscal Year creation, copying, approval, attachments and closure;
- Fiscal Year gap/overlap safeguards;
- Income and Expense budgets, hierarchy, Other, rejection, lock/unlock and remaining calculations;
- Entities including Financial Institution controls and duplicate warnings;
- Bank Accounts including encrypted account numbers, Primary account, register/non-register balances and closure rules;
- continuous Registers;
- normal and split Deposit/Withdrawal transactions;
- transaction allocations and cross-FY handling/review;
- clear dates, void lifecycle and zero-dollar void accountability records;
- PDF/JPEG/PNG attachments up to 5 MB per file;
- immutable application audit trail with sanitized before/after snapshots;
- simple role-appropriate dashboards and documented core screens;
- SQLite persistence and Alembic migrations;
- self-contained Windows and Linux deployment artifacts or verified build procedures producing them;
- optional Docker server deployment support if implemented without compromising native packaging;
- automated tests covering critical business rules and acceptance criteria.

## Explicitly Deferred / Day 2

The following are intentionally outside the required POC unless an implementation needs a small enabling component:
- AI analysis, RAG, MCP, embeddings or model integration;
- automated cloud backup/restore;
- user-facing backup export/import package;
- scheduled backups;
- full-database encryption/SQLCipher;
- PostgreSQL production profile;
- high-concurrency scaling work;
- bank feeds or direct banking integrations;
- automated reconciliation/cleared-balance calculations;
- formal Auditor sign-off workflow before Fiscal Year closure;
- advanced reporting/BI and enhanced dashboards;
- missing-receipt highlighting;
- attachment compression;
- TIFF/WebP attachments;
- invoice-generation/accounts-receivable module;
- explicit replacement-check relationship;
- advanced post-close correcting-entry workflow;
- email-based self-service password recovery;
- mobile/native clients;
- automatic public DNS/TLS/firewall/router configuration;
- native package formats such as MSI/DEB/RPM where a self-contained distribution already satisfies the POC.

## Architectural Future-Proofing Required in POC

Although deferred features are not to be implemented, the POC should avoid designs that unnecessarily prevent:
- PostgreSQL as a future database option;
- AI/RAG/MCP access to clean structured data;
- portable backup/restore;
- richer reporting;
- additional attachment storage backends;
- more advanced deployment packaging.

## Scope-Control Rule

An autonomous implementation agent must not implement Day-2 functionality at the expense of POC acceptance criteria. If a deferred feature appears necessary to satisfy a POC rule, document the dependency and implement only the minimum enabling behavior.

## Benchmark v1.1 POC Scope Additions

Required POC capabilities now explicitly include self-service password change, persistent Light/Dark mode, deterministic first-run initialization including Administrator email, correct initial Administrator bootstrap authorization/list visibility, and full documented Draft Fiscal Year visibility/use. Any prior Day-2 classification of Light/Dark mode is superseded.
