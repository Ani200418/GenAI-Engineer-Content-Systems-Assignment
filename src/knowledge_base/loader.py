"""Parses the curated reference notes into a simple structure with citable IDs."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.core.errors import ReferenceMaterialError

DEFAULT_KB_PATH = Path(__file__).with_name("rag_reference.md")
_SOURCE_RE = re.compile(r"^- ([A-Z]\d+): (.+)$")
_NOTE_RE = re.compile(r"^- (N\d+) \[([A-Z0-9, ]+)\]: (.+)$")


@dataclass(frozen=True)
class Note:
    id: str
    source_ids: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class KnowledgeBase:
    sources: dict[str, str]
    notes: dict[str, Note]
    raw: str


def load_knowledge_base(path: str | Path | None = None) -> KnowledgeBase:
    p = Path(path) if path else DEFAULT_KB_PATH
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReferenceMaterialError(f"Reference material missing or unreadable: {p}") from exc

    sources: dict[str, str] = {}
    notes: dict[str, Note] = {}
    for line in raw.splitlines():
        if m := _SOURCE_RE.match(line):
            sources[m.group(1)] = m.group(2).strip()
        elif m := _NOTE_RE.match(line):
            ids = tuple(s.strip() for s in m.group(2).split(","))
            notes[m.group(1)] = Note(m.group(1), ids, m.group(3).strip())

    if not notes:
        raise ReferenceMaterialError(f"Reference material contains no notes: {p}")
    for note in notes.values():
        missing = [s for s in note.source_ids if s not in sources]
        if missing:
            raise ReferenceMaterialError(f"Note {note.id} cites unknown source(s): {missing}")
    return KnowledgeBase(sources=sources, notes=notes, raw=raw)
