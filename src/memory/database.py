"""SQLite access layer. Tables are append-only in spirit: memory is never overwritten."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.core.errors import DatabaseError

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, topic TEXT NOT NULL,
    learner_level TEXT, max_retries INTEGER, status TEXT NOT NULL, attempts_count INTEGER NOT NULL,
    provider TEXT, simulated INTEGER NOT NULL, prompt_version TEXT, rubric_version TEXT,
    message TEXT, final_lesson TEXT, rejected_lesson TEXT, error TEXT, rejection_log_json TEXT
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL REFERENCES runs(id),
    attempt_no INTEGER NOT NULL, lesson TEXT NOT NULL, passed INTEGER NOT NULL,
    evaluation_json TEXT NOT NULL, feedback_sent TEXT, changes_from_previous TEXT
);
CREATE TABLE IF NOT EXISTS check_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL REFERENCES runs(id),
    attempt_no INTEGER NOT NULL, check_id TEXT NOT NULL, status TEXT NOT NULL, reason TEXT, correction TEXT
);
CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL REFERENCES runs(id),
    check_id TEXT NOT NULL, failed_attempt INTEGER NOT NULL, fixed_attempt INTEGER NOT NULL,
    correction_text TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learned_guidance (
    id INTEGER PRIMARY KEY AUTOINCREMENT, check_id TEXT NOT NULL UNIQUE, guidance TEXT NOT NULL,
    reason TEXT NOT NULL, prompt_version TEXT NOT NULL, fail_run_count INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prompt_versions (
    version TEXT PRIMARY KEY, description TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rubric_versions (
    content_hash TEXT PRIMARY KEY, version TEXT NOT NULL, checkpoint_ids TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL REFERENCES runs(id),
    rating INTEGER, comment TEXT, created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        try:
            conn = sqlite3.connect(self.path, timeout=10)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Cannot open database '{self.path}': {exc}") from exc
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise DatabaseError(f"Database error: {exc}") from exc
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
