"""All prompts live here. Versions are recorded with every run."""
from __future__ import annotations

from src.core.rubric import CHECKPOINTS, LLM_IDS, REQUIRED_SECTIONS

GENERATOR_PROMPT_VERSION = "gen-prompt-v1"
EVALUATOR_PROMPT_VERSION = "eval-prompt-v1"

GENERATOR_SYSTEM = """You are an expert teacher who writes lessons for beginners.
Your learner: a student who finished Class 12 in India, has limited English vocabulary, may not have studied in an
English-medium school, and has NO technical background.

Writing rules:
- Use simple, everyday English and short sentences (about 15 words or fewer).
- Explain every technical word the moment it first appears, in plain words.
- Use examples from Indian classrooms, colleges, libraries, shops or daily life.
- Assume zero prior knowledge. Never write phrases like "as you know" or "obviously".
- Be technically accurate. Use ONLY facts found in the REFERENCE MATERIAL. Never invent numbers, studies or URLs.
- After each important factual sentence, add the reference note ID in square brackets, for example [N3].
  Use only note IDs that exist in the reference material.
- The practical example must be a numbered list of steps that follows one concrete case from start to finish.
- The lesson must stand alone. Do not send the learner to other tutorials.
Output ONLY the lesson in Markdown. No preface, no code fences."""

EVALUATOR_SYSTEM = """You are a strict, independent quality inspector for beginner lessons.
You did NOT write the lesson. Do not be generous. Judge each checkpoint as PASS or FAIL only; there is no partial credit.
Compare factual claims against the REFERENCE MATERIAL. If a claim is wrong or unsupported, FAIL the relevant checkpoint.
For every checkpoint you MUST give evidence quoted or closely paraphrased from the lesson, the reason for your decision,
and, if it FAILS, one specific correction the writer must make.
Respond with ONLY valid JSON. No markdown fences. No extra text."""


def build_generator_prompt(topic: str, learner_level: str, kb_text: str, guidance: list[str],
                           feedback: str | None, previous_lesson: str | None) -> str:
    headings = "\n".join(f"## {h}" for h in REQUIRED_SECTIONS)
    parts = [
        f"Write a complete standalone lesson on: {topic}",
        f"Learner profile: {learner_level}",
        "Start with a '# Title' line, then use EXACTLY these '## ' headings in this order:\n" + headings,
        "Format rules:\n"
        "- 'Important Terms': one line per term, written as '- **Term**: simple definition'. Include at least 5.\n"
        "- 'Check Your Understanding': at least 3 numbered questions, each ending with '?'.\n"
        "- 'References Used': list every [N#] ID you cited, with its source.",
        "=== REFERENCE MATERIAL ===\n" + kb_text + "\n=== END REFERENCE ===",
    ]
    if guidance:
        parts.append("=== LEARNED GUIDANCE (from earlier runs; follow these) ===\n" + "\n".join(guidance)
                     + "\n=== END GUIDANCE ===")
    if feedback and previous_lesson:
        parts.append("=== PREVIOUS LESSON (rejected) ===\n" + previous_lesson + "\n=== END PREVIOUS ===")
        parts.append("=== EVALUATOR FEEDBACK (fix every item) ===\n" + feedback + "\n=== END FEEDBACK ===")
        parts.append("Rewrite the whole lesson. Fix every failed checkpoint and keep everything that already passed.")
    return "\n\n".join(parts)


def build_evaluator_prompt(lesson: str, kb_text: str, topic: str, learner_level: str) -> str:
    rubric = "\n".join(
        f"{c.id} {c.name}\n  PASS if: {c.pass_condition}\n  FAIL if: {c.fail_condition}"
        for c in CHECKPOINTS if c.method == "llm"
    )
    schema = ('{"checks": [{"check_id": "R1", "name": "Accuracy", "status": "PASS or FAIL", '
              '"evidence": "text from the lesson", "reason": "why", "correction": "what to change (empty if PASS)"}, ...]}')
    return (
        f"Topic: {topic}\nLearner profile: {learner_level}\n\n"
        f"Evaluate the lesson against ALL of these checkpoints ({', '.join(LLM_IDS)}):\n{rubric}\n\n"
        f"=== REFERENCE MATERIAL ===\n{kb_text}\n=== END REFERENCE ===\n\n"
        f"=== LESSON TO EVALUATE ===\n{lesson}\n=== END LESSON ===\n\n"
        f"Return exactly one JSON object with one entry for each of {', '.join(LLM_IDS)} in this shape:\n{schema}"
    )
