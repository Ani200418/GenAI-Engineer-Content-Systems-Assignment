"""Generate Agent: writes (or rewrites) the lesson. It never judges its own output."""
from __future__ import annotations

import re

from src.core.errors import GenerationError
from src.core.prompts import GENERATOR_SYSTEM, build_generator_prompt
from src.core.schemas import LearnedGuidance, LessonRequest
from src.knowledge_base.loader import KnowledgeBase
from src.providers.base import LLMProvider

_FENCE = re.compile(r"^```(?:markdown|md)?\s*\n|\n```\s*$", re.I)


class LessonGenerator:
    def __init__(self, provider: LLMProvider, kb: KnowledgeBase) -> None:
        self.provider = provider
        self.kb = kb

    def generate(self, request: LessonRequest, guidance: list[LearnedGuidance],
                 feedback: str | None = None, previous_lesson: str | None = None) -> str:
        prompt = build_generator_prompt(
            request.topic, request.learner_level, self.kb.raw,
            [f"- [{g.check_id}] {g.guidance}" for g in guidance], feedback, previous_lesson,
        )
        text = self.provider.complete(GENERATOR_SYSTEM, prompt, task="generate", max_tokens=6000)
        lesson = _FENCE.sub("", (text or "").strip()).strip()
        if len(lesson) < 200:
            raise GenerationError("The generator returned an empty or far too short lesson.")
        return lesson
