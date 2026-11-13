"""The hard pass/fail rubric.

Design rules (see docs/RUBRIC.md):
* Every checkpoint is mandatory. There are no weights and no averages.
* PASS overall  <=>  every checkpoint below returns PASS.
* The learning engine can add *generation guidance* but can never edit this file's
  checkpoints at runtime. A content hash of the rubric is stored with every run so
  silent changes are detectable.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

RUBRIC_VERSION = "rubric-v1"

REQUIRED_SECTIONS: tuple[str, ...] = (
    "What You Will Understand",
    "Introduction",
    "What It Means",
    "Why It Is Important",
    "How It Works, Step by Step",
    "A Simple Analogy",
    "A Detailed Practical Example",
    "Where It Is Used",
    "Advantages and Limitations",
    "Important Terms",
    "Summary",
    "Check Your Understanding",
    "References Used",
)
MIN_GLOSSARY_ENTRIES = 5
MIN_GLOSSARY_WORDS = 4
MIN_QUESTIONS = 3
MIN_DISTINCT_REFERENCES = 3


@dataclass(frozen=True)
class Checkpoint:
    id: str
    name: str
    method: str  # "deterministic" (code) or "llm" (independent evaluator model)
    pass_condition: str
    fail_condition: str


CHECKPOINTS: tuple[Checkpoint, ...] = (
    Checkpoint(
        "D1", "Required sections present", "deterministic",
        "The lesson has a '# Title' line and all 13 required '## ' sections with the exact headings, each non-empty.",
        "Title missing, or any required section missing or empty.",
    ),
    Checkpoint(
        "D2", "Valid reference IDs", "deterministic",
        f"At least {MIN_DISTINCT_REFERENCES} distinct [N#] note IDs are cited, every cited ID exists in the "
        "knowledge base, and every cited ID is listed under 'References Used'.",
        "Too few citations, an unknown ID (invented reference), or a cited ID missing from 'References Used'.",
    ),
    Checkpoint(
        "D3", "Glossary present", "deterministic",
        f"'Important Terms' has at least {MIN_GLOSSARY_ENTRIES} entries written as '- **Term**: definition', "
        f"each definition at least {MIN_GLOSSARY_WORDS} words.",
        "Fewer entries, wrong format, or one-word definitions.",
    ),
    Checkpoint(
        "D4", "Comprehension questions", "deterministic",
        f"'Check Your Understanding' has at least {MIN_QUESTIONS} numbered questions ending in '?'.",
        "Fewer questions or questions not numbered / not questions.",
    ),
    Checkpoint(
        "R1", "Accuracy", "llm",
        "Every technical statement is factually correct and does not contradict the reference notes.",
        "Any technical statement is wrong, misleading, or contradicts a reference note.",
    ),
    Checkpoint(
        "R2", "Grounding", "llm",
        "Each important factual claim is supported by a cited reference note, and the cited note really says it.",
        "An important factual claim has no support in the reference notes, or cites a note that does not support it.",
    ),
    Checkpoint(
        "R3", "Beginner friendliness", "llm",
        "A Class 12 graduate with no technical background can follow every section without outside knowledge.",
        "Any section assumes prior technical knowledge or skips a step a beginner needs.",
    ),
    Checkpoint(
        "R4", "Simple language", "llm",
        "Short sentences, everyday words, no unnecessary academic or formal vocabulary.",
        "Long or complex sentences, or difficult words used where a simple word works.",
    ),
    Checkpoint(
        "R5", "Jargon explanation", "llm",
        "Every important technical term used in the lesson is explained in plain words where it first appears or in "
        "'Important Terms'.",
        "Any important technical term is used but never explained.",
    ),
    Checkpoint(
        "R6", "Practical example", "llm",
        "The practical example is relevant, concrete, and explained as numbered steps from start to finish.",
        "The example is vague, irrelevant, or not broken into clear steps.",
    ),
    Checkpoint(
        "R7", "Key topic coverage", "llm",
        "The lesson clearly explains what the topic is, why it matters, and how it works.",
        "Any of these three is missing or only mentioned in passing.",
    ),
    Checkpoint(
        "R8", "Teaching flow", "llm",
        "Ideas move from basic to advanced in a logical order; each idea is introduced before it is used.",
        "An idea is used before it is introduced, or the order is confusing.",
    ),
    Checkpoint(
        "R9", "Standalone quality", "llm",
        "The learner needs no other tutorial or outside explanation to understand the lesson.",
        "The lesson sends the learner elsewhere to understand a core point.",
    ),
    Checkpoint(
        "R10", "Clarity and consistency", "llm",
        "No self-contradictions, no unsupported statistics, no absolute claims such as 'always' or 'guaranteed'.",
        "Any contradiction, invented number, or unjustified absolute claim.",
    ),
)

ALL_IDS: tuple[str, ...] = tuple(c.id for c in CHECKPOINTS)
LLM_IDS: tuple[str, ...] = tuple(c.id for c in CHECKPOINTS if c.method == "llm")
DETERMINISTIC_IDS: tuple[str, ...] = tuple(c.id for c in CHECKPOINTS if c.method == "deterministic")
_BY_ID = {c.id: c for c in CHECKPOINTS}


def get_checkpoint(check_id: str) -> Checkpoint:
    return _BY_ID[check_id]


def rubric_hash() -> str:
    """Stable fingerprint of every checkpoint definition (used for version tracking)."""
    payload = json.dumps([asdict(c) for c in CHECKPOINTS], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
