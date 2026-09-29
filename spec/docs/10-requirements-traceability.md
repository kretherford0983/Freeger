# 10 — Requirements Traceability

This matrix maps major requirement areas to objective acceptance criteria. Business-rule IDs refer to `03-business-rules.md`. Acceptance IDs refer to `08-acceptance-criteria.md`.

| Requirement Area | Business Rules | Acceptance Criteria |
|---|---|---|
| Fiscal Year naming/status | BR-001–BR-003, BR-011–BR-012 | AC-FY-001, AC-FY-008, AC-FY-009, AC-FY-013 |
| Fiscal Year continuity/overlap | BR-004–BR-010 | AC-FY-002–AC-FY-006 |
| Fiscal Year copy/approval/closure | BR-011–BR-015 | AC-FY-007, AC-FY-009–AC-FY-013 |
| Budget hierarchy/Other | BR-016–BR-020 | AC-BUD-001–AC-BUD-007 |
| Budget overage/lifecycle | BR-021–BR-025 | AC-BUD-008–AC-BUD-011 |
| Entity requirements/duplicates | BR-026–BR-031 | AC-ENT-001–AC-ENT-006 |
| Bank account security/primary | BR-032–BR-039 | AC-BANK-001–AC-BANK-007, AC-SEC-008 |
| Bank account closure | BR-040–BR-041, BR-093 | AC-BANK-008–AC-BANK-011 |
| Continuous register/balances | BR-042–BR-043 | AC-BANK-006, AC-REG-001–AC-REG-002 |
| Allocation/FY classification | BR-044–BR-051 | AC-REG-003–AC-REG-006 |
| Split transactions | BR-052–BR-059 | AC-REG-007–AC-REG-011 |
| Transaction editing/void | BR-060–BR-073 | AC-REG-012–AC-REG-019 |
| Attachments | BR-074–BR-076 | AC-ATT-001–AC-ATT-004, AC-FY-011 |
| Audit integrity | BR-077 and audit rules throughout | AC-AUD-001–AC-AUD-005 |
| Backend authorization | BR-078 | AC-SEC-002–AC-SEC-007 |
| Budget visual state | BR-079–BR-080 | AC-BUD-010–AC-BUD-011 |
| Deployment/security | BR-081–BR-092 | AC-DEP-001–AC-DEP-006, AC-SEC-001, AC-SEC-006, AC-SEC-021–AC-SEC-024 |
| Secure input/database handling | BR-094–BR-099 | AC-SEC-009–AC-SEC-014, AC-SEC-025 |
| File/path/command safety | BR-100–BR-102 | AC-SEC-015–AC-SEC-017, AC-SEC-023, AC-SEC-025 |
| Secrets/errors/logging | BR-103–BR-104 | AC-SEC-018–AC-SEC-019 |
| Security headers/dependencies/defaults/tests | BR-105–BR-108 | AC-SEC-021–AC-SEC-025 |

## Traceability Expectations During Implementation

Each automated test should reference one or more Acceptance Criterion IDs in its test name, metadata, or nearby comments/documentation. If an Acceptance Criterion cannot reasonably be automated, the implementation should provide a reproducible manual verification procedure.

No criterion should be marked complete solely because a UI element exists. Backend enforcement and persisted state must be verified where the requirement concerns security, financial integrity, lifecycle, audit, or calculations.

## Benchmark v1.1 Traceability Additions

| Requirement | Acceptance Criteria |
|---|---|
| BR-INIT-001..004 | AC-INIT-001..008 |
| BR-SEC-SELF-001..002 | AC-AUTH-SELF-001..006 |
| BR-UI-THEME-001..002 | AC-UI-THEME-001..003 |
| BR-FY-VIS-001..005 | AC-FY-VIS-001..011 |

Automated tests should cover these criteria where practical. Draft Fiscal Year coverage must exercise both API behavior and visible UI behavior.
