from __future__ import annotations

from core.confidence.scorer import ConfidenceScorer
from core.feedback.sme_signal import fetch_sme_signal
from core.rag.fusion import fuse
from core.rag.generator import AnswerGenerator
from core.rag.response_builder import ResponseBuilder
from core.rag.retrievers import GraphRetriever, VectorRetriever


class RagPipeline:
    def __init__(
        self,
        vector_store,
        graph_store,
        embedder,
        generator: AnswerGenerator,
        confidence: ConfidenceScorer,
        ontology: dict | None = None,
        feedback_handler=None,
        feedback_match_threshold: float = 0.6,
        priority_bonus: float = 0.0,
        vector_top_k: int = 8,
    ):
        self.vector_retriever = VectorRetriever(vector_store, embedder, top_k=vector_top_k)
        self.graph_retriever = GraphRetriever(
            graph_store,
            ontology=ontology,
            model=generator.model,
            api_key=generator.api_key,
            llm_provider=generator.provider,
            base_url=generator.base_url,
        )
        self.generator = generator
        self.confidence = confidence
        self.feedback_handler = feedback_handler
        self.feedback_match_threshold = feedback_match_threshold
        self.priority_bonus = priority_bonus
        self.response_builder = ResponseBuilder(scorer=confidence)
        self.top_k = vector_top_k

    def answer(self, question: str) -> dict:
        vector_results = self.vector_retriever.retrieve(question)
        graph_facts = self.graph_retriever.retrieve(question)
        fused_evidence = fuse(
            vector_results,
            graph_facts,
            top_k=self.top_k,
            priority_bonus=self.priority_bonus,
        )
        answer = self.generator.generate(question, fused_evidence)
        sme_signal = self._sme_signal(question)
        return self.response_builder.build(
            question=question,
            answer=answer,
            fused_evidence=fused_evidence,
            graph_facts=graph_facts,
            sme_validation=sme_signal,
        )

    def _sme_signal(self, question: str) -> float | None:
        if self.feedback_handler is None:
            return None
        try:
            return fetch_sme_signal(
                question,
                self.feedback_handler,
                threshold=self.feedback_match_threshold,
            )
        except Exception:  # noqa: BLE001
            return None
