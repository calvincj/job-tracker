"""Turn raw postings into filtered, tagged Job records.

A job passes if:
  title matches at least one keyword in keywords_any, AND
  it is not excluded by exclude_title (matched as whole words), AND
  - if it's an internship: location matches locations_any (San Diego, school-
    year workable) OR the job is remote OR the location is unknown/vague
    (kept on purpose so messy ATS location text doesn't cost coverage).
  - otherwise (new-grad/full-time/other): no location gate at all - willing
    to relocate anywhere once out of school.
  the location isn't clearly outside the US (non_us_country_names/_codes),
  AND
  it isn't older than max_days_since_posted (a zombie req still marked open),
  AND
  it doesn't ask for more than max_years_experience or explicitly require a
  PhD/doctorate, per the job's own description (where a source gives us one -
  see _min_years_required / _requires_phd).

Every passing job gets a role_type tag (intern / new_grad / other) and a
remote flag, so the report can group by what the user is actually after.
"""

import datetime
import re

# Locations we refuse to drop on: empty, or generic strings that carry no city
# signal. Better to show these than silently lose a real role.
VAGUE_LOCATIONS = ("", "us", "usa", "united states", "multiple locations",
                   "various", "various locations", "nationwide", "flexible",
                   "hybrid", "on-site", "onsite")

_TAG_RE = re.compile(r"<[^>]+>")

_WORKDAY_AGO_RE = re.compile(r"posted\s+(\d+)(\+?)\s+days?\s+ago", re.I)


def days_ago(posted):
    """Best-effort (days_since_posted, is_lower_bound) from whatever format
    the source gave us. Workday sends relative text ("Posted 3 Days Ago"),
    everything else sends a real ISO date/datetime. Shared by the age-cutoff
    gate below and report.py's display/sort - one parser, one set of quirks
    to reason about."""
    if not posted:
        return None, False
    p = posted.strip()
    low = p.lower()
    if low == "posted today":
        return 0, False
    if low == "posted yesterday":
        return 1, False
    m = _WORKDAY_AGO_RE.search(p)
    if m:
        return int(m.group(1)), bool(m.group(2))
    try:
        s = p.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        delta = (now.date() - dt.astimezone(datetime.timezone.utc).date()).days
        return max(delta, 0), False
    except (ValueError, TypeError):
        return None, False
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


# Degree mention near a requirement word, e.g. "PhD required", "must have a
# doctorate", "requires a Ph.D." - NOT "PhD preferred/a plus/nice to have" or
# "PhD OR equivalent experience" (a very common way of saying a PhD is NOT
# actually mandatory), neither of which blocks an application. Only fires on
# a clear phrase match, same recall-over-precision stance as
# _min_years_required: no match is not treated as a fail, since most sources
# don't give us a description to check at all.
_DEGREE_RE = re.compile(r"ph\.?\s?d\.?|doctoral degree|doctorate", re.IGNORECASE)
_REQUIRE_WORDS = ("required", "require", "requires", "must have", "must hold",
                  "must possess", "mandatory")
_SOFT_WORDS = ("preferred", "a plus", "nice to have", "not required", "optional",
              "bonus", "or equivalent", "or comparable", "or relevant experience")


def _requires_phd(description):
    if not description:
        return False
    text = _TAG_RE.sub(" ", description)
    for m in _DEGREE_RE.finditer(text):
        near = text[max(0, m.start() - 25):min(len(text), m.end() + 25)].lower()
        if any(w in near for w in _SOFT_WORDS):
            continue  # explicitly optional / has a non-PhD path right by the mention
        window = text[max(0, m.start() - 60):min(len(text), m.end() + 60)].lower()
        if any(w in window for w in _REQUIRE_WORDS):
            return True
    return False


# Explicit class-year / grad-year signals in a title or description. Each
# pattern only fires next to a keyword that actually ties the year to a grad
# cohort - a bare "2028" floating in a req ID or address would never match.
# "Class of 2028" is the standard label for a rising-senior summer-2027
# internship (the class one year behind you), which is exactly the mismatch
# you asked to catch. Kept separate from the summer-program year below: a
# posting that says both "Summer 2027" and "Class of 2028" is for the class
# of 2028, full stop - the cohort label wins over the summer-timing label.
_CLASS_YEAR_PATTERNS = (
    re.compile(r"class of\s*'?(\d{4})", re.I),
    re.compile(r"graduat\w*[^\d]{0,20}(\d{4})", re.I),
    re.compile(r"(\d{4})\s+grad(?:uate)?s?\b", re.I),
    re.compile(r"new\s+grad\w*[^\d]{0,15}(\d{4})", re.I),
    re.compile(r"(\d{4})\s+new\s+grad", re.I),
    re.compile(r"(\d{4})\s+(?:bachelor|master)\S*[^\d]{0,30}graduat", re.I),
)
_SUMMER_YEAR_RE = re.compile(r"summer\s+(\d{4})", re.I)


def _plausible_years(matches):
    return {int(y) for y in matches if 2000 <= int(y) <= 2100}


