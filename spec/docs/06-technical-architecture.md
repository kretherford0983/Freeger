# 06 --- Technical Architecture and Packaging

## 1. Technical Baseline

-   Frontend: React + TypeScript
-   Backend: Python + FastAPI
-   ORM: SQLAlchemy
-   Schema migrations: Alembic
-   POC database: SQLite
-   Attachments: filesystem
-   Authentication: secure server-side sessions
-   Deployment: self-contained Windows and Linux builds; optional Docker
    server deployment

## 2. Architecture

React communicates with FastAPI using same-origin HTTP(S). FastAPI owns
all authoritative authorization, validation, financial calculations,
lifecycle rules, audit creation, and file validation.

React may provide immediate UX validation but is never the authority for
financial or security rules.

Production builds serve the compiled React assets from the Python
application so only one application port is required.

## 3. Database

SQLite is application-managed and requires no separate database server.

Remote clients never directly access the SQLite file. In server mode:
Browser -\> HTTP(S) -\> FastAPI -\> SQLite on server-local storage.

SQLAlchemy is used to avoid unnecessary SQLite-specific coupling and
preserve a future PostgreSQL path.

Alembic migrations are mandatory for schema evolution. Production
upgrades must not rely on deleting/recreating the database.

## 4. Persistent Data Layout

Use an abstract configurable application data directory:

`APP_DATA_DIR/` - `database/` - `attachments/` - `secrets/` - `logs/` -
recovery-relevant configuration

Application binaries are replaceable; application data is persistent and
portable.

Typical locations may vary by operating system, but application code
must not depend on a Windows-specific path.

## 5. Attachments

Files are stored outside SQLite. Database metadata includes: -
attachment ID; - original filename; - generated storage filename; - MIME
type; - size; - uploader; - upload timestamp; - owning object/reference.

Use generated storage names rather than user filenames. Validate actual
file type/content in addition to extension.

## 6. Sensitive Data Encryption

Full bank account numbers are encrypted at the application layer using a
standard authenticated-encryption construction.

The encryption key: - is stored separately from SQLite; - is portable
across Windows and Linux; - is not bound to an OS-specific keystore; -
must migrate with the database for encrypted values to remain
recoverable; - is protected by restrictive filesystem
permissions/ACLs; - never appears in logs.

Store: - encrypted account number; - keyed one-way fingerprint for
uniqueness comparison; - last-four/display-supporting data as required.

Do not compare randomized ciphertext for uniqueness.

Audit snapshots must sanitize sensitive fields.

## 7. Packaging

The same codebase supports local and server use on Windows and Linux.

### Native Distribution

POC target: - self-contained Windows x86-64 build; - self-contained
Linux x86-64 build.

Target users must not be required to separately install: - Python; -
Node.js; - SQLite; - Docker; - a database service.

Separate OS-specific build jobs are acceptable.

### Local Mode

-   bind only to loopback by default;
-   start FastAPI;
-   apply pending migrations;
-   wait for health endpoint;
-   open default browser where desktop environment permits.

Local mode may use HTTP because traffic remains on loopback.

### Server Mode

-   configurable network binding;
-   same application and database model;
-   remote users access via browser;
-   HTTPS is expected for authenticated production network use.

### Docker

Provide optional server container support. Docker is not a prerequisite
for native local or server installations.

## 8. HTTPS

The application is not responsible for obtaining public TLS
certificates.

Recommended production server topology: Browser -\> HTTPS reverse proxy
-\> FastAPI.

Document compatible reverse-proxy approaches such as Caddy, nginx,
Apache, or existing organizational infrastructure.

Plain HTTP network deployment may be allowed for controlled testing or
TLS termination elsewhere, but must produce a prominent security warning
and must not be represented as secure.

Proxy-header trust must be explicitly configured.

## 9. Authentication and Sessions

Use server-side sessions and HttpOnly cookies.

Requirements: - secure password hashing, preferably Argon2id; - session
rotation on login; - server-side invalidation on logout; - authorization
rechecked server-side; - CSRF protection for state-changing requests; -
basic failed-login rate limiting; - Secure cookie flag under HTTPS; - no
auth tokens in browser localStorage.

No POC `remember me` requirement.

## 10. First Run

On an uninitialized installation: 1. create Workspace; 2. create initial
Administrator; 3. generate portable application encryption key; 4. seed
roles/permissions; 5. seed hidden Multiple entity and other required
system records; 6. complete login.

The initial Administrator remains subject to separation of duties and
cannot manage financial data.

## 11. Configuration

Support a small human-readable configuration file plus
environment-variable overrides for infrastructure deployments.

Suggested precedence: 1. built-in defaults; 2. config file; 3.
environment variables.

Secrets are not stored casually in the general-purpose configuration
file.

## 12. Portability

Moving application data from Windows local to Linux server, or vice
versa, must be architecturally possible by transferring the persistent
data set while the application is stopped, installing a compatible/newer
application version, running migrations, and starting the application.

Built-in Backup/Restore is deferred, but the architecture must not make
later portable backup/restore impractical.

## 13. Future Database Option

PostgreSQL is a future deployment option if concurrent-write scale
exceeds the practical SQLite deployment profile. The POC does not
require PostgreSQL.


## 14. Secure Implementation Baseline

FastAPI/Pydantic request models are used as explicit input contracts. Protected or derived model fields are not accepted merely because corresponding database columns exist. SQLAlchemy query construction must retain parameter binding, with allowlists for user-selectable structural query elements such as sort fields.

React must use normal escaped rendering for user-controlled values. Avoid `dangerouslySetInnerHTML` or equivalent raw markup for financial/user content.

File upload handling must generate storage names, canonicalize/control all storage paths server-side, inspect content/type, enforce size limits before persistence, and keep attachments outside executable/static application code paths.

Packaged production builds run with framework debug/development features disabled. Server logs and exception handlers redact sensitive values.

CI/development documentation must include repeatable dependency-vulnerability checks for both Python and JavaScript dependency sets, along with automated negative tests for authorization, request validation, injection resistance, unsafe file handling, and CSRF/session controls.

## Benchmark v1.1 Bootstrap and Preference Requirements

First-run detection must use required bootstrap state, not merely the existence of a SQLite file. An empty or partially seeded database must not suppress initialization.

Bootstrap must create the initial Administrator and role assignment coherently so authorization works on first login.

Light/Dark preference must persist beyond ephemeral React component state.
