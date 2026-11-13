# Quality Rubric — Hard Pass/Fail

**Decision rule:** `APPROVED = all 14 checkpoints PASS`. If any checkpoint is FAIL, the attempt fails.
There are no weights, no scores and no averages. Source of truth: `src/core/rubric.py` (version `rubric-v1`).

* **Deterministic (D1–D4)** are plain code in `src/utils/validators.py`. They give the same answer every time.
* **LLM (R1–R10)** need judgement, so an independent evaluator model decides them (`src/agents/evaluator.py`).
* Every result has: check ID, name, PASS/FAIL, **evidence** from the lesson, **reason**, and a **correction** if it failed.

| ID | Check | Type | PASS when | FAIL when |
|---|---|---|---|---|
| D1 | Required sections present | code | Title line (`# ...`) and all 13 `##` sections with exact headings, each non-empty | Anything missing or empty |
| D2 | Valid reference IDs | code | ≥ 3 distinct `[N#]` IDs cited; every ID exists in the knowledge base; every cited ID listed under *References Used* | < 3 citations, an unknown (invented) ID, or a cited ID not listed |
| D3 | Glossary present | code | ≥ 5 entries as `- **Term**: definition`, each definition ≥ 4 words | Fewer entries, wrong format, one/two-word definitions |
| D4 | Comprehension questions | code | ≥ 3 numbered questions ending with `?` | Fewer or not questions |
| R1 | Accuracy | LLM | Every technical statement is correct and consistent with the reference notes | Any wrong, misleading or contradicting statement |
| R2 | Grounding | LLM | Important factual claims are supported by a cited note that really says it | Unsupported claim, or a note cited for something it does not say |
| R3 | Beginner friendliness | LLM | A Class 12 graduate with no technical background can follow every section | A section assumes prior knowledge or skips a needed step |
| R4 | Simple language | LLM | Short sentences, everyday words | Long/complex sentences or unnecessary difficult words |
| R5 | Jargon explanation | LLM | Every important technical term is explained in plain words | A term is used but never explained |
| R6 | Practical example | LLM | Relevant, concrete example written as numbered steps from start to finish | Vague, irrelevant or not step by step |
| R7 | Key topic coverage | LLM | What it is, why it matters and how it works are all clearly explained | Any of the three missing or only mentioned in passing |
| R8 | Teaching flow | LLM | Basic → advanced; each idea introduced before use | Idea used before introduced; confusing order |
| R9 | Standalone quality | LLM | No other tutorial needed | Learner is sent elsewhere for a core point |
| R10 | Clarity and consistency | LLM | No contradictions, no invented numbers, no unjustified "always/guaranteed" | Any of those |

## Safeguards around the rubric
1. **Completeness:** the approval property (`EvaluationResult.passed`) is false unless the set of evaluated check IDs equals all 14 rubric IDs.
2. **Strict JSON:** the evaluator's reply must contain exactly R1–R10 (no missing, duplicate or unknown IDs). Otherwise it is re-requested once, then the run ends as `ERROR` — never as a pass.
3. **Evidence required:** a PASS with empty evidence is downgraded to FAIL. A FAIL with no correction receives a default correction from the pass condition.
4. **Learning cannot weaken it:** the learning engine only adds *generation guidance* text. It has no code path that edits checkpoints. A SHA-256 fingerprint of the rubric is stored in `rubric_versions` with each run (tested in `tests/test_memory.py`).
