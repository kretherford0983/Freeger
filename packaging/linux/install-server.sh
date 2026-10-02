#!/usr/bin/env bash
# Install or upgrade Fundwarden as an always-on systemd service (native, no Docker).
#
#   sudo ./install-server.sh Fundwarden-linux-x64-portable.tar.gz [--port 8765]
#
# Layout:  /opt/fundwarden/releases/<timestamp>/  binaries (replaceable)   /opt/fundwarden/current -> active release
#          /var/lib/fundwarden/                    APP_DATA_DIR: database, attachments, secrets, logs, config.toml
#          /var/backups/fundwarden/                automatic data snapshot taken before every upgrade
# The app listens on 127.0.0.1 only; publish it through Cloudflare Tunnel or a local HTTPS reverse proxy.
#
# 1.6.6 - the application was renamed (before: service "fmpoc", /opt/fmpoc, /var/lib/fmpoc). When this installer
# finds such an installation and no Fundwarden data yet, it MIGRATES it: the old service is stopped and disabled and
# its data directory is COPIED to /var/lib/fundwarden. Nothing of the old installation is changed or removed, so
# going back is "systemctl disable --now fundwarden; systemctl enable --now fmpoc". Remove the old installation by
# hand once you are satisfied (docs/upgrade.md, "Cleanup after the rename").
set -euo pipefail
TARBALL="${1:-}"; shift || true
PORT=""
while [ $# -gt 0 ]; do case "$1" in --port) PORT="$2"; shift 2;; *) echo "unknown option $1"; exit 2;; esac; done
[ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 1; }
[ -f "$TARBALL" ] || { echo "usage: sudo $0 <Fundwarden-linux-x64-portable.tar.gz> [--port N]"; exit 2; }
command -v systemctl >/dev/null || { echo "systemd is required"; exit 1; }

SVC=fundwarden; USER_=fundwarden; OPT=/opt/fundwarden; DATA=/var/lib/fundwarden; BK=/var/backups/fundwarden
OLD_SVC=fmpoc; OLD_OPT=/opt/fmpoc; OLD_DATA=/var/lib/fmpoc; OLD_BK=/var/backups/fmpoc   # names before 1.6.6
STAMP="$(date +%Y%m%d-%H%M%S)"; REL="$OPT/releases/$STAMP"

MIGRATE=0
if [ ! -d "$DATA/database" ] && [ -d "$OLD_DATA/database" ]; then MIGRATE=1; fi
if [ "$MIGRATE" = 0 ] && [ -d "$DATA/database" ] && systemctl is-active --quiet "$OLD_SVC"; then
  echo "Both a Fundwarden installation ($DATA) and a RUNNING old '$OLD_SVC' service exist."
  echo "Decide which one is current first:"
  echo "  keep Fundwarden:        sudo systemctl disable --now $OLD_SVC     (then run this installer again)"
  echo "  migrate the old one again: stop here, move $DATA away, then run this installer again"
  exit 1
fi

id "$USER_" >/dev/null 2>&1 || useradd --system --home-dir "$DATA" --shell /usr/sbin/nologin "$USER_"
install -d -m 0755 "$OPT/releases"

echo "==> unpacking release $STAMP"
install -d -m 0755 "$REL"
tar -xzf "$TARBALL" -C "$REL" --strip-components=1 --no-same-owner
chown -R root:root "$REL"; chmod -R go-w "$REL"
"$REL/fundwarden" --version >/dev/null

if [ "$MIGRATE" = 1 ]; then
  echo "==> found an installation under the old name ($OLD_SVC): migrating it to Fundwarden"
  NEED=$(du -sk "$OLD_DATA" | cut -f1); AVAIL=$(df -Pk "$(dirname "$DATA")" | awk 'NR==2 {print $4}')
  if [ "$AVAIL" -lt $((NEED + NEED / 10 + 10240)) ]; then
    echo "not enough free space in $(dirname "$DATA") to copy $OLD_DATA (needs about $((NEED / 1024 + 10)) MB) - nothing was changed"
    rm -rf "$REL"; exit 1
  fi
  OLD_WAS_ACTIVE=0; systemctl is-active --quiet "$OLD_SVC" && OLD_WAS_ACTIVE=1
  undo_migration() {
    echo "==> migration failed - the old installation is unchanged; putting it back in service"
    rm -rf "$DATA.migrating"
    [ "$OLD_WAS_ACTIVE" = 1 ] && systemctl start "$OLD_SVC" || true
  }
  trap undo_migration ERR
  echo "    stopping $OLD_SVC and copying $OLD_DATA -> $DATA (the old directory is left untouched)"
  systemctl stop "$OLD_SVC" 2>/dev/null || true
  rm -rf "$DATA.migrating"
  [ -d "$DATA" ] && rmdir "$DATA"          # only an empty leftover is acceptable here
  cp -a "$OLD_DATA" "$DATA.migrating"
  diff -rq "$OLD_DATA" "$DATA.migrating" >/dev/null   # every file identical before we switch
  chown -R "$USER_:$USER_" "$DATA.migrating"; chmod 0700 "$DATA.migrating"
  mv "$DATA.migrating" "$DATA"
  trap - ERR
  systemctl disable "$OLD_SVC" >/dev/null 2>&1 || true
elif [ -d "$DATA/database" ]; then
  echo "==> stopping the service and snapshotting data to $BK/$STAMP"
  systemctl stop "$SVC" 2>/dev/null || true
  install -d -m 0700 "$BK"; cp -a "$DATA" "$BK/$STAMP"
fi
install -d -m 0700 -o "$USER_" -g "$USER_" "$DATA"

if [ ! -f "$DATA/config.toml" ]; then
  [ -n "$PORT" ] || PORT=8765
  echo "==> writing $DATA/config.toml"
  cat > "$DATA/config.toml" <<CFG
# Fundwarden - server settings (see docs/configuration.md)
[server]
mode = "server"
host = "127.0.0.1"          # loopback only; Cloudflare Tunnel / reverse proxy connects locally
port = $PORT
secure_cookies = "true"     # browsers reach the app over HTTPS (Cloudflare edge)
trusted_proxies = "127.0.0.1"
CFG
  chown "$USER_:$USER_" "$DATA/config.toml"; chmod 0600 "$DATA/config.toml"
fi
# health check port: --port, else the port of the existing config.toml (never changed by an upgrade), else 8765
if [ -z "$PORT" ]; then
  PORT="$(sed -n 's/^[[:space:]]*port[[:space:]]*=[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$DATA/config.toml" | head -1)"
  [ -n "$PORT" ] || PORT=8765
