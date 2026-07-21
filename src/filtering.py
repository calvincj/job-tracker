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

_TAG_RE = re.compile(r"<[^>]+>")
# First number in a "3-5 years" / "5+ years" / "3 to 5 years" phrase - takes
# the lower bound of a range on purpose (recall > precision: a posting that
# accepts 3-5 years shouldn't be dropped for someone with 3).
_YEARS_RE = re.compile(r"(\d{1,2})\+?\s*(?:[-–]|to)?\s*(?:\d{1,2}\+?\s*)?years?",
                       re.IGNORECASE)


def _min_years_required(description, max_years):
    """Best-effort read of a job description: does it explicitly ask for more
    than max_years of experience? Only returns True on a clear numeric match
    with "experience" nearby - no match at all is NOT treated as a fail, since
    that just means we can't verify (most sources don't give us a description
    at all), and silently dropping unverifiable jobs would hurt recall."""
    if not description or not max_years:
        return False
    text = _TAG_RE.sub(" ", description)
    for m in _YEARS_RE.finditer(text):
        window = text[max(0, m.start() - 40):min(len(text), m.end() + 40)].lower()
        if "experience" in window or "exp." in window:
            if int(m.group(1)) > max_years:
                return True
    return False


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

    if job["uid"] in filters.get("known_dead_uids", []):
        return False

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

    # experience-level gate (only where we actually have a description)
    max_years = filters.get("max_years_experience")
    if _min_years_required(job.get("_description", ""), max_years):
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
        "_description": raw.get("_description", ""),
    }
    job["remote"] = is_remote(job["location"], job["title"], raw)
    job["role_type"] = detect_role_type(job["title"], filters)
    return job


def filter_jobs(raw_list, company, category, filters):
    out = []
    for raw in raw_list:
        job = build_job(raw, company, category, filters)
        if passes(job, filters):
            job.pop("_description", None)  # only needed for the gate above
            out.append(job)
    return out
