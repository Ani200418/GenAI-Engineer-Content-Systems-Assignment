"""SIMULATED evaluator heuristics for the mock provider (rules in code, no LLM).

These are intentionally simple pattern checks. They exist so the retry loop can be demonstrated and
tested offline. They are NOT a substitute for the real LLM evaluator.
"""
from __future__ import annotations

import re

from src.core.rubric import LLM_IDS, REQUIRED_SECTIONS, get_checkpoint
from src.utils.validators import CITATION_RE, get_section, norm, parse_lesson

_NEG = re.compile(r"\b(not|cannot|can't|doesn't|does not|no)\b", re.I)
_WRONG = [r"retrains? the model", r"changes? the model\b", r"updates? the model'?s? (weights|parameters)"]
_ABSOLUTE = [r"always correct", r"always right", r"guarantee[sd]?\b", r"100\s?%", r"never wrong", r"\bperfectly?\b"]
_NOT_BEGINNER = ["as you already know", "obviously", "needless to say", "it is trivial", "of course you know"]
_HARD_WORDS = ["utilize", "leverage", "paradigm", "aforementioned", "heterogeneous", "consequently",
               "furthermore", "methodology", "stochastic", "notwithstanding"]
_NOT_STANDALONE = ["refer to another", "see the paper", "read more before", "external tutorial", "beyond the scope",
                   "watch another video"]
_TERMS = [("language model", ["language model", "llm"]), ("retrieval", ["retrieval"]), ("chunk", ["chunk"]),
          ("embedding", ["embedding"]), ("vector", ["vector"]), ("hallucination", ["hallucination"]),
          ("grounding", ["grounding"]), ("fine-tuning", ["fine-tuning", "fine tuning"])]


def _sentences(text: str) -> list[str]:
    text = CITATION_RE.sub("", text)
    text = re.sub(r"[*_#>`]", "", text)
    text = re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", text, flags=re.M)
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.split()) >= 2]


def _find(sentences: list[str], patterns: list[str], skip_negated: bool = True) -> str | None:
    for s in sentences:
        low = s.lower()
        if any(re.search(p, low) for p in patterns) and not (skip_negated and _NEG.search(low)):
            return s
    return None


def _c(check_id: str, ok: bool, evidence: str, reason: str, correction: str) -> dict:
    return {"check_id": check_id, "name": get_checkpoint(check_id).name, "status": "PASS" if ok else "FAIL",
            "evidence": evidence, "reason": reason, "correction": "" if ok else correction}


def evaluate_lesson(lesson: str) -> list[dict]:
    parsed = parse_lesson(lesson)
    refs = get_section(parsed, "References Used")
    prose = lesson.replace(refs, "")
    sents = _sentences(prose)
    low = lesson.lower()
    out: list[dict] = []

    gloss = get_section(parsed, "Important Terms")
    hit = _find(_sentences(prose.replace(gloss, "")), _WRONG)  # glossary definitions are checked by R5
    out.append(_c("R1", hit is None, hit or _first(parsed, "What It Means"),
                  "No statement contradicts the reference notes." if not hit else
                  "This sentence contradicts note N15: RAG does not retrain or change the model.",
                  "Remove or rewrite the wrong sentence. RAG does not retrain the model; it only adds retrieved text to the prompt."))

    cites = set(CITATION_RE.findall(prose))
    out.append(_c("R2", len(cites) >= 4, f"Cited notes: {', '.join(sorted(cites))}",
                  "Important claims carry reference IDs." if len(cites) >= 4 else "Too few claims are tied to reference notes.",
                  "Add [N#] citations after important factual sentences."))

    bad = next((p for p in _NOT_BEGINNER if p in low), None)
    out.append(_c("R3", bad is None, _first(parsed, "Introduction"),
                  "No section assumes prior knowledge." if not bad else f"The phrase '{bad}' assumes the reader already knows something.",
                  "Remove phrases that assume prior knowledge and explain the idea from zero."))

    body = [s for s in sents if len(s.split()) > 2]
    avg = sum(len(s.split()) for s in body) / max(1, len(body))
    hard = next((w for w in _HARD_WORDS if w in low), None)
    out.append(_c("R4", avg <= 16 and hard is None, f"Average sentence length: {avg:.1f} words.",
                  "Sentences are short and words are simple." if avg <= 16 and hard is None else
                  f"Average sentence length {avg:.1f} words (limit 16)" + (f"; difficult word '{hard}'." if hard else "."),
                  "Use shorter sentences and everyday words."))

    gl = [t.lower() for t in re.findall(r"^\s*[-*]\s+\*\*(.+?)\*\*", get_section(parsed, "Important Terms"), flags=re.M)]
    text_wo_gloss = low.replace(get_section(parsed, "Important Terms").lower(), "")
    missing = [t for t, keys in _TERMS if t in text_wo_gloss and not any(k in g for g in gl for k in keys)]
    out.append(_c("R5", not missing, f"Glossary terms: {', '.join(gl) or 'none'}",
                  "Every technical term used is explained." if not missing else
                  f"These technical terms are used in the lesson but not explained in 'Important Terms': {', '.join(missing)}.",
                  f"Add a plain-English glossary entry for each of: {', '.join(missing)}."))

    example = get_section(parsed, "A Detailed Practical Example")
    steps = len(re.findall(r"^\s*(?:\d+[.)]|Step \d+)", example, flags=re.M))
    out.append(_c("R6", steps >= 3, example.splitlines()[0][:160] if example else "(no example)",
                  "The example is explained as numbered steps." if steps >= 3 else
                  f"The example is not broken into numbered steps (found {steps}, need at least 3).",
                  "Rewrite the example as a numbered list that follows one concrete case from the first step to the final answer."))

    cover = all(k in low for k in ("retriev", "generat", "augment")) and all(
        get_section(parsed, h) for h in ("What It Means", "Why It Is Important", "How It Works, Step by Step"))
    out.append(_c("R7", cover, _first(parsed, "What It Means"),
                  "What, why and how are all explained." if cover else "What, why or how is missing.",
                  "Explain what the topic is, why it matters and how it works."))

    order = [norm(h) for h in REQUIRED_SECTIONS]
    seen = [h for h in parsed.sections if h in order]
    in_order = seen == [h for h in order if h in seen]
    out.append(_c("R8", in_order, " > ".join(seen[:5]) + " ...",
                  "Sections follow a basic-to-advanced order." if in_order else "Sections are out of order.",
                  "Reorder sections to match the required teaching order."))

    nsa = next((p for p in _NOT_STANDALONE if p in low), None)
    out.append(_c("R9", nsa is None, _first(parsed, "Summary"),
                  "The lesson explains everything itself." if not nsa else f"The lesson sends the learner elsewhere ('{nsa}').",
                  "Explain the point inside the lesson instead of pointing to other material."))

    absolute = _find(sents, _ABSOLUTE)
    stat = next((s for s in sents if re.search(r"\d+\s?%", s)), None)
    bad10 = absolute or stat
    out.append(_c("R10", bad10 is None, _first(parsed, "Advantages and Limitations"),
                  "No contradictions or unsupported absolute claims." if not bad10 else f"Unsupported claim: '{bad10}'",
                  "Remove absolute claims and unsupported numbers."))
    assert [c["check_id"] for c in out] == list(LLM_IDS)
    return out


def _first(parsed, heading: str) -> str:
    body = get_section(parsed, heading)
    return (body.splitlines()[0] if body else "(section missing)")[:160]
