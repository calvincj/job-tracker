"""Workday career site client.

Most big firms on the target list (utilities, consultancies, env. consultants)
run Workday. There is no single public directory, so each company needs three
values found by inspecting its careers page (see PROJECT.md > Resolving Workday):

  host   e.g. nexteraenergy.wd1.myworkdayjobs.com
  tenant e.g. nexteraenergy
  site   e.g. nexteraenergy  (the career-site path segment)

The data endpoint is a POST:
  POST https://{host}/wday/cxs/{tenant}/{site}/jobs
  body: {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}

Returns {"total": N, "jobPostings": [{title, externalPath, locationsText,
postedOn, bulletFields}]}. Paginate with offset until offset >= total.

locationsText is only a real "City, Region" string for single-site postings -
for a job open at more than one site, Workday collapses it to a useless
placeholder like "2 Locations"/"Multiple Locations" (confirmed: the list API
has no other field with the actual location list; getting it requires a
per-job detail call we don't make). externalPath's first segment is Workday's
primary location slug (e.g. "New-Delhi-India", "Frankfurt-Germany") even when
locationsText is vague, so fall back to that - loses the "there are more
sites" info, but a real place name (and country signal for the US-only
filter) beats a location string that's just a number.
"""

import re
import requests

TIMEOUT = 25
PAGE = 20
_VAGUE_LOC_RE = re.compile(r"^(\d+\s+locations?|multiple locations)$", re.IGNORECASE)
_PATH_LOC_RE = re.compile(r"^/job/([^/]+)/")


def _location_text(j):
    text = (j.get("locationsText") or "").strip()
    if text and not _VAGUE_LOC_RE.match(text):
        return text
    m = _PATH_LOC_RE.match(j.get("externalPath", "") or "")
    return m.group(1).replace("-", " ") if m else text


def fetch(cfg):
    """cfg is the 'workday' block from companies.yaml for one company."""
    host = cfg["host"]
    tenant = cfg["tenant"]
    site = cfg["site"]
    search = cfg.get("search_text", "")
    api = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"

    out = []
    offset = 0
    total = None
    while total is None or offset < total:
        body = {"appliedFacets": {}, "limit": PAGE, "offset": offset,
                "searchText": search}
        resp = requests.post(api, json=body, timeout=TIMEOUT,
                             headers={"User-Agent": "personal-job-tracker",
                                      "Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        # Workday only reports the real count on the first page; later pages
        # report total=0 even with more jobPostings still coming, so only
        # trust it once or every company gets truncated to ~2 pages.
        if total is None:
            total = data.get("total", 0)
        postings = data.get("jobPostings", [])
        if not postings:
            break
        for j in postings:
            path = j.get("externalPath", "") or ""
            out.append({
                "job_id": path or (j.get("bulletFields") or [""])[0],
                "title": j.get("title", "") or "",
                "location": _location_text(j),
                "url": f"https://{host}/en-US/{site}{path}" if path else "",
                "posted": j.get("postedOn", "") or "",
                "source": "workday",
            })
        offset += PAGE
        if offset > 2000:  # safety valve
            break
    return out
