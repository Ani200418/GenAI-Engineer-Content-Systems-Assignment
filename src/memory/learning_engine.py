"""Turns recurring failures into stronger GENERATION guidance. It never touches the rubric.

Rules:
* A checkpoint must fail in >= `threshold` separate runs before guidance is created.
* Guidance is insert-only (never edited or deleted) and stores the reason it was added.
* The acceptance standard is unchanged: the rubric in src/core/rubric.py is not modified here.
"""
from __future__ import annotations

from src.core.prompts import GENERATOR_PROMPT_VERSION
from src.core.rubric import get_checkpoint
from src.core.schemas import LearnedGuidance
from src.memory.memory_manager import MemoryManager

GUIDANCE_TEMPLATES: dict[str, str] = {
    "D1": "Include the title and ALL 13 required '## ' sections with the exact headings; never leave a section empty.",
    "D2": "Cite at least 3 real reference IDs like [N3]; use only IDs from the reference material and list each one under 'References Used'.",
    "D3": "In 'Important Terms' define at least 5 terms as '- **Term**: definition' with plain-English definitions.",
    "D4": "End with at least 3 numbered comprehension questions, each ending with '?'.",
    "R1": "Double-check every technical sentence against the reference notes; RAG never retrains the model. Remove anything you are unsure about.",
    "R2": "After every important factual sentence add the supporting [N#] reference and make sure that note really says it.",
    "R3": "Explain every idea from zero. Never assume the reader knows any technical idea; add one extra plain-words sentence when unsure.",
    "R4": "Keep sentences under about 15 words. Replace formal words with everyday words.",
    "R5": "Every technical term used anywhere (embedding, vector, chunk, hallucination, etc.) MUST be defined in plain words and listed in 'Important Terms'. Before finishing, scan the lesson for terms that are missing from the glossary.",
    "R6": "Write the practical example as a numbered list of at least 5 steps following one concrete everyday case from the first step to the final answer.",
    "R7": "Clearly cover WHAT the topic is, WHY it matters, and HOW it works, each in its own section.",
    "R8": "Introduce each idea before using it; order the lesson from simple to advanced.",
    "R9": "Never tell the learner to read or watch something else; explain every point inside the lesson.",
    "R10": "Avoid words like 'always', 'guaranteed' or 'perfect'; do not state numbers or percentages that are not in the reference notes.",
}


class LearningEngine:
    def __init__(self, memory: MemoryManager, threshold: int = 2) -> None:
        self.memory = memory
        self.threshold = max(1, threshold)

    def active_guidance(self) -> list[LearnedGuidance]:
        return self.memory.guidance()

    def prompt_version(self) -> str:
        return f"{GENERATOR_PROMPT_VERSION}+g{len(self.active_guidance())}"

    def update(self) -> list[LearnedGuidance]:
        """Analyse failure history; add guidance for newly recurring failures. Returns the new items."""
        existing = {g.check_id for g in self.active_guidance()}
        added: list[str] = []
        for row in self.memory.failure_frequency():
            cid, runs_failed = row["check_id"], row["runs_failed"]
            if runs_failed < self.threshold or cid in existing:
                continue
            cp = get_checkpoint(cid)
            text = GUIDANCE_TEMPLATES.get(cid, f"Previous lessons failed '{cp.name}'. Make sure: {cp.pass_condition}")
            fix = self.memory.latest_correction(cid)
            if fix:
                text += f" A correction that worked before: {fix}"
            reason = (f"Checkpoint {cid} ({cp.name}) failed in {runs_failed} separate runs "
                      f"(threshold {self.threshold}). Rubric unchanged; only generation instructions strengthened.")
            version = f"{GENERATOR_PROMPT_VERSION}+g{len(existing) + len(added) + 1}"
            if self.memory.add_guidance(cid, text, reason, version, runs_failed):
                added.append(cid)
        return [g for g in self.active_guidance() if g.check_id in added]
