"""Persist which jobs have been seen so each run surfaces only new ones.

State maps uid -> {first_seen, last_seen, title, company} with full UTC
timestamps. Two things come out of a run:
  - new_this_run: jobs whose uid was never seen before (append to the CSV log)
  - recent:       open jobs first seen within the lookback window (the digest)

Decoupling those two is what lets us poll often (low latency, good coverage)
while the committed digest still shows a clean rolling day of new roles.
"""

import json
import os
import datetime

PRUNE_DAYS = 21


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _parse(ts, default):
    try:
        dt = datetime.datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return default


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


def diff_and_update(state, open_jobs, lookback_hours=30):
    """Return (new_this_run, recent, updated_state).

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

    # rolling window: every open role first seen within lookback_hours, so a
    # single morning read captures everything found across the overnight polls
    cutoff = now - datetime.timedelta(hours=lookback_hours)
    recent = [j for j in open_jobs
              if _parse(state[j["uid"]]["first_seen"], now) >= cutoff]

    # prune roles that have been gone a while so a reopening re-triggers as new
    prune_cutoff = (now - datetime.timedelta(days=PRUNE_DAYS)).isoformat()
    for uid in list(state.keys()):
        if uid not in open_uids and state[uid].get("last_seen", "") < prune_cutoff:
            del state[uid]

    return new_this_run, recent, state
