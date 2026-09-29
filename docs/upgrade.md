# Upgrading a Linux server install (e.g. 1.1.0 → 1.1.1)

The upgrade replaces only the application binaries. It does **not** modify:

- `/var/lib/fmpoc/config.toml` (only written when it does not exist)
- `/var/lib/fmpoc/secrets/` (portable encryption key), `database/`, `attachments/`, `logs/`

Before switching versions the installer stops the service and copies the whole data directory to
`/var/backups/fmpoc/<timestamp>/`. The previous release stays in `/opt/fmpoc/releases/` for rollback.
Version 1.1.1 has no database schema change.

## Steps

1. Copy the new package and installer to the server (from the Freedger folder on your PC):
   ```powershell
   scp dist\FinancialManagementPOC-linux-x64-portable.tar.gz packaging\linux\install-server.sh you@yourserver:~/
   ```
2. (Optional) note the current version: `curl -s http://127.0.0.1:8765/api/system/status`
3. Run the installer — the same command as the first install:
   ```bash
   sudo bash install-server.sh FinancialManagementPOC-linux-x64-portable.tar.gz
   ```
   If you installed on a non-default port, pass the same `--port N` (it only affects the health check; your
   `config.toml` keeps its own port).
4. Expected output ends with `"version":"1.1.1"` and `Installed.` The Cloudflare tunnel needs no change.
5. Verify: sign in, open **Register**, expand a VOID transaction → **Correct date…**.

## Rollback

```bash
sudo systemctl stop fmpoc
ls /opt/fmpoc/releases/                       # pick the previous release directory
sudo ln -sfn /opt/fmpoc/releases/<previous> /opt/fmpoc/current
sudo systemctl start fmpoc
```
Data written by 1.1.1 is compatible with 1.1.0 (no schema change). To also restore data as it was before the upgrade:
`sudo systemctl stop fmpoc && sudo rsync -a --delete /var/backups/fmpoc/<timestamp>/ /var/lib/fmpoc/ && sudo systemctl start fmpoc`.

## Notes

- The installer rewrites `/etc/systemd/system/fmpoc.service` on every run. Put any service customisations in a
  drop-in (`sudo systemctl edit fmpoc`), which is preserved.
- Old backups in `/var/backups/fmpoc/` are not pruned automatically; remove ones you no longer need.
