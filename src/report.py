"""Render the daily digest.

Three outputs:
  data/digest.md    readable on phone / in the repo, grouped for a morning skim.
                    Shows every currently-open job matching your filters, not
                    just recently-found ones - it's a live snapshot, not a
                    rolling window, so nothing disappears while it's still open.
  data/new_jobs.csv appendable log of every role ever surfaced (never lost, even
                    if you skip a day).
  docs/index.html   same data as digest.md, styled + searchable, served free via
                    GitHub Pages so there's a live link instead of a repo file.
                    Splits out "new today" (never seen before, or the source's
                    own posted date is today) from the rest.

The digest leads with the three tracks that matter:
  1. Full-time / new-grad roles
  2. Internships
  3. Remote / San Diego roles (workable during the school year)
"""

import csv
import datetime
import html
import os
import re


def _group(jobs):
    """Split into the digest's four buckets, each job appearing exactly once."""
    interns = [j for j in jobs if j["role_type"] == "intern"]
    grads = [j for j in jobs if j["role_type"] == "new_grad"]
    accounted = interns + grads
    remote = [j for j in jobs if j["remote"] and j not in accounted]
    accounted = accounted + remote
    other = [j for j in jobs if j not in accounted]
    return grads, interns, remote, other


def _section(title, jobs):
    if not jobs:
        return ""
    lines = [f"### {title} ({len(jobs)})", ""]
    for j in sorted(jobs, key=lambda x: (x["category"], x["company"])):
        loc = j["location"].strip() or "location unclear"
        tag = "REMOTE" if j["remote"] else loc
        lines.append(f"- **{j['company']}** ({j['category']}) - "
                     f"[{j['title']}]({j['url']}) - {tag}")
    lines.append("")
    return "\n".join(lines)


def render_markdown(open_jobs, stats):
    today = datetime.date.today().isoformat()
    grads, interns, remote, other = _group(open_jobs)

    out = [f"# Job digest - {today}", ""]
    if not open_jobs:
        out.append("No open roles matching your filters right now.")
        out.append("")
    else:
        out.append(f"**{len(open_jobs)} open roles** across "
                   f"{len({j['company'] for j in open_jobs})} firms.")
        out.append("")
        out.append(_section("New-grad / full-time", grads))
        out.append(_section("Internships", interns))
        out.append(_section("Remote (school-year workable)", remote))
        out.append(_section("Other matches", other))

    out.append("---")
    out.append(f"_Companies checked: {stats.get('checked', 0)}, "
               f"errors: {stats.get('errors', 0)}, "
               f"total open matches: {stats.get('open', 0)}._")
    if stats.get("error_list"):
        out.append("")
        out.append("Companies that failed this run (check slug/config):")
        for name, msg in stats["error_list"]:
            out.append(f"- {name}: {msg}")
    return "\n".join(out) + "\n"


def _esc(s):
    return html.escape(str(s), quote=True)


TRACK_LABEL = {"new_grad": "Full-time", "intern": "Internship", "other": "Other"}
TRACK_ORDER = {"new_grad": 0, "intern": 1, "other": 2}
TRACK_CLASS = {"new_grad": "t-grad", "intern": "t-intern", "other": "t-other"}
CATEGORY_PALETTE_SIZE = 10
AVATAR_PALETTE_SIZE = 10

_WORKDAY_AGO_RE = re.compile(r"posted\s+(\d+)(\+?)\s+days?\s+ago", re.I)


def _days_ago(posted):
    """Best-effort (days_since_posted, is_lower_bound) from whatever format
    the source gave us. Workday sends relative text ("Posted 3 Days Ago"),
    everything else sends a real ISO date/datetime."""
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


def _posted_label(posted):
    days, is_floor = _days_ago(posted)
    if days is None:
        return "—"
    if days == 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    return f"{days}{'+' if is_floor else ''}d ago"


