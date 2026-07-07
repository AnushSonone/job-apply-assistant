from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

if TYPE_CHECKING:
    from .db import Job

_STRIP_QUERY_KEYS = frozenset(
    {"utm_source", "utm_medium", "utm_campaign", "ref", "gh_src"}
)


def normalize_url(url: str) -> str:
    """Canonicalize apply/simplify URLs so tracking params do not break matching."""
    parsed = urlparse(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _STRIP_QUERY_KEYS
    ]
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            urlencode(query),
            "",
        )
    )


def legacy_job_id(company: str, role: str, location: str) -> str:
    raw = f"{company.strip().lower()}|{role.strip().lower()}|{location.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def stable_key_for(
    *,
    company: str,
    role: str,
    location: str,
    apply_url: str | None,
    simplify_url: str | None,
) -> str:
    if apply_url:
        return f"apply:{normalize_url(apply_url)}"
    if simplify_url:
        return f"simplify:{normalize_url(simplify_url)}"
    return f"legacy:{legacy_job_id(company, role, location)}"


def stable_key(job: Job) -> str:
    return stable_key_for(
        company=job.company,
        role=job.role,
        location=job.location,
        apply_url=job.apply_url,
        simplify_url=job.simplify_url,
    )
