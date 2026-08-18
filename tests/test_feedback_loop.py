from __future__ import annotations

import json

import pytest

from core.confidence.scorer import ConfidenceScorer
from core.config import Config
from core.feedback.calibration import calibrate_weights, load_weights, save_weights
from core.feedback.processor import FeedbackProcessor
from core.feedback.sme_signal import compute_sme_signal, query_similarity
from core.rag.fusion import fuse


class FakeFeedbackStore:
    def __init__(self):
        self.feedback: list[dict] = []
        self.boosts: dict[str, dict] = {}
        self._next_id = 1

    def add_feedback(self, query, original_answer, sme_answer, feedback_type, sme_id):
        record = {
            "id": self._next_id,
            "query": query,
            "original_answer": original_answer,
            "sme_answer": sme_answer,
            "feedback_type": feedback_type,
            "sme_id": sme_id,
            "created_at": "2026-08-13T00:00:00+00:00",
        }
        self._next_id += 1
        self.feedback.append(record)
        return dict(record)

    def list_feedback(self, limit=100):
        return list(self.feedback)

    def add_boost(self, query_key, boost_factor, approved_sources=None):
        boost = {
            "query_key": query_key,
            "boost_factor": boost_factor,
            "approved_sources": list(approved_sources or []),
            "created_at": "2026-08-13T00:00:00+00:00",
        }
        self.boosts[query_key] = boost
        return dict(boost)

    def list_boosts(self, limit=100):
        return list(self.boosts.values())

    def get_boost_for_query(self, query_key):
        boost = self.boosts.get(query_key)
        return dict(boost) if boost else None


class RecordingPipeline:
    def __init__(self):
        self.records = []

    def process_record(self, record, ingest_graph=True):
        self.records.append(record)
        return {"record_id": record.record_id, "chunks": 1, "entities": 0}


def _correction(store, query="Who owns the FIX session?"):
    return store.add_feedback(
        query=query,
        original_answer="old answer",
        sme_answer="The Connectivity team owns the FIX session.",
        feedback_type="correction",
        sme_id="sme-1",
    )


def test_correction_path_builds_golden_chunk():
    store = FakeFeedbackStore()
    pipeline = RecordingPipeline()
    processor = FeedbackProcessor(pipeline, store, golden_priority="high")
    feedback = _correction(store)
    result = processor.process(feedback)
    assert result["golden_chunk_added"] is True
    record = pipeline.records[0]
    assert record.source == "sme_feedback"
    assert record.metadata["priority"] == "high"
    assert record.metadata["feedback_id"] == feedback["id"]
    assert record.metadata["query"] == feedback["query"]
    assert record.text == feedback["sme_answer"]
    assert record.record_id == f"feedback-{feedback['id']}"


def test_annotation_path_is_normal_priority_and_kind_annotation():
    store = FakeFeedbackStore()
    pipeline = RecordingPipeline()
    processor = FeedbackProcessor(pipeline, store, golden_priority="high")
    feedback = store.add_feedback(
        query="What is the deployment process?",
        original_answer="",
        sme_answer="Deploys happen every Friday after market close.",
        feedback_type="annotation",
        sme_id="sme-1",
    )
    result = processor.process(feedback)
    assert result["annotation_added"] is True
    record = pipeline.records[0]
    assert record.metadata["kind"] == "annotation"
    assert record.metadata["priority"] == "normal"
    assert record.source == "sme_feedback"


def test_approval_path_stores_boost_and_origins():
    store = FakeFeedbackStore()
    pipeline = RecordingPipeline()
    processor = FeedbackProcessor(pipeline, store, priority_bonus=0.05)
    feedback = store.add_feedback(
        query="Who owns the FIX session?",
        original_answer="The Connectivity team owns the FIX session.",
        sme_answer="",
        feedback_type="approval",
        sme_id="sme-1",
    )
    feedback["source_origins"] = ["git:abc:0"]
    result = processor.process(feedback)
    assert result["boost_applied"] is True
    boost = store.get_boost_for_query("who owns the fix session")
    assert boost is not None
    assert boost["approved_sources"] == ["git:abc:0"]
    assert boost["boost_factor"] == pytest.approx(1.05)


