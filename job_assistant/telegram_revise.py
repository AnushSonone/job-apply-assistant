from __future__ import annotations

import re
import time

from . import config
from .db import LocalDatabase, ScannerDatabase
from .llm import check_ollama
from .resume import (
    resume_document_caption,
    revise_resume,
    row_to_job,
    tailor_resume,
)
from .telegram_client import TelegramClient


def _parse_job_id(text: str) -> str | None:
    m = re.search(r"\b([a-f0-9]{16})\b", text)
    return m.group(1) if m else None


def _extract_command_body(text: str, command: str, job_id: str | None) -> str:
    text = text.strip()
    if text.startswith(command):
        text = text[len(command) :].strip()
    if job_id and text.startswith(job_id):
        text = text[len(job_id) :].strip().lstrip(":").strip()
    return text


def handle_prepare_request(
    job_id: str,
    scanner: ScannerDatabase,
    local: LocalDatabase,
    telegram: TelegramClient,
) -> None:
    row = scanner.get_job(job_id)
    if not row:
        telegram.send_message(f"Unknown job ID: {job_id}")
        return

    job = row_to_job(row)
    telegram.send_message(f"Tailoring resume for {job.company}… (local Ollama, ~1–3 min)")

    out_path, diff, _ = tailor_resume(job, scanner)
    resp = telegram.send_document(out_path, caption=resume_document_caption(job))
    msg_id = resp.get("result", {}).get("message_id")
    if msg_id:
        local.save_telegram_message(msg_id, job_id)
    telegram.send_message(diff)


def handle_revise_request(
    job_id: str,
    feedback: str,
    scanner: ScannerDatabase,
    local: LocalDatabase,
    telegram: TelegramClient,
) -> None:
    if not feedback.strip():
        telegram.send_message("Send feedback text, e.g.:\n/revise abc123 Shorten the Visa bullet")
        return

    row = scanner.get_job(job_id)
    if not row:
        telegram.send_message(f"Unknown job ID: {job_id}")
        return

    job = row_to_job(row)
    telegram.send_message(f"Revising resume for {job.company}…")

    try:
        out_path, diff, _ = revise_resume(job, feedback, scanner, local)
    except FileNotFoundError as exc:
        telegram.send_message(f"{exc}\n\nOr send: /prepare {job_id}")
        return

    resp = telegram.send_document(out_path, caption=resume_document_caption(job))
    msg_id = resp.get("result", {}).get("message_id")
    if msg_id:
        local.save_telegram_message(msg_id, job_id)
    telegram.send_message(diff)


def process_update(update: dict, scanner: ScannerDatabase, local: LocalDatabase, telegram: TelegramClient) -> None:
    msg = update.get("message") or {}
    chat_id = str(msg.get("chat", {}).get("id", ""))
    if chat_id != config.TELEGRAM_CHAT_ID:
        return

    text = (msg.get("text") or msg.get("caption") or "").strip()
    if not text:
        return

    job_id: str | None = None
    feedback = text

    reply = msg.get("reply_to_message")
    if reply:
        reply_id = reply.get("message_id")
        if reply_id:
            job_id = local.job_id_for_telegram_message(reply_id)
        if not job_id:
            cap = reply.get("caption") or reply.get("text") or ""
            job_id = _parse_job_id(cap)

    if not job_id:
        job_id = _parse_job_id(text)

    if text.startswith("/prepare"):
        if not job_id:
            telegram.send_message("Usage: /prepare <job_id>")
            return
        handle_prepare_request(job_id, scanner, local, telegram)
        return

    if not job_id:
        if text.startswith(("/revise", "/help", "/start")):
            telegram.send_message(
                "Resume commands (laptop + Ollama must be running):\n"
                "• /prepare <job_id> — initial tailor\n"
                "• Reply to a resume file with feedback\n"
                "• /revise <job_id> <feedback>\n"
                "Example: /revise abc123 Don't use the word agentic in the Visa bullet"
            )
        return

    feedback = _extract_command_body(text, "/revise", job_id)
    if not feedback and not text.startswith("/revise"):
        feedback = text

    handle_revise_request(job_id, feedback, scanner, local, telegram)


def run_telegram_bot(poll_interval: float = 1.0) -> None:
    telegram = TelegramClient()
    scanner = ScannerDatabase(config.SCANNER_DB_PATH)
    local = LocalDatabase(config.LOCAL_DB_PATH)

    if not telegram.configured:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")

    check_ollama()

    telegram.send_message(
        "Resume bot active (local Ollama).\n"
        "• /prepare <job_id> — tailor when you're at your laptop\n"
        "• Reply to a resume file with feedback\n"
        "• /revise <job_id> <your changes>"
    )

    offset: int | None = None
    print("Listening for Telegram messages… (Ctrl+C to stop)")

    while True:
        try:
            updates = telegram.get_updates(offset=offset, timeout=30)
            for update in updates:
                offset = update["update_id"] + 1
                process_update(update, scanner, local, telegram)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as exc:
            print(f"Bot error: {exc}")
            time.sleep(poll_interval)
