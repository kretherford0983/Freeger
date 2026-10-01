# Upgrading a Linux server install (current release: 1.4.1)

The upgrade replaces only the application binaries. It does **not** modify:

- `/var/lib/fmpoc/config.toml` (only written when it does not exist)
- `/var/lib/fmpoc/secrets/` (portable encryption key), `database/`, `attachments/`, `logs/`

Before switching versions the installer stops the service and copies the whole data directory to
`/var/backups/fmpoc/<timestamp>/`. The previous release stays in `/opt/fmpoc/releases/` for rollback.

| Upgrade | Database change | Rollback |
|---|---|---|
| 1.5.0 → 1.6.0 | migration `0010` — **adds** column `workspace.fundraisers_enabled` (off) and tables `fundraiser`, `fundraiser_budget` | switch binaries **and** restore the pre-upgrade data backup |
| 1.4.1 → 1.5.0 | migration `0009` — **adds** column `app_user.dashboard_layout` (NULL = standard dashboard layout) | switch binaries **and** restore the pre-upgrade data backup |
| 1.3.0 → 1.4.1 | migrations `0006`–`0008` (as below) | switch binaries **and** restore the pre-upgrade data backup |
| 1.4.0 → 1.4.1 | migrations `0006` — **adds** table `signature_template`; `0007` — **adds** column `app_user.dashboard_charts`; `0008` — **adds** tables `user_mfa`, `mfa_recovery_code`, `trusted_device` and column `auth_session.mfa_pending`. **After the upgrade every user of a server install sets up two-step verification at the next sign-in** — see below | switch binaries **and** restore the pre-upgrade data backup |
| 1.3.0 → 1.4.0 | none | switch binaries only |
| 1.2.x → 1.4.0 | migration `0005` (see 1.2.x → 1.3.0) | switch binaries **and** restore the pre-upgrade data backup |
| 1.2.x → 1.3.0 | migration `0005` — **adds** tables `request_key`, `check_number_acknowledgement` and columns on `attachment` (document type, system-generated), `fiscal_year` (approval "no document" mark) and `app_user` (collapsed menu); existing Fiscal Year documents are labelled "Other" | switch binaries **and** restore the pre-upgrade data backup |
| 1.1.x → 1.3.0 | migrations `0003`–`0005` applied in order automatically | restore the pre-upgrade data backup |
| 1.2.0 → 1.2.1 | migration `0004` — **adds** four columns to `transaction_allocation` (per-allocation no-attachment flag, reason, who/when); no existing value is changed or removed | switch binaries **and** restore the pre-upgrade data backup (1.2.0 does not know revision 0004) |
| 1.1.x → 1.2.1 | migrations `0003` + `0004` applied in order automatically | restore the pre-upgrade data backup |
| 1.1.x → 1.2.0 | migration `0003` — **adds** columns to `register_transaction` (transfer link, no-attachment flag); no existing value is changed or removed | switch binaries **and** restore the pre-upgrade data backup (1.1.x cannot open a 0003 database) |
| 1.1.0 → 1.1.1 | none | switch binaries only |

