from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Page

from .field_matcher import MatchResult, match_field
from .page_snapshot import FormField, PageSnapshot, scrape_page


@dataclass
class FillReport:
    filled: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    required_empty: list[str] = field(default_factory=list)


def _click_ref(page: Page, ref: str) -> None:
    page.evaluate(
        """(ref) => {
          const el = window.__jobAssistantRefs.get(ref);
          if (el) el.click();
        }""",
        ref,
    )


def _fill_ref(page: Page, ref: str, value: str) -> None:
    page.evaluate(
        """({ ref, value }) => {
          const el = window.__jobAssistantRefs.get(ref);
          if (!el) return;
          el.focus();
          if (el.tagName === 'SELECT') {
            for (const opt of el.options) {
              if (opt.text.toLowerCase().includes(value.toLowerCase().slice(0, 20))) {
                el.value = opt.value;
                el.dispatchEvent(new Event('change', { bubbles: true }));
                return;
              }
            }
          } else {
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
          }
        }""",
        {"ref": ref, "value": value},
    )


def _upload_ref(page: Page, ref: str, file_path: Path) -> None:
    page.evaluate("() => {}")  # ensure refs map exists
    loc = page.locator(f'input[type="file"]').first
    for _ in range(3):
        try:
            page.set_input_files('input[type="file"]', str(file_path))
            return
        except Exception:
            pass
    _click_ref(page, ref)
    page.set_input_files('input[type="file"]', str(file_path))


def fill_snapshot(
    page: Page,
    snapshot: PageSnapshot,
    rules: list,
    profile: dict,
    resume_path: Path | None,
    *,
    dry_run: bool = False,
) -> FillReport:
    report = FillReport()
    for fld in snapshot.fields:
        if fld.value.strip():
            continue
        result = match_field(fld, rules, profile)
        if result is None:
            line = f"? {fld.label}  [{fld.type}]" + ("  REQUIRED" if fld.required else "")
            report.unmatched.append(line)
            if fld.required:
                report.required_empty.append(fld.label)
            continue
        if result.action == "skip":
            report.skipped.append(f"– {fld.label} (skip rule)")
            continue
        if result.action == "upload_file":
            if resume_path and resume_path.exists():
                if not dry_run:
                    _upload_ref(page, fld.ref, resume_path)
                report.filled.append(f"✓ {fld.label} → {resume_path.name}")
            else:
                report.unmatched.append(f"? {fld.label}  [file — no resume path]")
            continue
        if result.action == "fill" and result.value:
            if not dry_run:
                _fill_ref(page, fld.ref, result.value)
            report.filled.append(f"✓ {fld.label} → {result.value[:50]}")
    return report


def click_safe_next(page: Page, snapshot: PageSnapshot, dry_run: bool = False) -> bool:
    for btn in snapshot.buttons:
        if not btn.safe:
            continue
        if re.search(r"next|continue|save", btn.label, re.I):
            if not dry_run:
                _click_ref(page, btn.ref)
                page.wait_for_timeout(1500)
            return True
    return False


def print_report(report: FillReport) -> None:
    if report.filled:
        print(f"\nFilled ({len(report.filled)}):")
        for line in report.filled:
            print(f"  {line}")
    if report.skipped:
        print(f"\nSkipped ({len(report.skipped)}):")
        for line in report.skipped:
            print(f"  {line}")
    if report.unmatched:
        print(f"\nUnmatched — fill manually ({len(report.unmatched)}):")
        for line in report.unmatched:
            print(f"  {line}")
    if report.required_empty:
        print(f"\nRequired still empty ({len(report.required_empty)}):")
        for line in report.required_empty:
            print(f"  ! {line}")
