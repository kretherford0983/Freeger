# Comparative Test Scenarios

Use `08-acceptance-criteria.md` as the authoritative test inventory. At minimum, every comparative run should exercise the following high-risk scenarios:

1. Role separation and direct API authorization bypass attempts.
2. Fiscal Year gap and overlap creation.
3. Draft Fiscal Year transaction allocation.
4. Fiscal Year approval and automatic budget locking.
5. Fiscal Year closure with each blocker independently present.
6. Parent/sub-budget Other recalculation including zero hiding/reappearance.
7. Budget overage without transaction rejection.
8. Duplicate Entity creation and Entity Number disambiguation.
9. Register User Financial Institution restrictions.
10. Duplicate encrypted bank-account-number detection.
11. Account-number reveal permission and audit behavior.
12. Bank Account closure with uncleared transactions.
13. Bank Account closure with non-zero balance.
14. Final register transaction bringing account to exactly zero.
15. Cross-FY allocation and review workflow.
16. Split withdrawal and split deposit behavior.
17. Cleared transaction edit confirmation.
18. Wrong-bank-account correction through void/recreate.
19. Zero-dollar created-as-VOID check-accountability record.
20. Closed Fiscal Year immutability.
21. Attachment type/size/multiple-file behavior.
22. Audit rollback if audit persistence fails.
23. Local Windows/Linux self-contained startup.
24. Portable encrypted-data migration between supported OS installations where test infrastructure permits.


## Security Adversarial Scenarios

### S-SEC-01 — Injection attempts
Exercise representative text/search/filter inputs with SQL-injection strings and confirm no query manipulation, authorization bypass, or raw SQL disclosure.

### S-SEC-02 — Stored/reflected browser payloads
Persist HTML/script-shaped input in names/descriptions/notes and verify it remains inert wherever rendered.

### S-SEC-03 — Direct API privilege manipulation
Bypass the UI and attempt unauthorized role operations, Financial Institution edits, immutable Bank Account reassignment, protected field mass assignment, and object-ID substitution. Confirm backend rejection.

### S-SEC-04 — Hostile attachment metadata/content
Test path-traversal filenames, forged MIME types, executable content renamed to permitted extensions, and >5 MB uploads. Confirm safe rejection/storage behavior.

### S-SEC-05 — Session/CSRF/error/log hygiene
Verify CSRF enforcement, safe errors, absence of secrets from logs/audit data, secure session behavior, and security response headers.

### S-SEC-06 — Build/dependency posture
Run the documented dependency-vulnerability checks and verify packaged builds do not ship default credentials or debug consoles.

## Benchmark v1.1 Regression Scenarios

- Fresh install: verify wizard fields, bootstrap Administrator, User List visibility, Admin access, and financial-module denial.
- Draft Fiscal Year: create it without approval, open detail, find it in Budget selectors, create a budget, and create a valid Register allocation against it.
- Password: change own password, verify old/new credentials, other-session invalidation, and safe audit.
- Theme: switch Light/Dark, log out/in, and verify persistence and core-screen usability.