def test_deterministic_chunk_ids_for_feedback():
    store = FakeFeedbackStore()
    pipeline = RecordingPipeline()
    processor = FeedbackProcessor(pipeline, store, golden_priority="high")
    feedback = _correction(store)
    processor.process(feedback)
    record = pipeline.records[0]
    assert record.record_id == f"feedback-{feedback['id']}"
    chunk_ids = [f"{record.source}:{record.record_id}:{i}" for i in range(1)]
    assert chunk_ids == [f"sme_feedback:feedback-{feedback['id']}:0"]


def test_sme_signal_neutral_when_no_feedback():
    assert compute_sme_signal("Who owns the FIX session?", []) == 0.5


def test_sme_signal_approval_raises_above_neutral():
    records = [
        {
            "query": "Who owns the FIX session?",
            "feedback_type": "approval",
            "sme_answer": "",
            "original_answer": "answer",
        }
    ]
    signal = compute_sme_signal("Who owns the FIX session?", records, boost_factors={"who owns the fix session": 1.05})
    assert signal > 0.5


def test_sme_signal_correction_lowers_below_neutral():
    records = [
        {
            "query": "Who owns the FIX session?",
            "feedback_type": "correction",
            "sme_answer": "correct answer",
            "original_answer": "",
        }
    ]
    signal = compute_sme_signal("Who owns the FIX session?", records)
    assert signal <= 0.5


def test_sme_signal_no_similar_match_is_neutral():
    records = [
        {
            "query": "Who owns the FIX session?",
            "feedback_type": "approval",
            "sme_answer": "",
            "original_answer": "answer",
        }
    ]
    assert compute_sme_signal("What is the lunch menu?", records, boost_factors={}) == 0.5


def test_query_similarity():
    assert query_similarity("Who owns the FIX session?", "Who owns the FIX session?") == 1.0
    assert query_similarity("Who owns the FIX session?", "unrelated question") == 0.0
    assert 0.0 < query_similarity("Who owns the FIX session?", "Who owns the FIX adapter?") < 1.0


def test_fusion_priority_bonus_breaks_ties_for_sme_feedback():
    items = [
        {"text": "ordinary chunk", "distance": 0.3, "metadata": {"source": "git", "record_id": "abc"}},
        {
            "text": "golden chunk",
            "distance": 0.3,
            "metadata": {"source": "sme_feedback", "record_id": "feedback-1"},
        },
    ]
    ranked = fuse(items, [], top_k=8, priority_bonus=0.05)
    assert ranked[0]["metadata"]["source"] == "sme_feedback"
    assert ranked[0]["score"] > ranked[1]["score"]


def test_fusion_without_bonus_preserves_order():
    items = [
        {"text": "ordinary chunk", "distance": 0.3, "metadata": {"source": "git", "record_id": "abc"}},
        {
            "text": "golden chunk",
            "distance": 0.3,
            "metadata": {"source": "sme_feedback", "record_id": "feedback-1"},
        },
    ]
    ranked = fuse(items, [], top_k=8)
    assert ranked[0]["metadata"]["source"] == "git"


