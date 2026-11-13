# Project Report — Self-Evaluating Lesson Content Generator

## 1. Project overview
A Python/Streamlit application in which a Generate Agent writes a beginner lesson, an independent Evaluate Agent checks it against a hard pass/fail rubric, failures are sent back as precise feedback for regeneration (maximum two retries), and a SQLite memory records outcomes so future generations improve. Required demonstration topic: *Introduction to RAG*.

## 2. Problem statement
A single LLM call produces text with no guarantee of correctness, grounding or suitability for the learner, and a human has to judge it. The system must decide pass/fail itself, explain every failure, fix it, stop in bounded time, and learn from repeated mistakes.

## 3. Target audience and learning needs
A Class 12 graduate in India with limited English vocabulary, possibly from a non-English-medium school, no technical background, wanting to start learning AI. Needs: short sentences, everyday words, every technical term explained immediately, Indian everyday examples (college library, notice board, shops), zero assumed knowledge. These needs are encoded in the generator system prompt and in rubric checks R3–R6.

## 4. Proposed solution
An orchestrated generate → evaluate → regenerate loop with: grounded reference notes, 14 binary checkpoints, structured evaluator output, a complete rejection log, and thresholded learning stored in SQLite.

## 5. Requirements analysis
| Requirement | Where satisfied |
|---|---|
| Independent evaluator, structured output | `agents/evaluator.py`, `CheckResult` model |
| Hard pass/fail, no averages | `EvaluationResult.passed` |
| Grounding against references | `knowledge_base/`, D2, R1, R2 |
| Retry ≤ 2, always terminates | `LessonRequest` (ge=0, le=2) + bounded loop + re-clamp |
| Rejection log | `build_rejection_log`, `RejectionLogEntry` |
| Persistent memory & learning | `memory/*` |
| Mock mode, no key | `providers/mock_provider.py` |
| UI, exports | `app.py`, `ui/render.py`, `utils/export.py` |
| Tests, docs, demo script | `tests/`, `docs/`, `scripts/` |

## 6. System planning
See `docs/PLANNING.md`: decomposition, alternatives, build order and risks.

## 7. Architecture and component responsibilities
See `docs/ARCHITECTURE.md` (Mermaid component and workflow diagrams). Modules are separated by responsibility: generation, evaluation, orchestration, memory, prompts/rubric, providers, UI, export.

## 8. End-to-end workflow
1. UI builds a validated `LessonRequest` (topic non-empty, retries 0–2).
2. Orchestrator loads learned guidance from SQLite and computes prompt version `gen-prompt-v1+g<N>`.
3. Generator produces Markdown using reference notes + guidance (+ feedback and previous lesson on retries).
4. Evaluator runs D1–D4 and R1–R10; `passed` is true only if all 14 are PASS.
5. PASS → `APPROVED`, stop. FAIL with retries left → feedback built from every failed check → regenerate. FAIL with none left → `REJECTED`.
6. The run (attempts, per-check results, rejection log, corrections, versions) is saved; the learning engine updates guidance.

## 9. Generator design
`LessonGenerator.generate(request, guidance, feedback, previous_lesson)`. The prompt contains learner profile, mandatory headings (13 sections), formatting rules (glossary format, numbered questions, `[N#]` citations), the full reference notes, learned guidance, and — on retries — the rejected lesson and the evaluator feedback. It returns Markdown, strips code fences, and raises `GenerationError` on empty/too-short output. It never evaluates itself.

## 10. Evaluator design
`LessonEvaluator` combines two layers: deterministic checks and an LLM judge prompted separately (strict inspector persona, rubric text, reference notes, JSON schema). `parse_llm_checks` validates the reply: valid JSON, each entry valid, **exactly** R1–R10. PASS without evidence → downgraded to FAIL. FAIL without correction → default correction. One re-ask for malformed output, then `EvaluationError`. An optional separate `EVALUATOR_MODEL` increases independence.

## 11. Detailed pass/fail rubric
See `docs/RUBRIC.md` (all 14 checkpoints with exact pass/fail conditions).

