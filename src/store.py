"""Persist which jobs have been seen so each run knows what's genuinely new.

State maps uid -> {first_seen, last_seen, title, company} with full UTC
timestamps. new_this_run is jobs whose uid was never seen before (appended to
the CSV log, and what the email/dashboard "New today" section is seeded
from). The dashboard/digest.md themselves show every currently-open match,
not just recent ones - state here is purely for dedup, not a display window.
"""

import json
import os
import datetime

PRUNE_DAYS = 21


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def load(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def save(path, state):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def diff_and_update(state, open_jobs):
    """Return (new_this_run, updated_state).

    open_jobs is the list of Job dicts passing filters this run.
    """
    now = _now()
    now_iso = now.isoformat()
    open_uids = {j["uid"] for j in open_jobs}

    new_this_run = []
    for j in open_jobs:
        rec = state.get(j["uid"])
        if rec is None:
            new_this_run.append(j)
            state[j["uid"]] = {"first_seen": now_iso, "last_seen": now_iso,
                               "title": j["title"], "company": j["company"]}
        else:
            rec["last_seen"] = now_iso

    # prune roles that have been gone a while so a reopening re-triggers as new
    prune_cutoff = (now - datetime.timedelta(days=PRUNE_DAYS)).isoformat()
    for uid in list(state.keys()):
        if uid not in open_uids and state[uid].get("last_seen", "") < prune_cutoff:
            del state[uid]

    return new_this_run, state
