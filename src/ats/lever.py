"""Lever public postings API client.

Free, no auth. Endpoint:
  GET https://api.lever.co/v0/postings/{slug}?mode=json

The mode=json param is required or Lever returns HTML. Returns a JSON array.
Each posting has: id, text (title), hostedUrl, createdAt, workplaceType,
categories{location, team, commitment}.
"""

import requests

BASE = "https://api.lever.co/v0/postings/{slug}"
TIMEOUT = 20


def fetch(slug):
    url = BASE.format(slug=slug)
    resp = requests.get(url, params={"mode": "json"}, timeout=TIMEOUT,
                        headers={"User-Agent": "personal-job-tracker"})
    resp.raise_for_status()
    data = resp.json()
    out = []
    for j in data:
        cats = j.get("categories", {}) or {}
        out.append({
            "job_id": str(j.get("id")),
            "title": j.get("text", "") or "",
            "location": cats.get("location", "") or "",
            "url": j.get("hostedUrl", "") or "",
            "posted": _ms_to_iso(j.get("createdAt")),
            "source": "lever",
            "_workplace": (j.get("workplaceType") or "").lower(),
        })
    return out


def _ms_to_iso(ms):
    if not ms:
        return ""
    import datetime
    try:
        return datetime.datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")
    except Exception:
        return ""
