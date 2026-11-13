"""Pydantic models for every structured object that crosses a module boundary."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field, field_validator

from src.core.rubric import ALL_IDS

MAX_RETRIES_LIMIT = 2
DEFAULT_TOPIC = "Introduction to RAG (Retrieval-Augmented Generation)"
DEFAULT_LEARNER_LEVEL = (
    "Class 12 graduate from India with limited English and no technical background"
)
REJECTED_MESSAGE = (
    "REJECTED — Maximum retry limit reached. The lesson did not satisfy all mandatory quality checks."
)


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class RunStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


class Stage(str, Enum):
    GENERATING = "Generating"
    EVALUATING = "Evaluating"
    REGENERATING = "Regenerating"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    ERROR = "Error"


class LessonRequest(BaseModel):
    topic: str
    learner_level: str = DEFAULT_LEARNER_LEVEL
    max_retries: int = Field(default=MAX_RETRIES_LIMIT, ge=0, le=MAX_RETRIES_LIMIT)

    @field_validator("topic")
    @classmethod
    def _topic_ok(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Topic must not be empty.")
        if len(v) > 200:
            raise ValueError("Topic must be at most 200 characters.")
        return v

    @field_validator("learner_level")
    @classmethod
    def _level_ok(cls, v: str) -> str:
        return (v or "").strip() or DEFAULT_LEARNER_LEVEL


class CheckResult(BaseModel):
    check_id: str
    name: str
    status: Verdict
    evidence: str = ""
    reason: str = ""
    correction: str = ""
    method: str = "llm"

    @field_validator("status", mode="before")
    @classmethod
    def _norm_status(cls, v):
        return v.strip().upper() if isinstance(v, str) else v


class EvaluationResult(BaseModel):
    checks: list[CheckResult]
    evaluator_label: str = "evaluator"
    simulated: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def passed(self) -> bool:
        """PASS only if the full rubric was evaluated AND every check is PASS."""
        ids = [c.check_id for c in self.checks]
        complete = sorted(ids) == sorted(ALL_IDS)
        return complete and all(c.status == Verdict.PASS for c in self.checks)

    @property
    def failed_checks(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == Verdict.FAIL]

    @property
    def failed_ids(self) -> list[str]:
        return [c.check_id for c in self.failed_checks]


class AttemptRecord(BaseModel):
    attempt_no: int
    lesson: str
    evaluation: EvaluationResult
    feedback_sent: Optional[str] = None          # feedback given to generator for the NEXT attempt
    changes_from_previous: Optional[str] = None  # what changed versus the previous attempt

    @property
    def word_count(self) -> int:
        return len(self.lesson.split())

    @property
    def passed(self) -> bool:
        return self.evaluation.passed


class RejectionLogEntry(BaseModel):
    attempt_no: int
    lesson_version: str
    failed_check_ids: list[str]
    failures: list[CheckResult]
    feedback_sent_to_generator: Optional[str]
    changes_in_next_version: Optional[str]
    next_attempt_passed: Optional[bool]
    outcome: str  # "REGENERATED" or "REJECTED_FINAL"


class StageEvent(BaseModel):
    stage: Stage
    attempt: int
    message: str
    at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


class LearnedGuidance(BaseModel):
    id: int
    check_id: str
    guidance: str
    reason: str
    prompt_version: str
    created_at: str


class RunResult(BaseModel):
    request: LessonRequest
    status: RunStatus
    message: str
    attempts: list[AttemptRecord] = []
    rejection_log: list[RejectionLogEntry] = []
    final_lesson: Optional[str] = None      # ONLY set when APPROVED
    rejected_lesson: Optional[str] = None   # last draft when REJECTED (never labelled approved)
    provider_name: str = ""
    simulated: bool = False
    prompt_version: str = ""
    rubric_version: str = ""
    guidance_used: list[LearnedGuidance] = []
    new_guidance: list[LearnedGuidance] = []
    stage_log: list[StageEvent] = []
    warnings: list[str] = []
    error: Optional[str] = None
    run_id: Optional[int] = None
