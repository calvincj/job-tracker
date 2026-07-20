"""Resolve which ATS (and slug) a company uses.

Run this once per company you are unsure about. It tries a handful of slug
guesses against Greenhouse, Lever, and Ashby and reports which respond.

Usage:
  python -m src.discover "Fervo Energy"
  python -m src.discover "Fervo Energy" fervo fervoenergy

For Workday and bespoke sites this cannot help. See PROJECT.md > Resolving
Workday for the manual (10-second) inspection method.
"""

import sys
import re
import requests

TIMEOUT = 15


def _guesses(name):
    base = name.lower()
    base = re.sub(r"&", "and", base)
    base = re.sub(r"[^a-z0-9 ]", "", base)
    words = base.split()
    joined = "".join(words)
    hyphen = "-".join(words)
    first = words[0] if words else base
    # dedupe, preserve order
    seen, out = set(), []
    for g in [joined, hyphen, first, base.replace(" ", "")]:
        if g and g not in seen:
            seen.add(g)
            out.append(g)
    return out


def _try_greenhouse(slug):
    u = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    r = requests.get(u, timeout=TIMEOUT, headers={"User-Agent": "discover"})
    if r.status_code == 200 and "jobs" in r.json():
        return len(r.json()["jobs"])
    return None


def _try_lever(slug):
    u = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    r = requests.get(u, timeout=TIMEOUT, headers={"User-Agent": "discover"})
    if r.status_code == 200 and isinstance(r.json(), list):
        return len(r.json())
    return None


def _try_ashby(slug):
    u = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    r = requests.get(u, timeout=TIMEOUT, headers={"User-Agent": "discover"})
    if r.status_code == 200 and "jobs" in r.json():
        return len(r.json()["jobs"])
    return None


def discover(name, extra_slugs=None):
    slugs = _guesses(name) + list(extra_slugs or [])
    hits = []
    for slug in slugs:
        for ats, fn in [("greenhouse", _try_greenhouse),
                        ("lever", _try_lever),
                        ("ashby", _try_ashby)]:
            try:
                n = fn(slug)
            except Exception:
                n = None
            if n is not None:
                hits.append((ats, slug, n))
    return hits


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m src.discover \"Company Name\" [extra_slug ...]")
        sys.exit(1)
    company = sys.argv[1]
    extras = sys.argv[2:]
    print(f"Probing for: {company}")
    results = discover(company, extras)
    if not results:
        print("  No Greenhouse/Lever/Ashby board found. Likely Workday or bespoke.")
        print("  See PROJECT.md > Resolving Workday.")
    for ats, slug, count in results:
        print(f"  FOUND  ats={ats}  slug={slug}  open_jobs={count}")
