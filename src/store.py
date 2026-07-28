"""Persist which jobs have been seen so each run knows what's genuinely new.

State maps uid -> {first_seen, last_seen, title, company} with full UTC
timestamps. new_this_run is jobs whose uid was never seen before AND whose
company+title fingerprint wasn't seen recently either (a source reposting the
same role under a new job_id doesn't count as new - see REPOST_SUPPRESS_DAYS).
It's appended to the CSV log, and is what the email/dashboard "New today"
section is seeded from. The dashboard/digest.md themselves show every
currently-open match, not just recent ones - state here is purely for dedup,
not a display window.
"""

import json
import os
import re
import datetime

PRUNE_DAYS = 21

# A source can repost the same role under a brand new job_id (e.g. a company
# closing and reopening a req on Greenhouse) - the uid changes, so naively
# it looks "new" again even though it's the same posting. To catch that, we
# also track a company+title fingerprint; a fresh uid whose fingerprint was
# already seen recently is treated as a repost, not a new find. Fingerprint
# keys are stored in the same flat state dict under a "_fp:" prefix, which
# never collides with a real uid (uids are always "source:company:job_id").
REPOST_SUPPRESS_DAYS = 14


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _fingerprint(job):
    def norm(s):
        s = re.sub(r"[^a-z0-9]+", " ", (s or "").lower())
        return re.sub(r"\s+", " ", s).strip()
    return f"_fp:{norm(job['company'])}|{norm(job['title'])}"


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
    repost_cutoff = (now - datetime.timedelta(days=REPOST_SUPPRESS_DAYS)).isoformat()

    new_this_run = []
    for j in open_jobs:
        rec = state.get(j["uid"])
        fp = _fingerprint(j)
        if rec is None:
            fp_rec = state.get(fp)
            is_repost = fp_rec is not None and fp_rec.get("last_seen", "") >= repost_cutoff
            if not is_repost:
                new_this_run.append(j)
            state[j["uid"]] = {"first_seen": now_iso, "last_seen": now_iso,
                               "title": j["title"], "company": j["company"]}
        else:
            rec["last_seen"] = now_iso
        state[fp] = {"last_seen": now_iso}

    # prune roles that have been gone a while so a reopening re-triggers as new
    prune_cutoff = (now - datetime.timedelta(days=PRUNE_DAYS)).isoformat()
    for uid in list(state.keys()):
        if uid.startswith("_fp:"):
            continue
        if uid not in open_uids and state[uid].get("last_seen", "") < prune_cutoff:
            del state[uid]

    # fingerprints prune on the same schedule as the repost-suppression window
    # they exist to serve, once nothing open still carries that fingerprint
    open_fps = {_fingerprint(j) for j in open_jobs}
    for fp_key in list(state.keys()):
        if fp_key.startswith("_fp:") and fp_key not in open_fps \
                and state[fp_key].get("last_seen", "") < repost_cutoff:
            del state[fp_key]

    return new_this_run, state
