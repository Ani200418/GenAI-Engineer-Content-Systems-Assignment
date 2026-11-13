import json

import pytest

from src.agents.evaluator import LessonEvaluator, parse_llm_checks
from src.agents.generator import LessonGenerator
from src.core.errors import EvaluationError
from src.core.rubric import ALL_IDS, LLM_IDS
from src.core.schemas import LessonRequest
from src.providers.mock_provider import MockProvider
from tests.conftest import BadEvaluatorProvider, FlipProvider


def _lesson(kb, scenario="clean"):
    return LessonGenerator(MockProvider(scenario), kb).generate(LessonRequest(topic="RAG"), [])


def test_every_mandatory_checkpoint_is_evaluated(kb):
    result = LessonEvaluator(MockProvider("clean"), kb).evaluate(_lesson(kb))
    assert sorted(c.check_id for c in result.checks) == sorted(ALL_IDS)
    assert result.passed and result.simulated


def test_any_single_failed_checkpoint_prevents_approval(kb):
    for cid in ("R1", "R7", "R10"):
        ev = LessonEvaluator(FlipProvider("clean", flip=(cid,)), kb)
        result = ev.evaluate(_lesson(kb))
        assert not result.passed and result.failed_ids == [cid]


def test_defective_lesson_fails_the_right_checks(kb):
    result = LessonEvaluator(MockProvider("retry"), kb).evaluate(_lesson(kb, "retry"))
    assert set(result.failed_ids) == {"R5", "R6"}
    assert all(c.correction for c in result.failed_checks)
    assert all(c.evidence for c in result.checks)


@pytest.mark.parametrize("payload", [
    "this is not json",
    "",
    '{"checks": "nope"}',
    '{"checks": []}',
    json.dumps({"checks": [{"check_id": "R1", "name": "Accuracy", "status": "PASS", "evidence": "x", "reason": "y"}]}),
    json.dumps({"checks": [{"check_id": i, "name": "n", "status": "MAYBE", "evidence": "x"} for i in LLM_IDS]}),
])
def test_invalid_evaluator_output_raises_and_never_passes(kb, payload):
    ev = LessonEvaluator(BadEvaluatorProvider(payload), kb)
    with pytest.raises(EvaluationError):
        ev.evaluate(_lesson(kb))


def test_missing_checkpoint_is_rejected(kb):
    good = json.loads(MockProvider("clean")._evaluate("=== LESSON TO EVALUATE ===\n" + _lesson(kb) + "\n=== END LESSON ==="))
    good["checks"] = [c for c in good["checks"] if c["check_id"] != "R4"]
    with pytest.raises(EvaluationError, match="R4"):
        parse_llm_checks(json.dumps(good))


def test_pass_without_evidence_is_downgraded_to_fail():
    checks = [{"check_id": i, "name": "n", "status": "PASS", "evidence": "ok text", "reason": "r"} for i in LLM_IDS]
    checks[2]["evidence"] = ""
    parsed = parse_llm_checks(json.dumps({"checks": checks}))
    r3 = next(c for c in parsed if c.check_id == "R3")
    assert r3.status.value == "FAIL" and "without evidence" in r3.reason and r3.correction


def test_malformed_json_gets_one_retry_then_succeeds(kb):
    class Flaky(MockProvider):
        def _evaluate(self, user):
            if self.evaluate_calls == 0:
                self.evaluate_calls += 1
                return "garbage"
            return super()._evaluate(user)
    prov = Flaky("clean")
    result = LessonEvaluator(prov, kb).evaluate(_lesson(kb))
    assert result.passed and prov.evaluate_calls == 2


def test_json_in_code_fence_is_accepted(kb):
    raw = MockProvider("clean")._evaluate("=== LESSON TO EVALUATE ===\n" + _lesson(kb) + "\n=== END LESSON ===")
    assert len(parse_llm_checks("```json\n" + raw + "\n```")) == len(LLM_IDS)