## 12. Regeneration and retry mechanism
A bounded `for n in range(1, 1 + min(max_retries, 2) + 1)`. Feedback text lists, per failed check: ID, name, reason, evidence, required correction. Each new attempt records a change summary (fixed / still failing / newly failing, lines changed, word count). Termination is guaranteed three ways: schema validation (`le=2`), the orchestrator's own clamp, and the finite loop. `tests/test_retry_logic.py` verifies zero retries = 1 generation, one retry ≤ 2, two retries = 3, the schema bypass case, and that the loop stops as soon as a lesson passes.

Final statuses: `APPROVED`, `REJECTED` (message: *REJECTED — Maximum retry limit reached. The lesson did not satisfy all mandatory quality checks.*), `ERROR` (pipeline stopped safely; nothing approved). A rejected run exposes `rejected_lesson` (for review) and leaves `final_lesson` empty; the UI labels the draft "NOT APPROVED" and offers no approved-lesson export.

## 13. Persistent memory design
SQLite via `Database`/`MemoryManager`. Stored: runs, every attempt's lesson and full evaluation JSON, per-check results, rejection log JSON, successful corrections (check failed in attempt *k*, passed in *k+1*, with the correction text), learned guidance, prompt and rubric versions, user feedback. The dashboard shows total/approved/rejected/error runs, approved-after-regeneration, most frequently failed checkpoints, and learned guidance with reasons.

## 14. Self-evolution strategy
`LearningEngine.update()` counts, per checkpoint, the number of **distinct runs** in which it failed. At or above `LEARNING_THRESHOLD` (default 2) it inserts one guidance item per checkpoint: a strengthened instruction template plus, when available, a correction that previously worked. Each item stores `reason`, the prompt version it created and the failing-run count. Guarantees: insert-only (a second write for the same checkpoint returns false), rubric untouched (hash stored per run; test asserts it unchanged), traceable (dashboard + `learned_guidance` table). Demonstrated: after runs 1–2 fail R5/R6, run 3 receives the guidance in its first prompt and passes on attempt 1 (`tests/test_memory.py::test_12`). In mock mode this effect is scripted: the mock generator honours guidance. With a real LLM the effect depends on the model following the added instructions, and was not measured.

## 15. Database structure
`runs` (status, attempts, provider, simulated flag, prompt/rubric version, final/rejected lesson, rejection log JSON) · `attempts` · `check_results` · `corrections` · `learned_guidance` (UNIQUE check_id) · `prompt_versions` · `rubric_versions` (content hash) · `user_feedback`. Mock and real runs use separate files.

## 16. Prompt engineering strategy
Prompts live in `core/prompts.py` with version constants. Generator: persona, learner constraints, explicit structure, citation rule, "use only the reference material". Evaluator: role separation ("you did not write this"), PASS/FAIL only, evidence required, strict JSON schema, rubric injected from `rubric.py` so prompt and code cannot drift. Delimited blocks (`=== LEARNED GUIDANCE ===`, `=== EVALUATOR FEEDBACK ===`) make sections unambiguous.

## 17. Grounding and accuracy controls
17 curated notes (`rag_reference.md`) tied to source IDs S1–S3 and C1 (author-curated). Lesson must cite `[N#]`; D2 verifies the IDs exist and are listed; R1/R2 (LLM) verify the cited note really supports the claim. Notes are paraphrases, not quotations. N14–N16 are marked C1 (general explanation, not attributed to an external document). URLs were written without live verification in this environment and must be checked by the author before submission.

## 18. Error handling
Empty topic / invalid retries → Pydantic `ValidationError` shown in UI. Missing key in real mode → `MissingAPIKeyError` with fix instructions. API timeouts/rate limits/5xx → up to 3 attempts with backoff, then `ProviderError`; 4xx not retried. Malformed or incomplete evaluator JSON → one re-ask then `ERROR` (tested with 6 bad payloads). Missing/empty reference file → `ReferenceMaterialError`. Database failure → run still returned with a warning (tested by dropping a table); unopenable DB → `DatabaseError`. UI callback exceptions are swallowed so they cannot break the pipeline.

## 19. Security considerations
Keys only from environment/`.env`; `.env` is git-ignored; `.env.example` has no secrets. Log formatter redacts `sk-ant-…` and `api_key=…` patterns (tested). Parameterised SQL everywhere. LLM output is rendered as Markdown only (no HTML execution). Prompt-injection note: lesson text is placed inside delimiters for the evaluator, but a determined injection in generated text is not specifically defended against.

