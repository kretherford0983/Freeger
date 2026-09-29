# Financial Management POC — Agent-Agnostic Benchmark Package v1

This package is the canonical implementation and comparative-testing input for the Financial Management POC. It is intentionally independent of Devin, Claude, GitHub Copilot, or any other agentic software-engineering product.

## Start Here

An implementation agent should receive this entire package unchanged and begin with:
1. `PROMPT.md`
2. `AGENT.md`
3. all files in `docs/`
4. `evaluation/clarifications.md`

## Specification Documents

- `docs/01-product-requirements.md` — product and POC requirements
- `docs/02-domain-model.md` — domain concepts and relationships
- `docs/03-business-rules.md` — authoritative business rules, including secure-coding rules
- `docs/04-security-and-permissions.md` — RBAC, authentication, sensitive-data and secure-coding controls
- `docs/05-ui-and-workflows.md` — screens and operational workflows
- `docs/06-technical-architecture.md` — implementation, deployment, packaging and secure implementation baseline
- `docs/07-database-design.md` — proposed relational design
- `docs/08-acceptance-criteria.md` — objective functional and security verification criteria
- `docs/09-poc-scope-and-roadmap.md` — POC boundary and deferred features
- `docs/10-requirements-traceability.md` — requirements-to-test traceability

## Evaluation

`evaluation/` contains the common comparative-evaluation procedure, adversarial test scenarios, results template, and cross-agent clarification log.

For a fair comparison, each agent should receive the same repository state, canonical prompt/specifications, substantive clarifications, and materially equivalent constraints. Do not give one agent another agent's implementation.

## Version 1 Security Additions

The canonical baseline explicitly requires and tests server-side input validation, parameterized database access, XSS/output-encoding safety, mass-assignment protection, object-level authorization, path-traversal/file-type protections, safe process invocation, sensitive logging/error handling, security headers, dependency vulnerability checks, secure defaults, and automated negative security tests.

## Benchmark v1.1 Changes

This revision hardens requirements discovered during the first implementation run: self-service password changes; Light/Dark mode promoted to POC; first-run wizard requires Administrator email and must correctly bootstrap/list/authorize the initial Administrator; and Draft Fiscal Years are explicitly visible, navigable, budget-capable, and transaction-allocation-capable.

Use `initial_prompt.md` verbatim when starting a benchmark run and supply this package unchanged to each participating agent.
