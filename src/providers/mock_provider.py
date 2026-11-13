"""Deterministic SIMULATED provider. Works offline, needs no API key.

Scenarios (how the simulated generator behaves):
  clean        - always writes a flawless lesson.
  retry        - first draft has defects R5+R6; a defect is fixed when the prompt contains evaluator
                 feedback OR learned guidance mentioning that checkpoint (so memory visibly changes behaviour).
  slow         - scripted: draft 1 has R5+R6, draft 2 has R6, draft 3 is clean (needs both retries).
  always_fail  - every draft contains a factually wrong sentence (R1); ends in REJECTED.
"""
from __future__ import annotations

import json
import re

from src.core.errors import ProviderError
from src.knowledge_base.loader import load_knowledge_base
from src.providers.base import LLMProvider
from src.providers.mock_checks import evaluate_lesson
from src.providers.mock_lesson import build_lesson

SCENARIOS = ("clean", "retry", "slow", "always_fail")
_ID = re.compile(r"\[((?:R|D)\d+)\]")


def _block(prompt: str, start: str, end: str) -> str:
    m = re.search(re.escape(start) + r"(.*?)" + re.escape(end), prompt, flags=re.S)
    return m.group(1) if m else ""


class MockProvider(LLMProvider):
    name = "mock (SIMULATED)"
    is_simulated = True

    def __init__(self, scenario: str = "retry") -> None:
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown mock scenario '{scenario}'. Choose from {SCENARIOS}.")
        self.scenario = scenario
        self.generate_calls = 0
        self.evaluate_calls = 0
        self._kb = load_knowledge_base()

    def complete(self, system: str, user: str, *, task: str, max_tokens: int = 4096) -> str:
        if task == "generate":
            return self._generate(user)
        if task == "evaluate":
            return self._evaluate(user)
        raise ProviderError(f"Mock provider does not know task '{task}'.")

    def _defects(self, call_index: int, prompt: str) -> set[str]:
        if self.scenario == "clean":
            return set()
        if self.scenario == "always_fail":
            return {"R1"}
        if self.scenario == "slow":
            return [{"R5", "R6"}, {"R6"}, set()][min(call_index, 2)]
        fixed = set(_ID.findall(_block(prompt, "=== EVALUATOR FEEDBACK", "=== END FEEDBACK ==="))) | set(
            _ID.findall(_block(prompt, "=== LEARNED GUIDANCE", "=== END GUIDANCE ===")))
        return {"R5", "R6"} - fixed

    def _generate(self, user: str) -> str:
        idx = self.generate_calls
        self.generate_calls += 1
        return build_lesson(self._defects(idx, user), self._kb)

    def _evaluate(self, user: str) -> str:
        self.evaluate_calls += 1
        lesson = _block(user, "=== LESSON TO EVALUATE ===", "=== END LESSON ===").strip()
        return json.dumps({"checks": evaluate_lesson(lesson)})
