from __future__ import annotations

import math
from dataclasses import dataclass, field

DEFAULT_WEIGHTS: dict[str, float] = {
    "source_diversity": 0.25,
    "recency": 0.20,
    "embedding_similarity": 0.25,
    "graph_connectivity": 0.15,
    "sme_validation": 0.15,
}

DEFAULT_THRESHOLDS: dict[str, float] = {
    "low": 0.4,
    "high": 0.7,
}

_SIGNAL_NAMES = tuple(DEFAULT_WEIGHTS)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def source_diversity_signal(distinct_sources: int) -> float:
    return clamp(distinct_sources / 3.0)


def recency_signal(age_days: float, half_life_days: float = 180.0) -> float:
    return clamp(math.exp(-max(0.0, float(age_days)) / half_life_days))


def similarity_from_distance(distance: float) -> float:
    return clamp(1.0 - float(distance))


@dataclass
class ConfidenceResult:
    score: float
    signals: dict[str, float] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)
    low_confidence: bool = False
    high_confidence: bool = False
    threshold: float = DEFAULT_THRESHOLDS["low"]

    def as_dict(self) -> dict:
        return {
            "score": round(self.score, 4),
            "signals": {k: round(v, 4) for k, v in self.signals.items()},
            "low_confidence": self.low_confidence,
            "high_confidence": self.high_confidence,
            "threshold": self.threshold,
        }


class ConfidenceScorer:
    def __init__(self, weights: dict | None = None, thresholds: dict | None = None):
        merged_weights = dict(DEFAULT_WEIGHTS)
        merged_weights.update(weights or {})
        merged_thresholds = dict(DEFAULT_THRESHOLDS)
        merged_thresholds.update(thresholds or {})
        self.weights = {name: float(merged_weights[name]) for name in _SIGNAL_NAMES}
        self.thresholds = merged_thresholds

    def score(
        self,
        source_diversity: float = 0.0,
        recency: float = 0.0,
        embedding_similarity: float = 0.0,
        graph_connectivity: float = 0.0,
        sme_validation: float | None = None,
    ) -> ConfidenceResult:
        sme = 0.5 if sme_validation is None else clamp(sme_validation)
        signals = {
            "source_diversity": clamp(source_diversity),
            "recency": clamp(recency),
            "embedding_similarity": clamp(embedding_similarity),
            "graph_connectivity": clamp(graph_connectivity),
            "sme_validation": sme,
        }
        score = sum(self.weights[name] * signals[name] for name in _SIGNAL_NAMES)
        low = float(self.thresholds.get("low", 0.4))
        high = float(self.thresholds.get("high", 0.7))
        return ConfidenceResult(
            score=score,
            signals=signals,
            weights=self.weights,
            low_confidence=score < low,
            high_confidence=score >= high,
            threshold=low,
        )
