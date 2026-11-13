# Architecture

## Component diagram
```mermaid
flowchart LR
    UI[Streamlit UI<br/>app.py + src/ui] --> ORCH[Orchestrator<br/>src/core/orchestrator.py]
    ORCH --> GEN[Generate Agent<br/>src/agents/generator.py]
    ORCH --> EVAL[Evaluate Agent<br/>src/agents/evaluator.py]
    ORCH --> MEM[MemoryManager<br/>SQLite]
    ORCH --> LEARN[LearningEngine]
    LEARN --> MEM
    GEN --> PROV{{LLM Provider<br/>interface}}
    EVAL --> PROV
    EVAL --> DET[Deterministic validators<br/>D1-D4]
    PROV --> CLAUDE[AnthropicProvider<br/>real Claude API]
    PROV --> MOCK[MockProvider<br/>SIMULATED, offline]
    GEN --> KB[(Knowledge base<br/>rag_reference.md)]
    EVAL --> KB
    DET --> KB
    EVAL --> RUB[[Rubric<br/>rubric.py]]
    GEN --> PROMPTS[[prompts.py]]
    EVAL --> PROMPTS
    LEARN -. "reads failures, adds guidance<br/>(never edits)" .-> RUB
```

## Workflow diagram
```mermaid
flowchart TD
    A[INPUT: topic, learner, max retries 0-2] --> B[Load learned guidance from SQLite]
    B --> C[GENERATE lesson<br/>reference notes + guidance]
    C --> D[EVALUATE: D1-D4 code checks + R1-R10 independent judge]
    D --> E{All 14 checks PASS?}
    E -- yes --> F[APPROVED -> final output]
    E -- no --> G{Retries left?}
    G -- yes --> H[Build feedback: failed IDs, evidence, reason, correction]
    H --> I[REGENERATE with previous lesson + feedback]
    I --> D
    G -- no --> J[REJECTED - max retry limit reached]
    D -. invalid / incomplete evaluator output .-> K[ERROR - never approved]
    F --> M[MEMORY UPDATE: save run, attempts, rejection log, corrections]
    J --> M
    K --> M
    M --> N[Learning engine: recurring failures -> new generation guidance]
```

## Responsibilities
| Module | Responsibility | Does NOT do |
|---|---|---|
| `agents/generator.py` | Builds the prompt (reference notes, guidance, feedback) and returns lesson Markdown | Judge quality |
| `agents/evaluator.py` | Runs D1–D4, asks the judge for R1–R10, validates and enforces the response | Write lessons |
| `core/orchestrator.py` | Bounded retry loop, feedback, rejection log, final status, persistence | Contain prompts or SQL |
| `core/rubric.py`, `core/prompts.py` | Rubric definition; all prompt text and versions | Runtime logic |
| `memory/*` | SQLite schema, run storage, statistics, recurring-failure analysis, guidance | Change the rubric |
| `providers/*` | One interface (`complete(system, user, task)`); Claude and mock implementations | Know about rubric or memory |
| `utils/validators.py` | Deterministic checks | LLM calls |
| `ui/render.py`, `app.py` | Display and exports | Business logic |

## Database tables
`runs`, `attempts`, `check_results`, `corrections`, `learned_guidance` (unique per checkpoint, insert-only), `prompt_versions`, `rubric_versions`, `user_feedback`.
Mock and real runs use **separate DB files** (`memory_mock.db`, `memory_real.db`) so simulated failures never teach real runs.
