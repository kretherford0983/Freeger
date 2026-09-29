# Branching, builds and releases

```
 feature/cr-016-...  ─┐
 feature/cr-017-...  ─┼─► develop ──► test ──► main
 hotfix/...  ─────────┼──────────────────────► main  (then merged back into test and develop)
```

| Branch | Purpose | On every push/merge GitHub Actions… | Install with |
|---|---|---|---|
| `feature/*` | one enhancement / change request, branched from `develop` | runs all tests (`ci`) | — |
| `develop` | integration of finished features | runs all tests and builds the packages (workflow-run artifacts, 14 days) | optional, for a quick look |
| `test` | release candidate being tested | tests + packages + **GitHub pre-release** `v<version>-test.<n>` | test server |
| `main` | production | tests + packages + **GitHub release** `v<version>` and git tag | production server |

Packages in every build: `FinancialManagementPOC-linux-x64-portable.tar.gz` (servers), `FinancialManagementPOC-windows-x64.zip`,
`install-server.sh`, `build-info.json` (version, branch, commit, run) and `SHA256SUMS.txt`. Each package is smoke-tested
(started from a clean environment and checked for the expected version) before it is published.

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
   pre-release `v1.4.0-test.N`; download the portable package + `install-server.sh` from it and install on the test
   server exactly as today (`sudo bash install-server.sh FinancialManagementPOC-linux-x64-portable.tar.gz`).
5. **Release**: when testing is accepted, pull request **test → main**, merge with *Create a merge commit*. The build
   publishes release `v1.4.0` (notes = the CHANGELOG section). Install it in production the same way.
6. After merging on GitHub, update your local branches: `git checkout develop && git pull` (and `test`/`main` when
   needed).

**Versioning:** the first feature of a new release bumps the version on its feature branch (e.g. 1.3.0 → 1.4.0) and
adds the CHANGELOG section; later features of the same release add to that section.

**Hotfix** (urgent production fix): branch `hotfix/short-name` from `main`, bump the patch version (e.g. 1.4.1),
pull request into `main`; afterwards pull request `main → test` and `main → develop` so the fix is not lost.

## One-time GitHub settings (Settings tab of the repository)
1. **General → Default branch**: `develop` (new pull requests then target develop by default).
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
