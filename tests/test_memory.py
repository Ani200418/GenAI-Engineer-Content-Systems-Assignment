import sqlite3

import pytest

from src.core.errors import DatabaseError
from src.core.factory import build_pipeline
from src.core.rubric import ALL_IDS, CHECKPOINTS, rubric_hash
from src.core.schemas import LessonRequest, RunStatus
from src.memory.database import Database
from src.providers.mock_provider import MockProvider
from tests.conftest import SpyProvider


def test_10_rejection_logs_are_saved(make_pipeline, request_rag):
    pipe = make_pipeline("slow")
    r = pipe.orchestrator.run(request_rag())
    log = pipe.memory.get_rejection_log(r.run_id)
    assert [e["attempt_no"] for e in log] == [1, 2] and log[0]["failed_check_ids"] == ["R5", "R6"]
    with pipe.memory.db.connect() as c:
        assert c.execute("SELECT COUNT(*) FROM attempts WHERE run_id=?", (r.run_id,)).fetchone()[0] == 3
        assert c.execute("SELECT COUNT(*) FROM check_results WHERE run_id=?", (r.run_id,)).fetchone()[0] == 3 * len(ALL_IDS)
        assert c.execute("SELECT COUNT(*) FROM corrections WHERE run_id=?", (r.run_id,)).fetchone()[0] >= 2


def test_11_memory_survives_application_restart(tmp_path, request_rag):
    db = tmp_path / "persist.db"
    p1 = build_pipeline("mock", "retry", db_path=db, learning_threshold=2)
    p1.orchestrator.run(request_rag())
    p1.orchestrator.run(request_rag())
    del p1  # "close the application"
    p2 = build_pipeline("mock", "retry", db_path=db, learning_threshold=2)  # "restart"
    assert p2.memory.stats()["total_runs"] == 2
    assert {g.check_id for g in p2.memory.guidance()} == {"R5", "R6"}
    p2.orchestrator.run(request_rag())
    assert p2.memory.stats()["total_runs"] == 3


def test_12_previous_failures_influence_future_generation(tmp_path, request_rag):
    db = tmp_path / "learn.db"
    for _ in range(2):  # two separate runs fail R5 and R6 -> threshold reached
        build_pipeline("mock", "retry", db_path=db, learning_threshold=2).orchestrator.run(request_rag())
    spy = SpyProvider("retry")
    pipe = build_pipeline("mock", db_path=db, learning_threshold=2, provider=spy)
    r = pipe.orchestrator.run(request_rag())
    first_prompt = next(p for t, p in spy.prompts if t == "generate")
    assert "LEARNED GUIDANCE" in first_prompt and "[R5]" in first_prompt and "[R6]" in first_prompt
    assert r.status == RunStatus.APPROVED and len(r.attempts) == 1  # memory changed behaviour
    assert r.prompt_version == "gen-prompt-v1+g2" and len(r.guidance_used) == 2


def test_guidance_not_created_below_threshold(make_pipeline, request_rag):
    pipe = make_pipeline("retry", threshold=3)
    pipe.orchestrator.run(request_rag())
    pipe.orchestrator.run(request_rag())
    assert pipe.memory.guidance() == []


def test_guidance_is_traceable_and_never_overwritten(make_pipeline, request_rag):
    pipe = make_pipeline("retry", threshold=1)
    pipe.orchestrator.run(request_rag())
    first = {g.check_id: g for g in pipe.memory.guidance()}
    assert set(first) == {"R5", "R6"} and "failed in 1 separate runs" in first["R5"].reason
    pipe.orchestrator.run(request_rag())
    again = {g.check_id: g for g in pipe.memory.guidance()}
    assert again["R5"] == first["R5"]  # unchanged
    assert pipe.memory.add_guidance("R5", "new text", "why", "v", 9) is False


def test_learning_never_changes_the_rubric(make_pipeline, request_rag):
    before = (rubric_hash(), tuple(c.id for c in CHECKPOINTS))
    pipe = make_pipeline("always_fail", threshold=1)
    for _ in range(2):
        pipe.orchestrator.run(request_rag())
    assert (rubric_hash(), tuple(c.id for c in CHECKPOINTS)) == before
    assert len(ALL_IDS) == 14
    assert pipe.memory.guidance()  # R1 learned, yet still REJECTED on the full rubric
    assert pipe.orchestrator.run(request_rag()).status == RunStatus.REJECTED


def test_dashboard_statistics(make_pipeline, request_rag):
    pipe = make_pipeline("retry")
    pipe.orchestrator.run(request_rag())
    pipe.provider.scenario = "always_fail"
    pipe.orchestrator.run(request_rag())
    s = pipe.memory.stats()
    assert (s["total_runs"], s["approved"], s["rejected"]) == (2, 1, 1)
    freq = {f["check_id"]: f["runs_failed"] for f in pipe.memory.failure_frequency()}
    assert freq == {"R5": 1, "R6": 1, "R1": 1}


def test_error_runs_are_stored_and_version_tables_filled(make_pipeline, request_rag):
    from tests.conftest import BadEvaluatorProvider
    pipe = make_pipeline(provider=BadEvaluatorProvider("junk"))
    r = pipe.orchestrator.run(request_rag())
    assert pipe.memory.stats()["errors"] == 1 and r.run_id
    versions = pipe.memory.version_history()
    assert versions["rubric_versions"][0]["version"] == "rubric-v1" and versions["prompt_versions"]


def test_user_feedback_is_stored(make_pipeline, request_rag):
    pipe = make_pipeline("clean")
    r = pipe.orchestrator.run(request_rag())
    pipe.memory.add_user_feedback(r.run_id, 5, "great")
    assert pipe.memory.user_feedback()[0]["comment"] == "great"


def test_database_error_is_handled_without_crashing(tmp_path, request_rag):
    pipe = build_pipeline("mock", "clean", db_path=tmp_path / "ok.db")
    with sqlite3.connect(pipe.memory.db.path) as c:  # sabotage: remove a table
        c.execute("DROP TABLE check_results")
    r = pipe.orchestrator.run(request_rag())
    assert r.status == RunStatus.APPROVED and r.run_id is None
    assert any("could not be saved" in w for w in r.warnings)


def test_unopenable_database_raises_database_error(tmp_path):
    (tmp_path / "adir").mkdir()
    with pytest.raises(DatabaseError):
        Database(tmp_path / "adir")
