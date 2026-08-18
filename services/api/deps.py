from __future__ import annotations

import os
from dataclasses import dataclass

from core.confidence.scorer import ConfidenceScorer
from core.config import Config
from core.feedback.handler import FeedbackHandler
from core.feedback.processor import FeedbackProcessor
from core.graph.operations import Neo4jGraphStore, seed_ontology
from core.processing.embedder import ChromaVectorStore, Embedder
from core.rag.generator import AnswerGenerator
from core.rag.pipeline import RagPipeline
from core.storage.postgres import PostgresStore
from ingestion.ingest_all import build_pipeline, build_stores, load_ontology
from ingestion.pipeline import IngestionPipeline


@dataclass
class AppState:
    config: Config
    vector_store: ChromaVectorStore
    graph_store: Neo4jGraphStore
    feedback_store: PostgresStore
    feedback_handler: FeedbackHandler
    pipeline: RagPipeline
    ingestion_pipeline: IngestionPipeline
    ontology: dict


_state: AppState | None = None


def init_state(config_path: str | None = None) -> AppState:
    global _state
    if _state is not None:
        return _state
    config = Config.load(config_path)
    ontology = load_ontology(config)
    vector_store, graph_store, feedback_store = build_stores(config)
    feedback_store.init_schema()
    graph_store.ensure_constraints()
    seed_ontology(graph_store, ontology)

    generator = AnswerGenerator(
        model=config.llm.get("model", "claude-sonnet-4-20250514"),
        api_key=os.environ.get(config.llm.get("api_key_env", "ANTHROPIC_API_KEY")),
        provider=config.llm.get("provider", "anthropic"),
        base_url=config.llm.get("base_url", "http://localhost:11434"),
    )
    scorer = ConfidenceScorer(
        weights=config.calibrated_weights() or config.confidence.get("weights"),
        thresholds=config.confidence.get("thresholds"),
    )
    embedder = Embedder(config.embedding)
    ingestion_pipeline = build_pipeline(config, vector_store, graph_store, ontology)
    feedback_processor = FeedbackProcessor(
        pipeline=ingestion_pipeline,
        store=feedback_store,
        golden_priority=config.golden_priority(),
        priority_bonus=config.priority_bonus(),
    )
    feedback_handler = FeedbackHandler(feedback_store, processor=feedback_processor)
    pipeline = RagPipeline(
        vector_store=vector_store,
        graph_store=graph_store,
        embedder=embedder,
        generator=generator,
        confidence=scorer,
        ontology=ontology,
        feedback_handler=feedback_handler,
        feedback_match_threshold=config.approval_match_threshold(),
        priority_bonus=config.priority_bonus(),
        vector_top_k=int(config.ingestion.get("top_k", 8)),
    )
    _state = AppState(
        config=config,
        vector_store=vector_store,
        graph_store=graph_store,
        feedback_store=feedback_store,
        feedback_handler=feedback_handler,
        pipeline=pipeline,
        ingestion_pipeline=ingestion_pipeline,
        ontology=ontology,
    )
    return _state


def get_state() -> AppState:
    return init_state()


def reset_state() -> None:
    global _state
    _state = None
