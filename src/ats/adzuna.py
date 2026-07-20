"""Adzuna aggregator client (optional broad net).

Adzuna has a free API tier. Register at https://developer.adzuna.com to get an
app_id and app_key (free), then set them as env vars ADZUNA_APP_ID and
ADZUNA_APP_KEY (in GitHub: repo Settings > Secrets and variables > Actions).

This is the fallback for big firms with bespoke career systems that neither
Greenhouse/Lever/Ashby nor Workday cover. It searches by keyword + location
across the whole market, then the normal filter + company-match step narrows it.

Endpoint:
  GET https://api.adzuna.com/v1/api/jobs/us/search/{page}
      ?app_id=..&app_key=..&what=..&where=..&results_per_page=50
"""

import os
import requests

BASE = "https://api.adzuna.com/v1/api/jobs/us/search/{page}"
TIMEOUT = 25


def available():
    return bool(os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY"))


def fetch(what, where="", pages=2):
    """Search Adzuna. Returns raw normalized dicts tagged source='adzuna'.

    'what' is a keyword string (e.g. 'clean energy analyst').
    'where' is a city or '' for nationwide.
    """
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        return []

    out = []
    for page in range(1, pages + 1):
        params = {
            "app_id": app_id, "app_key": app_key,
            "what": what, "results_per_page": 50,
            "content-type": "application/json",
        }
        if where:
            params["where"] = where
        resp = requests.get(BASE.format(page=page), params=params, timeout=TIMEOUT,
                            headers={"User-Agent": "personal-job-tracker"})
        if resp.status_code != 200:
            break
        for j in resp.json().get("results", []):
            out.append({
                "job_id": str(j.get("id")),
                "title": j.get("title", "") or "",
                "location": (j.get("location") or {}).get("display_name", "") or "",
                "url": j.get("redirect_url", "") or "",
                "posted": (j.get("created", "") or "")[:10],
                "source": "adzuna",
                "_company": (j.get("company") or {}).get("display_name", "") or "",
            })
    return out
