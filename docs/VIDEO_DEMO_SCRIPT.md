# Video Demonstration Script (target 4:30)

> **Status:** this is a script only. No video has been recorded. Record your own screen with the real running app.
> The retry demo uses the **offline mock provider, which is simulated** — say so on camera. If you have an API key, you may add a short real-Claude run at the end.

## Before you record (2 minutes)
```bash
cd self-evaluating-lesson-generator
rm -f data/memory_mock.db          # fresh memory so the learning moment is visible
streamlit run app.py
```
Browser at `http://localhost:8501`. Sidebar: provider = **mock**, scenario = **retry**, learning threshold = **2**. Zoom the browser to ~110%. Close other tabs. Have `docs/ARCHITECTURE.md` open in another tab (rendered Mermaid) and the VS Code project tree ready.

## Timeline
| Time | Show on screen | Say (suggested wording) |
|---|---|---|
| 0:00–0:25 | Title / README top | "I built a self-evaluating lesson generator. It writes a beginner lesson, checks its own work with an independent evaluator using a strict pass/fail rubric, regenerates if needed, and remembers its mistakes across runs." |
| 0:25–0:50 | README "Problem" + stack table | "The problem: one LLM call gives unchecked text, with no proof it is correct or understandable. Stack: Python, Streamlit, Claude API, Pydantic, SQLite, Pytest. The demo uses a simulated mock provider so it runs offline." |
| 0:50–1:15 | App home page, sidebar, memory dashboard (empty) | "Here is the interface. Input on top, results in tabs, a memory dashboard. Memory is empty: zero runs." |
| 1:15–1:35 | Topic field already says *Introduction to RAG*; retries slider = 2; click **Generate Lesson** | "Topic is Introduction to RAG, learner is a Class 12 graduate, maximum two retries. I press Generate." |
| 1:35–2:10 | Live status box: Generating → Evaluating → Regenerating → Evaluating → Approved | "Watch the stages. The generator writes attempt one. The evaluator checks 14 checkpoints. Something failed, so it regenerates." |
| 2:10–2:50 | Tab **Evaluation results** → Attempt 1: R5 and R6 FAIL | "Attempt one failed R5, jargon explanation, and R6, practical example. See the evidence and the exact correction required. No scores, no averages: one failure means fail." |
| 2:50–3:20 | Tab **Rejection history** | "This is the rejection log: failed IDs, why, the exact feedback sent to the generator, what changed in version two, and the result. Attempt two passed all 14, so the lesson is approved." Then show Lesson tab and the green APPROVED banner. |
| 3:20–3:50 | Change scenario to **always_fail**, click Generate | "To show the other ending, this scenario can never fix a factual error. After exactly two retries the system stops and shows REJECTED. It never labels a failed lesson as approved." Show red banner and 'NOT APPROVED' draft. |
| 3:50–4:20 | Set scenario back to **retry**. Run it twice (so R5/R6 have each failed in two runs). Third run: approved on attempt 1. Open **Memory dashboard** | "Memory: R5 and R6 failed in two separate runs, so the system stored guidance with the reason. On the next run the prompt included that guidance and it passed first time. The rubric itself is unchanged; learning only strengthens generation." |
| 4:20–4:45 | `ARCHITECTURE.md` diagram, then terminal `python -m pytest` | "Architecture: orchestrator, generator, evaluator, memory, provider interface. 57 automated tests cover retry limits, invalid evaluator output, and persistence. Thank you." |

## Reliable scenario (checklist)
1. Fresh DB. Scenario `retry`, threshold 2.
2. Run 1 → fails R5+R6, then approved on attempt 2 ✔ (shows regeneration).
3. Run 2 → same; after it the dashboard shows learned guidance for R5 and R6.
4. Run 3 → approved on attempt 1, prompt version `gen-prompt-v1+g2` ✔ (shows memory influence).
5. Scenario `always_fail` → REJECTED after 3 attempts ✔.
To shorten the video, set `LEARNING_THRESHOLD=1`; guidance then appears after the first run.
Offline fallback: `python scripts/demo_retry.py` prints the same sequence in the terminal.

## Optional real-API segment (only if you have a key)
Set `ANTHROPIC_API_KEY` in `.env`, choose provider **anthropic**, run once. Results will vary and may pass or fail for real; narrate what you actually see.
