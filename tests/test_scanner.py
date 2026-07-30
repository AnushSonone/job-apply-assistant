"""Tests for commit-diff scanner logic."""

from __future__ import annotations

from job_assistant import config
from job_assistant.alerts import (
    format_job_message,
    parse_posting_age_days,
    should_alert,
)
from job_assistant.db import Job, ScannerDatabase
from job_assistant.diff import added_jobs
from job_assistant.job_keys import normalize_url, stable_key
from job_assistant.parser import parse_readme

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


_ROW_NO_TERMS = (
    "<tr>"
    '<td><strong><a href="https://simplify.jobs/c/Acme">Acme</a></strong></td>'
    "<td>{role}</td>"
    "<td>{location}</td>"
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


def test_should_alert_only_zero_day_skips_canada_and_uk() -> None:
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
    one_day = Job(**{**fresh.__dict__, "age": "1d"})
    older_age = Job(**{**fresh.__dict__, "age": "4d"})
    canada = Job(**{**fresh.__dict__, "location": "Remote in Canada"})
    uk = Job(**{**fresh.__dict__, "location": "London, UK"})
    no_link = Job(**{**fresh.__dict__, "apply_url": None, "is_closed": True})

    assert should_alert(fresh) is True
    assert should_alert(one_day) is False
    assert should_alert(older_age) is False
    assert should_alert(canada) is False
    assert should_alert(uk) is False
    assert should_alert(no_link) is False


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


def test_parses_five_column_main_season_table() -> None:
    """The main README has no Terms column; it must still parse."""
    content = (
        "<table><thead><tr><th>Company</th><th>Role</th>"
        "<th>Location</th><th>Application</th><th>Age</th></tr></thead><tbody>"
        + _ROW_NO_TERMS.format(
            role="SWE Intern",
            location="Anaheim, CA",
            apply_url="https://jobs.example.com/a",
            age="0d",
        )
        + "</tbody></table>"
    )
    jobs = parse_readme(content, "summer2027")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.role == "SWE Intern"
    assert job.location == "Anaheim, CA"
    assert job.age == "0d"
    assert job.terms == ""
    assert job.apply_url == "https://jobs.example.com/a"
    assert job.is_closed is False
    assert should_alert(job) is True


def test_six_column_table_still_reads_terms() -> None:
    jobs = parse_readme(
        _readme(_row("SWE Intern", "NYC", "https://jobs.example.com/a")),
    )
    assert jobs[0].terms == "Fall 2026"
    assert jobs[0].age == "0d"


def test_both_sources_enabled_with_distinct_baselines() -> None:
    keys = [s.key for s in config.SOURCES]
    assert keys == ["off-season", "summer2027"]
    paths = {s.readme_path for s in config.SOURCES}
    assert paths == {"README-Off-Season.md", "README.md"}
    sync_keys = {s.sync_key for s in config.SOURCES}
    assert sync_keys == {"upstream_sha:off-season", "upstream_sha:summer2027"}


def test_parse_readme_tags_source() -> None:
    jobs = parse_readme(
        _readme(_row("SWE Intern", "NYC", "https://jobs.example.com/a")),
        "summer2027",
    )
    assert [job.source for job in jobs] == ["summer2027"]


def test_added_jobs_tags_source() -> None:
    old = _readme()
    new = _readme(_row("SWE Intern", "NYC", "https://jobs.example.com/a"))
    added = added_jobs(old, new, "summer2027")
    assert [job.source for job in added] == ["summer2027"]


def test_message_names_the_source_repo() -> None:
    job = Job(
        id="x",
        company="Acme",
        role="SWE Intern",
        location="NYC",
        terms="Summer 2027",
        category="Software Engineering",
        apply_url="https://jobs.example.com/a",
        simplify_url=None,
        age="0d",
        is_closed=False,
        flags="",
        source="summer2027",
    )
    message = format_job_message(job)
    assert message.splitlines() == [
        "Acme — SWE Intern",
        "via SimplifyJobs/Summer2027-Internships (Summer 2027)",
        "https://jobs.example.com/a",
    ]

    off_season = Job(**{**job.__dict__, "source": "off-season"})
    assert "(Off-Season)" in format_job_message(off_season)

    untagged = Job(**{**job.__dict__, "source": ""})
    assert format_job_message(untagged).splitlines() == [
        "Acme — SWE Intern",
        "https://jobs.example.com/a",
    ]


def test_legacy_baseline_migrates_to_off_season_key(tmp_path) -> None:
    path = tmp_path / "scanner.db"
    db = ScannerDatabase(path)
    db.set_sync_value("upstream_sha", "deadbeef")

    # Re-opening runs the migration, as a deploy of this change would.
    migrated = ScannerDatabase(path)
    assert migrated.get_sync_value("upstream_sha:off-season") == "deadbeef"
    assert migrated.get_sync_value("upstream_sha:summer2027") is None


def test_source_recorded_and_not_stolen_by_second_source(tmp_path) -> None:
    db = ScannerDatabase(tmp_path / "scanner.db")
    job = parse_readme(
        _readme(_row("SWE Intern", "NYC", "https://jobs.example.com/a")),
        "off-season",
    )[0]
    db.upsert_job(job)
    assert db.get_job_by_stable_key(stable_key(job))["source"] == "off-season"

    same_job_other_list = Job(**{**job.__dict__, "source": "summer2027"})
    db.upsert_job(same_job_other_list)
    row = db.get_job_by_stable_key(stable_key(job))
    assert row["source"] == "off-season"
