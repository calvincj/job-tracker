# PROJECT.md - Build brief for Claude Code

Read this whole file first. It is the spec. The goal is a personal job tracker
that runs itself every morning and hands me a short list of new roles to apply
to, for free, with no manual polling.

## Who this is for and what it must do

I am an undergrad (graduating June 2027) targeting energy policy and clean-tech
roles, plus consulting, think tanks, econ, and supply-chain work. Three tracks
matter, and the digest must separate them:

1. Full-time / new-grad roles starting around June 2027
2. Internships (summer 2027 or later)
3. Remote or San Diego roles workable during the school year (2026-2027)

The pain being solved: I miss postings because I don't know when they open, and
applying early matters. So the one job that matters most is catching NEW roles
the day they appear at a curated set of firms.

Preferences that should show up in any docs or output you write: no em dashes,
tight clipped bullets over full sentences, lead with the framing before detail,
punchy and analytical over academic.

## What is already built (do not rebuild, extend)

A working scaffold is in place:

- `src/ats/greenhouse.py`, `lever.py`, `ashby.py` - free public JSON APIs, no
  auth. These work now for any company on those systems.
- `src/ats/workday.py` - client for Workday sites; needs per-company host/tenant/
  site values in config.
- `src/ats/adzuna.py` - optional broad-net aggregator (free key) for firms with
  no clean ATS API.
- `src/filtering.py` - keyword + location gate, role-type tagging, remote flag.
- `src/store.py` - tracks seen jobs, computes what is new since last run, prunes
  stale entries so reopened roles re-trigger.
- `src/report.py` - writes `data/digest.md` (grouped by the 3 tracks) and appends
  `data/new_jobs.csv`.
- `src/discover.py` - probes Greenhouse/Lever/Ashby to resolve a company's slug.
- `src/tracker.py` - orchestrates everything. Entry point: `python -m src.tracker`.
- `config/companies.yaml` - my 34 firms, categorized, with best-guess ATS + slugs.
- `config/filters.yaml` - keywords, target cities, role types, excludes.
- `.github/workflows/daily.yml` - daily cron on GitHub Actions, commits results.

## Your job: finish it and make every firm resolve

The scaffold runs, but most slugs are guesses and many firms are marked `manual`.
Work through these tasks in order. Test as you go.

### Task 1 - Verify it runs
`pip install -r requirements.txt` then `python -m src.tracker`. Fix any runtime
errors. A clean first run will show mostly errors for unverified slugs; that is
expected. Confirm the pipeline itself works end to end and writes a digest.

### Task 2 - Resolve the Greenhouse/Lever/Ashby firms
For every company in `companies.yaml` with `ats: greenhouse|lever|ashby`, confirm
the slug:
```
python -m src.discover "Fervo Energy"
```
It prints the ATS and slug that actually respond, with the open-job count. Update
the yaml with the confirmed `ats` and `slug`. If discover finds a company on a
different ATS than guessed, switch it. If it finds nothing, the firm is Workday
or bespoke; move it to Task 3 or 4.

### Task 3 - Resolve the Workday firms
Workday needs three values per company. Find them in ~10 seconds:
1. Open the firm's careers page and click into the job-search view.
2. The URL looks like `https://COMPANY.wdN.myworkdayjobs.com/en-US/SITE/...`.
3. `host` = the full `COMPANY.wdN.myworkdayjobs.com`, `tenant` = `COMPANY`,
   `site` = the `SITE` path segment (case-sensitive).
4. Verify with a quick POST to
   `https://{host}/wday/cxs/{tenant}/{site}/jobs` with body
   `{"appliedFacets":{},"limit":20,"offset":0,"searchText":""}`. A JSON body with
   `jobPostings` means it works. Update the `workday` block in the yaml.

Note: some firms wrap Workday in Cloudflare or use a custom domain (e.g.
`careers.company.com` that redirects). If the cxs endpoint 403s, leave the firm
as `manual` and rely on the Adzuna net.

### Task 4 - Handle the bespoke `manual` firms
Big consultancies (McKinsey, BCG, Bain, PwC, EY), some utilities, and market-
intel shops (Bloomberg, Wood Mackenzie) run custom systems with no clean public
feed. Do NOT try to scrape each one; that is brittle and breaks constantly.
Instead:
- Wire up Adzuna (Task 5) as the broad net. It searches the whole US market by
  keyword and the tracker keeps only hits whose employer matches a `manual` firm.
- Leave `careers_url` on each so I have a one-click bookmark for anything Adzuna
  misses. Optionally generate `data/manual_links.md`, a static list of those
  bookmarks grouped by category, so I can eyeball them weekly.

