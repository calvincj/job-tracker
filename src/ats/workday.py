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
"""

import requests

TIMEOUT = 25
PAGE = 20


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
                "location": j.get("locationsText", "") or "",
                "url": f"https://{host}/en-US/{site}{path}" if path else "",
                "posted": j.get("postedOn", "") or "",
                "source": "workday",
            })
        offset += PAGE
        if offset > 2000:  # safety valve
            break
    return out
