from __future__ import annotations

import json
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config
from .db import Job, LocalDatabase, ScannerDatabase
from .facts_extractor import load_or_build_facts
from .llm import complete as llm_complete
from .pdf_resume import import_resume_pdf
from .resume_diff import summarize_changes
from .resume_validator import validate_tailored


def load_profile(path: Path | None = None) -> dict:
    profile_path = path or config.PROFILE_PATH
    if not profile_path.exists():
        example = profile_path.parent / "profile.example.json"
        raise FileNotFoundError(
            f"Profile not found at {profile_path}. Copy {example} to profile.json and edit."
        )
    return json.loads(profile_path.read_text())


def ensure_master_resume() -> Path:
    if config.BASE_RESUME_PATH.exists():
        return config.BASE_RESUME_PATH
    if config.BASE_RESUME_PDF.exists():
        import_resume_pdf(config.BASE_RESUME_PDF, config.BASE_RESUME_PATH)
        return config.BASE_RESUME_PATH
    raise FileNotFoundError(
        f"No resume at {config.BASE_RESUME_PATH} or {config.BASE_RESUME_PDF}. "
        "Run: python -m job_assistant import-resume"
    )


def _render_tailor_prompt(job: Job, master: str, facts: dict) -> tuple[str, str]:
    env = Environment(
        loader=FileSystemLoader(str(config.PROMPTS_DIR)),
        autoescape=select_autoescape(default=False),
    )
    system = env.get_template("resume_tailor_system.jinja").render()
    user = env.get_template("resume_tailor_user.jinja").render(
        master_resume=master,
        facts_json=json.dumps(facts, indent=2),
        company=job.company,
        role=job.role,
        location=job.location,
        terms=job.terms,
        category=job.category,
        flags=job.flags or "none",
    )
    return system, user


def _resume_out_path(job: Job) -> Path:
    config.RESUMES_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\-]+", "_", f"{job.company}_{job.role}")[:80]
    return config.RESUMES_DIR / f"{job.id}_{safe_name}.md"


def row_to_job(row) -> Job:
    return Job(
        id=row["id"],
        company=row["company"],
        role=row["role"],
        location=row["location"],
        terms=row["terms"] or "",
        category=row["category"] or "",
        apply_url=row["apply_url"],
        simplify_url=row["simplify_url"],
        age=row["age"] or "",
        is_closed=bool(row["is_closed"]),
        flags=row["flags"] or "",
    )


def resume_document_caption(job: Job) -> str:
    return (
        f"Job ID: {job.id}\n"
        f"{job.company} — {job.role}\n\n"
        f"Reply with feedback to revise (requires telegram-bot running on laptop)."
    )


def tailor_resume(
    job: Job,
    db: ScannerDatabase,
    *,
    retry_on_fail: bool = True,
) -> tuple[Path, str, list[str]]:
    """Tailor resume via local Ollama — run on laptop only."""
    base_path = ensure_master_resume()
    master = base_path.read_text()
    facts = load_or_build_facts(base_path, config.FACTS_PATH)
    system, user = _render_tailor_prompt(job, master, facts)

    def _call(extra: str = "") -> str:
        suffix = f"Fix these validation errors:\n{extra}" if extra else ""
        return llm_complete(system, user, extra=suffix)

    print(f"Tailoring with {config.OLLAMA_MODEL}… (may take 1–3 min)")
    tailored = _call()
    validation = validate_tailored(master, tailored, facts)
    if not validation.ok and retry_on_fail:
        tailored = _call("\n".join(validation.errors))
        validation = validate_tailored(master, tailored, facts)

    out_path = _resume_out_path(job)
    out_path.write_text(tailored + "\n")
    db.save_resume_version(job.id, str(base_path), str(out_path))

    diff = summarize_changes(master, tailored, job.company)
    warnings = validation.errors + validation.warnings
    if warnings:
        diff = "⚠️ Validation notes:\n" + "\n".join(f"• {w}" for w in warnings) + "\n\n" + diff
    return out_path, diff, warnings


def revise_resume(
    job: Job,
    feedback: str,
    db: ScannerDatabase,
    local: LocalDatabase | None = None,
    *,
    retry_on_fail: bool = True,
) -> tuple[Path, str, list[str]]:
    latest = db.latest_resume_for_job(job.id)
    if not latest or not Path(latest.tailored_path).exists():
        raise FileNotFoundError(
            f"No tailored resume for {job.id}. Run: python -m job_assistant prepare-resume --job-id {job.id}"
        )

    base_path = ensure_master_resume()
    master = base_path.read_text()
    current = Path(latest.tailored_path).read_text()
    facts = load_or_build_facts(base_path, config.FACTS_PATH)

    env = Environment(
        loader=FileSystemLoader(str(config.PROMPTS_DIR)),
        autoescape=select_autoescape(default=False),
    )
    system = env.get_template("resume_revise_system.jinja").render()

    raw_feedback = feedback.strip()
    if local:
        prior = [c for r, c in local.get_revise_history(job.id) if r == "user"]
        if prior:
            feedback = (
                "Previous feedback:\n"
                + "\n".join(f"- {p}" for p in prior)
                + f"\n\nNew feedback:\n{raw_feedback}"
            )
        else:
            feedback = raw_feedback
        local.append_revise_message(job.id, "user", raw_feedback)
    else:
        feedback = raw_feedback

    user = env.get_template("resume_revise_user.jinja").render(
        master_resume=master,
        facts_json=json.dumps(facts, indent=2),
        company=job.company,
        role=job.role,
        location=job.location,
        current_tailored=current,
        feedback=feedback,
    )

    def _call(extra: str = "") -> str:
        suffix = f"Fix these validation errors:\n{extra}" if extra else ""
        return llm_complete(system, user, extra=suffix)

    print(f"Revising with {config.OLLAMA_MODEL}…")
    revised = _call()
    validation = validate_tailored(master, revised, facts)
    if not validation.ok and retry_on_fail:
        revised = _call("\n".join(validation.errors))
        validation = validate_tailored(master, revised, facts)

    out_path = Path(latest.tailored_path)
    out_path.write_text(revised + "\n")
    db.save_resume_version(job.id, str(base_path), str(out_path))

    if local:
        local.append_revise_message(job.id, "assistant", "revised")

    diff = summarize_changes(current, revised, job.company)
    diff = f"✏️ Revised resume for {job.company}:\n{diff}"
    warnings = validation.errors + validation.warnings
    if warnings:
        diff = "⚠️ Validation notes:\n" + "\n".join(f"• {w}" for w in warnings) + "\n\n" + diff
    return out_path, diff, warnings

