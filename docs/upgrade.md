# Upgrading a Linux server install (current release: 1.2.0)

The upgrade replaces only the application binaries. It does **not** modify:

- `/var/lib/fmpoc/config.toml` (only written when it does not exist)
- `/var/lib/fmpoc/secrets/` (portable encryption key), `database/`, `attachments/`, `logs/`

Before switching versions the installer stops the service and copies the whole data directory to
`/var/backups/fmpoc/<timestamp>/`. The previous release stays in `/opt/fmpoc/releases/` for rollback.

| Upgrade | Database change | Rollback |
|---|---|---|
| 1.1.x → 1.2.0 | migration `0003` — **adds** columns to `register_transaction` (transfer link, no-attachment flag); no existing value is changed or removed | switch binaries **and** restore the pre-upgrade data backup (1.1.x cannot open a 0003 database) |
| 1.1.0 → 1.1.1 | none | switch binaries only |

Verified during release testing: upgrading a 1.1.1 server with data left `config.toml`, the encryption key and
every attachment file byte-for-byte identical, kept all rows, and the audit/entity reports, transfers and
documentation review worked on the pre-existing data.

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
4. Expected output ends with `"version":"1.2.0"` and `Installed.` and names the backup folder
   (`snapshotting data to /var/backups/fmpoc/<timestamp>`). The Cloudflare tunnel needs no change.
5. Verify: sign in, check the new **Reports** menu item, the **Transfer…** button in the Register and the
   **Documentation review** section on a Fiscal Year page.

## Rollback

Rolling back from 1.2.0 to 1.1.x requires restoring the data snapshot taken by the upgrade, because 1.1.x cannot
open a database migrated to 1.2.0. **Anything entered after the upgrade is lost**, so export anything you need first.

```bash
sudo systemctl stop fmpoc
ls /opt/fmpoc/releases/ /var/backups/fmpoc/        # previous release + the snapshot taken at upgrade time
sudo ln -sfn /opt/fmpoc/releases/<previous> /opt/fmpoc/current
sudo rsync -a --delete /var/backups/fmpoc/<timestamp>/ /var/lib/fmpoc/
sudo systemctl start fmpoc
```
(Verified during release testing: 1.1.1 starts normally on the restored snapshot.)
For 1.1.1 → 1.1.0 (no schema change) switching the symlink alone is enough.

## Notes

- The installer rewrites `/etc/systemd/system/fmpoc.service` on every run. Put any service customisations in a
  drop-in (`sudo systemctl edit fmpoc`), which is preserved.
- Old backups in `/var/backups/fmpoc/` are not pruned automatically; remove ones you no longer need.

## Windows (local install)

Data lives in `%LOCALAPPDATA%\FinancialManagementPOC` and is separate from the program folder.

1. Close the running console window (Ctrl+C) so the app is stopped.
2. Copy `%LOCALAPPDATA%\FinancialManagementPOC` somewhere safe (backup).
3. Unzip the new `FinancialManagementPOC-windows-x64.zip` into a **new** folder (keep the old one for rollback).
4. Run `FinancialManagementPOC.cmd` from the new folder. The database is migrated automatically on start.

To roll back: stop the app, restore the backed-up data folder, and run the old program folder.
