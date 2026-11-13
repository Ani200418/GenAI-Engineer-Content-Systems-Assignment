"""Provider abstraction: the rest of the app only knows this interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.errors import MissingAPIKeyError, ProviderError  # re-exported

__all__ = ["LLMProvider", "ProviderError", "MissingAPIKeyError"]


class LLMProvider(ABC):
    name: str = "provider"
    is_simulated: bool = False

    @abstractmethod
    def complete(self, system: str, user: str, *, task: str, max_tokens: int = 4096) -> str:
        """Return the model's text. `task` is "generate" or "evaluate"."""
