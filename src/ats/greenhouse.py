"""Greenhouse public Job Board API client.

Free, no auth. Endpoint:
  GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true

Returns {"jobs": [...], "meta": {...}}. Each job has:
  id, title, updated_at, first_published, location.name, absolute_url,
  metadata[], content (HTML)

content=true costs nothing extra request-wise (still one call per board), just
a bigger payload - worth it since it lets filtering.py check years-of-experience
language in the actual description instead of just the title.

Uses first_published (not updated_at) as "posted": updated_at bumps on any
edit to the posting, including ones some boards make with no real content
change (confirmed on Redwood Materials - several week-old postings had
updated_at re-touched to "today" daily), which pinned stale postings to the
top of the dashboard as if freshly reposted. first_published is set once,
when the req first goes live, and doesn't move after that.
"""

import requests

BASE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
TIMEOUT = 20


def fetch(slug):
    """Return a list of normalized-ish raw dicts for one Greenhouse board.

    Raises requests.HTTPError on a bad slug so the caller can log and skip.
    """
    url = BASE.format(slug=slug)
    resp = requests.get(url, params={"content": "true"}, timeout=TIMEOUT,
                        headers={"User-Agent": "personal-job-tracker"})
    resp.raise_for_status()
    data = resp.json()
    out = []
    for j in data.get("jobs", []):
        out.append({
            "job_id": str(j.get("id")),
            "title": j.get("title", "") or "",
            "location": (j.get("location") or {}).get("name", "") or "",
            "url": j.get("absolute_url", "") or "",
            "posted": j.get("first_published") or j.get("updated_at", "") or "",
            "source": "greenhouse",
            "_description": j.get("content", "") or "",
        })
    return out