### Task 5 - Wire the Adzuna broad net (optional but recommended)
1. Register at https://developer.adzuna.com for a free app_id + app_key.
2. Add them as GitHub repo secrets: Settings > Secrets and variables > Actions >
   `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`.
3. Set `adzuna.enabled: true` in `filters.yaml`. Tune the queries.
4. Test locally by exporting the two env vars and running the tracker.

### Task 6 - Delivery (optional)
The digest is committed to the repo each morning, readable on GitHub mobile. If I
want it pushed to me instead, add one of:
- Email: a small SMTP step in `daily.yml` that sends `data/digest.md`. Gmail app
  password stored as a secret is the simplest free route.
- Or a GitHub issue created each run with the digest body, so I get a phone
  notification via the GitHub app.
Pick email; implement it behind a config flag so it is easy to turn off.

### Task 7 - Tune and document
- Run it a few times, eyeball the digest, and tighten `filters.yaml` if it is too
  noisy or too strict (the `exclude_title` list is a common over-filter; "ii"
  and "lead" can catch false positives).
- Update `README.md` with anything that changed.

## Commit style (do this for every commit you make)

- Do NOT add any attribution trailer. No "Generated with Claude Code", no
  "Co-Authored-By: Claude", nothing. Keep commits clean.
- Write short, lowercase, casual messages like a tired college student: "update",
  "fix slug", "workday stuff", "ok that works", "more firms". Not conventional-
  commits, not sentences.
- CLAUDE.md and .claude/ are gitignored. Leave them out of every commit.

## Coverage: the whole point, so get this right

Good coverage means catching new roles the day they open at the firms I care
about. It breaks down into three levers. Push all three.

1. Source reach (biggest lever). Every firm still marked `manual` is a blind spot
   unless the Adzuna net happens to index it. Your Task 2-4 work converts firms
   to real ATS pulls, and every conversion turns a blind spot into total coverage
   of that firm. Prioritize converting `manual` firms over everything else.
2. Poll latency. The workflow already polls every 6 hours and the digest shows a
   rolling ~30h window (`digest_lookback_hours`), so a role that opens and closes
   overnight still shows up in the morning read. If I later want tighter latency,
   drop the cron to every 3 hours; it stays inside free Actions limits.
3. Filter recall (silent failures). A fetched role dropped by an over-strict
   filter is invisible and I never know. Guardrails already added: excludes match
   whole words (so "lead" doesn't kill "Leadership Development"), and unknown or
   vague locations are KEPT, not dropped. When you tune `filters.yaml`, bias
   toward recall: it is better to show me a few off-target roles than to hide a
   real one. After a few live runs, sanity-check by spot-reading a firm's real
   careers page against what the tracker surfaced for it, and loosen filters if
   anything relevant was missing.

Coverage you cannot get for free, and should just tell me about: contractor-run
national labs (NREL, LBNL, PNNL) use their own systems and are not in USAJobs;
a few bespoke firms may resist every method. For those, the `careers_url` bookmark
list is the honest fallback.

## Architecture (how the pieces fit)

```
tracker.py
  -> loads companies.yaml + filters.yaml
  -> for each company: ats client fetch() -> raw postings
  -> filtering.filter_jobs()  (keyword + location gate, tag role_type + remote)
  -> optional adzuna broad net for manual firms
  -> dedupe by uid
  -> store.diff_and_update()  (what is new vs data/seen.json)
  -> report.write_outputs()   (digest.md + new_jobs.csv)
```

A "job" is normalized to: uid, company, category, title, location, url, posted,
source, role_type, remote. uid = `{source}:{company}:{job_id}` and is the dedupe
+ seen key.

## Design rules

- Free only. No paid APIs, no headless-browser scraping services.
- Be gentle: one pass per day, sane User-Agent, no hammering. The public ATS
  endpoints tolerate this; aggressive polling gets Cloudflared.
- Fail soft: one broken company must never crash the run. Catch, log to the
  digest's error list, continue.
- State lives in `data/seen.json`, committed by the Action, so "new" is stable
  across runs on a fresh runner each day.

## Honest limitations (tell me, don't paper over)

- The clean ATS APIs cover the cleantech startups well and some Workday firms.
  The big consultancies and a few utilities are bespoke; Adzuna is a net, not a
  guarantee, and will have some noise and some gaps.
- ATS slugs and Workday sites change when firms migrate systems. Expect to re-run
  discover.py every few months and fix a few entries.
- Adzuna's free tier has call limits. Two pages per query, once a day, stays well
  inside them.
