"""Orchestrator: INPUT -> GENERATE -> EVALUATE -> REGENERATE -> FINAL OUTPUT -> MEMORY UPDATE.

Termination is guaranteed: the loop is a bounded `for` over at most 1 + MAX_RETRIES_LIMIT attempts.
"""
from __future__ import annotations

import difflib
from typing import Callable, Optional

from src.agents.evaluator import LessonEvaluator
from src.agents.generator import LessonGenerator
from src.core.errors import (DatabaseError, EvaluationError, GenerationError, ProviderError,
                             ReferenceMaterialError)
from src.core.rubric import ALL_IDS, RUBRIC_VERSION
from src.core.prompts import GENERATOR_PROMPT_VERSION
from src.core.schemas import (MAX_RETRIES_LIMIT, REJECTED_MESSAGE, AttemptRecord, EvaluationResult,
                              LearnedGuidance, LessonRequest, RejectionLogEntry, RunResult, RunStatus, Stage,
                              StageEvent)
from src.knowledge_base.loader import KnowledgeBase
from src.memory.learning_engine import LearningEngine
from src.memory.memory_manager import MemoryManager
from src.utils.logger import get_logger

log = get_logger()
StageCallback = Callable[[Stage, int, str], None]


def build_feedback(evaluation: EvaluationResult) -> str:
    """The exact text sent back to the generator after a failed attempt."""
    lines = ["The previous lesson was REJECTED. Fix EVERY failed checkpoint below and keep everything that passed."]
    for c in evaluation.failed_checks:
        lines.append(f"[{c.check_id}] {c.name} — FAILED\n  Why: {c.reason}\n  Evidence: {c.evidence}\n"
                     f"  Correction required: {c.correction}")
    return "\n".join(lines)


def summarize_changes(prev: AttemptRecord, curr: AttemptRecord) -> str:
    before, after = set(prev.evaluation.failed_ids), set(curr.evaluation.failed_ids)
    sm = difflib.SequenceMatcher(None, prev.lesson.splitlines(), curr.lesson.splitlines())
    changed = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")
    fmt = lambda s: ", ".join(sorted(s)) or "none"  # noqa: E731
    return (f"Fixed: {fmt(before - after)}. Still failing: {fmt(before & after)}. Newly failing: {fmt(after - before)}. "
            f"About {changed} line(s) changed; words {prev.word_count} -> {curr.word_count}.")


def build_rejection_log(attempts: list[AttemptRecord]) -> list[RejectionLogEntry]:
    log_entries: list[RejectionLogEntry] = []
    for i, a in enumerate(attempts):
        if a.passed:
            continue
        nxt = attempts[i + 1] if i + 1 < len(attempts) else None
        log_entries.append(RejectionLogEntry(
            attempt_no=a.attempt_no, lesson_version=f"v{a.attempt_no}", failed_check_ids=a.evaluation.failed_ids,
            failures=a.evaluation.failed_checks, feedback_sent_to_generator=a.feedback_sent,
            changes_in_next_version=nxt.changes_from_previous if nxt else None,
            next_attempt_passed=nxt.passed if nxt else None,
            outcome="REGENERATED" if nxt else "REJECTED_FINAL"))
    return log_entries


