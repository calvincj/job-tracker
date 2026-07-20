# Job Tracker

My personal job feed. Runs every 6 hours on GitHub Actions, checks a curated
list of firms, emails me a digest of new postings. No manual polling.

Three tracks, always split:
1. Full-time / new-grad, starting ~June 2027
2. Internships, summer 2027+
3. Remote or San Diego, workable during the school year

## What it covers

- Cleantech / renewables: Redwood, Nexamp, Form Energy, Qcells, etc.
- Utilities and grid: Duke Energy, NextEra, PJM, CAISO, ERCOT
- Consulting: McKinsey, BCG, Bain, Deloitte, EY-P, PwC, Baker Tilly, ICF
- Environmental consulting: Guidehouse, AECOM, WSP, ERM, Tetra Tech, SWCA
- Market intelligence: BloombergNEF, Wood Mackenzie, Rystad
- National labs: NLR (formerly NREL), LBNL, PNNL, ORNL, Sandia, INL, LLNL
- Critical minerals / battery supply chain: MP Materials, Albemarle, Lithium
  Americas, KoBold Metals, Vulcan Elements, Ascend Elements, USA Rare Earth,
  Energy Fuels, ABTC, Talon Metals
- Plus Adzuna (broad market net) and USAJobs (DOE/FERC/EPA/EIA federal roles)

Full firm list with categories: `config/companies.yaml`.

## Where the digest goes

- **Dashboard: https://calvincj.github.io/job-tracker/** - searchable, same
  data as digest.md, regenerated every run. The main place to check.
- Email: only today's genuinely new roles (not the whole lookback window),
  after a quick dead-link check on that small set. See `src/notify.py`.
- `data/digest.md`, committed every run, readable on GitHub mobile.
- `data/new_jobs.csv` - full running log, never pruned.
- `data/manual_links.md` - bookmarks for firms with no clean ATS feed, regenerated
  every run, grouped by category. My weekly eyeball-it fallback.

## Tuning

- `config/filters.yaml` - keywords, target cities, excluded titles, role-type
  tagging, Adzuna/USAJobs/email flags.
- `config/companies.yaml` - add, drop, or recategorize firms. New firm on
  Greenhouse/Lever/Ashby? Confirm with `python -m src.discover "Name"`. New
  Workday firm? See `src/ats/workday.py` for how to find host/tenant/site.
- Bias filters toward recall over precision - a few off-target roles beat a
  silently dropped real one.

## Known gaps

- Manual firms (McKinsey, Bloomberg, most national labs, etc.) have no public
  API. Adzuna's broad net catches some; `data/manual_links.md` is the fallback.
- ATS slugs and Workday configs drift when firms migrate systems. Re-run
  `discover.py` every few months if a firm starts erroring out.
- Adzuna free tier: 250 calls/day. Current query set stays well under that.
