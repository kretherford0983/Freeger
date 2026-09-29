# Agent-Agnostic Comparative Evaluation Procedure

## Purpose

This project may be used to compare autonomous or agentic software-engineering systems. The evaluation process must avoid giving one system materially different product requirements than another.

## Canonical Inputs

Each evaluated system should receive:
- the same starting repository state;
- the same canonical `PROMPT.md` when finalized;
- the same `AGENT.md` when finalized;
- the same `/docs` specification set;
- the same evaluation constraints where the platform permits them.

Do not provide one system with another system's implementation.

## Clarifications

If an agent asks a substantive requirements question and a human supplies an answer, record that answer in `clarifications.md`. For a fair comparison, make the same clarification available to subsequent/parallel systems.

A clarification should resolve ambiguity, not introduce agent-specific requirements.

## Evidence Collection

Collect at least:
- repository commit/hash or archive;
- agent/system name and model/version where known;
- run date;
- elapsed wall-clock time where measurable;
- human interventions/clarifications;
- build results;
- automated test results;
- acceptance-criteria results;
- Windows/Linux packaging results;
- security/RBAC test results;
- known failures or incomplete areas.

## Evaluation Principle

Prefer objective pass/fail evidence over subjective impressions. Human review may assess UX, accessibility, maintainability, code organization and documentation, but should be recorded separately from objective acceptance results.

The evaluation framework records evidence; it does not prescribe a political-style ranking, weighted score, or predetermined winner.


## Security Evaluation

Security acceptance criteria are part of the objective benchmark. Evaluators should execute the documented adversarial scenarios against the running application/API rather than infer safety from source appearance or hidden UI controls. Capture commands, requests, test output, and relevant sanitized logs as evidence.

Dependency scanners may report ecosystem findings that change over time. Record the tool/version/date and distinguish exploitable/material findings from informational or transitive findings; do not silently waive failures.