def _class_year_conflict(title, description, target_year, role_type):
    """True if the title/description names a class year, or (for
    internships with no class-year label) a summer program year, that is NOT
    target_year. No mention at all is not a conflict - most postings don't
    say one, and dropping those on a guess would cost recall. Only checked
    for intern/new_grad; "other"-tagged roles aren't cohort-specific."""
    if not target_year or role_type not in ("intern", "new_grad"):
        return False
    text = f"{title} {_TAG_RE.sub(' ', description or '')}"
    # A class year in the TITLE wins outright - CRA's "(2028 Bachelor's/
    # Master's graduates) ... Intern (Summer 2027)" passed because its
    # description also mentioned 2027 somewhere, which satisfied the
    # combined title+description check.
    class_years = _plausible_years(
        y for pat in _CLASS_YEAR_PATTERNS for y in pat.findall(title or ""))
    if not class_years:
        class_years = _plausible_years(
            y for pat in _CLASS_YEAR_PATTERNS for y in pat.findall(text))
    if class_years:
        return target_year not in class_years
    # Not just interns: a "Summer 2028 ... Consultant" posting is tagged
    # new_grad by its "consultant" title but is really a summer program.
    if role_type in ("intern", "new_grad"):
        summer_years = _plausible_years(_SUMMER_YEAR_RE.findall(text))
        if summer_years:
            return target_year not in summer_years
    return False


def _lower(s):
    return (s or "").lower()


def _has_word(text, term):
    """Whole-word (or phrase) match, so 'lead' doesn't nuke 'Leadership'."""
    # Boundary guards only on ends that are word chars - a term like ", mid"
    # starts with punctuation, and "(?<!\w)" before the comma would never
    # match ("analyst, mid": the comma follows the "t").
    pre = r"(?<!\w)" if re.match(r"\w", term) else ""
    post = r"(?!\w)" if re.search(r"\w$", term) else ""
    return re.search(pre + re.escape(term) + post, text) is not None


def _has_prefix(text, stem):
    """Match a keyword stem at the START of a word ("econom" hits "Economist",
    "sustainab" hits "Sustainability") but never mid-word, so "mining" can't
    fire on "determining" or "trade" on "comrade". Prefix collisions that
    remain ("wind" -> "Windows") are handled in exclude_title."""
    return re.search(r"(?<!\w)" + re.escape(stem), text) is not None


def detect_role_type(title, filters):
    """Whole-word match, not substring: "intern" used to fire on
    "International Trade Analyst" / "Internal Audit", tagging them as
    internships and sending them through the intern-only location gate."""
    t = _lower(title)
    for label, needles in filters.get("role_types", {}).items():
        if any(_has_word(t, n) for n in needles):
            return label
    return "other"


def _is_non_us(location, filters):
    """Full country names anywhere (whole word); short country codes only as
    the exact LAST comma-separated segment (e.g. "Edinburgh, GB") - a bare
    substring scan on 2-letter codes is too easy to false-positive."""
    loc = _lower(location).strip()
    if not loc:
        return False
    for name in filters.get("non_us_country_names", []):
        if _has_word(loc, name):
            return True
    last = loc.split(",")[-1].strip()
    return last in filters.get("non_us_country_codes", [])


# CJK punctuation/ideographic space, hiragana, katakana, CJK ideographs,
# Hangul. A title written in one of these
# scripts is a Japan/China/Korea posting regardless of what the (often vague)
# location field says.
_CJK_RE = re.compile(r"[\u3000-\u30ff\u3400-\u9fff\uac00-\ud7af]")


_US_STATES = ("alabama alaska arizona arkansas california colorado connecticut "
    "delaware florida georgia hawaii idaho illinois indiana iowa kansas "
    "kentucky louisiana maine maryland massachusetts michigan minnesota "
    "mississippi missouri montana nebraska nevada ohio oklahoma oregon "
    "pennsylvania tennessee texas utah vermont virginia washington wisconsin "
    "wyoming").split() + ["new hampshire", "new jersey", "new mexico",
    "new york", "north carolina", "north dakota", "rhode island",
    "south carolina", "south dakota", "west virginia", "district of columbia"]
_US_CODES = ("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI "
             "MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT "
             "VT VA WA WV WI WY DC").split()
# A US state code only counts after a comma or at the very end ("Paris, TX",
# "Albany NY") - not mid-string, or "London OR Berlin" would read as Oregon.
_US_STATE_RE = re.compile(
    r"(?i:\b(?:" + "|".join(_US_STATES) + r")\b)"
    r"|,\s*(?:" + "|".join(_US_CODES) + r")\b"
    r"|\b(?:" + "|".join(_US_CODES) + r")\s*$")


def _has_non_us_place(location, filters):
    """non_us_title_terms (foreign cities) checked against the location text
    as well - "London GB80", "Ottawa ON", "Wiesbaden, Hesse" all slipped past
    the country-name/last-segment-code check."""
    if _US_STATE_RE.search(location or ""):
        return False  # "Vancouver, Washington", "Paris, TX", "Ontario, CA"
    loc = _lower(location)
    return any(_has_word(loc, term) for term in filters.get("non_us_title_terms", []))


