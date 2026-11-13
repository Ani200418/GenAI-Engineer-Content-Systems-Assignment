"""Smoke test of the Streamlit UI using Streamlit's headless AppTest (no browser, mock mode only)."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _app(monkeypatch, tmp_path):
    monkeypatch.setenv("PROVIDER_MODE", "mock")
    monkeypatch.setenv("LESSONGEN_DB_DIR", str(tmp_path))
    return AppTest.from_file(APP, default_timeout=60)


def test_app_loads_and_runs_retry_scenario(monkeypatch, tmp_path):
    at = _app(monkeypatch, tmp_path).run()
    assert not at.exception
    at.button[0].click().run()
    assert not at.exception
    texts = " ".join(s.value for s in at.success)
    assert "APPROVED" in texts
    assert any("SIMULATED" in w.value for w in at.warning)


def test_app_shows_rejection_for_always_fail(monkeypatch, tmp_path):
    at = _app(monkeypatch, tmp_path).run()
    at.selectbox[0].select("always_fail").run()
    at.button[0].click().run()
    assert not at.exception
    assert any("REJECTED — Maximum retry limit reached" in e.value for e in at.error)
    assert not any("APPROVED" in s.value for s in at.success)


def test_app_rejects_empty_topic(monkeypatch, tmp_path):
    at = _app(monkeypatch, tmp_path).run()
    at.text_input[0].set_value("   ")
    at.button[0].click().run()
    assert any("Topic must not be empty" in e.value for e in at.error)
