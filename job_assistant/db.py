from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .job_keys import legacy_job_id, stable_key, stable_key_for


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Job:
    id: str
    company: str
    role: str
    location: str
    terms: str
    category: str
    apply_url: str | None
    simplify_url: str | None
    age: str
    is_closed: bool
    flags: str
    row_index: int = 0


@dataclass
class ResumeVersion:
    id: int
    job_id: str
    source_path: str
    tailored_path: str
    created_at: str


class _BaseDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


class ScannerDatabase(_BaseDB):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    company TEXT NOT NULL,
                    role TEXT NOT NULL,
                    location TEXT NOT NULL,
                    terms TEXT,
                    category TEXT,
                    apply_url TEXT,
                    simplify_url TEXT,
                    age TEXT,
                    is_closed INTEGER NOT NULL DEFAULT 0,
                    flags TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    last_notified_at TEXT
                );

                CREATE TABLE IF NOT EXISTS resume_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    tailored_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sync_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            self._migrate_schema(conn)

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
        if "stable_key" not in columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN stable_key TEXT")
        if "row_index" not in columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN row_index INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_stable_key ON jobs(stable_key)"
        )
        rows = conn.execute(
            "SELECT id, company, role, location, apply_url, simplify_url, stable_key "
            "FROM jobs WHERE stable_key IS NULL OR stable_key = ''"
        ).fetchall()
        for row in rows:
            key = stable_key_for(
                company=row["company"],
                role=row["role"],
                location=row["location"],
                apply_url=row["apply_url"],
                simplify_url=row["simplify_url"],
            )
            conn.execute(
                "UPDATE jobs SET stable_key = ? WHERE id = ?",
                (key, row["id"]),
            )

    def get_job(self, job_id: str) -> sqlite3.Row | None:
        with self._conn() as conn:
            return conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    def get_job_by_stable_key(self, key: str) -> sqlite3.Row | None:
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM jobs WHERE stable_key = ?", (key,)
            ).fetchone()

    def upsert_job(self, job: Job) -> tuple[str, bool]:
        now = utc_now()
        key = stable_key(job)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE stable_key = ?", (key,)
            ).fetchone()
            if row is None:
                row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job.id,)).fetchone()

            if row is None:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        id, stable_key, company, role, location, terms, category,
                        apply_url, simplify_url, age, is_closed, flags, row_index,
                        first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.id,
                        key,
                        job.company,
                        job.role,
                        job.location,
                        job.terms,
                        job.category,
                        job.apply_url,
                        job.simplify_url,
                        job.age,
                        int(job.is_closed),
                        job.flags,
                        job.row_index,
                        now,
                        now,
                    ),
                )
                if not job.is_closed and job.apply_url:
                    return "new", True
                return "new_closed", False

            was_closed = bool(row["is_closed"])
            conn.execute(
                """
                UPDATE jobs SET
                    id = ?, stable_key = ?, company = ?, role = ?, location = ?,
                    terms = ?, category = ?, apply_url = ?, simplify_url = ?,
                    age = ?, is_closed = ?, flags = ?, row_index = ?, last_seen_at = ?
                WHERE stable_key = ?
                """,
                (
                    job.id,
                    key,
                    job.company,
                    job.role,
                    job.location,
                    job.terms,
                    job.category,
                    job.apply_url,
                    job.simplify_url,
                    job.age,
                    int(job.is_closed),
                    job.flags,
                    job.row_index,
                    now,
                    key,
                ),
            )
            if was_closed and not job.is_closed and job.apply_url:
                return "reopened", True
            return "unchanged", False

    def mark_notified(self, job_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET last_notified_at = ? WHERE id = ?",
                (utc_now(), job_id),
            )

    def save_resume_version(
        self, job_id: str, source_path: str, tailored_path: str
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO resume_versions (job_id, source_path, tailored_path, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, source_path, tailored_path, utc_now()),
            )
            return int(cur.lastrowid)

    def latest_resume_for_job(self, job_id: str) -> ResumeVersion | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM resume_versions
                WHERE job_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (job_id,),
            ).fetchone()
        if not row:
            return None
        return ResumeVersion(
            id=row["id"],
            job_id=row["job_id"],
            source_path=row["source_path"],
            tailored_path=row["tailored_path"],
            created_at=row["created_at"],
        )

    def list_jobs(self, active_only: bool = False) -> list[sqlite3.Row]:
        query = "SELECT * FROM jobs"
        if active_only:
            query += " WHERE is_closed = 0 AND apply_url IS NOT NULL"
        query += " ORDER BY row_index ASC, last_seen_at DESC"
        with self._conn() as conn:
            return list(conn.execute(query))

    def get_sync_value(self, key: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM sync_state WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else None

    def set_sync_value(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO sync_state (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )


class LocalDatabase(_BaseDB):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL UNIQUE,
                    resume_version_id INTEGER,
                    status TEXT NOT NULL,
                    applied_at TEXT,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS revise_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telegram_job_messages (
                    telegram_message_id INTEGER PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def save_telegram_message(self, message_id: int, job_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO telegram_job_messages (telegram_message_id, job_id, created_at)
                VALUES (?, ?, ?)
                """,
                (message_id, job_id, utc_now()),
            )

    def job_id_for_telegram_message(self, message_id: int) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT job_id FROM telegram_job_messages WHERE telegram_message_id = ?",
                (message_id,),
            ).fetchone()
        return row["job_id"] if row else None

    def append_revise_message(self, job_id: str, role: str, content: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO revise_messages (job_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, role, content, utc_now()),
            )

    def get_revise_history(self, job_id: str, limit: int = 20) -> list[tuple[str, str]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT role, content FROM revise_messages
                WHERE job_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (job_id, limit),
            ).fetchall()
        return [(r["role"], r["content"]) for r in reversed(rows)]

    def log_application(
        self,
        job_id: str,
        status: str,
        resume_version_id: int | None = None,
        notes: str = "",
    ) -> None:
        now = utc_now() if status == "applied" else None
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO applications (job_id, resume_version_id, status, applied_at, notes)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    resume_version_id = excluded.resume_version_id,
                    status = excluded.status,
                    applied_at = excluded.applied_at,
                    notes = excluded.notes
                """,
                (job_id, resume_version_id, status, now, notes),
            )


Database = ScannerDatabase


def job_id(company: str, role: str, location: str) -> str:
    return legacy_job_id(company, role, location)
