"""Entry point. Run: python -m src.tracker

Loads config/companies.yaml and config/filters.yaml, pulls each company from
its ATS, filters and tags the postings, diffs against data/seen.json, and writes
data/digest.md + data/new_jobs.csv + docs/index.html (GitHub Pages dashboard).
digest.md and the dashboard both show every currently-open matching job, not
just ones seen recently - state (data/seen.json) is only used to tell which
ones are genuinely new since the last run. If email delivery is on, it sends
just that new-this-run set, after a quick liveness check.
"""

import os
import sys
import yaml

from src.ats import greenhouse, lever, ashby, workday, adzuna, usajobs
from src import filtering, store, report, notify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config")
DATA = os.path.join(ROOT, "data")
SEEN = os.path.join(DATA, "seen.json")
DOTENV = os.path.join(ROOT, ".env")


def load_dotenv():
    """Load KEY=VALUE lines from .env into os.environ, for local runs. Never
    overrides a var already set (so real secrets in Actions always win)."""
    if not os.path.exists(DOTENV):
        return
    with open(DOTENV) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def load_yaml(name):
    with open(os.path.join(CONFIG, name)) as f:
        return yaml.safe_load(f)


def pull_company(c):
    """Dispatch one company entry to the right ATS client. Returns raw list."""
    ats = (c.get("ats") or "manual").lower()
    if ats == "greenhouse":
        return greenhouse.fetch(c["slug"])
    if ats == "lever":
        return lever.fetch(c["slug"])
    if ats == "ashby":
        return ashby.fetch(c["slug"])
    if ats == "workday":
        return workday.fetch(c["workday"])
    # 'manual' companies are not auto-pulled; Adzuna net (below) may catch them
    return []


def run():
    load_dotenv()
    companies = load_yaml("companies.yaml")["companies"]
    filters = load_yaml("filters.yaml")

    report.write_manual_links(companies, DATA)

    all_open = []
    errors = []
    checked = 0

    for c in companies:
        name = c["name"]
        category = c.get("category", "")
        if (c.get("ats") or "manual").lower() == "manual":
            continue
        checked += 1
        try:
            raw = pull_company(c)
            jobs = filtering.filter_jobs(raw, name, category, filters)
            all_open.extend(jobs)
        except Exception as e:
            errors.append((name, f"{type(e).__name__}: {e}"))

    # optional broad net for manual/bespoke firms
    if adzuna.available() and filters.get("adzuna", {}).get("enabled"):
        manual_names = {c["name"].lower() for c in companies
                        if (c.get("ats") or "manual").lower() == "manual"}
        cats = {c["name"].lower(): c.get("category", "") for c in companies}
        for query in filters["adzuna"].get("queries", []):
            what = query.get("what", "")
            where = query.get("where", "")
            try:
                raw = adzuna.fetch(what, where)
            except Exception as e:
                errors.append((f"adzuna:{what}", str(e)))
                continue
            for r in raw:
                comp = (r.get("_company") or "").lower()
                # only keep Adzuna hits that match a firm on the list
                match = next((n for n in manual_names if n and n in comp), None)
                if not match:
                    continue
                jobs = filtering.filter_jobs([r], r.get("_company", "Unknown"),
                                             cats.get(match, "Other"), filters)
                all_open.extend(jobs)

    # optional federal source (energy-policy track: DOE, FERC, EPA, EIA)
    if usajobs.available() and filters.get("usajobs", {}).get("enabled"):
        for kw in filters["usajobs"].get("keywords", []):
            try:
                raw = usajobs.fetch(kw)
            except Exception as e:
                errors.append((f"usajobs:{kw}", str(e)))
                continue
            for r in raw:
                jobs = filtering.filter_jobs([r], r.get("_company", "Federal"),
                                             "Government", filters)
                all_open.extend(jobs)

    # dedupe by uid
    seen_uid = {}
    for j in all_open:
        seen_uid[j["uid"]] = j
    all_open = list(seen_uid.values())

    state = store.load(SEEN)
    new_jobs, state = store.diff_and_update(state, all_open)
    store.save(SEEN, state)

    # Link-check everything actually shown (dashboard + digest.md + email),
    # not what's tracked as seen - a dead link shouldn't affect dedupe/state,
    # only presentation. Checked in parallel since this can be a few hundred.
    open_live = notify.filter_live(all_open)
    live_uids = {j["uid"] for j in open_live}
    new_jobs_live = [j for j in new_jobs if j["uid"] in live_uids]

    stats = {"checked": checked, "errors": len(errors),
             "open": len(all_open), "error_list": errors}
    md_path, csv_path = report.write_outputs(open_live, new_jobs, stats, DATA)
    report.write_dashboard(open_live, new_jobs_live, stats, ROOT)

    if new_jobs_live and filters.get("delivery", {}).get("email", {}).get("enabled") and notify.available():
        try:
            subject = f"{len(new_jobs_live)} new job{'s' if len(new_jobs_live) != 1 else ''} today"
            notify.send_digest(subject, report.render_email_body(new_jobs_live))
        except Exception as e:
            errors.append(("email delivery", f"{type(e).__name__}: {e}"))

    dead = len(all_open) - len(open_live)
    print(f"Checked {checked} companies. {len(open_live)} open matches "
          f"({dead} dropped as dead links), {len(new_jobs_live)} new this run. "
          f"{len(errors)} errors.")
    print(f"Digest: {md_path}")
    if errors:
        print("Errors:")
        for n, m in errors:
            print(f"  {n}: {m}")


if __name__ == "__main__":
    run()
