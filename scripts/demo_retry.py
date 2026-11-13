"""SIMULATED demonstration of the retry workflow and cross-run learning (offline, no API key).

Usage:  python scripts/demo_retry.py [--db PATH]
Everything printed here comes from the offline MockProvider; nothing is a real LLM judgement.
"""
from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.factory import build_pipeline  # noqa: E402
from src.core.schemas import LessonRequest  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402


def show(title: str, result) -> None:
    print(f"\n--- {title} ---")
    print(f"Decision : {result.status.value}   ({result.message})")
    print(f"Prompt   : {result.prompt_version}")
    for a in result.attempts:
        print(f"  Attempt {a.attempt_no}: {'PASS' if a.passed else 'FAIL'}  failed={a.evaluation.failed_ids or '-'}")
        if a.changes_from_previous:
            print(f"     changes: {a.changes_from_previous}")
    if result.new_guidance:
        print("  Learned after this run:", ", ".join(g.check_id for g in result.new_guidance))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=None, help="SQLite file (default: temporary file)")
    args = parser.parse_args()
    get_logger().setLevel(logging.WARNING)
    db = args.db or str(Path(tempfile.mkdtemp()) / "demo_memory.db")
    print("=== SIMULATED DEMO (mock provider, rule-based evaluator) ===")
    print(f"Memory file: {db}   learning threshold: 2 failing runs")

    request = LessonRequest(topic="Introduction to RAG (Retrieval-Augmented Generation)", max_retries=2)
    for n in (1, 2, 3):
        pipe = build_pipeline("mock", "retry", db_path=db, learning_threshold=2)
        show(f"Run {n} (scenario: retry)", pipe.orchestrator.run(request))

    pipe = build_pipeline("mock", "always_fail", db_path=db, learning_threshold=2)
    show("Run 4 (scenario: always_fail -> must end REJECTED after 2 retries)", pipe.orchestrator.run(request))

    print("\n=== MEMORY DASHBOARD ===")
    print("Stats:", pipe.memory.stats())
    print("Most failed:", [(r["check_id"], r["runs_failed"]) for r in pipe.memory.failure_frequency()])
    for g in pipe.memory.guidance():
        print(f"Guidance [{g.check_id}] ({g.prompt_version}): {g.reason}")


if __name__ == "__main__":
    main()
