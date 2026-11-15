"""Builds a ready-to-use pipeline (shared by the Streamlit app, the demo script and tests)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.agents.evaluator import LessonEvaluator
from src.agents.generator import LessonGenerator
from src.core.orchestrator import LessonOrchestrator
from src.knowledge_base.loader import KnowledgeBase, load_knowledge_base
from src.memory.database import Database
from src.memory.learning_engine import LearningEngine
from src.memory.memory_manager import MemoryManager
from src.providers import LLMProvider, create_provider
from src.utils.config import Settings, load_settings


@dataclass
class Pipeline:
    orchestrator: LessonOrchestrator
    memory: MemoryManager
    learning: LearningEngine
    provider: LLMProvider
    kb: KnowledgeBase


def build_pipeline(mode: str = "mock", scenario: str = "retry", db_path: str | Path | None = None,
                   learning_threshold: int | None = None, kb_path: str | Path | None = None,
                   settings: Settings | None = None, provider: LLMProvider | None = None,
                   evaluator_provider: LLMProvider | None = None) -> Pipeline:
    settings = settings or load_settings()
    provider = provider or create_provider(mode, api_key=settings.api_key, model=settings.model, scenario=scenario)
    if evaluator_provider is None:
        evaluator_provider = provider
        if mode == "anthropic" and settings.evaluator_model:
            evaluator_provider = create_provider(mode, api_key=settings.api_key, model=settings.evaluator_model)
    kb = load_knowledge_base(kb_path)
    memory = MemoryManager(Database(db_path or settings.db_path(mode)))
    learning = LearningEngine(
        memory, learning_threshold if learning_threshold is not None else settings.learning_threshold
    )
    orchestrator = LessonOrchestrator(
        LessonGenerator(provider, kb), LessonEvaluator(evaluator_provider, kb), kb, memory, learning,
        provider_name=provider.name, simulated=provider.is_simulated)
    return Pipeline(orchestrator, memory, learning, provider, kb)
