# AGENT.md — Canonical Implementation Instructions

## Purpose

You are implementing the Financial Management POC defined by this repository. These instructions are intentionally agent-agnostic and apply to any autonomous or agentic software-engineering system.

## Source of Truth

Before implementation, read this file, `PROMPT.md`, every document under `docs/`, and `evaluation/clarifications.md`.

Authority order for resolving implementation questions:
1. explicit business rules in `docs/03-business-rules.md`;
2. security/permission requirements in `docs/04-security-and-permissions.md`;
3. acceptance criteria in `docs/08-acceptance-criteria.md`;
4. domain/workflow/architecture/database documents;
5. product requirements and roadmap.

If two requirements appear contradictory and the conflict materially affects behavior, do not silently invent a rule. Record the ambiguity clearly in implementation notes and, if the operating environment supports questions, request a clarification. Do not substitute conventional accounting behavior for explicitly documented behavior.

## Implementation Principles

- Implement the POC scope in `docs/09-poc-scope-and-roadmap.md`; do not consume time implementing Day-2 features unless they are needed to satisfy a POC requirement.
- Preserve the specified React/TypeScript + FastAPI/Python + SQLAlchemy/Alembic + SQLite baseline unless a documented requirement explicitly permits a variation.
- Financial calculations, lifecycle rules, validation, authorization, and audit requirements are authoritative on the backend. UI-only enforcement is insufficient.
- No application-managed financial/business record is hard deleted where the specification requires inactivation/void/history preservation.
- Database changes use Alembic migrations. Do not rely on deleting/recreating user databases for upgrades.
- Auditable business mutations and their required audit events are atomic.
- Treat all client input as untrusted and satisfy BR-094 through BR-108 and AC-SEC-009 through AC-SEC-025.
- Do not weaken security, auditability, separation of duties, encryption portability, or historical integrity to simplify implementation.
- Do not store secrets in source control.
- Keep the implementation portable between supported Windows and Linux packaging targets.

## Testing Requirements

- Build automated tests for acceptance criteria wherever practical.
- Reference Acceptance Criterion IDs in test names, metadata, or nearby documentation.
- Include direct backend/API negative tests for security and authorization controls.
- Where a criterion cannot reasonably be automated, provide a reproducible manual verification procedure.
- A UI element existing is not proof of completion when backend state, security, calculations, lifecycle, or audit behavior is involved.

## Delivery Requirements

A complete implementation should include:
- working source code;
- database migrations;
- automated tests;
- build/run instructions;
- native self-contained Windows and Linux build process/artifacts where the execution environment permits artifact production;
- optional Docker server packaging;
- configuration documentation;
- security/dependency check commands;
- implementation notes identifying any unmet or manually verified acceptance criteria;
- an acceptance-criteria results report mapping each criterion to Pass, Fail, Not Implemented, or Manual Verification Required.

## Benchmark Integrity

This repository may be supplied unchanged to multiple AI engineering agents. Do not modify the specification to make your implementation easier. If you need to make an implementation-specific choice not prescribed by the documents, document the choice and rationale without changing the required external behavior.

## Benchmark v1.1 Regression Requirements

Before declaring completion, explicitly verify fresh-install bootstrap, initial Administrator authorization/User List visibility, self-service password change, Light/Dark persistence, and Draft Fiscal Year visibility/detail/Budget/Register behavior. Never infer that `DRAFT` means hidden, unusable, or not found.
