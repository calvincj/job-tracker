# Job Tracker

My personal job feed. Runs every 6 hours on GitHub Actions, checks a curated
list of firms, emails me a digest of new postings. No manual polling.

Three tracks, always split:
1. Full-time / new-grad, starting ~June 2027
2. Internships, summer 2027+
3. Remote or San Diego, workable during the school year

## What it covers

- Cleantech / renewables: Redwood, Nexamp, Form Energy, Qcells, Oklo, Kairos
  Power, Span, Base Power, Crusoe Energy, Heirloom, and more nuclear/geothermal/
  DAC/hydrogen startups
- Utilities and grid: Duke Energy, NextEra, PJM, CAISO, ERCOT, SDG&E, Sempra,
  SCE, PG&E, Southern Company, AEP, Xcel, ConEd, PSEG, Entergy, MISO, SPP,
  NYISO, ISO-NE
- Renewable developers: Nexamp, Clearway Energy, Silicon Ranch, Apex Clean
  Energy, Origis Energy, Invenergy, Orsted, AES, Pattern Energy, Longroad
- Consulting: McKinsey, BCG, Bain, Deloitte, EY-P, PwC, Baker Tilly, ICF,
  L.E.K., Oliver Wyman, Kearney
- Economic/energy consulting: Brattle, CRA, FTI, NERA, Compass Lexecon,
  Analysis Group, Cornerstone Research, Exponent, Secretariat International,
  London Economics International, plus Houston/TX boutiques
- Environmental consulting: Guidehouse, AECOM, WSP, ERM, Tetra Tech, SWCA
- Market intelligence: BloombergNEF, Wood Mackenzie, Rystad, Amperon
- Climate data & analytics: Sylvera, Watershed, Cloverly, ClimateAI, Persefoni,
  Kayrros, Climate X, Jupiter Intelligence, Overstory (carbon accounting, ESG,
  climate risk)
- Climate finance: Generate Capital, Galvanize Climate Solutions
- Trade / supply-chain data: Altana AI, Sayari, Everstream Analytics,
  project44, FourKites, Interos
- Think tanks: Brookings, Energy Innovation, Center for American Progress,
  Niskanen Center, Urban Institute, plus foreign-policy shops (CSIS, Atlantic
  Council, Rhodium Group, etc.)
- National labs: NLR (formerly NREL), LBNL, PNNL, ORNL, Sandia, INL, LLNL,
  Argonne, Brookhaven
- Critical minerals / battery supply chain: MP Materials, Albemarle, Lithium
  Americas, KoBold Metals, Vulcan Elements, Ascend Elements, USA Rare Earth,
  Energy Fuels, ABTC, Talon Metals, Group14 Technologies, Sila Nanotechnologies
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

"New today" dedup: keyed by uid, but also by a company+title fingerprint
(`src/store.py`), so a source reposting the same role under a fresh job_id
(closes/reopens a req, etc.) doesn't ping as new again for 14 days.

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