class LessonOrchestrator:
    def __init__(self, generator: LessonGenerator, evaluator: LessonEvaluator, kb: KnowledgeBase,
                 memory: Optional[MemoryManager] = None, learning: Optional[LearningEngine] = None,
                 provider_name: str = "", simulated: bool = False) -> None:
        if not kb or not kb.notes:
            raise ReferenceMaterialError("Reference material is required to run the pipeline.")
        self.generator, self.evaluator, self.kb = generator, evaluator, kb
        self.memory, self.learning = memory, learning
        self.provider_name, self.simulated = provider_name, simulated

    def run(self, request: LessonRequest, on_stage: Optional[StageCallback] = None) -> RunResult:
        stage_log: list[StageEvent] = []
        warnings: list[str] = []

        def emit(stage: Stage, attempt: int, message: str) -> None:
            stage_log.append(StageEvent(stage=stage, attempt=attempt, message=message))
            log.info("stage=%s attempt=%d %s", stage.value, attempt, message)
            if on_stage:
                try:
                    on_stage(stage, attempt, message)
                except Exception as exc:  # UI callback problems must never break the pipeline
                    log.warning("stage callback failed: %s", type(exc).__name__)

        guidance = self._load_guidance(warnings)
        prompt_version = f"{GENERATOR_PROMPT_VERSION}+g{len(guidance)}"
        attempts: list[AttemptRecord] = []
        status, error = RunStatus.ERROR, None
        max_attempts = 1 + min(request.max_retries, MAX_RETRIES_LIMIT)
        feedback: Optional[str] = None
        previous: Optional[str] = None

        try:
            for n in range(1, max_attempts + 1):
                if n == 1:
                    emit(Stage.GENERATING, n, f"Attempt {n}/{max_attempts}: generating the first lesson.")
                else:
                    emit(Stage.REGENERATING, n, f"Attempt {n}/{max_attempts}: regenerating with evaluator feedback.")
                lesson = self.generator.generate(request, guidance, feedback, previous)
                emit(Stage.EVALUATING, n, f"Attempt {n}/{max_attempts}: evaluating against {len(ALL_IDS)} mandatory checkpoints.")
                evaluation = self.evaluator.evaluate(lesson, request.topic, request.learner_level)
                record = AttemptRecord(attempt_no=n, lesson=lesson, evaluation=evaluation)
                if attempts:
                    record.changes_from_previous = summarize_changes(attempts[-1], record)
                attempts.append(record)
                if evaluation.passed:
                    status = RunStatus.APPROVED
                    break
                if n < max_attempts:
                    feedback = build_feedback(evaluation)
                    record.feedback_sent = feedback
                    previous = lesson
                else:
                    status = RunStatus.REJECTED
        except (ProviderError, GenerationError, EvaluationError) as exc:
            status, error = RunStatus.ERROR, f"{type(exc).__name__}: {exc}"

        last = attempts[-1] if attempts else None
        if status == RunStatus.APPROVED and last:
            message = f"APPROVED — all {len(ALL_IDS)} mandatory checkpoints passed on attempt {last.attempt_no}."
        elif status == RunStatus.REJECTED:
            message = REJECTED_MESSAGE
        else:
            message = f"ERROR — the pipeline stopped safely and did NOT approve any lesson. {error}"
        emit({RunStatus.APPROVED: Stage.APPROVED, RunStatus.REJECTED: Stage.REJECTED}.get(status, Stage.ERROR),
             len(attempts), message)

        result = RunResult(
            request=request, status=status, message=message, attempts=attempts,
            rejection_log=build_rejection_log(attempts),
            final_lesson=last.lesson if status == RunStatus.APPROVED and last else None,
            rejected_lesson=last.lesson if status == RunStatus.REJECTED and last else None,
            provider_name=self.provider_name, simulated=self.simulated, prompt_version=prompt_version,
            rubric_version=RUBRIC_VERSION, guidance_used=guidance, stage_log=stage_log, warnings=warnings, error=error)
        self._persist(result)
        return result

    def _load_guidance(self, warnings: list[str]) -> list[LearnedGuidance]:
        if not self.learning:
            return []
        try:
            return self.learning.active_guidance()
        except DatabaseError as exc:
            warnings.append(f"Memory unavailable; running without learned guidance. ({exc})")
            return []

    def _persist(self, result: RunResult) -> None:
        if not self.memory:
            return
        try:
            result.run_id = self.memory.save_run(result)
            if self.learning:
                result.new_guidance = self.learning.update()
        except DatabaseError as exc:
            result.warnings.append(f"Run could not be saved to memory: {exc}")
            log.error("memory save failed: %s", exc)
