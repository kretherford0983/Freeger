# Financial Management POC (Freedger)

Working implementation of the **Financial Management POC Agent-Agnostic Benchmark v1.1** (specification in
[`spec/`](spec/), unchanged). Cash/register and budget-management application with fiscal years, hierarchical
budgets, entities, encrypted bank accounts, continuous registers, split allocations, cross-fiscal-year review,
attachments, void lifecycle, immutable audit trail, role separation, and self-contained Windows/Linux packaging.

| | |
|---|---|
| Frontend | React 18 + TypeScript (Vite build, served by FastAPI; no router/UI libraries) |
| Backend | Python 3.11/3.12, FastAPI, SQLAlchemy 2, Alembic, SQLite |
| Security | Argon2id, server-side sessions (HttpOnly/SameSite=Strict), CSRF tokens, AES-256-GCM + HMAC fingerprint for account numbers, append-only audit (DB triggers), CSP & security headers |
| Tests | 135 backend API tests (AC/CR-ID named) + 11 Playwright E2E UI tests (run against source **and** the packaged Linux builds) |

## Documentation

- [docs/acceptance-results.md](docs/acceptance-results.md) — status and evidence for **every** acceptance criterion
- [docs/implementation-notes.md](docs/implementation-notes.md) — design decisions, specification ambiguities raised, limitations
- [docs/configuration.md](docs/configuration.md) — settings, config file, environment variables, data layout
- [docs/deployment.md](docs/deployment.md) — local/server modes, HTTPS reverse proxy, Docker, data portability
- [docs/security.md](docs/security.md) — security controls and dependency-vulnerability check commands/results
- [docs/manual-verification.md](docs/manual-verification.md) — procedures for criteria that need a real desktop/OS
- [docs/benchmark-results.md](docs/benchmark-results.md) — completed evaluation results template
- [docs/upgrade.md](docs/upgrade.md) — upgrading a Linux server install without touching data/config
- [CHANGELOG.md](CHANGELOG.md)

## Quick start (from source)

```bash
python3 -m venv .venv && . .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements-dev.txt
npm --prefix frontend ci && npm --prefix frontend run build   # emits backend/fmpoc/static
cd backend && python -m fmpoc                          # local mode: http://127.0.0.1:8765, opens browser
```

The first launch shows the **Initialization Wizard** (workspace name, administrator username, email, password,
confirmation). No default credentials exist. The Administrator then creates Financial users (Budget Manager /
Budget User / Register User) and Auditors under **Users**.

Since 1.2.0: **Reports** (printable End of Year Audit PDF with attachments after each transaction; Entity activity
report with CSV), **Transfer…** between register accounts, a searchable entity picker, a "no attachment will be
provided" flag and a Fiscal Year **documentation review** (see CHANGELOG.md).

Useful options: `--mode server --host 0.0.0.0 --port 8765 --data-dir DIR --no-browser` (see configuration docs).

Frontend development with hot reload: run the backend (`python -m fmpoc --no-browser`) and `npm --prefix frontend run dev`
(Vite proxies `/api` to port 8765).

## Tests

```bash
cd backend && python -m pytest                    # 135 API tests incl. security negative tests
cd frontend && npx tsc --noEmit -p . && npm run build
cd frontend && FM_PYTHON=$(which python) npx playwright test                     # E2E vs source
cd frontend && FM_BUNDLE=../dist/FinancialManagementPOC/FinancialManagementPOC npx playwright test   # E2E vs package
bash scripts/security_check.sh                    # pip-audit + npm audit + security tests (AC-SEC-024)
```

## Packaging

| Artifact | Command | Notes |
|---|---|---|
| Linux x86-64 portable (servers, glibc ≥ 2.27) | `bash packaging/build_linux_portable.sh` | → `dist/FinancialManagementPOC-linux-x64-portable.tar.gz`; install with `sudo bash packaging/linux/install-server.sh <tarball>` |
| Linux x86-64 self-contained | `bash packaging/build_linux.sh` | PyInstaller onedir → `dist/FinancialManagementPOC-linux-x64.tar.gz` |
| Windows x86-64 self-contained (portable) | `bash packaging/build_windows_portable.sh` | Runs on any OS; relocatable CPython + win_amd64 wheels → `dist/FinancialManagementPOC-windows-x64.zip`; launch `FinancialManagementPOC.cmd` |
| Windows x86-64 self-contained (PyInstaller) | `pwsh packaging/build_windows.ps1` | Build on Windows → `FinancialManagementPOC.exe` |
| Docker (optional, server) | `docker build -f packaging/docker/Dockerfile -t fmpoc .` | plus `docker-compose.yml` with Caddy HTTPS |
| Docker from bundle (no registry needed) | `bash packaging/docker/build_bundle_image.sh` | used for verification in this run |

CI (`.github/workflows/ci.yml`) runs tests, E2E, dependency audits and builds/smoke-tests Linux and Windows packages.

## Repository layout

```
backend/fmpoc/            FastAPI app (routers/, services/, security/, migrations/, static/ = built UI)
backend/tests/            pytest suite (test names reference AC IDs)
frontend/src/             React + TypeScript UI;  frontend/e2e/  Playwright tests
packaging/                PyInstaller spec, Linux/Windows build scripts, Docker
scripts/                  security_check.sh, run_tests.sh
spec/                     benchmark package (authoritative, unchanged)
docs/                     implementation documentation and acceptance results
```
