from __future__ import annotations

from core.confidence.scorer import ConfidenceScorer
from core.feedback.handler import FeedbackHandler
from core.feedback.processor import FeedbackProcessor
from core.processing.chunker import Chunker
from core.processing.embedder import Embedder
from core.processing.entity_extractor import EntityExtractor
from core.rag.generator import AnswerGenerator
from core.rag.pipeline import RagPipeline
from ingestion.pipeline import IngestionPipeline
from simulators.org_ontology import COMPONENTS, PEOPLE, TEAMS
from tests.test_feedback_loop import FakeFeedbackStore

ONTOLOGY = {
    "people": PEOPLE,
    "components": COMPONENTS,
    "teams": TEAMS,
    "instruments": ["NIFTY50", "BANKNIFTY"],
    "strategies": [],
}


class FakeVectorStore:
    def __init__(self):
        self.chunks: dict[str, tuple[str, dict, float]] = {}

    def upsert_chunks(self, chunks, embeddings):
        for chunk in chunks:
            self.chunks[chunk.chunk_id] = (chunk.text, chunk.metadata, 0.1)

    def query(self, embedding, top_k=8):
        rows = [
            {"id": cid, "text": text, "distance": distance, "metadata": metadata}
            for cid, (text, metadata, distance) in self.chunks.items()
        ]
        rows.sort(key=lambda r: r["distance"])
        return rows[:top_k]

    def is_healthy(self):
        return True


class FakeGraphStore:
    def run_template(self, name, **params):
        return []

    def run(self, cypher, **params):
        raise RuntimeError("llm cypher not exercised in offline test")

    def is_healthy(self):
        return True


def build_harness():
    vector_store = FakeVectorStore()
    graph_store = FakeGraphStore()
    feedback_store = FakeFeedbackStore()
    embedder = Embedder({"provider": "fallback", "dim": 64})
    ingestion_pipeline = IngestionPipeline(
        chunker=Chunker(),
        embedder=embedder,
        vector_store=vector_store,
        graph_store=graph_store,
        extractor=EntityExtractor(model="test", api_key=None, ontology=ONTOLOGY),
        ontology=ONTOLOGY,
    )
    processor = FeedbackProcessor(ingestion_pipeline, feedback_store, golden_priority="high", priority_bonus=0.05)
    handler = FeedbackHandler(feedback_store, processor=processor)
    pipeline = RagPipeline(
        vector_store=vector_store,
        graph_store=graph_store,
        embedder=embedder,
        generator=AnswerGenerator(model="test", api_key=None),
        confidence=ConfidenceScorer(),
        ontology=ONTOLOGY,
        feedback_handler=handler,
        feedback_match_threshold=0.6,
        priority_bonus=0.05,
        vector_top_k=8,
    )
    return vector_store, handler, pipeline, feedback_store


def _seed_ordinary_chunk(vector_store):
    vector_store.chunks["git:abc:0"] = (
        "Rohit Gupta committed a fix for the FIX session recovery in exchange-adapter.",
        {
            "source": "git",
            "repo": "exchange-adapter",
            "record_id": "abc",
            "timestamp": "2024-03-01T10:00:00+00:00",
        },
        0.5,
    )


def test_correction_roundtrip_returns_golden_answer_with_higher_confidence():
    vector_store, handler, pipeline, _ = build_harness()
    _seed_ordinary_chunk(vector_store)

    before = pipeline.answer("Who owns the FIX session?")
    before_score = before["confidence"]["score"]

    record = handler.submit(
        {
            "query": "Who owns the FIX session?",
            "original_answer": before["answer"],
            "sme_answer": "The Connectivity team owns the FIX session.",
            "feedback_type": "correction",
            "sme_id": "sme-1",
        }
    )
    assert record["processing"]["golden_chunk_added"] is True

    after = pipeline.answer("Who owns the FIX session?")
    assert "Connectivity team" in after["answer"]
    assert any("sme_feedback" in source["origin"] for source in after["sources"])
    assert after["confidence"]["signals"]["sme_validation"] <= 0.5
    assert after["confidence"]["score"] > before_score


def test_approval_roundtrip_boosts_confidence():
    vector_store, handler, pipeline, _ = build_harness()
    _seed_ordinary_chunk(vector_store)

    before = pipeline.answer("Who owns the FIX session?")
    baseline_sme = before["confidence"]["signals"]["sme_validation"]
    baseline_score = before["confidence"]["score"]

    record = handler.submit(
        {
            "query": "Who owns the FIX session?",
            "original_answer": "The Connectivity team owns the FIX session.",
            "sme_answer": "",
            "feedback_type": "approval",
            "sme_id": "sme-1",
            "source_origins": ["git:abc:0"],
        }
    )
    assert record["processing"]["boost_applied"] is True

    after = pipeline.answer("Who owns the FIX session?")
    assert after["confidence"]["signals"]["sme_validation"] > baseline_sme
    assert after["confidence"]["signals"]["sme_validation"] > 0.5
    assert after["confidence"]["score"] > baseline_score


def test_annotation_roundtrip_makes_chunk_retrievable():
    _, handler, pipeline, _ = build_harness()
    record = handler.submit(
        {
            "query": "What is the deploy process?",
            "original_answer": "",
            "sme_answer": "Production deploys happen every Friday after market close.",
            "feedback_type": "annotation",
            "sme_id": "sme-1",
        }
    )
    assert record["processing"]["annotation_added"] is True
    result = pipeline.answer("When do production deploys happen?")
    assert any("sme_feedback" in source["origin"] for source in result["sources"])


def test_invalid_feedback_raises_before_storing():
    vector_store, handler, _, feedback_store = build_harness()
    _seed_ordinary_chunk(vector_store)
    try:
        handler.submit(
            {
                "query": "",
                "original_answer": "x",
                "sme_answer": "",
                "feedback_type": "approval",
                "sme_id": "sme-1",
            }
        )
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    assert feedback_store.feedback == []

    try:
        handler.submit(
            {
                "query": "q",
                "original_answer": "x",
                "sme_answer": "",
                "feedback_type": "correction",
                "sme_id": "sme-1",
            }
        )
        raise AssertionError("expected ValueError for correction without sme_answer")
    except ValueError:
        pass
    assert feedback_store.feedback == []
