"""Real Claude provider with timeout, rate-limit and 5xx retry handling."""
from __future__ import annotations

import os
import time
from typing import Callable

from src.core.errors import MissingAPIKeyError, ProviderError
from src.providers.base import LLMProvider
from src.utils.logger import get_logger

DEFAULT_MODEL = "claude-sonnet-5-5"
log = get_logger()


class AnthropicProvider(LLMProvider):
    is_simulated = False

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        timeout: float = 90.0,
        max_attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise MissingAPIKeyError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file (see .env.example) "
                "or switch to mock mode (PROVIDER_MODE=mock) to run without an API key."
            )
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise ProviderError("The 'anthropic' package is not installed. Run: pip install -r requirements.txt") from exc
        self._sdk = anthropic
        self._client = anthropic.Anthropic(api_key=key, timeout=timeout, max_retries=0)
        self.model = model
        self.name = f"anthropic:{model}"
        self._max_attempts = max(1, max_attempts)
        self._sleep = sleep

    def complete(self, system: str, user: str, *, task: str, max_tokens: int = 4096) -> str:
        sdk = self._sdk
        retryable = (sdk.RateLimitError, sdk.APITimeoutError, sdk.APIConnectionError)
        for attempt in range(1, self._max_attempts + 1):
            try:
                resp = self._client.messages.create(
                    model=self.model, max_tokens=max_tokens, system=system,
                    messages=[{"role": "user", "content": user}],
                )
                text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
                if not text.strip():
                    raise ProviderError("The model returned an empty response.")
                return text
            except ProviderError:
                raise
            except retryable as exc:
                err = type(exc).__name__
            except sdk.APIStatusError as exc:
                if exc.status_code < 500:
                    raise ProviderError(f"Claude API error (HTTP {exc.status_code}): {type(exc).__name__}") from exc
                err = f"HTTP {exc.status_code}"
            except sdk.APIError as exc:
                raise ProviderError(f"Claude API error: {type(exc).__name__}") from exc

            log.warning("task=%s attempt=%d/%d failed with %s", task, attempt, self._max_attempts, err)
            if attempt == self._max_attempts:
                raise ProviderError(f"Claude API failed after {self._max_attempts} attempts ({err}).")
            self._sleep(2 ** attempt)
        raise ProviderError("unreachable")  # pragma: no cover
