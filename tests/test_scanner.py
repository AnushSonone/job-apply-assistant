"""Tests for commit-diff scanner logic."""

from __future__ import annotations

from job_assistant.alerts import parse_posting_age_days, should_alert
from job_assistant.db import Job
from job_assistant.diff import added_jobs
from job_assistant.job_keys import normalize_url, stable_key

_ROW = (
    "<tr>"
    '<td><strong><a href="https://simplify.jobs/c/Acme">Acme</a></strong></td>'
    "<td>{role}</td>"
    "<td>{location}</td>"
    "<td>Fall 2026</td>"
    '<td><div align="center">'
    '<a href="{apply_url}"><img src="https://i.imgur.com/fbjwDvo.png" alt="Apply"></a>'
    '<a href="https://simplify.jobs/p/abc123"><img src="https://i.imgur.com/aVnQdox.png" alt="Simplify"></a>'
    "</div></td>"
    "<td>{age}</td>"
    "</tr>"
)


def _readme(*rows: str) -> str:
    body = "\n".join(rows)
    return (
        "<table><thead><tr><th>Company</th><th>Role</th>"
        "<th>Location</th><th>Terms</th><th>Application</th><th>Age</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def _row(
    role: str,
    location: str,
    apply_url: str,
    age: str = "0d",
) -> str:
    return _ROW.format(role=role, location=location, apply_url=apply_url, age=age)


def test_normalize_url_strips_tracking_params() -> None:
    raw = "https://jobs.example.com/role?utm_source=Simplify&ref=Simplify"
    assert normalize_url(raw) == "https://jobs.example.com/role"


def test_added_jobs_detects_only_new_rows() -> None:
    old = _readme(
        _row("Engineer Intern", "NYC", "https://jobs.example.com/a"),
    )
    new = _readme(
        _row("Engineer Intern", "NYC", "https://jobs.example.com/a"),
        _row("Firmware Intern", "SF", "https://jobs.example.com/b"),
    )
    added = added_jobs(old, new)
    assert len(added) == 1
    assert added[0].role == "Firmware Intern"


def test_added_jobs_ignores_text_change_same_url() -> None:
    old = _readme(
        _row("Engineer Intern", "NYC", "https://jobs.example.com/a", age="1d"),
    )
    new = _readme(
        _row("Engineer Intern - Updated Title", "NYC", "https://jobs.example.com/a", age="0d"),
    )
    assert added_jobs(old, new) == []


def test_should_alert_rejects_stale_and_canada() -> None:
    fresh = Job(
        id="x",
        company="Acme",
        role="SWE Intern",
        location="NYC",
        terms="Fall 2026",
        category="Software Engineering",
        apply_url="https://jobs.example.com/a",
        simplify_url=None,
        age="0d",
        is_closed=False,
        flags="",
    )
    stale = Job(**{**fresh.__dict__, "age": "4d"})
    canada = Job(**{**fresh.__dict__, "location": "Remote in Canada"})

    assert should_alert(fresh) is True
    assert should_alert(stale) is False
    assert should_alert(canada) is False


def test_stable_key_prefers_apply_url() -> None:
    job = Job(
        id="legacy",
        company="Acme",
        role="Role A",
        location="NYC",
        terms="Fall 2026",
        category="Software Engineering",
        apply_url="https://jobs.example.com/a?utm_source=Simplify",
        simplify_url="https://simplify.jobs/p/abc",
        age="0d",
        is_closed=False,
        flags="",
    )
    other = Job(**{**job.__dict__, "role": "Role B"})
    assert stable_key(job) == stable_key(other)


def test_parse_posting_age_days() -> None:
    assert parse_posting_age_days("0d") == 0
    assert parse_posting_age_days("1d") == 1
    assert parse_posting_age_days("2mo") == 60
