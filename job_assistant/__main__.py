"""Job apply assistant — SimplifyJobs watcher, resume prep, Brave autofill."""

from __future__ import annotations

import argparse
import hashlib
import sys

import yaml

from . import config
from .autofill import connect_and_autofill
from .db import LocalDatabase, ScannerDatabase
from .facts_extractor import load_or_build_facts
from .pdf_resume import import_resume_pdf
from .resume import ensure_master_resume, revise_resume, row_to_job, tailor_resume
from .telegram_revise import run_telegram_bot
from .watcher import fetch_readme, scan_once, watch


def cmd_scan(_: argparse.Namespace) -> None:
    hits = scan_once()
    if hits:
        print(f"Triggered {len(hits)} notification(s):")
        for job_id, event in hits:
            print(f"  {event}: {job_id}")
    else:
        print("No new or reopened listings.")


def cmd_watch(_: argparse.Namespace) -> None:
    watch()


def cmd_list(args: argparse.Namespace) -> None:
    db = ScannerDatabase(config.SCANNER_DB_PATH)
    rows = db.list_jobs(active_only=args.active)
    for row in rows[: args.limit]:
        status = "closed" if row["is_closed"] else "open"
        print(
            f"{row['id']}  [{status}]  {row['company']} — {row['role']}  ({row['location']})"
        )
        if row["apply_url"]:
            print(f"  {row['apply_url']}")


def cmd_show(args: argparse.Namespace) -> None:
    db = ScannerDatabase(config.SCANNER_DB_PATH)
    row = db.get_job(args.job_id)
    if not row:
        raise SystemExit(f"Unknown job: {args.job_id}")
    for key in row.keys():
        print(f"{key}: {row[key]}")


def cmd_autofill(args: argparse.Namespace) -> None:
    connect_and_autofill(
        job_id=args.job_id,
        url_hint=args.url,
        advance=args.advance,
        dry_run=args.dry_run,
    )


def cmd_log_apply(args: argparse.Namespace) -> None:
    scanner = ScannerDatabase(config.SCANNER_DB_PATH)
    local = LocalDatabase(config.LOCAL_DB_PATH)
    resume = scanner.latest_resume_for_job(args.job_id)
    local.log_application(
        args.job_id,
        status="applied",
        resume_version_id=resume.id if resume else None,
        notes=args.notes,
    )
    row = scanner.get_job(args.job_id)
    company = row["company"] if row else args.job_id
    print(f"Logged application: {company}")


def cmd_init_db(_: argparse.Namespace) -> None:
    from .parser import parse_readme

    db = ScannerDatabase(config.SCANNER_DB_PATH)
    content = fetch_readme()
    db.set_sync_value("readme_sha256", hashlib.sha256(content.encode()).hexdigest())
    jobs = parse_readme(content)
    for job in jobs:
        db.upsert_job(job)
    open_count = sum(1 for j in jobs if not j.is_closed)
    print(
        f"Seeded {len(jobs)} jobs ({open_count} open) into {config.SCANNER_DB_PATH}. "
        "Future scans only alert on new/reopened listings."
    )


def cmd_import_resume(_: argparse.Namespace) -> None:
    pdf = config.BASE_RESUME_PDF
    if not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}")
    md = import_resume_pdf(pdf, config.BASE_RESUME_PATH)
    facts = load_or_build_facts(config.BASE_RESUME_PATH, config.FACTS_PATH)
    print(f"Imported resume → {config.BASE_RESUME_PATH} ({len(md)} chars)")
    print(f"Facts manifest → {config.FACTS_PATH}")
    print(f"  employers: {facts.get('employers', [])}")


def cmd_add_answer(args: argparse.Namespace) -> None:
    path = config.ANSWER_BANK_PATH
    if path.exists():
        data = yaml.safe_load(path.read_text()) or {"rules": []}
    else:
        example = path.parent / "answer_bank.example.yaml"
        data = yaml.safe_load(example.read_text()) if example.exists() else {"rules": []}

    data.setdefault("rules", []).append({"match": [args.pattern], "value": args.value})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    print(f"Added rule to {path}")


def cmd_prepare_resume(args: argparse.Namespace) -> None:
    scanner = ScannerDatabase(config.SCANNER_DB_PATH)
    row = scanner.get_job(args.job_id)
    if not row:
        raise SystemExit(f"Unknown job: {args.job_id}")
    job = row_to_job(row)
    out_path, diff, _ = tailor_resume(job, scanner)
    print(diff)
    print(f"\nSaved: {out_path}")
    if args.telegram:
        from .telegram_client import TelegramClient
        from .resume import resume_document_caption

        local = LocalDatabase(config.LOCAL_DB_PATH)
        tg = TelegramClient()
        resp = tg.send_document(out_path, caption=resume_document_caption(job))
        msg_id = resp.get("result", {}).get("message_id")
        if msg_id:
            local.save_telegram_message(msg_id, job.id)
        tg.send_message(diff)


