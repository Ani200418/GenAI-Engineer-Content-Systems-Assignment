"""Reads and writes everything the system remembers between runs."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src.core.rubric import ALL_IDS, RUBRIC_VERSION, rubric_hash
from src.core.schemas import LearnedGuidance, RunResult, Verdict
from src.memory.database import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MemoryManager:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ---- writing -------------------------------------------------------------------------------
    def save_run(self, result: RunResult) -> int:
        """Persist one run with all attempts, check results, successful corrections and versions."""
        now = _now()
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO runs (created_at, topic, learner_level, max_retries, status, attempts_count, provider, "
                "simulated, prompt_version, rubric_version, message, final_lesson, rejected_lesson, error, "
                "rejection_log_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (now, result.request.topic, result.request.learner_level, result.request.max_retries,
                 result.status.value, len(result.attempts), result.provider_name, int(result.simulated),
                 result.prompt_version, result.rubric_version, result.message, result.final_lesson,
                 result.rejected_lesson, result.error,
                 json.dumps([e.model_dump(mode="json") for e in result.rejection_log])),
            )
            run_id = int(cur.lastrowid)
            for a in result.attempts:
                conn.execute(
                    "INSERT INTO attempts (run_id, attempt_no, lesson, passed, evaluation_json, feedback_sent, "
                    "changes_from_previous) VALUES (?,?,?,?,?,?,?)",
                    (run_id, a.attempt_no, a.lesson, int(a.passed), a.evaluation.model_dump_json(),
                     a.feedback_sent, a.changes_from_previous),
                )
                for c in a.evaluation.checks:
                    conn.execute(
                        "INSERT INTO check_results (run_id, attempt_no, check_id, status, reason, correction) "
                        "VALUES (?,?,?,?,?,?)",
                        (run_id, a.attempt_no, c.check_id, c.status.value, c.reason, c.correction),
                    )
            # successful corrections: failed in attempt k, passed in attempt k+1
            for prev, nxt in zip(result.attempts, result.attempts[1:]):
                passed_next = {c.check_id for c in nxt.evaluation.checks if c.status == Verdict.PASS}
                for c in prev.evaluation.failed_checks:
                    if c.check_id in passed_next:
                        conn.execute(
                            "INSERT INTO corrections (run_id, check_id, failed_attempt, fixed_attempt, correction_text, "
                            "created_at) VALUES (?,?,?,?,?,?)",
                            (run_id, c.check_id, prev.attempt_no, nxt.attempt_no, c.correction, now),
                        )
            conn.execute("INSERT OR IGNORE INTO prompt_versions (version, description, created_at) VALUES (?,?,?)",
                         (result.prompt_version, f"{len(result.guidance_used)} learned guidance item(s) active", now))
            conn.execute("INSERT OR IGNORE INTO rubric_versions (content_hash, version, checkpoint_ids, created_at) "
                         "VALUES (?,?,?,?)", (rubric_hash(), RUBRIC_VERSION, ",".join(ALL_IDS), now))
        return run_id

    def add_guidance(self, check_id: str, guidance: str, reason: str, prompt_version: str, fail_run_count: int) -> bool:
        """Insert-only. Returns False if guidance for this checkpoint already exists (never overwritten)."""
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO learned_guidance (check_id, guidance, reason, prompt_version, fail_run_count, "
                "created_at) VALUES (?,?,?,?,?,?)",
                (check_id, guidance, reason, prompt_version, fail_run_count, _now()),
            )
            return cur.rowcount == 1

    def add_user_feedback(self, run_id: int, rating: int | None, comment: str) -> None:
        with self.db.connect() as conn:
            conn.execute("INSERT INTO user_feedback (run_id, rating, comment, created_at) VALUES (?,?,?,?)",
                         (run_id, rating, comment, _now()))

    # ---- reading -------------------------------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) total, "
                "COALESCE(SUM(status='APPROVED'),0) approved, COALESCE(SUM(status='REJECTED'),0) rejected, "
                "COALESCE(SUM(status='ERROR'),0) errors, "
                "COALESCE(SUM(status='APPROVED' AND attempts_count=1),0) first_try, "
                "COALESCE(SUM(status='APPROVED' AND attempts_count>1),0) after_regen FROM runs").fetchone()
        return {"total_runs": row["total"], "approved": row["approved"], "rejected": row["rejected"],
                "errors": row["errors"], "approved_first_attempt": row["first_try"],
                "approved_after_regeneration": row["after_regen"]}

    def failure_frequency(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT check_id, COUNT(DISTINCT run_id) runs_failed, COUNT(*) total_failures FROM check_results "
                "WHERE status='FAIL' GROUP BY check_id ORDER BY runs_failed DESC, total_failures DESC, check_id").fetchall()
        return [dict(r) for r in rows]

    def guidance(self) -> list[LearnedGuidance]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM learned_guidance ORDER BY id").fetchall()
        return [LearnedGuidance(id=r["id"], check_id=r["check_id"], guidance=r["guidance"], reason=r["reason"],
                                prompt_version=r["prompt_version"], created_at=r["created_at"]) for r in rows]

    def latest_correction(self, check_id: str) -> str | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT correction_text FROM corrections WHERE check_id=? AND correction_text != '' "
                               "ORDER BY id DESC LIMIT 1", (check_id,)).fetchone()
        return row["correction_text"] if row else None

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT id, created_at, topic, status, attempts_count, provider, simulated, prompt_version, "
                "rubric_version FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_rejection_log(self, run_id: int) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT rejection_log_json FROM runs WHERE id=?", (run_id,)).fetchone()
        return json.loads(row["rejection_log_json"]) if row and row["rejection_log_json"] else []

    def corrections(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM corrections ORDER BY id").fetchall()]

    def user_feedback(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM user_feedback ORDER BY id").fetchall()]

    def version_history(self) -> dict[str, list[dict[str, Any]]]:
        with self.db.connect() as conn:
            return {
                "prompt_versions": [dict(r) for r in conn.execute("SELECT * FROM prompt_versions ORDER BY created_at")],
                "rubric_versions": [dict(r) for r in conn.execute("SELECT * FROM rubric_versions ORDER BY created_at")],
            }

    def export_history(self) -> dict[str, Any]:
        return {"stats": self.stats(), "runs": self.list_runs(1000), "failure_frequency": self.failure_frequency(),
                "learned_guidance": [g.model_dump() for g in self.guidance()], "corrections": self.corrections(),
                "user_feedback": self.user_feedback(), "versions": self.version_history()}
