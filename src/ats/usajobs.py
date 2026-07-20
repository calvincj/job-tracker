"""USAJobs client (optional). Federal roles, free API.

High value for the energy-policy track: DOE, FERC, EPA, EIA, and other federal
agencies post here. It will NOT cover contractor-run national labs (NREL, LBNL),
which use their own systems, but it catches the federal side that no ATS pull or
Adzuna query surfaces cleanly.

Get a free key at https://developer.usajobs.gov/apirequest/ and set env vars:
  USAJOBS_KEY   the Authorization-Key
  USAJOBS_EMAIL the email you registered (sent as User-Agent)

Endpoint:
  GET https://data.usajobs.gov/api/search?Keyword=..&LocationName=..
"""

import os
import requests

BASE = "https://data.usajobs.gov/api/search"
TIMEOUT = 25


def available():
    return bool(os.environ.get("USAJOBS_KEY") and os.environ.get("USAJOBS_EMAIL"))


def fetch(keyword, location=""):
    key = os.environ.get("USAJOBS_KEY")
    email = os.environ.get("USAJOBS_EMAIL")
    if not (key and email):
        return []

    headers = {
        "Host": "data.usajobs.gov",
        "User-Agent": email,
        "Authorization-Key": key,
    }
    params = {"Keyword": keyword, "ResultsPerPage": 50}
    if location:
        params["LocationName"] = location

    resp = requests.get(BASE, headers=headers, params=params, timeout=TIMEOUT)
    if resp.status_code != 200:
        return []

    items = (resp.json().get("SearchResult", {}) or {}).get("SearchResultItems", [])
    out = []
    for it in items:
        d = it.get("MatchedObjectDescriptor", {}) or {}
        out.append({
            "job_id": str(d.get("PositionID") or it.get("MatchedObjectId", "")),
            "title": d.get("PositionTitle", "") or "",
            "location": d.get("PositionLocationDisplay", "") or "",
            "url": d.get("PositionURI", "") or "",
            "posted": (d.get("PublicationStartDate", "") or "")[:10],
            "source": "usajobs",
            "_company": d.get("OrganizationName", "") or "Federal",
        })
    return out
