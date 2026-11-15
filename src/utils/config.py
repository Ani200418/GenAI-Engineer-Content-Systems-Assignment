"""Environment-based settings. Secrets are read from the environment only."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv is optional at runtime
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEARNING_THRESHOLD = 2
MIN_LEARNING_THRESHOLD = 1
MAX_LEARNING_THRESHOLD = 10


@dataclass(frozen=True)
class Settings:
    provider_mode: str
    api_key: str | None
    model: str
    evaluator_model: str | None
    learning_threshold: int
    db_dir: Path

    def db_path(self, mode: str) -> Path:
        """Mock and real runs use separate memory files so simulated failures never teach real runs."""
        return self.db_dir / ("memory_mock.db" if mode == "mock" else "memory_real.db")


def parse_learning_threshold(value: object, *, source: str = "LEARNING_THRESHOLD") -> int:
    """Parse and validate the number of failing runs required for learning."""
    if value is None:
        return DEFAULT_LEARNING_THRESHOLD
    if isinstance(value, bool):
        raise ValueError(f"{source} must be a whole number from {MIN_LEARNING_THRESHOLD} to {MAX_LEARNING_THRESHOLD}.")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{source} must not be empty; use a whole number from {MIN_LEARNING_THRESHOLD} to {MAX_LEARNING_THRESHOLD}.")
    try:
        threshold = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{source} must be a whole number from {MIN_LEARNING_THRESHOLD} to {MAX_LEARNING_THRESHOLD}."
        ) from exc
    if threshold < MIN_LEARNING_THRESHOLD or threshold > MAX_LEARNING_THRESHOLD:
        raise ValueError(
            f"{source} must be between {MIN_LEARNING_THRESHOLD} and {MAX_LEARNING_THRESHOLD}."
        )
    return threshold


def load_settings() -> Settings:
    db_dir = Path(os.getenv("LESSONGEN_DB_DIR", "data"))
    if not db_dir.is_absolute():
        db_dir = PROJECT_ROOT / db_dir
    threshold = parse_learning_threshold(os.getenv("LEARNING_THRESHOLD"))
    return Settings(
        provider_mode=os.getenv("PROVIDER_MODE", "mock").strip().lower() or "mock",
        api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        evaluator_model=os.getenv("EVALUATOR_MODEL") or None,
        learning_threshold=threshold,
        db_dir=db_dir,
    )
