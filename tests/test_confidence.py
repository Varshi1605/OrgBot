from __future__ import annotations

import pytest

from core.confidence.scorer import ConfidenceScorer, recency_signal, source_diversity_signal


def test_default_weights_sum_to_one():
    scorer = ConfidenceScorer()
    assert abs(sum(scorer.weights.values()) - 1.0) < 1e-6


def test_full_evidence_scores_high():
    scorer = ConfidenceScorer()
    result = scorer.score(
        source_diversity=1.0,
        recency=1.0,
        embedding_similarity=1.0,
        graph_connectivity=1.0,
        sme_validation=1.0,
    )
    assert result.score == pytest.approx(1.0, abs=1e-6)
    assert result.high_confidence


def test_sparse_evidence_scores_low():
    scorer = ConfidenceScorer()
    result = scorer.score(
        source_diversity=0.0,
        recency=0.0,
        embedding_similarity=0.1,
        graph_connectivity=0.0,
        sme_validation=0.0,
    )
    assert result.score < 0.2
    assert result.low_confidence


def test_sme_validation_neutral_when_absent():
    scorer = ConfidenceScorer()
    with_absent = scorer.score(source_diversity=1.0, recency=1.0, embedding_similarity=1.0, graph_connectivity=1.0)
    with_neutral = scorer.score(
        source_diversity=1.0, recency=1.0, embedding_similarity=1.0, graph_connectivity=1.0, sme_validation=0.5
    )
    assert with_absent.score == with_neutral.score


def test_custom_weights_override_defaults():
    scorer = ConfidenceScorer(weights={"recency": 1.0, "source_diversity": 0.0})
    assert scorer.weights["recency"] == 1.0
    assert scorer.weights["source_diversity"] == 0.0
    result = scorer.score(
        source_diversity=1.0,
        recency=0.5,
        embedding_similarity=0.0,
        graph_connectivity=0.0,
        sme_validation=0.0,
    )
    assert result.score == pytest.approx(0.5)


def test_signal_helpers_bounded():
    assert 0.0 <= source_diversity_signal(0) <= 1.0
    assert source_diversity_signal(3) == pytest.approx(1.0)
    assert 0.0 < recency_signal(0) <= 1.0
    assert 0.0 <= recency_signal(10_000) <= 1.0