def _is_non_us_title(title, filters):
    """Non-US signal in the title itself (e.g. "Consultant - Toronto, ON",
    "Consultant (m/w/d)"), for postings whose location field misses it.
    Uses its own short list, not non_us_country_names - a title like "China
    Policy Analyst" is a US role."""
    if _CJK_RE.search(title or ""):
        return True
    t = _lower(title)
    return any(_has_word(t, term) for term in filters.get("non_us_title_terms", []))


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


# "Consultant / Senior Consultant", "Analyst / Sr. Analyst": one req open at
# two rungs, the first of which is entry-level. Strip the senior alternate
# before the exclude_title check so "senior" doesn't drop the whole posting.
_SLASH_SENIOR_RE = re.compile(r"/\s*(?:senior|sr\.?)\s+", re.IGNORECASE)


def passes(job, filters, require_domain=False):
    title = _lower(job["title"])
    title = _SLASH_SENIOR_RE.sub("/ ", title)
    loc = _lower(job["location"]).strip()

    if job["uid"] in filters.get("known_dead_uids", []):
        return False

    # exclude senior / leadership titles (whole-word match)
    for bad in filters.get("exclude_title", []):
        if _has_word(title, _lower(bad)):
            return False

    # exclude whole employers (whole-word match against company name) - for
    # cases where the disqualifying signal is who the job is with, not what
    # the title says (e.g. a USAJobs "Economist" posting at the Army Corps of
    # Engineers - the title alone gives no hint it's a military agency).
    company_name = _lower(job.get("company", ""))
    for bad in filters.get("exclude_employer", []):
        if _has_word(company_name, _lower(bad)):
            return False

    # keyword gate (word-prefix match, see _has_prefix)
    kw = filters.get("keywords_any", [])
    if kw and not any(_has_prefix(title, k) for k in kw):
        return False

    # domain gate - generalist firms only (Guidehouse, Booz Allen, GM...).
    # At a firm whose feed is mostly federal health/IT/defense work, a bare
    # role word ("Consultant", "Data Analyst", "Research", "Strategy") says
    # nothing; the title also has to name your actual field. Specialist firms
    # (RMI, Brattle, Watershed) skip this - there every role is in-field.
    if require_domain:
        dom = filters.get("domain_keywords", [])
        if not any(_has_prefix(title, k) for k in dom):
            return False

    # location gate - internships only (school-year, can't relocate). New-grad
    # and everything else is open to relocating anywhere, so skip this gate
    # for them entirely. Remote always allowed; unknown/vague locations are
    # KEPT rather than dropped, so inconsistent ATS location text doesn't
    # cost coverage - you eyeball the exact location on the linked page.
    # Summer internships are exempt - you can relocate for a summer, the
    # gate is only about school-year work (PROJECT.md track 3).
    locs = filters.get("locations_any", [])
    is_summer = "summer" in title
    if locs and job["role_type"] == "intern" and not is_summer:
        vague = loc in VAGUE_LOCATIONS
        if not (job["remote"] or vague or any(l in loc for l in locs)):
            return False

    # US-only gate. Applies even to remote postings - an explicit
    # "Remote - Canada" still isn't a US role.
    if (_is_non_us(job["location"], filters)
            or _has_non_us_place(job["location"], filters)
            or _is_non_us_title(job["title"], filters)):
        return False

    # absolute age cutoff (e.g. a zombie req still marked open at 700+ days).
    # Unparseable/unknown posted dates are NOT dropped - can't verify = kept.
    max_days = filters.get("max_days_since_posted")
    if max_days:
        age, _ = days_ago(job.get("posted", ""))
        if age is not None and age > max_days:
            return False

    # experience-level gate (only where we actually have a description)
    max_years = filters.get("max_years_experience")
    if _min_years_required(job.get("_description", ""), max_years):
        return False

    # degree gate: drop postings that explicitly require a PhD/doctorate,
    # even when the title itself gives no hint (e.g. a plain "Research
    # Analyst" whose qualifications section requires one). "PhD preferred"
    # doesn't trigger this - see _requires_phd.
    if _requires_phd(job.get("_description", "")):
        return False

    # class-year gate: drop postings that explicitly name a grad/summer year
    # other than yours (e.g. "Class of 2028", "Summer 2026 Internship"). No
    # year mentioned at all is not a conflict - see _class_year_conflict.
    target_year = filters.get("target_grad_year")
    if _class_year_conflict(job["title"], job.get("_description", ""),
                            target_year, job["role_type"]):
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


def filter_jobs(raw_list, company, category, filters, require_domain=False):
    out = []
    for raw in raw_list:
        job = build_job(raw, company, category, filters)
        if passes(job, filters, require_domain):
            job.pop("_description", None)  # only needed for the gate above
            out.append(job)
    return out
