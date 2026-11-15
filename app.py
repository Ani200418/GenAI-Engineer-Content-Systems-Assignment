"""Streamlit interface for the Self-Evaluating Lesson Content Generator."""
from __future__ import annotations

import streamlit as st
from pydantic import ValidationError

from src.core.errors import LessonGenError
from src.core.factory import build_pipeline
from src.core.schemas import DEFAULT_LEARNER_LEVEL, DEFAULT_TOPIC, LessonRequest, Stage
from src.providers import SCENARIOS
from src.ui import render
from src.utils.config import load_settings, parse_learning_threshold

st.set_page_config(page_title="Self-Evaluating Lesson Generator", page_icon="🎓", layout="wide")
try:
    settings = load_settings()
except ValueError as exc:
    st.error(f"Invalid configuration: {exc}")
    st.stop()

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Configuration")
    modes = ["mock", "anthropic"]
    mode = st.radio("LLM provider", modes, index=modes.index(settings.provider_mode) if settings.provider_mode in modes else 0,
                    help="mock = offline SIMULATED provider (no API key). anthropic = real Claude API.")
    scenario = "retry"
    if mode == "mock":
        scenario = st.selectbox("Mock scenario", SCENARIOS, index=SCENARIOS.index("retry"),
                                help="clean: passes first time · retry: fails once then passes · "
                                     "slow: needs both retries · always_fail: ends REJECTED")
        st.caption("Simulated demo: outputs are scripted, not produced by an LLM.")
    elif not settings.api_key:
        st.warning("ANTHROPIC_API_KEY is not set. Add it to .env or switch to mock mode.")
    threshold = st.number_input(
        "Learning threshold (failing runs)", min_value=1, max_value=10,
        value=settings.learning_threshold, step=1,
        help="How many separate failing runs are needed before guidance is learned.",
    )
    st.caption(f"Memory file: `{settings.db_path(mode).name}`")

try:
    threshold = parse_learning_threshold(threshold, source="Learning threshold")
except ValueError as exc:
    st.error(f"Invalid learning threshold: {exc}")
    st.stop()

st.title("🎓 Self-Evaluating Lesson Content Generator")
st.caption("INPUT → GENERATE → EVALUATE → REGENERATE → FINAL OUTPUT → MEMORY UPDATE")

# ---------------------------------------------------------------- input
with st.form("input_form"):
    topic = st.text_input("Topic", value=DEFAULT_TOPIC)
    level = st.text_input("Learner profile", value=DEFAULT_LEARNER_LEVEL)
    retries = st.select_slider("Maximum retries", options=[0, 1, 2], value=2)
    submitted = st.form_submit_button("Generate Lesson", type="primary")

try:
    pipeline = build_pipeline(mode, scenario, learning_threshold=int(threshold), settings=settings)
except LessonGenError as exc:
    st.error(f"Cannot start the pipeline: {exc}")
    st.stop()

if submitted:
    try:
        request = LessonRequest(topic=topic, learner_level=level, max_retries=retries)
    except ValidationError as exc:
        st.error("Invalid input: " + "; ".join(e["msg"] for e in exc.errors()))
    else:
        status_box = st.status("Starting pipeline…", expanded=True)

        def on_stage(stage: Stage, attempt: int, message: str) -> None:
            status_box.update(label=f"{stage.value} (attempt {attempt})")
            status_box.write(f"**{stage.value}** — {message}")

        result = pipeline.orchestrator.run(request, on_stage)
        status_box.update(label=f"{result.status.value}", state="error" if result.status.value != "APPROVED" else "complete")
        st.session_state["result"] = result

result = st.session_state.get("result")
if result is None:
    st.info("Enter a topic and press **Generate Lesson**. In mock mode no API key is needed.")
    with st.expander("Memory dashboard", expanded=True):
        render.render_memory(pipeline.memory, pipeline.learning)
else:
    render.render_decision(result)
    tabs = st.tabs(["Lesson", "Evaluation results", "Rejection history", "Pipeline status", "Memory dashboard", "Export"])
    with tabs[0]:
        render.render_lesson(result)
    with tabs[1]:
        render.render_evaluation(result)
    with tabs[2]:
        render.render_rejections(result)
    with tabs[3]:
        render.render_pipeline_log(result)
        if result.guidance_used:
            st.write("**Learned guidance used in this run:**")
            for g in result.guidance_used:
                st.write(f"- [{g.check_id}] {g.guidance}")
        if result.new_guidance:
            st.success("New guidance learned from this run: " + ", ".join(g.check_id for g in result.new_guidance))
    with tabs[4]:
        render.render_memory(pipeline.memory, pipeline.learning)
    with tabs[5]:
        render.render_exports(result, pipeline.memory)
        if result.run_id:
            st.write("**Your feedback on this run (stored in memory)**")
            rating = st.slider("Rating", 1, 5, 4, key="rating")
            comment = st.text_input("Comment", key="comment")
            if st.button("Save feedback"):
                pipeline.memory.add_user_feedback(result.run_id, rating, comment)
                st.success("Feedback saved.")
