from __future__ import annotations

from . import config
from .db import Job
from .job_keys import stable_key
from .parser import parse_readme


def added_jobs(old_content: str, new_content: str) -> list[Job]:
    """Return open jobs present in new README but not in old (by stable apply URL)."""
    old_keys = {
        stable_key(job)
        for job in parse_readme(old_content)
        if not job.is_closed and job.apply_url
    }
    added: list[Job] = []
    seen: set[str] = set()
    for job in parse_readme(new_content):
        if job.is_closed or not job.apply_url:
            continue
        key = stable_key(job)
        if key in old_keys or key in seen:
            continue
        seen.add(key)
        added.append(job)
    return added
