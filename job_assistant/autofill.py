from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

from . import config
from .db import LocalDatabase, ScannerDatabase
from .fill.field_matcher import load_answer_bank
from .fill.filler import click_safe_next, fill_snapshot, print_report
from .fill.page_snapshot import scrape_page
from .resume import load_profile


def connect_and_autofill(
    job_id: str | None = None,
    url_hint: str | None = None,
    *,
    advance: bool = False,
    dry_run: bool = False,
    max_pages: int = 10,
) -> None:
    profile = load_profile()
    scanner = ScannerDatabase(config.SCANNER_DB_PATH)
    local = LocalDatabase(config.LOCAL_DB_PATH)
    rules = load_answer_bank(config.ANSWER_BANK_PATH)

    target_url = url_hint
    resume_path: Path | None = None
    if job_id:
        row = scanner.get_job(job_id)
        if not row:
            raise SystemExit(f"Unknown job id: {job_id}")
        target_url = row["apply_url"]
        print(f"Job: {row['company']} — {row['role']}")
        latest = scanner.latest_resume_for_job(job_id)
        if latest:
            resume_path = Path(latest.tailored_path)
        if resume_path is None or not resume_path.exists():
            resume_path = config.BASE_RESUME_PDF if config.BASE_RESUME_PDF.exists() else config.BASE_RESUME_PATH

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(config.CDP_URL)
        except Exception:
            raise SystemExit(
                "Could not connect to Brave.\n"
                "1. Quit Brave (Cmd+Q)\n"
                '2. open -a "Brave Browser" --args --remote-debugging-port=9222\n'
                "3. Open the application page, then rerun autofill."
            )

        pages = [pg for ctx in browser.contexts for pg in ctx.pages]
        page = None
        if target_url:
            for pg in pages:
                if target_url.split("?")[0] in pg.url:
                    page = pg
                    break
        if page is None and pages:
            page = pages[-1]
        if page is None:
            raise SystemExit("No browser tab found. Open the application page in Brave first.")

        print(f"Autofilling: {page.url}")
        if dry_run:
            print("(dry run — no changes will be made)")

        for page_num in range(max_pages):
            snapshot = scrape_page(page)
            report = fill_snapshot(
                page, snapshot, rules, profile, resume_path, dry_run=dry_run
            )
            print_report(report)
            if not advance:
                break
            if not click_safe_next(page, snapshot, dry_run=dry_run):
                break
            if page_num < max_pages - 1:
                print(f"\n--- Page {page_num + 2} ---")

        print("\nReview the form before submitting.")

        if job_id:
            latest = scanner.latest_resume_for_job(job_id)
            local.log_application(
                job_id,
                status="in_progress",
                resume_version_id=latest.id if latest else None,
            )