_STATE_CODES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
# Longest names first so "West Virginia" matches before a hypothetical
# shorter overlapping name would.
_STATE_RE = re.compile(
    r",\s*(" + "|".join(re.escape(n) for n in
                        sorted(_STATE_CODES, key=len, reverse=True)) + r")\s*(?=,|$)",
    re.IGNORECASE)
_DC_RE = re.compile(r"washington,\s*(?:d\.?c\.?|district of columbia)\.?(?=[,\s]|$)",
                    re.IGNORECASE)
_DC_REVERSED_RE = re.compile(r"(?<!\w)(?:d\.?c\.?|district of columbia),\s*washington(?!\w)",
                             re.IGNORECASE)
_US_RE = re.compile(r"(?<!\w)(united states of america|united states|u\.s\.a\.|u\.s\.|usa)(?!\w)",
                    re.IGNORECASE)
_CITY_NICKNAMES = {"san francisco": "SF", "los angeles": "LA"}


def _shorten_location(loc):
    """Cosmetic only: California -> CA, United States -> US, etc. Anchored to
    comma-delimited segments (", California," not bare "California") so it
    doesn't mangle street addresses like "205 N Michigan Ave"."""
    if not loc:
        return loc
    s = _DC_RE.sub("DC", loc)
    s = _DC_REVERSED_RE.sub("DC", s)
    s = _STATE_RE.sub(lambda m: ", " + _STATE_CODES[m.group(1).lower()], s)
    s = _US_RE.sub("US", s)
    for name, nick in _CITY_NICKNAMES.items():
        s = re.sub(r"(?<!\w)" + re.escape(name) + r"(?!\w)", nick, s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip(" ,")


def _avatar_class(company):
    idx = sum(ord(c) for c in company) % AVATAR_PALETTE_SIZE
    return f"av-{idx}"


def _category_class(category):
    # Deterministic (not Python's randomized hash()) so colors are stable run
    # to run instead of reshuffling every time the tracker restarts.
    idx = sum(ord(c) for c in category) % CATEGORY_PALETTE_SIZE
    return f"cat-{idx}"


# 10-hue categorical palette, pastel-on-light / desaturated-on-dark.
# Reused for both sector badges and company avatars (different hash offsets).
_PALETTE = [
    ("#fee2e2", "#991b1b", "#3a1414", "#fca5a5"),
    ("#ffedd5", "#9a3412", "#3a1a06", "#fdba74"),
    ("#fef3c7", "#92400e", "#3a1a03", "#fcd34d"),
    ("#ecfccb", "#3f6212", "#1a2a05", "#bef264"),
    ("#ccfbf1", "#115e59", "#042b2a", "#5eead4"),
    ("#cffafe", "#155e75", "#07303e", "#67e8f9"),
    ("#dbeafe", "#1e40af", "#1c3455", "#93c5fd"),
    ("#e0e7ff", "#3730a3", "#221e54", "#a5b4fc"),
    ("#ede9fe", "#5b21b6", "#2c1760", "#c4b5fd"),
    ("#fce7f3", "#9d174d", "#3f0a24", "#f9a8d4"),
]


def _row(j, applied=False):
    loc = "Remote" if j["remote"] else _shorten_location(j["location"].strip()) or "Unclear"
    track = TRACK_LABEL.get(j["role_type"], "Other")
    track_cls = TRACK_CLASS.get(j["role_type"], "t-other")
    cat_cls = _category_class(j["category"])
    av_cls = _avatar_class(j["company"])
    initial = _esc(j["company"][:1].upper() or "?")
    days, _ = _days_ago(j.get("posted", ""))
    days_val = days if days is not None else 99999
    posted = _esc(_posted_label(j.get("posted", "")))
    action = ('<button class="apply-btn remove" type="button" data-unmark="1">Remove</button>'
             if applied else '<button class="apply-btn" type="button">Mark applied</button>')
    return f"""<div class="row{' is-applied' if applied else ' job'}" data-uid="{_esc(j['uid'])}"
     data-title="{_esc(j['title'])}" data-company="{_esc(j['company'])}"
     data-sector="{_esc(j['category'])}" data-location="{_esc(loc)}"
     data-posted="{posted}" data-days="{days_val}" data-track="{track}" data-url="{_esc(j['url'])}"
     data-cat-cls="{cat_cls}" data-track-cls="{track_cls}">
  <div class="c-role">
    <span class="avatar {av_cls}">{initial}</span>
    <div class="role-text">
      <a href="{_esc(j['url'])}" target="_blank" rel="noopener">{_esc(j['title'])}</a>
      <div class="row-meta">{_esc(j['company'])} &middot; <span class="badge {cat_cls}">{_esc(j['category'])}</span>
        &middot; {_esc(loc)} &middot; {posted}</div>
    </div>
  </div>
  <div class="c-company">{_esc(j['company'])}</div>
  <div class="c-sector"><span class="badge {cat_cls}">{_esc(j['category'])}</span></div>
  <div class="c-location">{_esc(loc)}</div>
  <div class="c-posted">{posted}</div>
  <div class="c-bottom">
    <span class="badge {track_cls}">{track}</span>
    {action}
  </div>
</div>"""


def _header_row():
    return ('<div class="row row-head"><div class="c-role">Role</div>'
            '<div class="c-company">Company</div><div class="c-sector">Sector</div>'
            '<div class="c-location">Location</div><div class="c-posted">Posted</div>'
            '<div class="c-bottom">Type</div></div>')


def _list(jobs, empty_msg, applied=False, sortable=False):
    header = _header_row()
    if not jobs:
        return f'<div class="list">{header}<p class="empty">{_esc(empty_msg)}</p></div>'
    # default: most recently posted first (ties broken by company, for a
    # stable order); the client-side sort toggle re-sorts from here.
    sorted_jobs = sorted(jobs, key=lambda x: (_days_ago(x.get("posted", ""))[0]
                                              if _days_ago(x.get("posted", ""))[0] is not None
                                              else 99999, x["company"]))
    rows = "\n".join(_row(j, applied=applied) for j in sorted_jobs)
    cls = "list sortable-list" if sortable else "list"
    return f'<div class="{cls}">{header}{rows}</div>'


def render_html(open_jobs, new_jobs, stats):
    # "New today" = genuinely new to the tracker this run, OR the source's own
    # posted date is today - a job posted this morning and first caught by an
    # earlier poll today is still "today" even once it's no longer new-to-us.
    never_seen_uids = {j["uid"] for j in new_jobs}
    def _posted_today(j):
        days, _ = _days_ago(j.get("posted", ""))
        return days == 0
    new_today = [j for j in open_jobs if j["uid"] in never_seen_uids or _posted_today(j)]
    new_uids = {j["uid"] for j in new_today}
    rest = [j for j in open_jobs if j["uid"] not in new_uids]

    errors_html = ""
    if stats.get("error_list"):
        items = "".join(f"<li>{_esc(n)}: {_esc(m)}</li>" for n, m in stats["error_list"])
        errors_html = (f'<details><summary>Companies that failed this run '
                       f'({stats.get("errors", 0)})</summary><ul>{items}</ul></details>')

    cat_css_light = "\n".join(f"  .cat-{i} {{ background:{bg}; color:{fg}; }}"
                              for i, (bg, fg, _, _) in enumerate(_PALETTE))
    cat_css_dark = "\n".join(f"    .cat-{i} {{ background:{bg}; color:{fg}; }}"
                             for i, (_, _, bg, fg) in enumerate(_PALETTE))
    av_css_light = "\n".join(f"  .av-{i} {{ background:{bg}; color:{fg}; }}"
                             for i, (bg, fg, _, _) in enumerate(_PALETTE))
    av_css_dark = "\n".join(f"    .av-{i} {{ background:{bg}; color:{fg}; }}"
                            for i, (_, _, bg, fg) in enumerate(_PALETTE))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Tracker</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    color-scheme: light dark;
    --bg: #f4f5f7; --card: #ffffff; --text: #16181d; --muted: #6b7280;
    --border: #e7e8ec; --accent: #2f5fe0; --new-bg: #eef3ff; --new-border: #cddcfb;
    --shadow: 0 1px 2px rgba(16,24,40,.04);
    --t-grad-bg: #dbeafe; --t-grad-fg: #1e40af;
    --t-intern-bg: #dcfce7; --t-intern-fg: #166534;
    --t-other-bg: #f1f5f9; --t-other-fg: #475569;
  }}
{cat_css_light}
{av_css_light}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0a0d13; --card: #12151d; --text: #e7e9ed; --muted: #939aa8;
      --border: #232733; --accent: #7ba1f7; --new-bg: #101a2e; --new-border: #21365c;
      --shadow: 0 1px 2px rgba(0,0,0,.3);
      --t-grad-bg: #1e3a5f; --t-grad-fg: #93c5fd;
      --t-intern-bg: #143523; --t-intern-fg: #86efac;
      --t-other-bg: #1a2130; --t-other-fg: #9aa4b2;
    }}
{cat_css_dark}
{av_css_dark}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: 'Plus Jakarta Sans', ui-sans-serif, -apple-system, BlinkMacSystemFont, sans-serif;
    max-width: 1180px; margin: 0 auto; padding: 2rem 1.5rem 4rem;
    line-height: 1.45; background: var(--bg); color: var(--text);
    -webkit-font-smoothing: antialiased;
  }}
  h1 {{ font-size: 1.6rem; font-weight: 800; letter-spacing: -0.02em; margin: 0; }}
  .topbar {{
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 0.8rem; margin-bottom: 1.75rem;
  }}
  .sort-toggle {{
    display: inline-flex; border: 1px solid var(--border); border-radius: 9px;
    padding: 0.2rem; background: var(--card); gap: 0.2rem;
  }}
  .sort-btn {{
    font-family: inherit; font-size: 0.8rem; font-weight: 600; padding: 0.35rem 0.75rem;
    border-radius: 6px; border: none; background: transparent; color: var(--muted); cursor: pointer;
  }}
  .sort-btn.active {{ background: var(--accent); color: #fff; }}
  h2 {{
    font-size: 1.05rem; font-weight: 700; margin: 2.4rem 0 0.8rem;
    display: flex; align-items: baseline; gap: 0.55rem;
  }}
  h2 .count {{
    color: var(--muted); font-weight: 600; font-size: 0.78rem; background: var(--card);
    border: 1px solid var(--border); border-radius: 999px; padding: 0.1rem 0.6rem;
  }}
  .new h2 {{ color: var(--accent); }}
  .list {{ display: flex; flex-direction: column; gap: 0.5rem; }}
  .row {{
    display: grid; align-items: center; gap: 0.75rem;
    grid-template-columns: minmax(220px,2.3fr) minmax(120px,1.1fr) minmax(110px,1fr) minmax(100px,1fr) 78px 168px;
    background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 0.85rem 1.1rem; box-shadow: var(--shadow);
  }}
  .new .row {{ background: var(--new-bg); border-color: var(--new-border); }}
  .row-head {{
    background: transparent; border: none; box-shadow: none; padding: 0 1.1rem;
  }}
  .row-head > div {{
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--muted); font-weight: 650; line-height: 1.4; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
  }}
  .row:not(.row-head):hover {{ border-color: var(--accent); }}
  .c-role {{ display: flex; align-items: center; gap: 0.7rem; min-width: 0; }}
  .avatar {{
    flex: none; width: 2.1rem; height: 2.1rem; border-radius: 9px; display: flex;
    align-items: center; justify-content: center; font-weight: 700; font-size: 0.85rem;
  }}
  .role-text {{ min-width: 0; }}
  .row-head .c-role {{ padding-left: calc(2.1rem + 0.7rem); }}
  .c-role a {{
    font-weight: 650; text-decoration: none; color: var(--text); font-size: 0.95rem;
    display: block; overflow-wrap: break-word;
  }}
  .c-role a:hover {{ color: var(--accent); text-decoration: underline; }}
  .row-meta {{ display: none; color: var(--muted); font-size: 0.8rem; margin-top: 0.2rem; }}
  .row > div {{ min-width: 0; }}
  .c-company, .c-location, .c-posted {{ color: var(--text); font-size: 0.88rem; overflow-wrap: break-word; }}
  .c-posted {{ color: var(--muted); font-size: 0.83rem; }}
  .applied-date {{ color: var(--muted); font-size: 0.78rem; margin-top: 0.2rem; }}
  .badge {{
    display: inline-block; font-size: 0.72rem; font-weight: 650; padding: 0.18rem 0.6rem;
    border-radius: 999px; overflow-wrap: break-word; max-width: 100%;
  }}
  .c-bottom .badge {{ white-space: nowrap; }}
  .t-grad {{ background: var(--t-grad-bg); color: var(--t-grad-fg); }}
  .t-intern {{ background: var(--t-intern-bg); color: var(--t-intern-fg); }}
  .t-other {{ background: var(--t-other-bg); color: var(--t-other-fg); }}
  .c-bottom {{ display: flex; align-items: center; justify-content: flex-end; gap: 0.6rem; }}
  .row-head .c-bottom {{ justify-content: flex-start; }}
  .apply-btn {{
    font-family: inherit; font-size: 0.78rem; font-weight: 600; padding: 0.35rem 0.7rem;
    border-radius: 8px; border: 1px solid var(--border); background: var(--bg);
    color: var(--text); cursor: pointer; white-space: nowrap;
  }}
  .apply-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  .apply-btn.remove {{ color: #dc2626; }}
  .apply-btn.remove:hover {{ border-color: #dc2626; }}
  .empty {{ color: var(--muted); font-size: 0.9rem; padding: 0.5rem 0; }}
  .row.hide {{ display: none; }}
  details {{ margin-top: 2.5rem; font-size: 0.85rem; color: #b45309; }}
  details summary {{ cursor: pointer; }}
  @media (max-width: 760px) {{
    .row-head {{ display: none; }}
    .row {{ grid-template-columns: 1fr; gap: 0; }}
    .c-company, .c-sector, .c-location, .c-posted {{ display: none; }}
    .row-meta {{ display: block; }}
    .c-bottom {{ justify-content: space-between; margin-top: 0.65rem; }}
  }}
</style>
</head>
<body>
<div class="topbar">
  <h1>Job Tracker</h1>
  <div class="sort-toggle" role="group" aria-label="Sort order">
    <button type="button" class="sort-btn active" data-sort="recent">Most recent</button>
    <button type="button" class="sort-btn" data-sort="firm">Firm</button>
  </div>
</div>

<section class="new">
  <h2>New today <span class="count" id="new-count">{len(new_today)}</span></h2>
  {_list(new_today, "Nothing new since the last check.", sortable=True)}
</section>

<section>
  <h2>Rest of the window <span class="count" id="rest-count">{len(rest)}</span></h2>
  {_list(rest, "Nothing else in the current window.", sortable=True)}
</section>

<section id="applied-section">
  <h2>Applied <span class="count" id="applied-count">0</span></h2>
  <div id="applied-list" class="list">{_header_row()}</div>
  <p class="empty" id="applied-empty">Nothing marked as applied yet.</p>
</section>

{errors_html}
<script>
var STORE_KEY = 'jobtracker_applied_v1';

function getApplied() {{
  try {{ return JSON.parse(localStorage.getItem(STORE_KEY)) || {{}}; }}
  catch (e) {{ return {{}}; }}
}}
function saveApplied(obj) {{ localStorage.setItem(STORE_KEY, JSON.stringify(obj)); }}

function renderApplied() {{
  var applied = getApplied();
  var uids = Object.keys(applied);
  var list = document.getElementById('applied-list');
  var empty = document.getElementById('applied-empty');
  document.getElementById('applied-count').textContent = uids.length;
  // wipe everything except the header row
  Array.prototype.slice.call(list.querySelectorAll('.row:not(.row-head)')).forEach(function(r) {{ r.remove(); }});
  if (uids.length === 0) {{ empty.style.display = ''; return; }}
  empty.style.display = 'none';
  uids.sort(function(a, b) {{ return (applied[b].at || '').localeCompare(applied[a].at || ''); }});
  uids.forEach(function(uid) {{
    var j = applied[uid];
    var row = document.createElement('div');
    row.className = 'row is-applied';
    row.innerHTML =
      '<div class="c-role"><span class="avatar ' + j.avCls + '">' + (j.company.slice(0,1).toUpperCase() || '?') + '</span>' +
      '<div class="role-text"><a href="' + j.url + '" target="_blank" rel="noopener">' + j.title + '</a>' +
      '<div class="row-meta">' + j.company + ' &middot; <span class="badge ' + j.catCls + '">' + j.sector + '</span> &middot; ' + j.location + '</div>' +
      '<div class="applied-date">Applied ' + j.at + '</div></div></div>' +
      '<div class="c-company">' + j.company + '</div>' +
      '<div class="c-sector"><span class="badge ' + j.catCls + '">' + j.sector + '</span></div>' +
      '<div class="c-location">' + j.location + '</div>' +
      '<div class="c-posted"></div>' +
      '<div class="c-bottom"><span class="badge ' + j.trackCls + '">' + j.track + '</span>' +
      '<button class="apply-btn remove" type="button" data-unmark="' + uid + '">Remove</button></div>';
    list.appendChild(row);
  }});
}}

function syncJobVisibility() {{
  var applied = getApplied();
  document.querySelectorAll('.row.job[data-uid]').forEach(function(row) {{
    row.classList.toggle('hide', !!applied[row.dataset.uid]);
  }});
}}

document.addEventListener('click', function(e) {{
  var markBtn = e.target.closest('.apply-btn:not(.remove)');
  if (markBtn) {{
    var row = markBtn.closest('.row[data-uid]');
    var applied = getApplied();
    applied[row.dataset.uid] = {{
      title: row.dataset.title, company: row.dataset.company, sector: row.dataset.sector,
      location: row.dataset.location, track: row.dataset.track, url: row.dataset.url,
      catCls: row.dataset.catCls, trackCls: row.dataset.trackCls,
      avCls: [].find.call(row.querySelectorAll('.avatar'), function() {{ return true; }})
             ? row.querySelector('.avatar').className.replace('avatar ', '') : 'av-0',
      at: new Date().toISOString().slice(0, 10)
    }};
    saveApplied(applied);
    row.classList.add('hide');
    renderApplied();
    return;
  }}
  var unmarkUid = e.target.getAttribute && e.target.getAttribute('data-unmark');
  if (unmarkUid) {{
    var applied = getApplied();
    delete applied[unmarkUid];
    saveApplied(applied);
    renderApplied();
    syncJobVisibility();
  }}
}});

function sortList(list, mode) {{
  var rows = Array.prototype.slice.call(list.querySelectorAll('.row.job'));
  rows.sort(function(a, b) {{
    if (mode === 'firm') {{
      var c = a.dataset.company.localeCompare(b.dataset.company);
      return c !== 0 ? c : (parseFloat(a.dataset.days) - parseFloat(b.dataset.days));
    }}
    var d = parseFloat(a.dataset.days) - parseFloat(b.dataset.days);
    return d !== 0 ? d : a.dataset.company.localeCompare(b.dataset.company);
  }});
  rows.forEach(function(row) {{ list.appendChild(row); }});
}}

document.querySelectorAll('.sort-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    document.querySelectorAll('.sort-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
    document.querySelectorAll('.sortable-list').forEach(function(list) {{
      sortList(list, btn.dataset.sort);
    }});
  }});
}});

syncJobVisibility();
renderApplied();
</script>
</body>
</html>
"""


def write_dashboard(open_jobs, new_jobs, stats, root_dir):
    docs_dir = os.path.join(root_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    path = os.path.join(docs_dir, "index.html")
    with open(path, "w") as f:
        f.write(render_html(open_jobs, new_jobs, stats))
    return path


def render_email_body(new_jobs):
    """Plain-text body for the 'just today's new roles' email - a small
    subset of what digest.md/index.html show (which list every open match)."""
    today = datetime.date.today().isoformat()
    grads, interns, remote, other = _group(new_jobs)
    out = [f"New roles - {today}", ""]
    out.append(_section("New-grad / full-time", grads))
    out.append(_section("Internships", interns))
    out.append(_section("Remote (school-year workable)", remote))
    out.append(_section("Other matches", other))
    return "\n".join(out) + "\n"


_LINKEDIN_LINKS = [
    # f_E=1,2 = Internship + Entry level only, so this stays undergrad-relevant.
    ("Jobs - energy/cleantech/critical minerals (entry-level, US)",
     "https://www.linkedin.com/jobs/search/?keywords=energy%20policy%20OR%20clean%20energy%20OR%20"
     "critical%20minerals%20OR%20supply%20chain&f_E=1%2C2&location=United%20States"),
    ("Jobs - foreign policy/China (entry-level, US)",
     "https://www.linkedin.com/jobs/search/?keywords=China%20OR%20foreign%20policy%20OR%20industrial%20policy&"
     "f_E=1%2C2&location=United%20States"),
    ("Posts - people announcing they're hiring (sorted by recent)",
     "https://www.linkedin.com/search/results/content/?keywords=hiring%20energy%20OR%20policy%20OR%20"
     "supply%20chain%20analyst&sortBy=%22date_posted%22"),
]


def render_manual_links(companies):
    manual = [c for c in companies if (c.get("ats") or "manual").lower() == "manual"]
    out = ["# Manual bookmarks", "",
           "Firms with no clean public ATS feed. Adzuna's broad net may still catch",
           "postings from these; check by hand weekly regardless.", ""]
    by_cat = {}
    for c in manual:
        by_cat.setdefault(c.get("category", "Other"), []).append(c)
    for cat in sorted(by_cat):
        out.append(f"### {cat}")
        out.append("")
        for c in sorted(by_cat[cat], key=lambda x: x["name"]):
            out.append(f"- [{c['name']}]({c.get('careers_url', '')})")
        out.append("")

    out.append("### LinkedIn (no free API - saved searches instead)")
    out.append("")
    out.append("LinkedIn has no public API for jobs or feed posts, and scraping it isn't")
    out.append("something this tracker does (against their ToS, real account-ban risk).")
    out.append("These are just pre-built search links - one click, no automation:")
    out.append("")
    for label, url in _LINKEDIN_LINKS:
        out.append(f"- [{label}]({url})")
    out.append("")
    return "\n".join(out) + "\n"


def write_manual_links(companies, data_dir):
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "manual_links.md")
    with open(path, "w") as f:
        f.write(render_manual_links(companies))
    return path


def write_outputs(open_jobs, new_this_run, stats, data_dir):
    os.makedirs(data_dir, exist_ok=True)

    md_path = os.path.join(data_dir, "digest.md")
    with open(md_path, "w") as f:
        f.write(render_markdown(open_jobs, stats))

    # CSV logs only genuinely-new roles, so no duplicates across intraday polls
    csv_path = os.path.join(data_dir, "new_jobs.csv")
    exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["date", "company", "category", "title", "location",
                        "role_type", "remote", "url"])
        today = datetime.date.today().isoformat()
        for j in new_this_run:
            w.writerow([today, j["company"], j["category"], j["title"],
                        j["location"], j["role_type"], j["remote"], j["url"]])

    return md_path, csv_path
