# Changelog

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
