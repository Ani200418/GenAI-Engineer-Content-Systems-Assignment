import pytest

from src.agents.generator import LessonGenerator
from src.core.errors import GenerationError, ProviderError
from src.core.schemas import LearnedGuidance, LessonRequest
from src.providers.base import LLMProvider
from src.providers.mock_provider import MockProvider
from src.utils.validators import run_deterministic_checks
from tests.conftest import SpyProvider


def test_generator_returns_full_lesson_that_passes_deterministic_checks(kb):
    lesson = LessonGenerator(MockProvider("clean"), kb).generate(LessonRequest(topic="RAG"), [])
    assert lesson.startswith("# ")
    assert all(c.status.value == "PASS" for c in run_deterministic_checks(lesson, kb))


def test_generator_prompt_contains_guidance_and_feedback(kb):
    spy = SpyProvider("retry")
    gen = LessonGenerator(spy, kb)
    g = LearnedGuidance(id=1, check_id="R5", guidance="Define every term.", reason="r", prompt_version="v", created_at="t")
    gen.generate(LessonRequest(topic="RAG"), [g], feedback="[R6] Practical example — FAILED", previous_lesson="old lesson")
    prompt = spy.prompts[0][1]
    assert "LEARNED GUIDANCE" in prompt and "[R5] Define every term." in prompt
    assert "EVALUATOR FEEDBACK" in prompt and "old lesson" in prompt
    assert "=== REFERENCE MATERIAL ===" in prompt


def test_generator_rejects_empty_output(kb):
    class Empty(MockProvider):
        def _generate(self, user):
            return "  "
    with pytest.raises(GenerationError):
        LessonGenerator(Empty("clean"), kb).generate(LessonRequest(topic="RAG"), [])


def test_generator_propagates_provider_error(kb):
    class Down(LLMProvider):
        name = "down"

        def complete(self, *a, **k):
            raise ProviderError("timeout")
    with pytest.raises(ProviderError):
        LessonGenerator(Down(), kb).generate(LessonRequest(topic="RAG"), [])


def test_empty_topic_and_invalid_retries_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        LessonRequest(topic="   ")
    for bad in (-1, 3, 10):
        with pytest.raises(ValidationError):
            LessonRequest(topic="RAG", max_retries=bad)


def test_deterministic_checks_catch_invented_reference_and_missing_sections(kb):
    lesson = LessonGenerator(MockProvider("clean"), kb).generate(LessonRequest(topic="RAG"), [])
    broken = lesson.replace("[N3]", "[N99]").replace("## Summary", "## Wrap up")
    results = {c.check_id: c for c in run_deterministic_checks(broken, kb)}
    assert results["D1"].status.value == "FAIL" and "Summary" in results["D1"].evidence
    assert results["D2"].status.value == "FAIL" and "N99" in results["D2"].reason
