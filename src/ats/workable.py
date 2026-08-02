"""Workable public widget API client.

Free, no auth. Endpoint:
  GET https://apply.workable.com/api/v1/widget/accounts/{account}?details=true

Returns {"name": ..., "jobs": [...]}. Each job has: shortcode, title, url,
published_on, city, state, country, description (HTML) - description is
worth keeping (like Greenhouse's content=true) so filtering.py can check
years-of-experience language in the actual posting, not just the title.
"""

import requests

BASE = "https://apply.workable.com/api/v1/widget/accounts/{account}"
TIMEOUT = 20


def fetch(account):
    resp = requests.get(BASE.format(account=account), params={"details": "true"},
                        timeout=TIMEOUT, headers={"User-Agent": "personal-job-tracker"})
    resp.raise_for_status()
    data = resp.json()
    out = []
    for j in data.get("jobs", []):
        loc = ", ".join(p for p in [j.get("city"), j.get("state") or j.get("country")] if p)
        out.append({
            "job_id": j.get("shortcode", "") or "",
            "title": j.get("title", "") or "",
            "location": loc,
            "url": j.get("url", "") or j.get("shortlink", "") or "",
            "posted": j.get("published_on", "") or "",
            "source": "workable",
            "_description": j.get("description", "") or "",
        })
    return out