def test_calibration_fits_weights_in_valid_range():
    rows = [
        {"source_diversity": 1.0, "recency": 1.0, "embedding_similarity": 1.0, "graph_connectivity": 1.0, "sme_validation": 1.0},
        {"source_diversity": 0.0, "recency": 0.0, "embedding_similarity": 0.0, "graph_connectivity": 0.0, "sme_validation": 0.0},
        {"source_diversity": 1.0, "recency": 0.0, "embedding_similarity": 0.0, "graph_connectivity": 0.0, "sme_validation": 0.0},
        {"source_diversity": 0.0, "recency": 1.0, "embedding_similarity": 0.0, "graph_connectivity": 0.0, "sme_validation": 0.0},
        {"source_diversity": 0.0, "recency": 0.0, "embedding_similarity": 1.0, "graph_connectivity": 0.0, "sme_validation": 0.0},
        {"source_diversity": 0.0, "recency": 0.0, "embedding_similarity": 0.0, "graph_connectivity": 1.0, "sme_validation": 0.0},
        {"source_diversity": 0.0, "recency": 0.0, "embedding_similarity": 0.0, "graph_connectivity": 0.0, "sme_validation": 1.0},
    ]
    targets = [1.0, 0.0, 0.8, 0.6, 0.7, 0.5, 0.3]
    weights = calibrate_weights(rows, targets)
    assert weights is not None
    assert all(0.0 <= v <= 1.0 for v in weights.values())
    assert abs(sum(weights.values()) - 1.0) < 1e-6
    assert weights["source_diversity"] > weights["sme_validation"]


def test_calibration_returns_none_without_rows():
    assert calibrate_weights([], []) is None
    assert calibrate_weights([{"source_diversity": 1.0}], [1.0]) is None


def test_load_weights_falls_back_when_missing_or_invalid(tmp_path):
    missing = tmp_path / "missing.json"
    assert load_weights(missing) is None

    invalid = tmp_path / "invalid.json"
    invalid.write_text("not json", encoding="utf-8")
    assert load_weights(invalid) is None

    bad_weights = tmp_path / "bad.json"
    bad_weights.write_text(json.dumps({"weights": {"source_diversity": 2.5}}), encoding="utf-8")
    assert load_weights(bad_weights) is None


def test_save_then_load_weights_roundtrip(tmp_path):
    weights = {
        "source_diversity": 0.3,
        "recency": 0.2,
        "embedding_similarity": 0.2,
        "graph_connectivity": 0.15,
        "sme_validation": 0.15,
    }
    path = tmp_path / "weights.json"
    save_weights(path, weights, samples=3)
    loaded = load_weights(path)
    assert loaded is not None
    for name, value in weights.items():
        assert loaded[name] == pytest.approx(value)


def test_config_calibrated_weights_loads_and_falls_back(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    weights_path = tmp_path / "calibrated_weights.json"
    (config_dir / "config.yaml").write_text(
        "confidence:\n"
        "  calibrated_weights_path: calibrated_weights.json\n"
        "  weights:\n"
        "    source_diversity: 0.25\n"
        "    recency: 0.20\n"
        "    embedding_similarity: 0.25\n"
        "    graph_connectivity: 0.15\n"
        "    sme_validation: 0.15\n",
        encoding="utf-8",
    )
    config = Config.load(str(config_dir / "config.yaml"))
    assert config.calibrated_weights() is None

    save_weights(
        weights_path,
        {
            "source_diversity": 0.4,
            "recency": 0.1,
            "embedding_similarity": 0.3,
            "graph_connectivity": 0.1,
            "sme_validation": 0.1,
        },
    )
    config = Config.load(str(config_dir / "config.yaml"))
    loaded = config.calibrated_weights()
    assert loaded is not None
    assert loaded["source_diversity"] == pytest.approx(0.4)


def test_scorer_with_calibrated_weights(tmp_path):
    scorer = ConfidenceScorer(
        weights={
            "source_diversity": 0.4,
            "recency": 0.1,
            "embedding_similarity": 0.3,
            "graph_connectivity": 0.1,
            "sme_validation": 0.1,
        }
    )
    result = scorer.score(
        source_diversity=1.0,
        recency=1.0,
        embedding_similarity=1.0,
        graph_connectivity=1.0,
        sme_validation=1.0,
    )
    assert result.score == pytest.approx(1.0)