## 20. Testing strategy and actual results
Command: `python -m pytest` → **57 passed in ~4 s** (Python 3.12, pytest 9.2, no network, no API key).

| File | Tests | Covers |
|---|---|---|
| `test_orchestrator.py` | 10 | first-attempt approval; fail→pass; two failures→pass; all fail→REJECTED; single failed check blocks approval; invalid evaluator output → ERROR; provider failure; stage order; callback safety; missing KB |
| `test_retry_logic.py` | 7 | 0 retries = 1 call; 1 retry; never >2 retries; clamp when schema bypassed; early stop; feedback completeness; rejection-log fields |
| `test_evaluator.py` | 13 | all 14 checks evaluated; any single failure blocks; defects map to right checks; 6 invalid payloads; missing checkpoint; evidence enforcement; one JSON re-ask; code-fenced JSON |
| `test_memory.py` | 11 | rejection logs saved; restart persistence; past failures change later prompts and outcome; threshold; insert-only guidance; rubric unchanged; statistics; version tables; user feedback; DB error handling |
| `test_generator.py` | 6 | complete lesson passes D1–D4; prompt contains guidance/feedback; empty output; provider error; empty topic / bad retries; invented reference and missing section detection |
| `test_providers.py` | 7 | mock works without key; real mode without key errors clearly; unknown mode; rate-limit retry then give up; no retry on 4xx; empty reply; log redaction |
| `test_app.py` | 3 | Streamlit AppTest: retry scenario approved + SIMULATED banner; always_fail shows REJECTED; empty topic error |

Additional checks performed: (1) mutation test — forcing `passed = True` made `test_app_shows_rejection_for_always_fail` fail; allowing extra retries made 6 tests fail (both mutations reverted). (2) `streamlit run app.py --server.headless true` returned HTTP 200 on `/_stcore/health` and `/`. (3) `python scripts/demo_retry.py` produced the expected sequence (see §14).

**Not tested:** any call to the live Anthropic API, so real-model quality, real evaluator strictness and real learning effect are unmeasured. Visual appearance in a real browser was not reviewed (headless tests only).

## 21. Design decisions and why
- **Plain loop instead of LangGraph:** one linear loop with a cap; a graph framework adds dependency without benefit.
- **Hybrid evaluation:** code for countable rules, LLM for meaning.
- **Markdown lesson + JSON evaluation:** lesson prose is robust as Markdown; evaluation needs structure for validation.
- **Provider interface:** enables deterministic tests and offline demo.
- **Threshold learning with templates:** avoids over-reacting to one failure and keeps guidance readable and auditable.
- **Insert-only memory:** satisfies "never overwrite" and keeps history inspectable.
- **Separate DB per mode:** prevents simulated data from steering real runs.

## 22. Trade-offs and limitations
- The mock evaluator is rule-based and the mock generator is scripted; they demonstrate the mechanics, not LLM quality.
- Live-API behaviour is untested (see §20).
- With the same model as generator and judge, independence is procedural (separate prompt) rather than model-level; set `EVALUATOR_MODEL` to improve it.
- The knowledge base is RAG-only and small (17 notes); other topics will fail grounding.
- Learning is rule-based (templates); it does not discover novel failure causes.
- Three-attempt cap means a lesson that needs more fixes is rejected rather than perfected.
- SQLite is single-user; no authentication in the UI.
- Sentence-length and vocabulary judgement for R4 in real mode relies on the LLM judge, which can be inconsistent.

## 23. Possible future improvements
Add a second evaluator model and require agreement; retrieval over a larger knowledge base; automatic regression suite of "golden" good/bad lessons to calibrate the judge; guidance retirement with explicit human approval (still append-only); multi-language output; export to PDF; per-topic knowledge bases.

## 24. Conclusion
The project delivers a working closed-loop system whose key guarantees — binary rubric, independent evaluation, bounded regeneration, honest REJECTED/ERROR states, and traceable persistent learning — are enforced in code and verified by 57 automated tests. The principal remaining step is a real-API run with your key to confirm live behaviour.
