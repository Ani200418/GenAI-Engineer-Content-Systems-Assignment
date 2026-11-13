import pytest

from src.core.errors import MissingAPIKeyError, ProviderError
from src.core.factory import build_pipeline
from src.core.schemas import LessonRequest, RunStatus
from src.providers import create_provider
from src.providers.anthropic_provider import AnthropicProvider
from src.providers.mock_provider import MockProvider
from src.utils.logger import redact


def test_13_mock_mode_runs_without_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    pipe = build_pipeline("mock", "clean", db_path=tmp_path / "m.db")
    r = pipe.orchestrator.run(LessonRequest(topic="Introduction to RAG"))
    assert r.status == RunStatus.APPROVED and r.simulated is True
    assert all(a.evaluation.simulated for a in r.attempts)
    assert "SIMULATED" in r.provider_name


def test_14_real_mode_without_key_gives_clear_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider()
    with pytest.raises(MissingAPIKeyError, match="mock"):
        create_provider("anthropic")


def test_unknown_mode_and_scenario():
    with pytest.raises(ValueError):
        create_provider("gpt")
    with pytest.raises(ValueError):
        MockProvider("nonsense")


def test_anthropic_provider_retries_rate_limits_then_gives_up():
    import anthropic
    sleeps = []
    prov = AnthropicProvider(api_key="test-key", max_attempts=3, sleep=sleeps.append)

    class Boom:
        calls = 0

        def create(self, **kw):
            Boom.calls += 1
            raise anthropic.RateLimitError("slow down", response=_resp(429), body=None)
    prov._client.messages = Boom()
    with pytest.raises(ProviderError, match="3 attempts"):
        prov.complete("s", "u", task="generate")
    assert Boom.calls == 3 and len(sleeps) == 2


def test_anthropic_provider_does_not_retry_client_errors():
    import anthropic
    prov = AnthropicProvider(api_key="test-key", sleep=lambda s: None)

    class Bad:
        calls = 0

        def create(self, **kw):
            Bad.calls += 1
            raise anthropic.BadRequestError("bad", response=_resp(400), body=None)
    prov._client.messages = Bad()
    with pytest.raises(ProviderError, match="400"):
        prov.complete("s", "u", task="evaluate")
    assert Bad.calls == 1


def test_anthropic_provider_success_and_empty_reply():
    class Block:
        type = "text"

        def __init__(self, t):
            self.text = t

    class Resp:
        def __init__(self, t):
            self.content = [Block(t)]

    class Fake:
        reply = "hello"

        def create(self, **kw):
            return Resp(Fake.reply)
    prov = AnthropicProvider(api_key="test-key")
    prov._client.messages = Fake()
    assert prov.complete("s", "u", task="generate") == "hello"
    Fake.reply = "   "
    with pytest.raises(ProviderError, match="empty"):
        prov.complete("s", "u", task="generate")


def test_secrets_are_redacted_in_logs():
    assert "sk-ant-abc123" not in redact("key sk-ant-abc123 leaked")
    assert "hunter2" not in redact("api_key=hunter2")


class _FakeResponse:
    """Minimal stand-in for an HTTP response, enough for the SDK's exception constructors."""
    def __init__(self, status):
        self.status_code = status
        self.headers = {}
        self.request = object()


def _resp(status):
    return _FakeResponse(status)
