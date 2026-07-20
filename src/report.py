"""Render the daily digest.

Two outputs:
  data/digest.md    readable on phone / in the repo, grouped for a morning skim.
                    Shows every role first seen in the last `lookback` hours, so
                    one morning read captures the whole prior day across polls.
  data/new_jobs.csv appendable log of every role ever surfaced (never lost, even
                    if you skip a day).

The digest leads with the three tracks that matter:
  1. Full-time / new-grad roles
  2. Internships
  3. Remote / San Diego roles (workable during the school year)
"""

import csv
import datetime
import os


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
    interns = [j for j in recent_jobs if j["role_type"] == "intern"]
    grads = [j for j in recent_jobs if j["role_type"] == "new_grad"]
    accounted = interns + grads
    remote = [j for j in recent_jobs if j["remote"] and j not in accounted]
    accounted = accounted + remote
    other = [j for j in recent_jobs if j not in accounted]

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
