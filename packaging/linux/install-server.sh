#!/usr/bin/env bash
# Install or upgrade the Financial Management POC as an always-on systemd service (native, no Docker).
#
#   sudo ./install-server.sh FinancialManagementPOC-linux-x64-portable.tar.gz [--port 8765]
#
# Layout:  /opt/fmpoc/releases/<timestamp>/  binaries (replaceable)   /opt/fmpoc/current -> active release
#          /var/lib/fmpoc/                    APP_DATA_DIR: database, attachments, secrets, logs, config.toml
#          /var/backups/fmpoc/                automatic data snapshot taken before every upgrade
# The app listens on 127.0.0.1 only; publish it through Cloudflare Tunnel or a local HTTPS reverse proxy.
set -euo pipefail
TARBALL="${1:-}"; shift || true
PORT=8765
while [ $# -gt 0 ]; do case "$1" in --port) PORT="$2"; shift 2;; *) echo "unknown option $1"; exit 2;; esac; done
[ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 1; }
[ -f "$TARBALL" ] || { echo "usage: sudo $0 <FinancialManagementPOC-linux-x64-portable.tar.gz> [--port N]"; exit 2; }
command -v systemctl >/dev/null || { echo "systemd is required"; exit 1; }

SVC=fmpoc; USER_=fmpoc; OPT=/opt/fmpoc; DATA=/var/lib/fmpoc; BK=/var/backups/fmpoc
STAMP="$(date +%Y%m%d-%H%M%S)"; REL="$OPT/releases/$STAMP"

id "$USER_" >/dev/null 2>&1 || useradd --system --home-dir "$DATA" --shell /usr/sbin/nologin "$USER_"
install -d -m 0755 "$OPT/releases"
install -d -m 0700 -o "$USER_" -g "$USER_" "$DATA"

echo "==> unpacking release $STAMP"
install -d -m 0755 "$REL"
tar -xzf "$TARBALL" -C "$REL" --strip-components=1 --no-same-owner
chown -R root:root "$REL"; chmod -R go-w "$REL"
"$REL/FinancialManagementPOC" --version >/dev/null

if systemctl is-active --quiet "$SVC"; then
  echo "==> stopping running service and snapshotting data to $BK/$STAMP"
  systemctl stop "$SVC"
  install -d -m 0700 "$BK"; cp -a "$DATA" "$BK/$STAMP"
fi

if [ ! -f "$DATA/config.toml" ]; then
  echo "==> writing $DATA/config.toml"
  cat > "$DATA/config.toml" <<CFG
# Financial Management POC - server settings (see docs/configuration.md)
[server]
mode = "server"
host = "127.0.0.1"          # loopback only; Cloudflare Tunnel / reverse proxy connects locally
port = $PORT
secure_cookies = "true"     # browsers reach the app over HTTPS (Cloudflare edge)
trusted_proxies = "127.0.0.1"
CFG
  chown "$USER_:$USER_" "$DATA/config.toml"; chmod 0600 "$DATA/config.toml"
fi

cat > /etc/systemd/system/$SVC.service <<UNIT
[Unit]
Description=Financial Management POC
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_
Group=$USER_
ExecStart=$OPT/current/FinancialManagementPOC --mode server --no-browser --data-dir $DATA
Restart=on-failure
RestartSec=3
UMask=0077
Environment=PYTHONDONTWRITEBYTECODE=1
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=$DATA
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictNamespaces=true
RestrictSUIDSGID=true
LockPersonality=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
CapabilityBoundingSet=

[Install]
WantedBy=multi-user.target
UNIT

ln -sfn "$REL" "$OPT/current"
systemctl daemon-reload
systemctl enable --now "$SVC" >/dev/null
systemctl restart "$SVC"

echo -n "==> waiting for health"
for i in $(seq 1 60); do
  if "$REL/python/bin/python3" -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:$PORT/api/health', timeout=2)" 2>/dev/null; then echo " OK"; break; fi
  echo -n "."; sleep 1
  [ "$i" = 60 ] && { echo " FAILED"; journalctl -u "$SVC" -n 40 --no-pager; exit 1; }
done
# keep the three newest releases
ls -1dt "$OPT"/releases/* | tail -n +4 | xargs -r rm -rf
"$REL/python/bin/python3" -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:$PORT/api/system/status').read().decode())"
echo "Installed. Service: systemctl status $SVC | logs: journalctl -u $SVC -f | data: $DATA"
echo "Point your tunnel/reverse proxy at http://127.0.0.1:$PORT"
