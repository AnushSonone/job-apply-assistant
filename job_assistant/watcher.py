from __future__ import annotations

import hashlib
import time

import httpx

from . import config
from .db import ScannerDatabase
from .parser import parse_readme
from .resume import format_job_message
from .telegram_client import TelegramClient


def fetch_readme(url: str = config.README_URL) -> str:
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        resp = client.get(url, headers={"User-Agent": "job-apply-assistant/0.1"})
        resp.raise_for_status()
        return resp.text


def scan_once(
    db: ScannerDatabase | None = None,
    telegram: TelegramClient | None = None,
    *,
    notify: bool = True,
) -> list[tuple[str, str]]:
    """Alert only — resume tailoring happens locally when you sit down."""
    db = db or ScannerDatabase(config.SCANNER_DB_PATH)
    telegram = telegram or TelegramClient()

    if config.UPSTREAM_SHA:
        db.set_sync_value("upstream_sha", config.UPSTREAM_SHA)

    content = fetch_readme()
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    prev_hash = db.get_sync_value("readme_sha256")
    if prev_hash == content_hash:
        return []

    first_sync = prev_hash is None
    db.set_sync_value("readme_sha256", content_hash)
    jobs = parse_readme(content)
    triggered: list[tuple[str, str]] = []

    for job in jobs:
        event, should_notify = db.upsert_job(job)
        if first_sync or not should_notify:
            continue

        triggered.append((job.id, event))
        if notify and telegram.configured:
            telegram.send_message(format_job_message(job, event))

        db.mark_notified(job.id)

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
