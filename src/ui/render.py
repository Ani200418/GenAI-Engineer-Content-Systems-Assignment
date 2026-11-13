"""Streamlit rendering helpers (kept out of app.py so the entry point stays small)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core.rubric import CHECKPOINTS
from src.core.schemas import RunResult, RunStatus, Verdict
from src.memory.learning_engine import LearningEngine
from src.memory.memory_manager import MemoryManager
from src.utils import export


def render_decision(result: RunResult) -> None:
    if result.simulated:
        st.warning("SIMULATED RUN — offline mock provider. The evaluator here is rule-based code, not a real LLM.")
    if result.status == RunStatus.APPROVED:
        st.success(f"✅ {result.message}")
    elif result.status == RunStatus.REJECTED:
        st.error(f"❌ {result.message}")
    else:
        st.error(f"⚠️ {result.message}")
    for w in result.warnings:
        st.warning(w)


def render_pipeline_log(result: RunResult) -> None:
    for e in result.stage_log:
        st.write(f"**{e.stage.value}** · attempt {e.attempt} · {e.message}")


def render_lesson(result: RunResult) -> None:
    if result.status == RunStatus.APPROVED and result.final_lesson:
        st.subheader("Final approved lesson")
        st.markdown(result.final_lesson)
    elif result.status == RunStatus.REJECTED and result.rejected_lesson:
        st.subheader("No approved lesson")
        st.error("The system did not approve any version. The last draft is shown for review only — it is NOT approved.")
        with st.expander("Last rejected draft (NOT APPROVED)"):
            st.markdown(result.rejected_lesson)
    else:
        st.info("No lesson is available because the pipeline stopped with an error.")


def _checks_frame(checks) -> pd.DataFrame:
    return pd.DataFrame([{
        "ID": c.check_id, "Check": c.name, "Type": c.method,
        "Result": ("✅ PASS" if c.status == Verdict.PASS else "❌ FAIL"),
        "Evidence": c.evidence, "Reason": c.reason, "Correction required": c.correction} for c in checks])


def render_evaluation(result: RunResult) -> None:
    for a in result.attempts:
        label = f"Attempt {a.attempt_no} — {'PASS' if a.passed else 'FAIL'} ({len(a.evaluation.failed_ids)} failed)"
        with st.expander(label, expanded=(a is result.attempts[-1])):
            st.caption(f"Evaluator: {a.evaluation.evaluator_label}")
            st.dataframe(_checks_frame(a.evaluation.checks), use_container_width=True, hide_index=True)
            if not a.passed:
                with st.expander("Lesson text of this attempt"):
                    st.markdown(a.lesson)


def render_rejections(result: RunResult) -> None:
    if not result.rejection_log:
        st.info("No attempt was rejected in this run.")
        return
    for e in result.rejection_log:
        st.markdown(f"#### Lesson {e.lesson_version} — {e.outcome.replace('_', ' ')}")
        st.write("**Failed checkpoints:** " + ", ".join(e.failed_check_ids))
        for f in e.failures:
            st.write(f"- **{f.check_id} {f.name}** — {f.reason}")
        if e.feedback_sent_to_generator:
            st.write("**Exact feedback sent to generator:**")
            st.code(e.feedback_sent_to_generator, language="text")
        if e.changes_in_next_version:
            st.write(f"**What changed in the next version:** {e.changes_in_next_version}")
        if e.next_attempt_passed is not None:
            st.write(f"**Next attempt result:** {'PASS' if e.next_attempt_passed else 'FAIL'}")
        st.divider()


def render_memory(memory: MemoryManager, learning: LearningEngine) -> None:
    s = memory.stats()
    cols = st.columns(5)
    for col, (label, key) in zip(cols, [("Total runs", "total_runs"), ("Approved", "approved"),
                                         ("Rejected", "rejected"), ("Errors", "errors"),
                                         ("Approved after regeneration", "approved_after_regeneration")]):
        col.metric(label, s[key])
    st.write("**Most frequently failed checkpoints**")
    freq = memory.failure_frequency()
    if freq:
        df = pd.DataFrame(freq).rename(columns={"check_id": "Checkpoint", "runs_failed": "Runs failed",
                                                "total_failures": "Total failures"})
        st.bar_chart(df.set_index("Checkpoint")["Runs failed"])
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.caption("No failures recorded yet.")
    st.write(f"**Learned generation guidance** (learning threshold: {learning.threshold} failing runs) — "
             f"current prompt version `{learning.prompt_version()}`")
    guidance = memory.guidance()
    if guidance:
        for g in guidance:
            st.info(f"**[{g.check_id}]** {g.guidance}\n\n_Why added:_ {g.reason} · _Version:_ `{g.prompt_version}`")
    else:
        st.caption("Nothing learned yet. Guidance is added when a checkpoint fails in enough separate runs.")
    with st.expander("Rubric (fixed — never changed by learning)"):
        st.dataframe(pd.DataFrame([{"ID": c.id, "Check": c.name, "Type": c.method, "Pass condition": c.pass_condition}
                                   for c in CHECKPOINTS]), hide_index=True, use_container_width=True)
    runs = memory.list_runs(20)
    if runs:
        with st.expander("Recent run history"):
            st.dataframe(pd.DataFrame(runs), hide_index=True, use_container_width=True)


def render_exports(result: RunResult, memory: MemoryManager) -> None:
    lesson_md = export.approved_lesson_markdown(result)
    c1, c2, c3, c4, c5 = st.columns(5)
    if lesson_md:
        c1.download_button("Approved lesson (.md)", lesson_md, "approved_lesson.md", "text/markdown")
    else:
        c1.caption("No approved lesson to export.")
    c2.download_button("Evaluation report (.md)", export.report_markdown(result), "evaluation_report.md", "text/markdown")
    c3.download_button("Evaluation report (.json)", export.report_json(result), "evaluation_report.json", "application/json")
    c4.download_button("Rejection log (.json)", export.rejection_log_json(result), "rejection_log.json", "application/json")
    import json
    c5.download_button("Run history (.json)", json.dumps(memory.export_history(), indent=2, default=str),
                       "run_history.json", "application/json")
