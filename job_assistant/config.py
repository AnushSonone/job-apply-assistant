from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent


def expand(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


UPSTREAM_REPO = os.getenv("UPSTREAM_REPO", "SimplifyJobs/Summer2026-Internships")
README_PATH = os.getenv("README_PATH", "README-Off-Season.md")
UPSTREAM_BRANCH = os.getenv("UPSTREAM_BRANCH", "dev")
README_URL = os.getenv(
    "README_URL",
    f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{UPSTREAM_BRANCH}/{README_PATH}",
)
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "600"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
UPSTREAM_SHA = os.getenv("UPSTREAM_SHA", "")
# Only alert when SimplifyJobs age column is still this fresh (0 = "0d" only).
MAX_POSTING_AGE_DAYS = int(os.getenv("MAX_POSTING_AGE_DAYS", "0"))
SCAN_DRY_RUN = os.getenv("SCAN_DRY_RUN", "").lower() in {"1", "true", "yes"}

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:32b-instruct-q4_K_M")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "32768"))
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "600"))

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
JOB_CONTEXT_DIR = expand(
    os.getenv("JOB_CONTEXT_DIR", str(ROOT / "data" / "job_descriptions"))
)
JOB_DESCRIPTION_MAX_CHARS = int(os.getenv("JOB_DESCRIPTION_MAX_CHARS", "24000"))

PROMPTS_DIR = ROOT / "prompts"
RESUME_SCHEMA_PATH = ROOT / "resume_schema.yaml"
