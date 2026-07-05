from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent


def expand(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


README_URL = os.getenv(
    "README_URL",
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README-Off-Season.md",
)
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "600"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
UPSTREAM_SHA = os.getenv("UPSTREAM_SHA", "")

BASE_RESUME_PATH = expand(
    os.getenv("BASE_RESUME_PATH", str(ROOT / "data" / "master_resume.md"))
)
BASE_RESUME_PDF = expand(
    os.getenv(
        "BASE_RESUME_PDF",
        str(
            Path.home()
            / "Library/Mobile Documents/com~apple~CloudDocs/resume/Anush_Sonone_Resume_2028.pdf"
        ),
    )
)
PROFILE_PATH = expand(os.getenv("PROFILE_PATH", str(ROOT / "data" / "profile.json")))
ANSWER_BANK_PATH = expand(
    os.getenv("ANSWER_BANK_PATH", str(ROOT / "data" / "answer_bank.yaml"))
)
FACTS_PATH = expand(os.getenv("FACTS_PATH", str(ROOT / "data" / "facts.json")))

SCANNER_DB_PATH = expand(
    os.getenv(
        "DATABASE_PATH",
        os.getenv("SCANNER_DB_PATH", str(ROOT / "data" / "scanner.db")),
    )
)
LOCAL_DB_PATH = expand(os.getenv("LOCAL_DB_PATH", str(ROOT / "data" / "local.db")))

RESUMES_DIR = Path(
    os.getenv(
        "RESUMES_DIR",
        "/tmp/job-assistant-resumes" if os.getenv("CI") else str(ROOT / "resumes"),
    )
)
CDP_URL = os.getenv("CDP_URL", "http://127.0.0.1:9222")

PROMPTS_DIR = ROOT / "prompts"
RESUME_SCHEMA_PATH = ROOT / "resume_schema.yaml"
