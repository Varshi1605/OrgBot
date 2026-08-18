from __future__ import annotations

from core.storage.postgres import PostgresStore

VALID_TYPES = {"correction", "approval", "annotation"}


class FeedbackHandler:
    def __init__(self, store: PostgresStore, processor=None):
        self.store = store
        self.processor = processor

    def submit(self, payload: dict) -> dict:
        feedback_type = payload.get("feedback_type")
        if feedback_type not in VALID_TYPES:
            raise ValueError(f"feedback_type must be one of {sorted(VALID_TYPES)}")
        query = payload.get("query")
        if not query:
            raise ValueError("query is required")
        sme_id = payload.get("sme_id")
        if not sme_id:
            raise ValueError("sme_id is required")
        if feedback_type in ("correction", "annotation") and not payload.get("sme_answer"):
            raise ValueError(f"sme_answer is required for {feedback_type}")
        if feedback_type == "approval" and not payload.get("original_answer"):
            raise ValueError("original_answer is required for approval")
        record = self.store.add_feedback(
            query=query,
            original_answer=payload.get("original_answer", ""),
            sme_answer=payload.get("sme_answer", ""),
            feedback_type=feedback_type,
            sme_id=sme_id,
        )
        if self.processor is not None:
            try:
                record["processing"] = self.processor.process(record)
            except Exception as exc:  # noqa: BLE001 - record is already persisted
                record["processing"] = {"error": str(exc)}
        return record

    def approvals_for_query(self, query: str) -> list[dict]:
        feedback = self.store.list_feedback()
        return [f for f in feedback if f["feedback_type"] == "approval"]

    def feedback_records(self) -> list[dict]:
        return self.store.list_feedback()

    def boost_factors(self) -> dict[str, float]:
        return {b["query_key"]: b["boost_factor"] for b in self.store.list_boosts()}
