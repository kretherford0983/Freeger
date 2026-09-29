# Manual verification procedures

Criteria that need a real Windows machine, a desktop session, or two operating systems. Everything else is
covered by automated tests (see acceptance-results.md).

## MV-1 — AC-DEP-001 Windows self-contained build

Preconditions: clean Windows 10/11 x64 machine or VM **without** Python, Node.js, SQLite or Docker installed
(`where python` / `where node` return nothing, or rename them temporarily).

1. Copy `dist/FinancialManagementPOC-windows-x64.zip` (from `bash packaging/build_windows_portable.sh`) to the machine
   and extract it to e.g. `C:\Apps\FinancialManagementPOC-windows-x64`.
   (Alternative: `FinancialManagementPOC-windows-x64-pyinstaller.zip` from `packaging/build_windows.ps1` / CI.)
2. Double-click `FinancialManagementPOC.cmd` (or run it from `cmd.exe`).
3. Expected: console prints `Financial Management POC 1.1.0 - local mode - http://127.0.0.1:8765`; the default browser
   opens on the Initialization Wizard.
4. Complete the wizard; create a Budget Manager, a Draft Fiscal Year, a budget, a Financial Institution and a bank
   account; reveal the account number.
5. Verify `%LOCALAPPDATA%\FinancialManagementPOC\` contains `database\`, `attachments\`, `secrets\`, `logs\`.
6. `netstat -ano | findstr 8765` shows `127.0.0.1:8765 LISTENING` only.

Pass if all steps succeed without installing anything.

## MV-2 — AC-DEP-003 local mode opens the browser

On a desktop Windows or Linux session run the packaged launcher without `--no-browser`.
Expected: the default browser opens `http://127.0.0.1:8765` after `/api/health` responds; the listener is bound to
`127.0.0.1` only (`ss -ltn | grep 8765` on Linux, `netstat` on Windows). Headless environments simply skip the
browser step (the Python `webbrowser` module finds no browser).

## MV-3 — AC-DEP-006 portable encrypted data between operating systems

1. On Windows (MV-1 installation), create a bank account with number `123456789012` and upload an attachment. Stop the app.
2. Copy `%LOCALAPPDATA%\FinancialManagementPOC\` (whole directory) to a Linux machine, e.g. `/srv/fmpoc-data`.
3. On Linux: `./FinancialManagementPOC/FinancialManagementPOC --data-dir /srv/fmpoc-data --no-browser`.
4. Sign in as the Budget Manager → Bank Accounts → **Reveal**: the number `123456789012` is shown; the attachment opens.
5. Repeat in the opposite direction (Linux → Windows).

Negative check: removing `secrets/portable-encryption-key.json` must make startup fail with a clear message
(automated in `test_portable_key_required`).

## MV-4 — Visual review of Light/Dark (supports AC-UI-THEME-003)

`npx playwright test` (frontend) writes `frontend/e2e-screenshots/{light,dark}-*.png` for Dashboard, Fiscal Year
detail, Budgets, Register, Bank Accounts and Entities. Review for legible text, visible status icons/text and
distinguishable Draft/Approved/Rejected row backgrounds.
