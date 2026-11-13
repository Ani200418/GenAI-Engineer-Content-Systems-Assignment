"""Evaluate Agent: independent checker. Combines deterministic checks with an LLM judge.

Safety rules enforced here:
* The LLM must return an entry for EVERY LLM checkpoint, no more, no fewer. Otherwise -> EvaluationError.
* A PASS without evidence is downgraded to FAIL. A FAIL without a correction gets a default correction.
* Malformed JSON is re-requested once; if it is still invalid we raise. We never assume a pass.
"""
from __future__ import annotations

import json
import re

from pydantic import ValidationError

from src.core.errors import EvaluationError
from src.core.prompts import EVALUATOR_SYSTEM, build_evaluator_prompt
from src.core.rubric import LLM_IDS, get_checkpoint
from src.core.schemas import CheckResult, EvaluationResult, Verdict
from src.knowledge_base.loader import KnowledgeBase
from src.providers.base import LLMProvider
from src.utils.logger import get_logger
from src.utils.validators import run_deterministic_checks

log = get_logger()


def parse_llm_checks(raw: str) -> list[CheckResult]:
    """Validate the judge's JSON. Raises EvaluationError on anything unexpected."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.I)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise EvaluationError("Evaluator did not return a JSON object.")
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"Evaluator returned malformed JSON: {exc.msg}") from exc
    items = data.get("checks") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise EvaluationError("Evaluator JSON has no 'checks' list.")
    try:
        checks = [CheckResult.model_validate({**i, "method": "llm"}) for i in items]
    except (ValidationError, TypeError) as exc:
        raise EvaluationError(f"Evaluator check entry is invalid: {exc}") from exc
    ids = [c.check_id for c in checks]
    missing = [i for i in LLM_IDS if i not in ids]
    extra = [i for i in ids if i not in LLM_IDS]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if missing or extra or dupes:
        raise EvaluationError(f"Evaluator checkpoints incomplete or wrong (missing={missing}, unexpected={extra}, duplicated={dupes}).")
    return [_enforce(c) for c in sorted(checks, key=lambda c: LLM_IDS.index(c.check_id))]


def _enforce(c: CheckResult) -> CheckResult:
    cp = get_checkpoint(c.check_id)
    c = c.model_copy(update={"name": cp.name})  # canonical name from the rubric
    if c.status == Verdict.PASS and len(c.evidence.strip()) < 3:
        return c.model_copy(update={
            "status": Verdict.FAIL,
            "reason": (c.reason + " ").lstrip() + "[Downgraded: evaluator gave PASS without evidence.]",
            "correction": f"Make the lesson clearly satisfy: {cp.pass_condition}",
        })
    if c.status == Verdict.FAIL and not c.correction.strip():
        return c.model_copy(update={"correction": f"Revise the lesson so that: {cp.pass_condition}"})
    return c


class LessonEvaluator:
    def __init__(self, provider: LLMProvider, kb: KnowledgeBase, format_retries: int = 1) -> None:
        self.provider = provider
        self.kb = kb
        self.format_retries = format_retries

    def evaluate(self, lesson: str, topic: str = "", learner_level: str = "") -> EvaluationResult:
        deterministic = run_deterministic_checks(lesson, self.kb)
        llm_checks = self._llm_checks(lesson, topic, learner_level)
        label = f"{self.provider.name} evaluator" + (" (SIMULATED heuristics, not a real LLM)" if self.provider.is_simulated else "")
        return EvaluationResult(checks=deterministic + llm_checks, evaluator_label=label,
                                simulated=self.provider.is_simulated)

    def _llm_checks(self, lesson: str, topic: str, level: str) -> list[CheckResult]:
        prompt = build_evaluator_prompt(lesson, self.kb.raw, topic, level)
        last_error: EvaluationError | None = None
        for attempt in range(self.format_retries + 1):
            raw = self.provider.complete(EVALUATOR_SYSTEM, prompt, task="evaluate", max_tokens=4000)
            try:
                return parse_llm_checks(raw)
            except EvaluationError as exc:
                last_error = exc
                log.warning("evaluator output invalid (attempt %d): %s", attempt + 1, exc)
                prompt += f"\n\nYour previous reply was rejected: {exc} Reply again with ONLY the valid JSON object."
        raise EvaluationError(f"Evaluator output stayed invalid after retry: {last_error}")
