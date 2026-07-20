# Job Tracker

A personal, free, self-running tracker for energy / clean-tech / consulting roles.
Checks a curated set of firms every morning and writes a short digest of new
postings, split into full-time, internship, and remote/San Diego tracks.

## Quick start

1. Push this folder to a new GitHub repo (public repo = free Actions minutes).
2. Open it in Claude Code and say: **"Read PROJECT.md and work through the tasks."**
   That resolves the firm slugs and finishes wiring.
3. Enable the daily run: the workflow in `.github/workflows/daily.yml` runs on a
   cron and commits `data/digest.md` each morning. Trigger a first run manually
   from the repo's Actions tab (workflow_dispatch).
4. Each morning, open `data/digest.md` on your phone via the GitHub app and apply.

## Run it locally

```
pip install -r requirements.txt
python -m src.tracker
cat data/digest.md
```

## Resolve a company's ATS slug

```
python -m src.discover "Fervo Energy"
```

Prints which of Greenhouse / Lever / Ashby responds, and the open-job count.
Update `config/companies.yaml` with the result.

## Tuning what you see

Edit `config/filters.yaml`:
- `keywords_any` - a title must contain one of these
- `locations_any` - a location must contain one of these (remote always allowed)
- `exclude_title` - senior/leadership terms to drop
- `role_types` - how roles get grouped in the digest

Edit `config/companies.yaml` to add or remove firms.

## How firms map to sources

- Cleantech startups (Redwood, Nexamp, Form Energy): free public ATS APIs
  (Greenhouse/Ashby), clean and reliable.
- Firms on Workday (Duke Energy, Baker Tilly, ICF, Guidehouse): supported, each
  needs host/tenant/site filled in once. See PROJECT.md.
- Bespoke systems (McKinsey, Fervo, Qcells, SWCA, Bloomberg, etc.): no clean
  feed. Covered by the optional Adzuna broad net plus a bookmarked careers URL
  (see `data/manual_links.md`, regenerated each run).

## Optional: Adzuna broad net

Catches postings from the bespoke/manual firms. Free tier.
1. Register at https://developer.adzuna.com for an app_id + app_key.
2. Add them as GitHub repo secrets: `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`.
3. `adzuna.enabled` is already `true` in `filters.yaml` - it just no-ops until
   the two secrets exist (locally or in Actions).

## Optional: email delivery

Off by default. To get the digest emailed instead of just reading it on
GitHub:
1. Generate a Gmail app password: https://myaccount.google.com/apppasswords
2. Add repo secrets: `GMAIL_USER`, `GMAIL_APP_PASSWORD`, and optionally
   `DIGEST_TO_EMAIL` (defaults to `GMAIL_USER`).
3. Set `delivery.email.enabled: true` in `config/filters.yaml`.

See `src/notify.py` for details. A failed send never breaks the run.

## Files

```
config/companies.yaml   your firms, categorized
config/filters.yaml     keywords, cities, role types, adzuna/email flags
src/tracker.py          entry point
src/ats/                one client per ATS
src/discover.py         slug resolver
src/notify.py           optional email delivery
data/digest.md          latest morning digest (generated)
data/new_jobs.csv       running log of everything surfaced (generated)
data/manual_links.md    bookmarks for firms with no clean ATS feed (generated)
.github/workflows/      the daily cron
PROJECT.md              full build brief for Claude Code
```
# job-tracker