def cmd_revise_resume(args: argparse.Namespace) -> None:
    scanner = ScannerDatabase(config.SCANNER_DB_PATH)
    local = LocalDatabase(config.LOCAL_DB_PATH)
    row = scanner.get_job(args.job_id)
    if not row:
        raise SystemExit(f"Unknown job: {args.job_id}")
    job = row_to_job(row)
    out_path, diff, _ = revise_resume(job, args.feedback, scanner, local)
    print(diff)
    print(f"\nSaved: {out_path}")
    if args.telegram:
        from .telegram_client import TelegramClient
        from .resume import resume_document_caption

        tg = TelegramClient()
        resp = tg.send_document(out_path, caption=resume_document_caption(job))
        msg_id = resp.get("result", {}).get("message_id")
        if msg_id:
            local.save_telegram_message(msg_id, job.id)
        tg.send_message(diff)


def cmd_revise_chat(args: argparse.Namespace) -> None:
    scanner = ScannerDatabase(config.SCANNER_DB_PATH)
    local = LocalDatabase(config.LOCAL_DB_PATH)
    row = scanner.get_job(args.job_id)
    if not row:
        raise SystemExit(f"Unknown job: {args.job_id}")
    job = row_to_job(row)
    print(f"Revise chat for {job.company} — {job.role} ({job.id})")
    print("Type feedback (empty line or Ctrl+D to quit):\n")
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if not line:
            break
        out_path, diff, _ = revise_resume(job, line, scanner, local)
        print(diff)
        print(f"Saved: {out_path}\n")


def cmd_telegram_bot(_: argparse.Namespace) -> None:
    run_telegram_bot()


def cmd_setup_profile(_: argparse.Namespace) -> None:
    """Copy example profile/answer bank if missing."""
    profile_dst = config.PROFILE_PATH
    if not profile_dst.exists():
        src = profile_dst.parent / "profile.example.json"
        profile_dst.write_text(src.read_text())
        print(f"Created {profile_dst} — edit with your info.")
    bank_dst = config.ANSWER_BANK_PATH
    if not bank_dst.exists():
        src = bank_dst.parent / "answer_bank.example.yaml"
        bank_dst.write_text(src.read_text())
        print(f"Created {bank_dst}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="SimplifyJobs off-season apply assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scan", help="One-shot fetch; notify on new/reopened listings")
    sub.add_parser("watch", help="Poll README locally (fallback)")
    sub.add_parser("init-db", help="Seed scanner DB from current README")
    sub.add_parser("import-resume", help="Import PDF resume to master_resume.md + facts")
    sub.add_parser("setup", help="Create local profile.json and answer_bank.yaml")
    sub.add_parser("telegram-bot", help="Listen for Telegram replies to revise resumes")

    prep_p = sub.add_parser("prepare-resume", help="Tailor resume locally with Ollama (laptop)")
    prep_p.add_argument("--job-id", required=True)
    prep_p.add_argument("--telegram", action="store_true", help="Send tailored resume to Telegram")

    revise_p = sub.add_parser("revise-resume", help="Revise tailored resume with local Ollama")
    revise_p.add_argument("--job-id", required=True)
    revise_p.add_argument("feedback", help="What to change")
    revise_p.add_argument("--telegram", action="store_true", help="Send revised resume to Telegram")

    chat_p = sub.add_parser("revise-chat", help="Interactive resume revision in terminal")
    chat_p.add_argument("--job-id", required=True)

    list_p = sub.add_parser("list", help="List tracked jobs")
    list_p.add_argument("--active", action="store_true")
    list_p.add_argument("--limit", type=int, default=30)

    show_p = sub.add_parser("show", help="Show one job by id")
    show_p.add_argument("job_id")

    fill_p = sub.add_parser("autofill", help="Fill Brave tab from answer bank")
    fill_p.add_argument("--job-id")
    fill_p.add_argument("--url")
    fill_p.add_argument("--advance", action="store_true", help="Click Next through wizard pages")
    fill_p.add_argument("--dry-run", action="store_true")

    log_p = sub.add_parser("log-apply", help="Record submitted application")
    log_p.add_argument("job_id")
    log_p.add_argument("--notes", default="")

    add_p = sub.add_parser("add-answer", help="Add answer bank rule")
    add_p.add_argument("pattern", help="Label text or regex to match")
    add_p.add_argument("value", help="Value to fill")

    args = parser.parse_args(argv)
    commands = {
        "scan": cmd_scan,
        "watch": cmd_watch,
        "init-db": cmd_init_db,
        "import-resume": cmd_import_resume,
        "setup": cmd_setup_profile,
        "telegram-bot": cmd_telegram_bot,
        "prepare-resume": cmd_prepare_resume,
        "revise-resume": cmd_revise_resume,
        "revise-chat": cmd_revise_chat,
        "list": cmd_list,
        "show": cmd_show,
        "autofill": cmd_autofill,
        "log-apply": cmd_log_apply,
        "add-answer": cmd_add_answer,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main(sys.argv[1:])
