"""Ashby public job board API client.

Free, no auth. Endpoint:
  GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true

Returns {"jobs": [...]}. Field names to VERIFY against a live response (Ashby
has changed these before): title, location, employmentType, jobUrl / applyUrl,
publishedAt, isRemote. If a field is missing, inspect one response and adjust.
"""

import requests

BASE = "https://api.ashbyhq.com/posting-api/job-board/{slug}"
TIMEOUT = 20


def fetch(slug):
    url = BASE.format(slug=slug)
    resp = requests.get(url, params={"includeCompensation": "false"}, timeout=TIMEOUT,
                        headers={"User-Agent": "personal-job-tracker"})
    resp.raise_for_status()
    data = resp.json()
    out = []
    for j in data.get("jobs", []):
        out.append({
            "job_id": str(j.get("id") or j.get("jobId") or j.get("jobUrl", "")),
            "title": j.get("title", "") or "",
            "location": j.get("location", "") or "",
            "url": j.get("jobUrl") or j.get("applyUrl", "") or "",
            "posted": j.get("publishedAt", "") or "",
            "source": "ashby",
            "_remote": bool(j.get("isRemote")),
        })
    return out
