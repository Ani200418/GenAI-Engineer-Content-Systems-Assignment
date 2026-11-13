"""Deterministic (code-only) rubric checks D1-D4 plus markdown parsing helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.core.rubric import (
    MIN_DISTINCT_REFERENCES, MIN_GLOSSARY_ENTRIES, MIN_GLOSSARY_WORDS, MIN_QUESTIONS,
    REQUIRED_SECTIONS, get_checkpoint,
)
from src.core.schemas import CheckResult, Verdict
from src.knowledge_base.loader import KnowledgeBase

CITATION_RE = re.compile(r"\[(N\d+)\]")
_GLOSSARY_RE = re.compile(r"^\s*[-*]\s+\*\*(.+?)\*\*\s*[:\-–—]\s*(.+)$")
_QUESTION_RE = re.compile(r"^\s*\d+[.)]\s+(.+\?)\s*$")


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


@dataclass
class ParsedLesson:
    title: str | None
    sections: dict[str, str]  # normalised heading -> body


def parse_lesson(lesson: str) -> ParsedLesson:
    title = None
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lesson.splitlines():
        if line.startswith("## "):
            current = norm(line[3:])
            sections.setdefault(current, [])
        elif line.startswith("# ") and title is None:
            title = line[2:].strip()
        elif current is not None:
            sections[current].append(line)
    return ParsedLesson(title, {k: "\n".join(v).strip() for k, v in sections.items()})


def get_section(parsed: ParsedLesson, heading: str) -> str:
    return parsed.sections.get(norm(heading), "")


def glossary_entries(parsed: ParsedLesson) -> list[tuple[str, str]]:
    out = []
    for line in get_section(parsed, "Important Terms").splitlines():
        if m := _GLOSSARY_RE.match(line):
            out.append((m.group(1).strip(), m.group(2).strip()))
    return out


def cited_ids(lesson: str, parsed: ParsedLesson) -> set[str]:
    """IDs cited in the lesson body (the References Used section is excluded)."""
    refs = get_section(parsed, "References Used")
    return set(CITATION_RE.findall(lesson.replace(refs, "")))


def _result(check_id: str, ok: bool, evidence: str, reason: str, correction: str) -> CheckResult:
    cp = get_checkpoint(check_id)
    return CheckResult(
        check_id=check_id, name=cp.name, status=Verdict.PASS if ok else Verdict.FAIL,
        evidence=evidence, reason=reason, correction="" if ok else correction, method="deterministic",
    )


def run_deterministic_checks(lesson: str, kb: KnowledgeBase) -> list[CheckResult]:
    parsed = parse_lesson(lesson)
    results: list[CheckResult] = []

    # D1 — required sections
    missing = [h for h in REQUIRED_SECTIONS if not get_section(parsed, h)]
    if not parsed.title:
        missing.insert(0, "# Title line")
    results.append(_result(
        "D1", not missing,
        f"Found title '{parsed.title}' and {len(REQUIRED_SECTIONS) - len(missing)}/{len(REQUIRED_SECTIONS)} sections."
        if not missing else f"Missing or empty: {', '.join(missing)}",
        "All required sections are present." if not missing else "Required sections are missing or empty.",
        f"Add these sections using the exact '## ' headings and real content: {', '.join(missing)}.",
    ))

    # D2 — reference IDs
    cited = cited_ids(lesson, parsed)
    unknown = sorted(cited - set(kb.notes))
    refs_section = get_section(parsed, "References Used")
    unlisted = sorted(i for i in cited if f"[{i}]" not in refs_section)
    problems = []
    if len(cited & set(kb.notes)) < MIN_DISTINCT_REFERENCES:
        problems.append(f"only {len(cited & set(kb.notes))} valid reference IDs cited (need {MIN_DISTINCT_REFERENCES})")
    if unknown:
        problems.append(f"unknown reference IDs (invented): {', '.join(unknown)}")
    if unlisted:
        problems.append(f"cited but not listed under 'References Used': {', '.join(unlisted)}")
    results.append(_result(
        "D2", not problems,
        f"Cited IDs: {', '.join(sorted(cited)) or 'none'}",
        "All citations are valid and listed." if not problems else "; ".join(problems),
        "Cite at least 3 real note IDs like [N3] after factual sentences, use only IDs from the reference material, "
        "and list every cited ID under 'References Used'.",
    ))

    # D3 — glossary
    entries = glossary_entries(parsed)
    short = [t for t, d in entries if len(d.split()) < MIN_GLOSSARY_WORDS]
    ok3 = len(entries) >= MIN_GLOSSARY_ENTRIES and not short
    results.append(_result(
        "D3", ok3,
        f"{len(entries)} glossary entries found.",
        "Glossary is complete." if ok3 else
        f"Need >= {MIN_GLOSSARY_ENTRIES} entries of >= {MIN_GLOSSARY_WORDS} words; found {len(entries)}"
        + (f", too short: {', '.join(short)}" if short else "") + ".",
        "Write 'Important Terms' as '- **Term**: plain-English definition of at least 4 words' for every key term.",
    ))

    # D4 — questions
    questions = [l for l in get_section(parsed, "Check Your Understanding").splitlines() if _QUESTION_RE.match(l)]
    results.append(_result(
        "D4", len(questions) >= MIN_QUESTIONS,
        f"{len(questions)} numbered questions found.",
        "Enough comprehension questions." if len(questions) >= MIN_QUESTIONS
        else f"Need at least {MIN_QUESTIONS} numbered questions ending with '?'.",
        "Add numbered questions (1. ... ?) that test understanding.",
    ))
    return results
