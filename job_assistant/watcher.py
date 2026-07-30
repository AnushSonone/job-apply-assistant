from __future__ import annotations

import time

from . import config
from .alerts import format_job_message, should_alert
from .db import ScannerDatabase
from .diff import added_jobs
from .job_keys import stable_key
from .parser import parse_readme
from .telegram_client import TelegramClient
from .upstream import (
    fetch_latest_sha_for_source,
    fetch_readme,
    fetch_source_readme_at_commit,
)


def scan_source(
    source: config.Source,
    db: ScannerDatabase,
    telegram: TelegramClient,
    *,
    notify: bool = True,
) -> list[tuple[str, str]]:
    """Diff one upstream README and alert only on rows added in the latest change."""
    dry_run = config.SCAN_DRY_RUN

    new_sha = config.PINNED_SHAS.get(source.key) or fetch_latest_sha_for_source(source)
    old_sha = db.get_sync_value(source.sync_key)

    if old_sha == new_sha:
        return []

    # Diff against the exact SHA we are about to record, not branch HEAD, so
    # the stored baseline always matches the content we actually compared.
    new_content = fetch_source_readme_at_commit(source, new_sha)
    if old_sha:
        old_content = fetch_source_readme_at_commit(source, old_sha)
        candidates = added_jobs(old_content, new_content, source.key)
    else:
        # First sight of a source: seed the baseline, never alert on the backlog.
        candidates = []

    for job in parse_readme(new_content, source.key):
        db.upsert_job(job)

    triggered: list[tuple[str, str]] = []
    for job in candidates:
        if not should_alert(job):
            continue

        # A posting listed in two READMEs is still one job: the stable key
        # lookup sees the earlier notification and skips the duplicate.
        row = db.get_job_by_stable_key(stable_key(job)) or db.get_job(job.id)
        if row and row["last_notified_at"]:
            continue

        triggered.append((job.id, "added"))
        label = f"{job.company} — {job.role} ({job.age}) [{source.key}]"
        if dry_run:
            print(f"[dry-run] would alert: {label}")
        elif notify and telegram.configured:
            telegram.send_message(format_job_message(job))

        if not dry_run:
            db.mark_notified(job.id)

    db.set_sync_value(source.sync_key, new_sha)
    return triggered


def scan_once(
    db: ScannerDatabase | None = None,
    telegram: TelegramClient | None = None,
    *,
    notify: bool = True,
) -> list[tuple[str, str]]:
    """Scan every enabled source. One failing source must not skip the others."""
    db = db or ScannerDatabase(config.SCANNER_DB_PATH)
    telegram = telegram or TelegramClient()

    triggered: list[tuple[str, str]] = []
    errors: list[str] = []
    for source in config.SOURCES:
        try:
            triggered.extend(scan_source(source, db, telegram, notify=notify))
        except Exception as exc:
            errors.append(f"{source.display}: {exc}")
            print(f"Scan error for {source.key}: {exc}")

    if errors and len(errors) == len(config.SOURCES):
        raise RuntimeError("; ".join(errors))
    return triggered


def watch() -> None:
    db = ScannerDatabase(config.SCANNER_DB_PATH)
    telegram = TelegramClient()
    for source in config.SOURCES:
        print(f"Watching {source.readme_url}")
    print(f"Poll interval: {config.POLL_INTERVAL_SECONDS}s")

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
