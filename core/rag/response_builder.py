from __future__ import annotations

from datetime import datetime, timezone

from core.confidence.scorer import (
    ConfidenceScorer,
    recency_signal,
    source_diversity_signal,
)
from core.rag.fusion import origin_for_chunk


def _chunk_timestamp(metadata: dict) -> str | None:
    return metadata.get("timestamp")


class ResponseBuilder:
    def __init__(self, scorer: ConfidenceScorer | None = None):
        self.scorer = scorer or ConfidenceScorer()

    def build(
        self,
        question: str,
        answer: str,
        fused_evidence: list[dict],
        graph_facts: list[dict],
        sme_validation: float | None = None,
    ) -> dict:
        sources = []
        vector_scores = []
        timestamps = []
        for item in fused_evidence:
            excerpt = item.get("text", "").strip().replace("\n", " ")[:240]
            sources.append(
                {
                    "origin": item["origin"],
                    "kind": item["kind"],
                    "excerpt": excerpt,
                    "score": round(item["score"], 4),
                }
            )
            if item["kind"] == "vector":
                vector_scores.append(item["score"])
            ts = _chunk_timestamp(item.get("metadata") or {})
            if ts:
                timestamps.append(ts)

        distinct_sources = {s["origin"] for s in sources}
        diversity = source_diversity_signal(len(distinct_sources))
        embedding_similarity = (sum(vector_scores) / len(vector_scores)) if vector_scores else 0.5
        has_graph = any(item["kind"] == "graph" for item in fused_evidence)
        graph_connectivity = 1.0 if has_graph else 0.5
        recency = self._recency_signal(timestamps)

        result = self.scorer.score(
            source_diversity=diversity,
            recency=recency,
            embedding_similarity=embedding_similarity,
            graph_connectivity=graph_connectivity,
            sme_validation=sme_validation,
        )

        return {
            "question": question,
            "answer": answer,
            "confidence": result.as_dict(),
            "sources": sources,
            "graph_path": self._graph_path(graph_facts),
        }

    def _recency_signal(self, timestamps: list[str]) -> float:
        if not timestamps:
            return 0.5
        parsed = []
        now = datetime.now(timezone.utc)
        for raw in timestamps:
            try:
                value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                parsed.append((now - value).total_seconds() / 86400.0)
            except ValueError:
                continue
        if not parsed:
            return 0.5
        return recency_signal(min(parsed))

    @staticmethod
    def _graph_path(graph_facts: list[dict]) -> list[str]:
        path = []
        for fact in graph_facts:
            for row in fact.get("facts") or []:
                path.append(str(row))
        return path
