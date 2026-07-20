"""Turn raw postings into filtered, tagged Job records.

A job passes if:
  title matches at least one keyword in keywords_any, AND
  it is not excluded by exclude_title (matched as whole words), AND
  location matches locations_any OR the job is remote OR the location is
  unknown/vague (kept on purpose so messy ATS location text doesn't cost
  coverage).

Every passing job gets a role_type tag (intern / new_grad / other) and a
remote flag, so the report can group by what the user is actually after.
"""

import re

# Locations we refuse to drop on: empty, or generic strings that carry no city
# signal. Better to show these than silently lose a real role.
VAGUE_LOCATIONS = ("", "us", "usa", "united states", "multiple locations",
                   "various", "various locations", "nationwide", "flexible",
                   "hybrid", "on-site", "onsite")


def _lower(s):
    return (s or "").lower()


def _has_word(text, term):
    """Whole-word (or phrase) match, so 'lead' doesn't nuke 'Leadership'."""
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) is not None


def detect_role_type(title, filters):
    t = _lower(title)
    for label, needles in filters.get("role_types", {}).items():
        if any(n in t for n in needles):
            return label
    return "other"


def is_remote(location, title, raw):
    loc = _lower(location)
    if "remote" in loc:
        return True
    if raw.get("_remote"):
        return True
    if _lower(raw.get("_workplace")) == "remote":
        return True
    # some ATS (e.g. Workday) list the physical office as location and note
    # "Remote" only in the title itself, so check there too.
    if _has_word(_lower(title), "remote"):
        return True
    return False


def passes(job, filters):
    title = _lower(job["title"])
    loc = _lower(job["location"]).strip()

    # exclude senior / leadership titles (whole-word match)
    for bad in filters.get("exclude_title", []):
        if _has_word(title, _lower(bad)):
            return False

    # keyword gate
    kw = filters.get("keywords_any", [])
    if kw and not any(k in title for k in kw):
        return False

    # location gate. Remote always allowed. Unknown/vague locations are KEPT
    # rather than dropped, so inconsistent ATS location text doesn't cost
    # coverage; you eyeball the exact location on the linked page.
    locs = filters.get("locations_any", [])
    if locs:
        vague = loc in VAGUE_LOCATIONS
        if not (job["remote"] or vague or any(l in loc for l in locs)):
            return False

    return True


def build_job(raw, company, category, filters):
    """Normalize + tag a raw posting into a full Job dict."""
    job = {
        "uid": f"{raw['source']}:{company}:{raw['job_id']}",
        "company": company,
        "category": category,
        "title": raw.get("title", ""),
        "location": raw.get("location", ""),
        "url": raw.get("url", ""),
        "posted": raw.get("posted", ""),
        "source": raw.get("source", ""),
    }
    job["remote"] = is_remote(job["location"], job["title"], raw)
    job["role_type"] = detect_role_type(job["title"], filters)
    return job


def filter_jobs(raw_list, company, category, filters):
    out = []
    for raw in raw_list:
        job = build_job(raw, company, category, filters)
        if passes(job, filters):
            out.append(job)
    return out
