from src.core.schemas import REJECTED_MESSAGE, RunStatus, Stage
from tests.conftest import BadEvaluatorProvider, FlipProvider


def test_01_first_attempt_approved(make_pipeline, request_rag):
    r = make_pipeline("clean").orchestrator.run(request_rag())
    assert r.status == RunStatus.APPROVED and len(r.attempts) == 1
    assert r.final_lesson and r.rejection_log == [] and "APPROVED" in r.message


def test_02_fail_then_pass_on_second_attempt(make_pipeline, request_rag):
    r = make_pipeline("retry").orchestrator.run(request_rag())
    assert r.status == RunStatus.APPROVED and len(r.attempts) == 2
    assert r.attempts[0].evaluation.failed_ids == ["R5", "R6"]
    assert r.attempts[0].feedback_sent and "[R5]" in r.attempts[0].feedback_sent
    assert "Fixed: R5, R6" in r.attempts[1].changes_from_previous


def test_03_two_failures_then_pass_on_third(make_pipeline, request_rag):
    r = make_pipeline("slow").orchestrator.run(request_rag(2))
    assert r.status == RunStatus.APPROVED and len(r.attempts) == 3
    assert [a.passed for a in r.attempts] == [False, False, True]


def test_04_all_attempts_fail_is_rejected_not_approved(make_pipeline, request_rag):
    r = make_pipeline("always_fail").orchestrator.run(request_rag(2))
    assert r.status == RunStatus.REJECTED and len(r.attempts) == 3
    assert r.message == REJECTED_MESSAGE
    assert r.final_lesson is None and r.rejected_lesson  # never labelled approved
    assert r.rejection_log[-1].outcome == "REJECTED_FINAL"


def test_08_failed_checkpoint_blocks_approval_end_to_end(make_pipeline, request_rag):
    pipe = make_pipeline(provider=FlipProvider("clean", flip=("R9",)))
    r = pipe.orchestrator.run(request_rag(1))
    assert r.status == RunStatus.REJECTED and r.final_lesson is None and len(r.attempts) == 2


def test_09_invalid_evaluator_output_never_approves(make_pipeline, request_rag):
    for payload in ("not json", '{"checks": []}'):
        prov = BadEvaluatorProvider(payload)
        r = make_pipeline(provider=prov).orchestrator.run(request_rag())
        assert r.status == RunStatus.ERROR and r.final_lesson is None
        assert "EvaluationError" in r.error and r.stage_log[-1].stage == Stage.ERROR
        assert prov.generate_calls == 1  # stopped safely, no endless regeneration


def test_provider_failure_is_reported_as_error(make_pipeline, request_rag):
    from src.core.errors import ProviderError
    from src.providers.mock_provider import MockProvider

    class Down(MockProvider):
        def _generate(self, user):
            raise ProviderError("rate limited")
    r = make_pipeline(provider=Down("clean")).orchestrator.run(request_rag())
    assert r.status == RunStatus.ERROR and "rate limited" in r.error and r.final_lesson is None


def test_stage_callback_receives_stages_in_order(make_pipeline, request_rag):
    seen = []
    make_pipeline("retry").orchestrator.run(request_rag(), lambda s, a, m: seen.append((s, a)))
    assert [s for s, _ in seen] == [Stage.GENERATING, Stage.EVALUATING, Stage.REGENERATING, Stage.EVALUATING, Stage.APPROVED]


def test_broken_callback_does_not_break_pipeline(make_pipeline, request_rag):
    def boom(*a):
        raise RuntimeError("ui crashed")
    assert make_pipeline("clean").orchestrator.run(request_rag(), boom).status == RunStatus.APPROVED


def test_missing_reference_material_is_a_clear_error(tmp_path):
    import pytest
    from src.core.errors import ReferenceMaterialError
    from src.core.factory import build_pipeline
    with pytest.raises(ReferenceMaterialError):
        build_pipeline("mock", db_path=tmp_path / "x.db", kb_path=tmp_path / "missing.md")
    (tmp_path / "empty.md").write_text("# nothing here")
    with pytest.raises(ReferenceMaterialError):
        build_pipeline("mock", db_path=tmp_path / "x.db", kb_path=tmp_path / "empty.md")
