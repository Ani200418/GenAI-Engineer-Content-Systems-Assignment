from src.providers.anthropic_provider import DEFAULT_MODEL, AnthropicProvider
from src.providers.base import LLMProvider
from src.providers.mock_provider import SCENARIOS, MockProvider


def create_provider(mode: str, *, api_key: str | None = None, model: str | None = None,
                    scenario: str = "retry") -> LLMProvider:
    mode = (mode or "").strip().lower()
    if mode == "mock":
        return MockProvider(scenario)
    if mode == "anthropic":
        return AnthropicProvider(api_key=api_key, model=model or DEFAULT_MODEL)
    raise ValueError(f"Unknown provider mode '{mode}'. Use 'mock' or 'anthropic'.")


__all__ = ["create_provider", "LLMProvider", "MockProvider", "AnthropicProvider", "SCENARIOS"]
