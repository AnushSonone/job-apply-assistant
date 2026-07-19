from __future__ import annotations

import time

from . import config
from .alerts import format_job_message, should_alert
from .db import ScannerDatabase
from .diff import added_jobs
from .job_keys import stable_key
from .parser import parse_readme
from .telegram_client import TelegramClient
from .upstream import fetch_latest_upstream_sha, fetch_readme, fetch_readme_at_commit


def scan_once(
    db: ScannerDatabase | None = None,
    telegram: TelegramClient | None = None,
    *,
    notify: bool = True,
) -> list[tuple[str, str]]:
    """Diff upstream commits and alert only on rows added in the latest change."""
    db = db or ScannerDatabase(config.SCANNER_DB_PATH)
    telegram = telegram or TelegramClient()
    dry_run = config.SCAN_DRY_RUN

    new_sha = config.UPSTREAM_SHA or fetch_latest_upstream_sha()
    old_sha = db.get_sync_value("upstream_sha")

    if old_sha == new_sha:
        return []

    # Diff against the exact SHA we are about to record, not branch HEAD, so
    # the stored baseline always matches the content we actually compared.
    new_content = fetch_readme_at_commit(new_sha)
    if old_sha:
        old_content = fetch_readme_at_commit(old_sha)
        candidates = added_jobs(old_content, new_content)
    else:
        candidates = []

    jobs = parse_readme(new_content)
    for job in jobs:
        db.upsert_job(job)

    triggered: list[tuple[str, str]] = []
    for job in candidates:
        if not should_alert(job):
            continue

        row = db.get_job_by_stable_key(stable_key(job)) or db.get_job(job.id)
        if row and row["last_notified_at"]:
            continue

        triggered.append((job.id, "added"))
        label = f"{job.company} — {job.role} ({job.age})"
        if dry_run:
            print(f"[dry-run] would alert: {label}")
        elif notify and telegram.configured:
            telegram.send_message(format_job_message(job))

        if not dry_run:
            db.mark_notified(job.id)

    db.set_sync_value("upstream_sha", new_sha)
    return triggered


def watch() -> None:
    db = ScannerDatabase(config.SCANNER_DB_PATH)
    telegram = TelegramClient()
    print(f"Watching {config.README_URL} every {config.POLL_INTERVAL_SECONDS}s")

    if telegram.configured:
        telegram.send_message("job-apply-assistant watcher started (alert-only).")
    else:
        print("Telegram not configured — notifications disabled.")

    while True:
        try:
            hits = scan_once(db, telegram)
            if hits:
                print(f"Notified for {len(hits)} job(s): {hits}")
            else:
                print("No new active listings.")
        except Exception as exc:
            print(f"Scan error: {exc}")
            if telegram.configured:
                try:
                    telegram.send_message(f"⚠️ Scan error: {exc}")
                except Exception:
                    pass
        time.sleep(config.POLL_INTERVAL_SECONDS)
