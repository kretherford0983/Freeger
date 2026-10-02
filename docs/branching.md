# Branching, builds and releases

```
 feature/cr-016-...  ─┐
 feature/cr-017-...  ─┼─► develop ──► test ──► main
 hotfix/...  ─────────┼──────────────────────► main  (then merged back into test and develop)
```

| Branch | Purpose | On every push/merge GitHub Actions… | Install with |
|---|---|---|---|
| `feature/*` | one enhancement / change request, branched from `develop` | runs all tests (`ci`) | — |
| `develop` | integration of finished features | runs all tests and builds the packages (workflow-run artifacts, 7 days) | optional, for a quick look |
| `test` | release candidate being tested | tests + packages + **GitHub pre-release** `v<version>-test.<n>` | test server |
| `main` | production | tests + packages + **GitHub release** `v<version>` and git tag | production server |

Packages in every build: `FinancialManagementPOC-linux-x64-portable.tar.gz` (servers), `FinancialManagementPOC-windows-x64.zip`,
`Freedger-<version>-windows-x64.exe` (one file, since 1.5.0), `install.sh` (one-command Linux install, since 1.5.0),
`install-server.sh`, `build-info.json` (version, branch, commit, run) and `SHA256SUMS.txt`. Each package is smoke-tested
(started from a clean environment and checked for the expected version — the Windows .exe and zip on a Windows
runner) before it is published. To try the packages of a feature branch without publishing anything, run the
**build** workflow by hand on that branch (Actions → build → Run workflow).
Workflow-run copies of the packages are kept 7 days (develop) or 1 day (test/main — the GitHub release keeps the
permanent copy), so Actions artifact storage stays well within the GitHub Pro allowance (1 GB).

## Rules enforced by the pipeline (`scripts/check_promotion.sh`)
- Pull requests into **develop** come from `feature/*` or `hotfix/*` (or a back-merge from `test`/`main`).
- Pull requests into **test** come from `develop` (or `hotfix/*`, or a back-merge from `main`).
- Pull requests into **main** come from `test` or `hotfix/*`, **and** the version must not be released yet and must
  have a `## <version>` section in `CHANGELOG.md`.
- The version in `backend/fmpoc/config.py` and `frontend/package.json` must always match.
- A version is released only once; a test pre-release is not created for a version that is already released.

## Day-to-day flow
1. **Start an enhancement** – make sure your local `develop` is current (`git checkout develop && git pull`), then ask
   me to start it. I create `feature/cr-NNN-short-name` from `develop` in the Freedger folder, implement it, run the
   full backend + E2E suite and package build locally, and commit on that branch. (I can't push: pushing needs your
   GitHub credentials.)
2. **Push the feature branch** (Windows terminal in the Freedger folder):
   `git push -u origin feature/cr-NNN-short-name` → the `ci` workflow runs.
3. **Pull request feature → develop** on GitHub; merge when green (squash or merge commit — your choice).
4. **Promote to test**: pull request **develop → test**, merge with *Create a merge commit*. The build publishes a
   pre-release `v<version>-test.N`; install it on the test server with the command in its release notes
   (`curl -fsSL …/releases/download/<tag>/install.sh | sudo bash -s -- --version <tag>`), or as before with
   `sudo bash install-server.sh FinancialManagementPOC-linux-x64-portable.tar.gz`.
5. **Release**: when testing is accepted, pull request **test → main**, merge with *Create a merge commit*. The build
   publishes release `v<version>` (notes = that version's CHANGELOG section) and marks it *latest*. Install it in
   production with `curl -fsSL …/releases/latest/download/install.sh | sudo bash`.
6. After merging on GitHub, update your local branches: `git checkout develop && git pull` (and `test`/`main` when
   needed).

**Versioning (from 1.6.0): `Breaking.Major.Minor`** (same three numbers as before, so tags, pre-releases and the
pipeline are unchanged):
- **Breaking** (1.x → 2.0) — very large changes that may break the app, e.g. moving the data to a different database
  server. Users decide deliberately whether to upgrade.
- **Major** (1.5 → 1.6) — one or more large new features within the current Breaking line.
- **Minor** (1.6.0 → 1.6.1) — fixes, polish and performance; occasionally one planned feature of a Major line is
  released on its own so beta feedback can come in before the next one.

The first feature of a new release bumps the version on its feature branch (e.g. 1.5.0 → 1.6.0) and adds the
CHANGELOG section; later features of the same release add to that section.

**Production releases started with 1.6.5.** Before that (beta) every version existed only as a test pre-release and
fixes simply went into the next version. From 1.6.5 on, `main` is what people run:

**Hotfix** (urgent production fix): branch `hotfix/short-name` from `main`, bump the Minor number (e.g. 1.6.5 → 1.6.6),
pull request into `main`; afterwards pull request `main → test` and `main → develop` so the fix is not lost.

## One-time GitHub settings (Settings tab of the repository)
1. **General → Default branch**: `main` — visitors then see the README and docs of the production release (choose
   `develop` as the base when opening a feature pull request). `Closes #n` in a commit closes the issue when the
   commit reaches `main`, i.e. when the fix is released.
2. **General → Pull Requests**: allow *merge commits* (needed for develop→test→main); squash merging optional.
3. **Rules → Rulesets → New branch ruleset** (or *Branches → Add branch protection rule*), one for `main`, `test` and
   `develop` (target: include those three branches):
   - *Restrict deletions* and *Block force pushes*;
   - *Require a pull request before merging* — required approvals **0** (you are the only reviewer; GitHub does not
     let an author approve their own pull request);
   - *Require status checks to pass* — add **`tests / test`** and **`promotion-rules`** (they appear in the list after
     the first pull request has run the `ci` workflow).
4. **Actions → General → Workflow permissions**: the default *Read repository contents* is fine — the release job
   asks for write access itself.