Verified during release testing: upgrading a 1.4.0 server with data to 1.4.1 (installer, simulated systemd) left
`config.toml`, the key and all attachments byte-for-byte identical, kept every row and applied `0006`–`0008`; users
were then asked to set up two-step verification; a backup → restore round trip on the upgraded server worked
(including two-step verification from the backup). Rollback: the 1.4.0 binaries alone refuse the 1.4.1 database
("Can't locate revision"); restoring the installer's data snapshot with the 1.4.0 binaries returned exactly the
pre-upgrade data.
Verified for 1.6.0: a 1.5.0 server with data was upgraded with `install.sh` (test channel): `config.toml`, the key and
the attachment byte-for-byte identical, every row kept, `0010` applied (two new empty tables, module off). Rollback
(previous release + snapshot) started 1.5.0 on the identical data.
Verified for 1.5.0: a 1.4.1 server installation with data (users, accounts, transactions, an attachment) was
upgraded with the one-command `install.sh` from a (local) release: it chose the test pre-release, verified the
checksums, read the port from `config.toml`, snapshotted the data and ran `install-server.sh`. `config.toml`, the key
and the attachment were byte-for-byte identical, every row was kept and `0009` was applied. Rollback (previous
release + the snapshot) started 1.4.1 on the identical data.
Earlier: upgrading a 1.2.1 server with data to 1.3.0 left `config.toml`, the key and all
attachments byte-for-byte identical, kept every row, applied `0005`, labelled the existing Fiscal Year document "Other"
and reported the Audit Signoff as the only new closing requirement.
Earlier: upgrading a 1.2.0 server with data to 1.2.1 left `config.toml`, the key and all
attachments byte-for-byte identical, kept every row and existing no-attachment marks, and applied `0004`.
Earlier: upgrading a 1.1.1 server with data left `config.toml`, the encryption key and
every attachment file byte-for-byte identical, kept all rows, and the audit/entity reports, transfers and
documentation review worked on the pre-existing data.

## Steps

**Since 1.5.0 — one command on the server** (does steps 1–4 below; the data snapshot and rollback copy are the same):
```bash
curl -fsSL https://github.com/kretherford0983/Freeger/releases/download/<tag>/install.sh | sudo bash -s -- --version <tag>
```
(`<tag>` e.g. `v1.5.0-test.14`; after the first production release:
`curl -fsSL https://github.com/kretherford0983/Freeger/releases/latest/download/install.sh | sudo bash`.)
The port of the existing installation is read from `config.toml`. Then continue with *Verify*.

**Manual:**

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
4. Expected output ends with `"version":"1.3.0"` and `Installed.` and names the backup folder
   (`snapshotting data to /var/backups/fmpoc/<timestamp>`). The Cloudflare tunnel needs no change.
5. Verify: sign in, check the collapsible menu («), open a Fiscal Year page (**Fiscal Year documents** section),
   Register → **Fiscal Year reviews** (missing checks), and Reports → **Fiscal Year Close**.
6. **After upgrading to 1.3.0:** open each Fiscal Year that is not closed yet. Documents uploaded earlier are listed
   under *Other documents*; use the drop-down to mark the signoff as **Audit Signoff** and the budget approval as
   **Approval document** (or tick "No approval document"). Closed years are unaffected.

## Rollback

Rolling back from 1.3.0 (or 1.2.1) to an earlier release requires restoring the data snapshot taken by the upgrade, because an older release
cannot open a database migrated by a newer one. **Anything entered after the upgrade is lost**, so export anything you need first.

```bash
sudo systemctl stop fmpoc
ls /opt/fmpoc/releases/ /var/backups/fmpoc/        # previous release + the snapshot taken at upgrade time
sudo ln -sfn /opt/fmpoc/releases/<previous> /opt/fmpoc/current
sudo mv /var/lib/fmpoc /var/lib/fmpoc.failed-upgrade      # keep it until you are sure
sudo cp -a /var/backups/fmpoc/<timestamp> /var/lib/fmpoc
sudo systemctl start fmpoc
```
(Verified during release testing: the previous release starts normally on the restored snapshot. Switching only the
symlink is not enough after a schema change — the older release refuses to start with "Can't locate revision".)
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

## 1.4.1: two-step verification after the upgrade (server installs)

Sessions that were open before the upgrade keep working until they end. At the **next sign-in every user** is asked to
set up an authenticator app (QR code or typed key) and to save 10 recovery codes. Do it yourself first as the
Administrator, with your phone at hand.

If a user loses both the phone and the recovery codes: Users → *Reset two-step* (Administrator, reason required).
If the only Administrator is locked out, on the server:

```
sudo -u fmpoc /opt/fmpoc/current/FinancialManagementPOC reset-mfa --user <username> --data-dir /var/lib/fmpoc
```

(run it as the `fmpoc` service account so file ownership in the data directory does not change). The reset is
recorded in the audit log; the user sets up two-step verification again at the next sign-in.
