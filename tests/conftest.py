import logging

import pytest

from src.core.factory import build_pipeline
from src.core.schemas import LessonRequest
from src.knowledge_base.loader import load_knowledge_base
from src.providers.mock_provider import MockProvider
from src.utils.logger import get_logger

get_logger().setLevel(logging.CRITICAL)


@pytest.fixture
def kb():
    return load_knowledge_base()


@pytest.fixture
def make_pipeline(tmp_path):
    """make_pipeline(scenario, provider=None, threshold=2, db='memory.db')"""
    def _make(scenario="retry", provider=None, threshold=2, db="memory.db"):
        return build_pipeline("mock", scenario, db_path=tmp_path / db, learning_threshold=threshold, provider=provider)
    return _make


@pytest.fixture
def request_rag():
    def _make(retries=2):
        return LessonRequest(topic="Introduction to RAG", max_retries=retries)
    return _make


class FlipProvider(MockProvider):
    """Mock whose evaluator marks chosen checkpoints FAIL (to test that any single failure blocks approval)."""
    def __init__(self, scenario="clean", flip=("R3",)):
        super().__init__(scenario)
        self.flip = set(flip)

    def _evaluate(self, user):
        import json
        data = json.loads(super()._evaluate(user))
        for c in data["checks"]:
            if c["check_id"] in self.flip:
                c.update(status="FAIL", reason="forced failure", correction="fix it")
        return json.dumps(data)


class BadEvaluatorProvider(MockProvider):
    """Mock whose evaluator returns whatever `payload` says (garbage / incomplete JSON)."""
    def __init__(self, payload):
        super().__init__("clean")
        self.payload = payload

    def _evaluate(self, user):
        self.evaluate_calls += 1
        return self.payload


class SpyProvider(MockProvider):
    """Mock that records every (task, prompt) so tests can inspect what the generator was sent."""
    def __init__(self, scenario="clean"):
        super().__init__(scenario)
        self.prompts = []

    def complete(self, system, user, *, task, max_tokens=4096):
        self.prompts.append((task, user))
        return super().complete(system, user, task=task, max_tokens=max_tokens)
