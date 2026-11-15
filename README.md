# Self-Evaluating Lesson Content Generator

An agentic content system that **generates** a beginner lesson, **evaluates** it against a strict binary rubric, **regenerates** with targeted feedback (max 2 retries), and **remembers** recurring failures in SQLite to improve future generations — without ever lowering the quality bar.

```
INPUT → GENERATE → EVALUATE → REGENERATE → FINAL OUTPUT → MEMORY UPDATE
```
Demo topic: **Introduction to RAG (Retrieval-Augmented Generation)** for a Class 12 graduate in India with limited English and no technical background.

## Features
- Generate Agent and an independent Evaluate Agent (separate prompts; optional separate model)
- 14 mandatory checkpoints: 4 deterministic code checks (D1–D4) + 10 LLM-judged (R1–R10). **Any FAIL = FAIL.** No averages.
- Grounding against curated reference notes with citable IDs (`[N1]`…); invented IDs are rejected
- Bounded retry loop (0–2 retries), full rejection log, `REJECTED` clearly shown, never mislabelled as approved
- SQLite memory: runs, attempts, rejection logs, corrections, learned guidance (with reasons), prompt/rubric versions, user feedback
- Streamlit UI with live pipeline status, evaluation tables, rejection history, memory dashboard, exports
- **Mock mode** (offline, no API key). All mock output is labelled **SIMULATED**.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env                    # Windows: copy only if .env does not exist
streamlit run app.py
```
Opens at http://localhost:8501. Default provider is **mock** (no key needed).

### Use the real Claude API
Edit `.env`:
```
PROVIDER_MODE=anthropic
ANTHROPIC_API_KEY=your-key-here
ANTHROPIC_MODEL=claude-sonnet-5-5
EVALUATOR_MODEL=          # optional: a different model for a more independent judge
```
Or pick **anthropic** in the app sidebar. Without a key you get a clear error telling you to set it or use mock mode. Never commit `.env`.

> The Anthropic code path is covered by unit tests with a stubbed SDK client. It has **not** been exercised against the live API in the development environment (no key available). Run it once with your key before submitting.

### Environment variables
| Variable | Default | Meaning |
|---|---|---|
| `PROVIDER_MODE` | `mock` | `mock` or `anthropic` |
| `ANTHROPIC_API_KEY` | – | Required only for `anthropic` |
| `ANTHROPIC_MODEL` | `claude-sonnet-5-5` | Generator (and evaluator) model |
| `EVALUATOR_MODEL` | – | Optional separate evaluator model |
| `LEARNING_THRESHOLD` | `2` | Separate runs a checkpoint must fail in before guidance is learned |
| `LESSONGEN_DB_DIR` | `data` | Folder for `memory_mock.db` / `memory_real.db` |
| `LOG_LEVEL` | `INFO` | JSON logs on stderr, secrets redacted |

## Run the tests
```bash
python -m pytest
```
Result at time of writing: **57 passed** (no network or API key needed).

## Demonstrate it
1. **Initial generation:** mock scenario `clean` → approved on attempt 1.
2. **Failure and regeneration:** scenario `retry` → attempt 1 fails R5+R6, feedback is sent, attempt 2 passes. See *Evaluation results* and *Rejection history* tabs.
3. **Rejection:** scenario `always_fail` → exactly 3 attempts, then `REJECTED — Maximum retry limit reached…`.
4. **Memory:** with scenario `retry`, run twice (R5 and R6 each fail in 2 runs → guidance stored). The third run passes on attempt 1 with prompt version `gen-prompt-v1+g2`. Restart the app: memory is still there.
5. Terminal version of all of the above (simulated): `python scripts/demo_retry.py`

Mock scenarios: `clean`, `retry`, `slow` (needs both retries), `always_fail`.

## Project structure
```
app.py                      Streamlit entry point
src/agents/                 generator.py, evaluator.py
src/core/                   orchestrator.py, schemas.py, rubric.py, prompts.py, factory.py, errors.py
src/memory/                 database.py, memory_manager.py, learning_engine.py
src/providers/              base.py, anthropic_provider.py, mock_provider.py (+ mock_lesson.py, mock_checks.py)
src/knowledge_base/         rag_reference.md, loader.py
src/utils/                  config.py, logger.py, validators.py, export.py
src/ui/render.py            Streamlit rendering helpers
tests/                      57 pytest tests
docs/                       PROJECT_REPORT, ARCHITECTURE, PLANNING, RUBRIC, VIDEO_DEMO_SCRIPT
scripts/demo_retry.py       Simulated retry + learning demo
```

## Documentation
[`docs/PROJECT_REPORT.md`](docs/PROJECT_REPORT.md) · [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · [`docs/RUBRIC.md`](docs/RUBRIC.md) · [`docs/PLANNING.md`](docs/PLANNING.md) · [`docs/VIDEO_DEMO_SCRIPT.md`](docs/VIDEO_DEMO_SCRIPT.md)

## Reference material
`src/knowledge_base/rag_reference.md` holds short paraphrased notes citing: Lewis et al. 2020 (arXiv:2005.11401), AWS "What is RAG?", and Anthropic "Contextual Retrieval". Open each URL and confirm the notes before submission. The knowledge base covers RAG only; other topics will be judged against RAG notes and are expected to fail grounding.
