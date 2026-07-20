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


def _html_rows(jobs):
    rows = []
    for j in sorted(jobs, key=lambda x: (x["category"], x["company"])):
        loc = j["location"].strip() or "location unclear"
        tag = "REMOTE" if j["remote"] else loc
        haystack = _esc(f"{j['company']} {j['title']} {j['category']} {loc}").lower()
        rows.append(
            f'<li class="job" data-q="{haystack}">'
            f'<a href="{_esc(j["url"])}" target="_blank" rel="noopener">{_esc(j["title"])}</a>'
            f'<span class="meta">{_esc(j["company"])} &middot; {_esc(j["category"])} &middot; '
            f'{"<b>REMOTE</b>" if j["remote"] else _esc(tag)}</span></li>'
        )
    return "\n".join(rows)


def _html_section(title, jobs):
    if not jobs:
        return ""
    return (f'<section><h2>{_esc(title)} <span class="count">{len(jobs)}</span></h2>'
            f'<ul class="jobs">{_html_rows(jobs)}</ul></section>')


def render_html(recent_jobs, stats):
    today = datetime.date.today().isoformat()
    grads, interns, remote, other = _group(recent_jobs)

    body = (_html_section("New-grad / full-time", grads) +
            _html_section("Internships", interns) +
            _html_section("Remote (school-year workable)", remote) +
            _html_section("Other matches", other))
    if not recent_jobs:
        body = '<p class="empty">No new roles in the window. Boards checked, nothing new passed filters.</p>'

    errors_html = ""
    if stats.get("error_list"):
        items = "".join(f"<li>{_esc(n)}: {_esc(m)}</li>" for n, m in stats["error_list"])
        errors_html = f'<details><summary>Companies that failed this run</summary><ul>{items}</ul></details>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job digest - {today}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          max-width: 720px; margin: 0 auto; padding: 1rem 1.25rem 3rem;
          line-height: 1.4; }}
  h1 {{ font-size: 1.3rem; margin-bottom: 0.1rem; }}
  .stats {{ color: #888; font-size: 0.85rem; margin-bottom: 1rem; }}
  input#q {{ width: 100%; box-sizing: border-box; padding: 0.6rem 0.8rem;
             font-size: 1rem; border: 1px solid #999; border-radius: 8px;
             margin-bottom: 1.2rem; background: canvas; color: canvastext; }}
  h2 {{ font-size: 1rem; border-bottom: 1px solid #8884; padding-bottom: 0.3rem;
        margin-top: 1.6rem; }}
  .count {{ color: #888; font-weight: normal; }}
  ul.jobs {{ list-style: none; padding: 0; margin: 0.5rem 0; }}
  li.job {{ padding: 0.55rem 0; border-bottom: 1px solid #8882; }}
  li.job a {{ font-weight: 600; text-decoration: none; }}
  li.job a:hover {{ text-decoration: underline; }}
  li.job .meta {{ display: block; font-size: 0.85rem; color: #888; margin-top: 0.15rem; }}
  li.job.hide {{ display: none; }}
  .empty {{ color: #888; }}
  details {{ margin-top: 2rem; font-size: 0.85rem; color: #a55; }}
</style>
</head>
<body>
<h1>Job digest - {today}</h1>
<div class="stats">Window: last {stats.get('lookback', 30)}h &middot;
  companies checked: {stats.get('checked', 0)} &middot;
  errors: {stats.get('errors', 0)} &middot;
  total open matches: {stats.get('open', 0)}</div>
<input id="q" type="search" placeholder="Filter by company, title, or location&hellip;" oninput="filterJobs(this.value)">
{body}
{errors_html}
<script>
function filterJobs(q) {{
  q = q.trim().toLowerCase();
  document.querySelectorAll('li.job').forEach(function(li) {{
    li.classList.toggle('hide', q && li.dataset.q.indexOf(q) === -1);
  }});
  document.querySelectorAll('section').forEach(function(sec) {{
    var visible = sec.querySelectorAll('li.job:not(.hide)').length;
    sec.style.display = visible === 0 ? 'none' : '';
  }});
}}
</script>
</body>
</html>
"""


def write_dashboard(recent_jobs, stats, root_dir):
    docs_dir = os.path.join(root_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    path = os.path.join(docs_dir, "index.html")
    with open(path, "w") as f:
        f.write(render_html(recent_jobs, stats))
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
