import pytest
from pydantic import ValidationError

from src.core.schemas import LessonRequest, RunStatus


def test_05_zero_retries_means_exactly_one_generation(make_pipeline, request_rag):
    pipe = make_pipeline("always_fail")
    r = pipe.orchestrator.run(request_rag(0))
    assert len(r.attempts) == 1 and pipe.provider.generate_calls == 1
    assert r.status == RunStatus.REJECTED and r.attempts[0].feedback_sent is None


def test_one_retry_means_at_most_two_generations(make_pipeline, request_rag):
    pipe = make_pipeline("always_fail")
    pipe.orchestrator.run(request_rag(1))
    assert pipe.provider.generate_calls == 2


def test_06_never_more_than_two_retries(make_pipeline, request_rag):
    pipe = make_pipeline("always_fail")
    r = pipe.orchestrator.run(request_rag(2))
    assert pipe.provider.generate_calls == 3 and pipe.provider.evaluate_calls == 3 and len(r.attempts) == 3
    with pytest.raises(ValidationError):
        LessonRequest(topic="RAG", max_retries=3)


def test_orchestrator_clamps_even_if_schema_is_bypassed(make_pipeline):
    pipe = make_pipeline("always_fail")
    req = LessonRequest.model_construct(topic="RAG", learner_level="x", max_retries=50)  # bypass validation
    r = pipe.orchestrator.run(req)
    assert len(r.attempts) == 3


def test_stops_as_soon_as_lesson_passes(make_pipeline, request_rag):
    pipe = make_pipeline("retry")
    pipe.orchestrator.run(request_rag(2))
    assert pipe.provider.generate_calls == 2  # third attempt never happens


def test_feedback_contains_every_failed_checkpoint_with_correction(make_pipeline, request_rag):
    r = make_pipeline("retry").orchestrator.run(request_rag())
    fb = r.attempts[0].feedback_sent
    for f in r.attempts[0].evaluation.failed_checks:
        assert f"[{f.check_id}]" in fb and f.correction in fb and f.reason in fb


def test_rejection_log_entries_are_complete(make_pipeline, request_rag):
    r = make_pipeline("slow").orchestrator.run(request_rag())
    assert [e.attempt_no for e in r.rejection_log] == [1, 2]
    first, second = r.rejection_log
    assert first.failed_check_ids == ["R5", "R6"] and first.outcome == "REGENERATED"
    assert first.next_attempt_passed is False and "Fixed: R5" in first.changes_in_next_version
    assert second.failed_check_ids == ["R6"] and second.next_attempt_passed is True
    assert first.lesson_version == "v1" and first.feedback_sent_to_generator
