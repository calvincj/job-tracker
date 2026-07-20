"""Optional email delivery of the digest (Gmail SMTP, free).

Off by default. Turn on with `delivery.email.enabled: true` in filters.yaml and
set these env vars (GitHub: repo Settings > Secrets and variables > Actions):
  GMAIL_USER          the sending Gmail address
  GMAIL_APP_PASSWORD  a Gmail app password (not your login password) -
                       generate one at https://myaccount.google.com/apppasswords
  DIGEST_TO_EMAIL     where to send it (defaults to GMAIL_USER if unset)

Uses Gmail's SMTP relay (smtp.gmail.com:587, STARTTLS) - no third-party API,
no cost.
"""

import concurrent.futures
import os
import smtplib
import requests
from email.message import EmailMessage

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
LINK_CHECK_TIMEOUT = 10
LINK_CHECK_WORKERS = 12


def available():
    return bool(os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD"))


def is_link_live(url):
    """HTTP-level liveness check for a single job URL: drops hard 404s/dead
    domains. Fails open (treats errors/timeouts as live) so a flaky network
    blip never silently drops a good link.

    Known gap: Ashby-hosted postings are a client-rendered SPA that returns
    200 for any URL shape, including ones that render "Page not found" in
    the browser - their server and their own listing API can disagree with
    each other. Catching that specific case would need a real browser (e.g.
    headless Chrome) rendering every link, which is a meaningfully heavier
    and slower pipeline; skipped for now as a known, occasional false-live."""
    headers = {"User-Agent": "personal-job-tracker"}
    try:
        r = requests.head(url, timeout=LINK_CHECK_TIMEOUT, allow_redirects=True,
                          headers=headers)
        if r.status_code == 405:  # some ATS boards reject HEAD
            r = requests.get(url, timeout=LINK_CHECK_TIMEOUT, headers=headers,
                             stream=True)
        return r.status_code < 400
    except requests.RequestException:
        return True


def filter_live(jobs):
    """Checks links in parallel - meant for the full open-jobs set (can be a
    few hundred), so a sequential pass would be too slow."""
    if not jobs:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=LINK_CHECK_WORKERS) as ex:
        live = list(ex.map(lambda j: is_link_live(j["url"]), jobs))
    return [j for j, ok in zip(jobs, live) if ok]


def send_digest(subject, body_markdown):
    """Send the digest body as a plain-text email. Raises on failure so the
    caller can catch it and keep the run failing soft."""
    user = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    to_addr = os.environ.get("DIGEST_TO_EMAIL", user)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(body_markdown)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
