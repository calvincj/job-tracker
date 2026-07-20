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

- Cleantech startups (Fervo, Form Energy, Lilac, Redwood): free public ATS APIs,
  clean and reliable.
- Big firms on Workday (many utilities, some consultancies, env. consultants):
  supported, but each needs host/tenant/site filled in once. See PROJECT.md.
- Bespoke systems (McKinsey, BCG, Bloomberg, etc.): no clean feed. Covered by the
  optional Adzuna broad net plus a bookmarked careers URL.

## Files

```
config/companies.yaml   your firms, categorized
config/filters.yaml     keywords, cities, role types
src/tracker.py          entry point
src/ats/                one client per ATS
src/discover.py         slug resolver
data/digest.md          latest morning digest (generated)
data/new_jobs.csv       running log of everything surfaced (generated)
.github/workflows/      the daily cron
PROJECT.md              full build brief for Claude Code
```
# job-tracker
