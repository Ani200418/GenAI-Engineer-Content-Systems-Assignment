"""All custom exceptions in one place so callers can catch them precisely."""


class LessonGenError(Exception):
    """Base class for all application errors."""


class ProviderError(LessonGenError):
    """The LLM provider failed (network, rate limit, timeout, empty reply)."""


class MissingAPIKeyError(ProviderError):
    """Real mode was requested but no API key is configured."""


class GenerationError(LessonGenError):
    """The generator returned unusable output."""


class EvaluationError(LessonGenError):
    """The evaluator output was invalid or incomplete. Never treated as a pass."""


class ReferenceMaterialError(LessonGenError):
    """The reference knowledge base is missing or malformed."""


class DatabaseError(LessonGenError):
    """SQLite persistence failed."""
