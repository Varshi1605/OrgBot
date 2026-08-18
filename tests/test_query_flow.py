from __future__ import annotations

from core.confidence.scorer import ConfidenceScorer
from core.processing.embedder import Embedder
from core.rag.generator import AnswerGenerator
from core.rag.pipeline import RagPipeline
from simulators.org_ontology import COMPONENTS, PEOPLE, TEAMS

ONTOLOGY = {
    "people": PEOPLE,
    "components": COMPONENTS,
    "teams": TEAMS,
    "instruments": ["NIFTY50", "BANKNIFTY", "RELIANCE", "INFY", "TCS", "HDFC", "ICICIBANK", "SBIN"],
    "strategies": [],
}


class FakeVectorStore:
    def __init__(self):
        self.calls = 0

    def query(self, embedding, top_k=8):
        self.calls += 1
        return [
            {
                "id": "git:abc:0",
                "text": "Rohit Gupta committed a fix for the FIX session recovery in exchange-adapter.",
                "distance": 0.1,
                "metadata": {"source": "git", "repo": "exchange-adapter", "record_id": "abc", "timestamp": "2024-03-01T10:00:00+00:00"},
            },
            {
                "id": "slack:thr:0",
                "text": "Who owns the FIX session? Connectivity team handles exchange-adapter.",
                "distance": 0.2,
                "metadata": {"source": "slack", "channel": "exchange-ops", "record_id": "thr", "timestamp": "2024-03-02T10:00:00+00:00"},
            },
        ]

    def is_healthy(self):
        return True


class FakeGraphStore:
    def run_template(self, name, **params):
        if name == "component_team_contacts":
            return [{"name": "Vikram Das", "role": "Senior Connectivity Engineer", "slack_handle": "vikramdas"}]
        if name == "entity_neighborhood":
            return [{"entity": "exchange-adapter", "labels": ["Component"], "outbound": [], "inbound": []}]
        return []

    def run(self, cypher, **params):
        raise RuntimeError("llm cypher not exercised in offline test")

    def is_healthy(self):
        return True


def test_query_to_answer_flow():
    pipeline = RagPipeline(
        vector_store=FakeVectorStore(),
        graph_store=FakeGraphStore(),
        embedder=Embedder({"provider": "fallback", "dim": 64}),
        generator=AnswerGenerator(model="test", api_key=None),
        confidence=ConfidenceScorer(),
        ontology=ONTOLOGY,
        vector_top_k=8,
    )
    result = pipeline.answer("Who owns the FIX session?")
    assert result["question"] == "Who owns the FIX session?"
    assert result["answer"]
    assert result["confidence"]["score"] >= 0.0
    assert result["confidence"]["score"] <= 1.0
    assert result["sources"]
    assert any(source["kind"] == "vector" for source in result["sources"])
    assert result["graph_path"]


def test_query_with_no_evidence():
    class EmptyVectorStore(FakeVectorStore):
        def query(self, embedding, top_k=8):
            return []

    class EmptyGraphStore(FakeGraphStore):
        def run_template(self, name, **params):
            return []

    pipeline = RagPipeline(
        vector_store=EmptyVectorStore(),
        graph_store=EmptyGraphStore(),
        embedder=Embedder({"provider": "fallback", "dim": 64}),
        generator=AnswerGenerator(model="test", api_key=None),
        confidence=ConfidenceScorer(),
        ontology=ONTOLOGY,
        vector_top_k=8,
    )
    result = pipeline.answer("What color is the trading desk wall?")
    assert "No evidence" in result["answer"]
    assert result["confidence"]["score"] < 0.8
