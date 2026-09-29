## What & why
<!-- Change request(s), e.g. CR-016, and a one-line summary -->

## Branch flow
- [ ] feature/* or hotfix/* → **develop**   ·   develop → **test**   ·   test → **main**   (use *Create a merge commit* for develop→test and test→main)

## Checklist
- [ ] Version bumped in `backend/fmpoc/config.py` **and** `frontend/package.json` (first change of a new release)
- [ ] `CHANGELOG.md` section for this version; `docs/upgrade.md` updated if the database changes (new migration)
- [ ] Tests added/updated; CI green
- [ ] For test → main: installed and accepted on the test server
