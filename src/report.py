"""Render the daily digest.

Three outputs:
  data/digest.md    readable on phone / in the repo, grouped for a morning skim.
                    Shows every role first seen in the last `lookback` hours, so
                    one morning read captures the whole prior day across polls.
  data/new_jobs.csv appendable log of every role ever surfaced (never lost, even
                    if you skip a day).
  docs/index.html   same data as digest.md, styled + searchable, served free via
                    GitHub Pages so there's a live link instead of a repo file.

The digest leads with the three tracks that matter:
  1. Full-time / new-grad roles
  2. Internships
  3. Remote / San Diego roles (workable during the school year)
"""

import csv
import datetime
import html
import os


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


def render_markdown(recent_jobs, stats):
    today = datetime.date.today().isoformat()
    grads, interns, remote, other = _group(recent_jobs)

    out = [f"# Job digest - {today}", ""]
    if not recent_jobs:
        out.append("No new roles in the window. Boards checked, nothing new passed filters.")
        out.append("")
    else:
        out.append(f"**{len(recent_jobs)} new roles** across "
                   f"{len({j['company'] for j in recent_jobs})} firms.")
        out.append("")
        out.append(_section("New-grad / full-time", grads))
        out.append(_section("Internships", interns))
        out.append(_section("Remote (school-year workable)", remote))
        out.append(_section("Other matches", other))

    out.append("---")
    out.append(f"_Window: last {stats.get('lookback', 30)}h. "
               f"Companies checked: {stats.get('checked', 0)}, "
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


def _category_class(category):
    # Deterministic (not Python's randomized hash()) so colors are stable run
    # to run instead of reshuffling every time the tracker restarts.
    idx = sum(ord(c) for c in category) % CATEGORY_PALETTE_SIZE
    return f"cat-{idx}"


def _table_rows(jobs):
    rows = []
    for j in sorted(jobs, key=lambda x: (TRACK_ORDER.get(x["role_type"], 9),
                                          x["category"], x["company"])):
        loc = "Remote" if j["remote"] else (j["location"].strip() or "Unclear")
        track = TRACK_LABEL.get(j["role_type"], "Other")
        track_cls = TRACK_CLASS.get(j["role_type"], "t-other")
        cat_cls = _category_class(j["category"])
        rows.append(f"""<tr class="job" data-uid="{_esc(j['uid'])}" data-title="{_esc(j['title'])}"
    data-company="{_esc(j['company'])}" data-sector="{_esc(j['category'])}"
    data-location="{_esc(loc)}" data-track="{track}" data-url="{_esc(j['url'])}">
  <td class="c-role" data-label="Role"><a href="{_esc(j['url'])}" target="_blank" rel="noopener">{_esc(j['title'])}</a></td>
  <td data-label="Company">{_esc(j['company'])}</td>
  <td data-label="Sector"><span class="badge {cat_cls}">{_esc(j['category'])}</span></td>
  <td data-label="Location">{_esc(loc)}</td>
  <td data-label="Track"><span class="badge {track_cls}">{track}</span></td>
  <td class="c-apply" data-label=""><button class="apply-btn" type="button">Mark applied</button></td>
</tr>""")
    return "\n".join(rows)


def _table(jobs, empty_msg):
    if not jobs:
        return f'<p class="empty">{_esc(empty_msg)}</p>'
    return f"""<div class="table-wrap"><table>
<thead><tr><th>Role</th><th>Company</th><th>Sector</th><th>Location</th><th>Track</th><th></th></tr></thead>
<tbody>{_table_rows(jobs)}</tbody>
</table></div>"""


def render_html(recent_jobs, new_jobs, stats):
    today = datetime.date.today().isoformat()
    new_uids = {j["uid"] for j in new_jobs}
    rest = [j for j in recent_jobs if j["uid"] not in new_uids]

    errors_html = ""
    if stats.get("error_list"):
        items = "".join(f"<li>{_esc(n)}: {_esc(m)}</li>" for n, m in stats["error_list"])
        errors_html = (f'<details><summary>Companies that failed this run '
                       f'({stats.get("errors", 0)})</summary><ul>{items}</ul></details>')

    cat_vars_light = []
    cat_vars_dark = []
    # 10-hue categorical palette, pastel-on-light / desaturated-on-dark.
    palette = [
        ("#fee2e2", "#991b1b", "#451a1a", "#fca5a5"),
        ("#ffedd5", "#9a3412", "#431407", "#fdba74"),
        ("#fef3c7", "#92400e", "#451a03", "#fcd34d"),
        ("#ecfccb", "#3f6212", "#1a2e05", "#bef264"),
        ("#ccfbf1", "#115e59", "#042f2e", "#5eead4"),
        ("#cffafe", "#155e75", "#083344", "#67e8f9"),
        ("#dbeafe", "#1e40af", "#1e3a5f", "#93c5fd"),
        ("#e0e7ff", "#3730a3", "#1e1b4b", "#a5b4fc"),
        ("#ede9fe", "#5b21b6", "#2e1065", "#c4b5fd"),
        ("#fce7f3", "#9d174d", "#500724", "#f9a8d4"),
    ]
    cat_css_light = "\n".join(f"  .cat-{i} {{ background:{bg}; color:{fg}; }}"
                              for i, (bg, fg, _, _) in enumerate(palette))
    cat_css_dark = "\n".join(f"    .cat-{i} {{ background:{bg}; color:{fg}; }}"
                             for i, (_, _, bg, fg) in enumerate(palette))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Tracker</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    color-scheme: light dark;
    --bg: #ffffff; --card: #f8fafc; --text: #14181f; --muted: #6b7280;
    --border: #e5e7eb; --accent: #2563eb; --new-bg: #eff6ff; --new-border: #bfdbfe;
    --t-grad-bg: #dbeafe; --t-grad-fg: #1e40af;
    --t-intern-bg: #dcfce7; --t-intern-fg: #166534;
    --t-other-bg: #f1f5f9; --t-other-fg: #475569;
  }}
{cat_css_light}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0b0f17; --card: #10151f; --text: #e6e8eb; --muted: #9aa4b2;
      --border: #232a36; --accent: #60a5fa; --new-bg: #0f1c33; --new-border: #1e3a5f;
      --t-grad-bg: #1e3a5f; --t-grad-fg: #93c5fd;
      --t-intern-bg: #14352380; --t-intern-fg: #86efac;
      --t-other-bg: #1a2130; --t-other-fg: #9aa4b2;
    }}
{cat_css_dark}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: 'Inter', ui-sans-serif, -apple-system, BlinkMacSystemFont, sans-serif;
    max-width: 1040px; margin: 0 auto; padding: 1.75rem 1.25rem 4rem;
    line-height: 1.45; background: var(--bg); color: var(--text);
    -webkit-font-smoothing: antialiased; font-feature-settings: "cv11", "ss01";
  }}
  h1 {{ font-size: 1.5rem; font-weight: 800; letter-spacing: -0.02em; margin: 0 0 1.6rem; }}
  h2 {{
    font-size: 1.05rem; font-weight: 700; margin: 2.2rem 0 0.7rem;
    display: flex; align-items: baseline; gap: 0.5rem;
  }}
  h2 .count {{
    color: var(--muted); font-weight: 600; font-size: 0.8rem; background: var(--card);
    border: 1px solid var(--border); border-radius: 999px; padding: 0.1rem 0.55rem;
  }}
  .new h2 {{ color: var(--accent); }}
  .table-wrap {{
    border: 1px solid var(--border); border-radius: 12px; overflow: hidden;
    background: var(--card);
  }}
  .new .table-wrap {{ background: var(--new-bg); border-color: var(--new-border); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; table-layout: fixed; }}
  th:nth-child(1), td:nth-child(1) {{ width: 32%; }}
  th:nth-child(2), td:nth-child(2) {{ width: 19%; }}
  th:nth-child(3), td:nth-child(3) {{ width: 17%; }}
  th:nth-child(4), td:nth-child(4) {{ width: 15%; }}
  th:nth-child(5), td:nth-child(5) {{ width: 10%; }}
  th:nth-child(6), td:nth-child(6) {{ width: 7%; }}
  thead th {{
    text-align: left; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em;
    color: var(--muted); font-weight: 650; padding: 0.65rem 0.9rem; border-bottom: 1px solid var(--border);
  }}
  tbody td {{ padding: 0.65rem 0.9rem; border-bottom: 1px solid var(--border); vertical-align: top;
              overflow-wrap: break-word; }}
  tbody tr:last-child td {{ border-bottom: none; }}
  tbody tr:hover {{ background: color-mix(in srgb, var(--accent) 6%, transparent); }}
  .c-role a {{ font-weight: 620; text-decoration: none; color: var(--text); }}
  .c-role a:hover {{ color: var(--accent); text-decoration: underline; }}
  .applied-date {{ color: var(--muted); font-size: 0.78rem; margin-top: 0.15rem; }}
  .badge {{
    display: inline-block; font-size: 0.72rem; font-weight: 650; padding: 0.15rem 0.55rem;
    border-radius: 999px; white-space: nowrap;
  }}
  .t-grad {{ background: var(--t-grad-bg); color: var(--t-grad-fg); }}
  .t-intern {{ background: var(--t-intern-bg); color: var(--t-intern-fg); }}
  .t-other {{ background: var(--t-other-bg); color: var(--t-other-fg); }}
  .apply-btn {{
    font-family: inherit; font-size: 0.76rem; font-weight: 600; padding: 0.3rem 0.6rem;
    border-radius: 7px; border: 1px solid var(--border); background: var(--bg);
    color: var(--text); cursor: pointer; white-space: nowrap;
  }}
  .apply-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  .apply-btn.remove {{ color: #b91c1c; }}
  .apply-btn.remove:hover {{ border-color: #b91c1c; }}
  .empty {{ color: var(--muted); font-size: 0.9rem; padding: 0.5rem 0; }}
  .job.hide {{ display: none; }}
  details {{ margin-top: 2.5rem; font-size: 0.85rem; color: #b45309; }}
  details summary {{ cursor: pointer; }}
  @media (max-width: 680px) {{
    thead {{ display: none; }}
    table, tbody, tr, td {{ display: block; width: 100% !important; }}
    tbody tr {{ padding: 0.7rem 0.9rem; border-bottom: 1px solid var(--border); }}
    tbody tr:last-child {{ border-bottom: none; }}
    tbody td {{ border: none; padding: 0.15rem 0; }}
    tbody td[data-label]:not([data-label=""])::before {{
      content: attr(data-label) ": "; color: var(--muted); font-size: 0.78rem;
    }}
    .c-role {{ padding-bottom: 0.3rem !important; font-size: 1rem; }}
    .c-apply {{ padding-top: 0.4rem !important; }}
  }}
</style>
</head>
<body>
<h1>Job Tracker</h1>

<section class="new">
  <h2>New today <span class="count" id="new-count">{len(new_jobs)}</span></h2>
  {_table(new_jobs, "Nothing new since the last check.")}
</section>

<section>
  <h2>Rest of the window <span class="count" id="rest-count">{len(rest)}</span></h2>
  {_table(rest, "Nothing else in the current window.")}
</section>

<section id="applied-section">
  <h2>Applied <span class="count" id="applied-count">0</span></h2>
  <div class="table-wrap"><table>
    <thead><tr><th>Role</th><th>Company</th><th>Sector</th><th>Location</th><th>Track</th><th></th></tr></thead>
    <tbody id="applied-tbody"></tbody>
  </table></div>
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
  var tbody = document.getElementById('applied-tbody');
  var empty = document.getElementById('applied-empty');
  document.getElementById('applied-count').textContent = uids.length;
  if (uids.length === 0) {{
    tbody.innerHTML = '';
    empty.style.display = '';
    return;
  }}
  empty.style.display = 'none';
  uids.sort(function(a, b) {{ return (applied[b].at || '').localeCompare(applied[a].at || ''); }});
  tbody.innerHTML = uids.map(function(uid) {{
    var j = applied[uid];
    return '<tr>' +
      '<td class="c-role"><a href="' + j.url + '" target="_blank" rel="noopener">' + j.title + '</a>' +
      '<div class="applied-date">Applied ' + j.at + '</div></td>' +
      '<td>' + j.company + '</td>' +
      '<td><span class="badge ' + j.catCls + '">' + j.sector + '</span></td>' +
      '<td>' + j.location + '</td>' +
      '<td><span class="badge ' + j.trackCls + '">' + j.track + '</span></td>' +
      '<td><button class="apply-btn remove" type="button" data-unmark="' + uid + '">Remove</button></td>' +
      '</tr>';
  }}).join('');
}}

function syncJobVisibility() {{
  var applied = getApplied();
  document.querySelectorAll('tr.job[data-uid]').forEach(function(tr) {{
    tr.classList.toggle('hide', !!applied[tr.dataset.uid]);
  }});
}}

document.addEventListener('click', function(e) {{
  var markBtn = e.target.closest('.apply-btn:not(.remove)');
  if (markBtn) {{
    var tr = markBtn.closest('tr.job');
    var applied = getApplied();
    applied[tr.dataset.uid] = {{
      title: tr.dataset.title, company: tr.dataset.company, sector: tr.dataset.sector,
      location: tr.dataset.location, track: tr.dataset.track, url: tr.dataset.url,
      catCls: [].find.call(tr.querySelectorAll('.badge'), function(b) {{ return b.className.indexOf('cat-') !== -1; }}).className.replace('badge ', ''),
      trackCls: [].find.call(tr.querySelectorAll('.badge'), function(b) {{ return b.className.indexOf('t-') !== -1; }}).className.replace('badge ', ''),
      at: new Date().toISOString().slice(0, 10)
    }};
    saveApplied(applied);
    tr.classList.add('hide');
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

syncJobVisibility();
renderApplied();
</script>
</body>
</html>
"""


def write_dashboard(recent_jobs, new_jobs, stats, root_dir):
    docs_dir = os.path.join(root_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    path = os.path.join(docs_dir, "index.html")
    with open(path, "w") as f:
        f.write(render_html(recent_jobs, new_jobs, stats))
    return path


def render_email_body(new_jobs):
    """Plain-text body for the 'just today's new roles' email - a small
    subset of what digest.md/index.html show, not the full lookback window."""
    today = datetime.date.today().isoformat()
    grads, interns, remote, other = _group(new_jobs)
    out = [f"New roles - {today}", ""]
    out.append(_section("New-grad / full-time", grads))
    out.append(_section("Internships", interns))
    out.append(_section("Remote (school-year workable)", remote))
    out.append(_section("Other matches", other))
    return "\n".join(out) + "\n"


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
    return "\n".join(out) + "\n"


def write_manual_links(companies, data_dir):
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "manual_links.md")
    with open(path, "w") as f:
        f.write(render_manual_links(companies))
    return path


def write_outputs(recent_jobs, new_this_run, stats, data_dir):
    os.makedirs(data_dir, exist_ok=True)

    md_path = os.path.join(data_dir, "digest.md")
    with open(md_path, "w") as f:
        f.write(render_markdown(recent_jobs, stats))

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