fi

cat > /etc/systemd/system/$SVC.service <<UNIT
[Unit]
Description=Fundwarden
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_
Group=$USER_
ExecStart=$OPT/current/fundwarden --mode server --no-browser --data-dir $DATA
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
  if [ "$i" = 60 ]; then
    echo " FAILED"; journalctl -u "$SVC" -n 40 --no-pager || true
    if [ "$MIGRATE" = 1 ]; then
      echo "==> Fundwarden did not start after the migration - switching back to the old installation"
      systemctl disable --now "$SVC" >/dev/null 2>&1 || true
      mv "$DATA" "$DATA.failed-migration-$STAMP"
      systemctl enable --now "$OLD_SVC" >/dev/null 2>&1 || true
      echo "    the old service '$OLD_SVC' is running again on its unchanged data; the copy is in $DATA.failed-migration-$STAMP"
    fi
    exit 1
  fi
done
# keep the three newest releases
ls -1dt "$OPT"/releases/* | tail -n +4 | xargs -r rm -rf
"$REL/python/bin/python3" -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:$PORT/api/system/status').read().decode())"
echo "Installed. Service: systemctl status $SVC | logs: journalctl -u $SVC -f | data: $DATA"
echo "Point your tunnel/reverse proxy at http://127.0.0.1:$PORT"
if [ "$MIGRATE" = 1 ]; then
  echo
  echo "MIGRATED from the old name. Your tunnel/reverse proxy needs no change (same port)."
  echo "The old installation was left in place, stopped and disabled, so you can go back:"
  echo "    sudo systemctl disable --now $SVC && sudo systemctl enable --now $OLD_SVC"
fi
if [ -e "$OLD_DATA" ] || [ -e "$OLD_OPT" ] || [ -e "$OLD_BK" ] || [ -e /etc/systemd/system/$OLD_SVC.service ]; then
  echo "NOTE: files of the old installation still exist ($OLD_OPT, $OLD_DATA, $OLD_BK, $OLD_SVC.service)."
  echo "      Remove them when you no longer need them: docs/upgrade.md, \"Cleanup after the rename\"."
fi
