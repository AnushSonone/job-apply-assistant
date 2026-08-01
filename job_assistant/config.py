from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent


def expand(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


UPSTREAM_REPO = os.getenv("UPSTREAM_REPO", "SimplifyJobs/Summer2027-Internships")
README_PATH = os.getenv("README_PATH", "README-Off-Season.md")
MAIN_README_PATH = os.getenv("MAIN_README_PATH", "README.md")
UPSTREAM_BRANCH = os.getenv("UPSTREAM_BRANCH", "dev")
README_URL = os.getenv(
    "README_URL",
    f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{UPSTREAM_BRANCH}/{README_PATH}",
)


@dataclass(frozen=True)
class Source:
    """One upstream README we diff independently.

    Each source keeps its own baseline SHA in sync_state, so a rename or a
    stalled list on one never resets the other.
    """

    key: str
    label: str
    repo: str
    branch: str
    readme_path: str

    @property
    def sync_key(self) -> str:
        return f"upstream_sha:{self.key}"

    @property
    def readme_url(self) -> str:
        return (
            f"https://raw.githubusercontent.com/{self.repo}/"
            f"{self.branch}/{self.readme_path}"
        )

    def readme_url_at(self, sha: str) -> str:
        return (
            f"https://raw.githubusercontent.com/{self.repo}/{sha}/{self.readme_path}"
        )

    @property
    def display(self) -> str:
        return f"{self.repo} ({self.label})"


_ALL_SOURCES = (
    Source("off-season", "Off-Season", UPSTREAM_REPO, UPSTREAM_BRANCH, README_PATH),
    Source("summer2027", "Summer 2027", UPSTREAM_REPO, UPSTREAM_BRANCH, MAIN_README_PATH),
)

ENABLED_SOURCES = [
    key.strip()
    for key in os.getenv("ENABLED_SOURCES", "off-season,summer2027").split(",")
    if key.strip()
]
SOURCES = [s for s in _ALL_SOURCES if s.key in ENABLED_SOURCES]
SOURCES_BY_KEY = {s.key: s for s in _ALL_SOURCES}


def source_display(key: str) -> str:
    """Human label for a stored source key, tolerant of keys we no longer track."""
    source = SOURCES_BY_KEY.get(key)
    return source.display if source else key


def source_label(key: str) -> str:
    """Short list name for alert text ("Off-Season"), not the full repo path."""
    source = SOURCES_BY_KEY.get(key)
    return source.label if source else key


POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "600"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Legacy single-source pin; still honoured for the off-season list.
UPSTREAM_SHA = os.getenv("UPSTREAM_SHA", "")


def _pinned_shas() -> dict[str, str]:
    """CI pins the exact SHAs it detected so scan compares what check saw."""
    raw = os.getenv("UPSTREAM_SHAS", "").strip()
    pinned: dict[str, str] = {}
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            pinned = {str(k): str(v) for k, v in parsed.items() if v}
    if UPSTREAM_SHA and "off-season" not in pinned:
        pinned["off-season"] = UPSTREAM_SHA
    return pinned


PINNED_SHAS = _pinned_shas()
# Only alert when SimplifyJobs age column is still this fresh (0 = "0d" only).
# 1d, not 0d: the age column counts from the *company's* posting date, not from
# when SimplifyJobs added the row, so only ~14% of new rows ever land stamped 0d.
# A 0d gate discarded roughly 80% of everything the commit-diff found.
MAX_POSTING_AGE_DAYS = int(os.getenv("MAX_POSTING_AGE_DAYS", "1"))
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
