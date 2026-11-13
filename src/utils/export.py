"""Markdown / JSON exports. An approved lesson is only ever exported from an APPROVED run."""
from __future__ import annotations

import json
from typing import Optional

from src.core.schemas import RunResult, RunStatus

SIM_NOTICE = ("> **SIMULATED RUN** — produced by the offline mock provider. The 'evaluator' is rule-based code, "
              "not a real LLM judgement.\n\n")


def approved_lesson_markdown(result: RunResult) -> Optional[str]:
    if result.status != RunStatus.APPROVED or not result.final_lesson:
        return None
    return (SIM_NOTICE if result.simulated else "") + result.final_lesson


def rejection_log_json(result: RunResult) -> str:
    return json.dumps([e.model_dump(mode="json") for e in result.rejection_log], indent=2, ensure_ascii=False)


def report_json(result: RunResult) -> str:
    data = result.model_dump(mode="json")
    data["final_decision"] = result.status.value
    return json.dumps(data, indent=2, ensure_ascii=False)


def report_markdown(result: RunResult) -> str:
    out = [f"# Evaluation Report — {result.request.topic}", ""]
    if result.simulated:
        out.append(SIM_NOTICE)
    out += [f"**Final decision: {result.status.value}**", "", result.message, "",
            f"- Provider: {result.provider_name}", f"- Prompt version: {result.prompt_version}",
            f"- Rubric version: {result.rubric_version}", f"- Attempts: {len(result.attempts)}",
            f"- Max retries allowed: {result.request.max_retries}", ""]
    if result.guidance_used:
        out.append("## Learned guidance applied in this run")
        out += [f"- [{g.check_id}] {g.guidance}" for g in result.guidance_used] + [""]
    for a in result.attempts:
        out += [f"## Attempt {a.attempt_no} — {'PASS' if a.passed else 'FAIL'}", ""]
        if a.changes_from_previous:
            out += [f"_Changes from previous attempt:_ {a.changes_from_previous}", ""]
        out += ["| ID | Check | Result | Evidence | Reason | Correction |", "|---|---|---|---|---|---|"]
        for c in a.evaluation.checks:
            esc = lambda t: (t or "").replace("|", "\\|").replace("\n", " ")  # noqa: E731
            out.append(f"| {c.check_id} | {c.name} | {c.status.value} | {esc(c.evidence)} | {esc(c.reason)} | {esc(c.correction)} |")
        out.append("")
    if result.rejection_log:
        out += ["## Rejection log", ""]
        for e in result.rejection_log:
            out += [f"### {e.lesson_version} — {e.outcome}", f"- Failed checks: {', '.join(e.failed_check_ids)}"]
            out += [f"  - **{f.check_id} {f.name}**: {f.reason}" for f in e.failures]
            out += ["- Feedback sent to generator:", "```", e.feedback_sent_to_generator or "(none — final attempt)", "```",
                    f"- Changes in next version: {e.changes_in_next_version or 'n/a'}",
                    f"- Next attempt passed: {e.next_attempt_passed}", ""]
    if result.warnings:
        out += ["## Warnings"] + [f"- {w}" for w in result.warnings]
    return "\n".join(out)
