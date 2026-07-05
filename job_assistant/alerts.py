from __future__ import annotations

from .db import Job


def is_canada_location(location: str) -> bool:
    return "canada" in location.lower()


def should_alert(job: Job) -> bool:
    return not is_canada_location(job.location)


def format_job_message(job: Job) -> str:
    url = job.apply_url or job.simplify_url
    if url:
        return f"{job.role}\n{url}"
    return job.role
