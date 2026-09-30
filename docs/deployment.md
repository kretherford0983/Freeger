# Deployment

The same application and data model serve both **local** and **server** use on Windows and Linux (BR-082).
Native packages need no separately installed Python, Node.js, SQLite, Docker or database server (BR-083).

## Local installation (single user, loopback)

- **Windows**: unzip `FinancialManagementPOC-windows-x64.zip` anywhere (e.g. `%LOCALAPPDATA%\Programs`), double-click
  `FinancialManagementPOC.cmd`. (PyInstaller variant: run `FinancialManagementPOC.exe`.)
- **Linux**: `tar xzf FinancialManagementPOC-linux-x64.tar.gz && ./FinancialManagementPOC/FinancialManagementPOC`

Startup applies pending Alembic migrations, binds to `127.0.0.1:8765`, waits for `/api/health`, and opens the
default browser when a desktop session is available. Plain HTTP is acceptable because traffic stays on loopback.

> **Data protection:** create encrypted backups regularly (System/About → Backup / Restore, since 1.4.1 — see
> docs/backup-restore.md) and keep them off this machine together with their passphrase.

## Server installation (multiple users)

```bash
FinancialManagementPOC --mode server --host 127.0.0.1 --port 8765 --no-browser     # behind a local reverse proxy
```

Authenticated network use must be served over HTTPS (BR-090). The application does not obtain certificates;
terminate TLS in a reverse proxy and set `FM_SECURE_COOKIES=true`, `FM_HSTS=true`, and `FM_TRUSTED_PROXIES` to the
proxy address. Binding to a network interface without `secure_cookies=true` prints a prominent
**SECURITY WARNING** at startup and shows a banner in the UI; it is never represented as secure.

### Caddy
```
finance.example.org {
    reverse_proxy 127.0.0.1:8765
}
```
### nginx
```nginx
server {
    listen 443 ssl http2;
    server_name finance.example.org;
    ssl_certificate     /etc/ssl/finance.crt;
    ssl_certificate_key /etc/ssl/finance.key;
    client_max_body_size 6m;
    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```
### Apache
```apache
<VirtualHost *:443>
  ServerName finance.example.org
  SSLEngine on
  SSLCertificateFile /etc/ssl/finance.crt
  SSLCertificateKeyFile /etc/ssl/finance.key
  ProxyPreserveHost On
  RequestHeader set X-Forwarded-Proto "https"
  ProxyPass / http://127.0.0.1:8765/
  ProxyPassReverse / http://127.0.0.1:8765/
</VirtualHost>
```

Run as a service: systemd unit (`ExecStart=/opt/fmpoc/FinancialManagementPOC --mode server --no-browser`,
`Environment=FM_DATA_DIR=/var/lib/fmpoc`, dedicated user) or on Windows with Task Scheduler/NSSM running
`FinancialManagementPOC-Server.cmd`. Run a single application process per data directory (SQLite + in-process
login rate limiter).

## Docker (optional)

```bash
docker build -f packaging/docker/Dockerfile -t fmpoc:1.1.0 .
docker run -d -p 127.0.0.1:8765:8765 -v fmpoc-data:/data fmpoc:1.1.0
# or with automatic HTTPS:
docker compose -f packaging/docker/docker-compose.yml up -d     # edit Caddyfile host name first
```
Where a registry is unavailable, `packaging/docker/build_bundle_image.sh` builds an image from the self-contained
Linux bundle (this path was built and run during verification).

## Upgrades

Stop the application, replace the binaries, start it again. Alembic migrations run automatically; databases are
never dropped or recreated.

## Moving data between machines / operating systems (AC-DEP-006)

1. Stop the application.
2. Copy the whole application data directory (`database/`, `attachments/`, `secrets/`, optional `config.toml`).
3. Install a compatible or newer version on the target (Windows or Linux) and point `FM_DATA_DIR`/`--data-dir` at the copy.
4. Start: migrations run; encrypted account numbers decrypt with the portable key (plain JSON key file, no OS keystore).

On Windows, keep the data directory under the user profile (default `%LOCALAPPDATA%`) or restrict its ACL to the
service account, because POSIX `chmod 600` is not meaningful there.
