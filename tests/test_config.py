import pytest

from src.utils.config import (
    DEFAULT_LEARNING_THRESHOLD,
    load_settings,
    parse_learning_threshold,
)


def test_missing_threshold_uses_documented_default(monkeypatch):
    monkeypatch.delenv("LEARNING_THRESHOLD", raising=False)
    assert load_settings().learning_threshold == DEFAULT_LEARNING_THRESHOLD


def test_empty_threshold_is_rejected(monkeypatch):
    monkeypatch.setenv("LEARNING_THRESHOLD", "")
    with pytest.raises(ValueError, match="must not be empty"):
        load_settings()


@pytest.mark.parametrize("value", ["3", 3])
def test_valid_threshold_is_parsed(value):
    assert parse_learning_threshold(value) == 3


@pytest.mark.parametrize("value", ["abc", "", None])
def test_invalid_ui_threshold_is_rejected(value):
    if value is None:
        assert parse_learning_threshold(value) == DEFAULT_LEARNING_THRESHOLD
    else:
        with pytest.raises(ValueError):
            parse_learning_threshold(value, source="Learning threshold")


@pytest.mark.parametrize("value", ["0", "11", -1, 11])
def test_out_of_range_threshold_is_rejected(value):
    with pytest.raises(ValueError, match="between|whole number"):
        parse_learning_threshold(value)


def test_invalid_environment_threshold_is_not_silently_defaulted(monkeypatch):
    monkeypatch.setenv("LEARNING_THRESHOLD", "not-a-number")
    with pytest.raises(ValueError, match="whole number"):
        load_settings()
