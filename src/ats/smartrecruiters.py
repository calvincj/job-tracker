"""SmartRecruiters public postings API client.

Free, no auth. Endpoint:
  GET https://api.smartrecruiters.com/v1/companies/{company}/postings

Returns {"totalFound": N, "limit": L, "offset": O, "content": [...]}. Each
posting has: id, name, releasedDate, location{city, region, country,
fullLocation}. The API itself doesn't return a public posting URL, but every
SmartRecruiters posting is reachable at a stable, undocumented-but-stable
generic URL: https://jobs.smartrecruiters.com/{company}/{id}.
"""

import requests

BASE = "https://api.smartrecruiters.com/v1/companies/{company}/postings"
TIMEOUT = 20
PAGE = 100


def fetch(company):
    out = []
    offset = 0
    total = None
    while total is None or offset < total:
        resp = requests.get(BASE.format(company=company),
                            params={"limit": PAGE, "offset": offset}, timeout=TIMEOUT,
                            headers={"User-Agent": "personal-job-tracker"})
        resp.raise_for_status()
        data = resp.json()
        total = data.get("totalFound", 0)
        postings = data.get("content", [])
        if not postings:
            break
        for j in postings:
            loc = j.get("location") or {}
            out.append({
                "job_id": str(j.get("id")),
                "title": j.get("name", "") or "",
                "location": loc.get("fullLocation", "") or "",
                "url": f"https://jobs.smartrecruiters.com/{company}/{j.get('id')}",
                "posted": j.get("releasedDate", "") or "",
                "source": "smartrecruiters",
            })
        offset += PAGE
    return out
