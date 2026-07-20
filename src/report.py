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


def _table_rows(jobs):
    rows = []
    for j in sorted(jobs, key=lambda x: (TRACK_ORDER.get(x["role_type"], 9),
                                          x["category"], x["company"])):
        loc = "Remote" if j["remote"] else (j["location"].strip() or "Unclear")
        track = TRACK_LABEL.get(j["role_type"], "Other")
        track_cls = TRACK_CLASS.get(j["role_type"], "t-other")
        haystack = _esc(f"{j['company']} {j['title']} {j['category']} {loc}").lower()
        rows.append(f"""<tr class="job" data-q="{haystack}">
  <td class="c-role" data-label="Role"><a href="{_esc(j['url'])}" target="_blank" rel="noopener">{_esc(j['title'])}</a></td>
  <td data-label="Company">{_esc(j['company'])}</td>
  <td data-label="Sector">{_esc(j['category'])}</td>
  <td data-label="Location">{_esc(loc)}</td>
  <td data-label="Track"><span class="badge {track_cls}">{track}</span></td>
</tr>""")
    return "\n".join(rows)


def _table(jobs, empty_msg):
    if not jobs:
        return f'<p class="empty">{_esc(empty_msg)}</p>'
    return f"""<div class="table-wrap"><table>
<thead><tr><th>Role</th><th>Company</th><th>Sector</th><th>Location</th><th>Track</th></tr></thead>
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

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job digest - {today}</title>
<style>
  :root {{
    color-scheme: light dark;
    --bg: #ffffff; --card: #f8fafc; --text: #14181f; --muted: #6b7280;
    --border: #e5e7eb; --accent: #2563eb; --new-bg: #eff6ff; --new-border: #bfdbfe;
    --grad-bg: #dbeafe; --grad-text: #1e40af;
    --intern-bg: #dcfce7; --intern-text: #166534;
    --other-bg: #f1f5f9; --other-text: #475569;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0b0f17; --card: #10151f; --text: #e6e8eb; --muted: #9aa4b2;
      --border: #232a36; --accent: #60a5fa; --new-bg: #0f1c33; --new-border: #1e3a5f;
      --grad-bg: #1e3a5f; --grad-text: #93c5fd;
      --intern-bg: #14352380; --intern-text: #86efac;
      --other-bg: #1a2130; --other-text: #9aa4b2;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 980px; margin: 0 auto; padding: 1.75rem 1.25rem 4rem;
    line-height: 1.45; background: var(--bg); color: var(--text);
    -webkit-font-smoothing: antialiased;
  }}
  h1 {{ font-size: 1.55rem; font-weight: 750; letter-spacing: -0.02em; margin: 0 0 0.2rem; }}
  .stats {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 1.4rem; }}
  input#q {{
    width: 100%; box-sizing: border-box; padding: 0.7rem 0.9rem; font-size: 0.95rem;
    border: 1px solid var(--border); border-radius: 10px; margin-bottom: 1.8rem;
    background: var(--card); color: var(--text); outline: none;
  }}
  input#q:focus {{ border-color: var(--accent); }}
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
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  thead th {{
    text-align: left; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em;
    color: var(--muted); font-weight: 650; padding: 0.65rem 0.9rem; border-bottom: 1px solid var(--border);
  }}
  tbody td {{ padding: 0.65rem 0.9rem; border-bottom: 1px solid var(--border); vertical-align: top; }}
  tbody tr:last-child td {{ border-bottom: none; }}
  tbody tr:hover {{ background: color-mix(in srgb, var(--accent) 6%, transparent); }}
  .c-role a {{ font-weight: 620; text-decoration: none; color: var(--text); }}
  .c-role a:hover {{ color: var(--accent); text-decoration: underline; }}
  .badge {{
    display: inline-block; font-size: 0.72rem; font-weight: 650; padding: 0.15rem 0.55rem;
    border-radius: 999px; white-space: nowrap;
  }}
  .t-grad {{ background: var(--grad-bg); color: var(--grad-text); }}
  .t-intern {{ background: var(--intern-bg); color: var(--intern-text); }}
  .t-other {{ background: var(--other-bg); color: var(--other-text); }}
  .empty {{ color: var(--muted); font-size: 0.9rem; padding: 0.5rem 0; }}
  .job.hide {{ display: none; }}
  details {{ margin-top: 2.5rem; font-size: 0.85rem; color: #b45309; }}
  details summary {{ cursor: pointer; }}
  @media (max-width: 680px) {{
    thead {{ display: none; }}
    table, tbody, tr, td {{ display: block; width: 100%; }}
    tbody tr {{ padding: 0.7rem 0.9rem; border-bottom: 1px solid var(--border); }}
    tbody tr:last-child {{ border-bottom: none; }}
    tbody td {{ border: none; padding: 0.12rem 0; }}
    tbody td[data-label]:not(.c-role)::before {{
      content: attr(data-label) ": "; color: var(--muted); font-size: 0.78rem;
    }}
    .c-role {{ padding-bottom: 0.25rem !important; font-size: 1rem; }}
  }}
</style>
</head>
<body>
<h1>Job digest - {today}</h1>
<div class="stats">Window: last {stats.get('lookback', 30)}h &middot;
  companies checked: {stats.get('checked', 0)} &middot;
  errors: {stats.get('errors', 0)} &middot;
  total open matches: {stats.get('open', 0)}</div>
<input id="q" type="search" placeholder="Filter by company, title, or location&hellip;" oninput="filterJobs(this.value)">

<section class="new">
  <h2>New today <span class="count">{len(new_jobs)}</span></h2>
  {_table(new_jobs, "Nothing new since the last check.")}
</section>

<section>
  <h2>Rest of the window <span class="count">{len(rest)}</span></h2>
  {_table(rest, "Nothing else in the current window.")}
</section>

{errors_html}
<script>
function filterJobs(q) {{
  q = q.trim().toLowerCase();
  document.querySelectorAll('tr.job').forEach(function(tr) {{
    tr.classList.toggle('hide', q && tr.dataset.q.indexOf(q) === -1);
  }});
}}
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
