# Planning — How the Problem Was Broken Down

## 1. What the assignment really asks
Not "call an LLM and show text", but a **closed loop**: generate → judge → feed failures back → regenerate → stop → remember.
Three properties matter most: (a) the judge is independent and strict, (b) the loop always terminates, (c) learning is traceable and cannot lower the standard.

## 2. Decomposition
| # | Sub-problem | Decision | Alternatives considered |
|---|---|---|---|
| 1 | Define "good" objectively | 14 binary checkpoints; any FAIL = FAIL | Weighted score (rejected: lets a bad lesson pass); single "is this good?" prompt (rejected: not inspectable) |
| 2 | Automate what can be automated | D1–D4 in code (sections, citation IDs, glossary, questions) | Everything by LLM (rejected: slower, less reliable for countable things) |
| 3 | Judge semantics (accuracy, grounding, teaching) | Separate evaluator prompt + JSON schema, evidence required | Same prompt as generator (rejected: self-grading bias) |
| 4 | Grounding | Small curated knowledge base with note IDs `[N#]` the lesson must cite; D2 verifies IDs, R1/R2 verify meaning | Open web retrieval (rejected: non-reproducible, over-engineered for scope) |
| 5 | Regeneration | Plain bounded `for` loop in an orchestrator class | LangGraph (rejected: no benefit for one linear loop; adds a dependency) |
| 6 | Memory | SQLite, insert-only guidance, thresholded learning | JSON files (no queries/integrity); vector memory (unnecessary) |
| 7 | Testability without paid API | Provider interface + deterministic `MockProvider` with scenarios | Mocking `requests` (brittle) |
| 8 | Honesty about simulation | Every mock result is labelled SIMULATED in UI, exports and provider name | — |
| 9 | UI | Streamlit single page: form, live status, tabs for lesson / checks / rejections / memory / export | Gradio, Flask (Streamlit was in the brief) |

## 3. Build order followed
1. Inspect workspace (empty) → pick architecture.
2. Foundation: schemas, rubric, knowledge base, config, logging.
3. Agents: generator, evaluator, deterministic validators, structured result.
4. Orchestrator: retry loop, feedback text, rejection log, hard cap.
5. Memory: schema, run persistence, failure analysis, guidance.
6. UI and exports.
7. Tests (57), mutation sanity checks, fix defects.
8. Documentation and demo script.

## 4. Risks identified up front and mitigations
| Risk | Mitigation |
|---|---|
| Judge returns bad JSON or skips checks | Strict validation, one re-ask, then `ERROR` (never approve) |
| Infinite loop | Bounded `for`; schema caps retries at 2; orchestrator re-clamps; tested with a bypassed schema |
| Learning lowers the bar | Learning only writes guidance text; rubric hash stored per run; test asserts rubric unchanged |
| Simulated results mistaken for real | Labels everywhere; separate DB files |
| Invented citations | D2 rejects IDs not in the knowledge base |
