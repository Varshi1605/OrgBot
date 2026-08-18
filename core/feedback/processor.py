from __future__ import annotations

from core.connectors.base import SourceRecord
from core.feedback.sme_signal import query_key

NORMAL_PRIORITY = "normal"


class FeedbackProcessor:
    def __init__(
        self,
        pipeline,
        store,
        golden_priority: str = "high",
        priority_bonus: float = 0.05,
    ):
        self.pipeline = pipeline
        self.store = store
        self.golden_priority = golden_priority
        self.priority_bonus = priority_bonus

    def process(self, feedback: dict) -> dict:
        feedback_type = feedback.get("feedback_type")
        if feedback_type == "correction":
            return self.process_correction(feedback)
        if feedback_type == "approval":
            return self.process_approval(feedback)
        if feedback_type == "annotation":
            return self.process_annotation(feedback)
        raise ValueError(f"Unsupported feedback_type: {feedback_type}")

    def process_correction(self, feedback: dict) -> dict:
        record = self._feedback_record(feedback, priority=self.golden_priority, kind="golden")
        stats = self.pipeline.process_record(record, ingest_graph=False)
        return {
            "type": "correction",
            "golden_chunk_added": True,
            "chunks": stats["chunks"],
            "record_id": record.record_id,
        }

    def process_annotation(self, feedback: dict) -> dict:
        record = self._feedback_record(feedback, priority=NORMAL_PRIORITY, kind="annotation")
        stats = self.pipeline.process_record(record, ingest_graph=False)
        return {
            "type": "annotation",
            "annotation_added": True,
            "chunks": stats["chunks"],
            "record_id": record.record_id,
        }

    def process_approval(self, feedback: dict) -> dict:
        query = feedback.get("query", "")
        origins = feedback.get("source_origins") or []
        boost = self.store.add_boost(
            query_key(query),
            1.0 + self.priority_bonus,
            approved_sources=origins,
        )
        return {
            "type": "approval",
            "boost_applied": True,
            "boost_factor": boost["boost_factor"],
            "approved_sources": origins,
        }

    def _feedback_record(self, feedback: dict, priority: str, kind: str) -> SourceRecord:
        record_id = f"feedback-{feedback['id']}"
        return SourceRecord(
            source="sme_feedback",
            record_id=record_id,
            text=feedback.get("sme_answer") or feedback.get("query") or "",
            timestamp=feedback.get("created_at"),
            metadata={
                "priority": priority,
                "feedback_id": feedback.get("id"),
                "query": feedback.get("query"),
                "feedback_type": feedback.get("feedback_type"),
                "kind": kind,
            },
            cursor="",
        )
