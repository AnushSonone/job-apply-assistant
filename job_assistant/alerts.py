from __future__ import annotations

from .db import Job


def laptop_commands(job_id: str) -> str:
    return (
        f"At your laptop:\n"
        f"  python -m job_assistant prepare-resume --job-id {job_id}\n"
        f"  python -m job_assistant revise-chat --job-id {job_id}\n"
        f"  python -m job_assistant autofill --job-id {job_id} --advance"
    )


def format_job_message(job: Job, event: str) -> str:
    label = "New listing" if event == "new" else "Reopened"
    lines = [
        f"🟢 {label}: {job.company}",
        f"Role: {job.role}",
        f"Location: {job.location}",
        f"Term: {job.terms}",
        f"Category: {job.category}",
    ]
    if job.flags:
        lines.append(f"Flags: {job.flags}")
    if job.apply_url:
        lines.append(f"Apply: {job.apply_url}")
    lines.append(f"Job ID: {job.id}")
    lines.append("")
    lines.append(laptop_commands(job.id))
    return "\n".join(lines)
