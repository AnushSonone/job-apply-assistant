from __future__ import annotations

import re

from . import config
from .db import Job

_AGE_RE = re.compile(
    r"^(\d+)\s*(d|day|days|w|wk|wks|week|weeks|mo|mos|month|months|y|yr|yrs|year|years)$",
    re.I,
)


def parse_posting_age_days(age: str) -> int | None:
    """Parse SimplifyJobs age column (e.g. 4d, 2mo) into approximate days."""
    text = age.strip().lower()
    if not text:
        return None
    m = _AGE_RE.match(text)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    if unit.startswith("d"):
        return n
    if unit.startswith("w"):
        return n * 7
    if unit.startswith("mo"):
        return n * 30
    if unit.startswith("y"):
        return n * 365
    return None


def is_canada_location(location: str) -> bool:
    return "canada" in location.lower()


_UK_RE = re.compile(r"\buk\b|united kingdom|\blondon\b|\bengland\b", re.I)


def is_uk_location(location: str) -> bool:
    return bool(_UK_RE.search(location))


def is_recent_posting(job: Job) -> bool:
    """True only for postings still marked 0d (or ≤ MAX_POSTING_AGE_DAYS)."""
    days = parse_posting_age_days(job.age)
    if days is None:
        return False
    return days <= config.MAX_POSTING_AGE_DAYS


def should_alert(job: Job) -> bool:
    """Alert only on newly added, applyable, 0d postings — skip Canada and UK/London.

    Commit-diff decides *new to the README*; the age column decides *fresh enough*.
    Without the age gate, a lagging upstream_sha dumps every row added during the
    gap (days/months old) as Telegram spam.
    """
    if job.is_closed or not job.apply_url:
        return False
    if is_canada_location(job.location) or is_uk_location(job.location):
        return False
    return is_recent_posting(job)


def format_job_message(job: Job) -> str:
    url = job.apply_url or job.simplify_url
    header = f"{job.company} — {job.role}"
    if url:
        return f"{header}\n{url}"
    return header
