from __future__ import annotations

import re

NEUTRAL = 0.5
CORRECTION_SIGNAL = 0.3

_WORD_RE = re.compile(r"[a-z0-9_]+")


def normalize_query(query: str) -> str:
    return " ".join(_WORD_RE.findall(str(query).lower()))


def query_key(query: str) -> str:
    return normalize_query(query)


def query_similarity(a: str, b: str) -> float:
    na = normalize_query(a)
    nb = normalize_query(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    tokens_a = set(na.split())
    tokens_b = set(nb.split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def compute_sme_signal(
    query: str,
    feedback_records: list[dict],
    boost_factors: dict[str, float] | None = None,
    threshold: float = 0.6,
) -> float:
    boost_factors = boost_factors or {}
    matches = [
        record
        for record in feedback_records
        if query_similarity(query, record.get("query", "")) >= threshold
    ]
    if not matches:
        return NEUTRAL
    if any(record.get("feedback_type") == "correction" for record in matches):
        return CORRECTION_SIGNAL
    approvals = [record for record in matches if record.get("feedback_type") == "approval"]
    if approvals:
        boosts = [
            boost_factors.get(query_key(record.get("query", "")), 1.0)
            for record in approvals
            if record.get("query")
        ]
        boost = max(boosts) if boosts else 1.0
        return min(1.0, 0.5 + 0.1 * boost)
    return NEUTRAL


def fetch_sme_signal(query: str, handler, threshold: float = 0.6) -> float:
    records = handler.feedback_records()
    if not records:
        return NEUTRAL
    boosts = handler.boost_factors()
    return compute_sme_signal(query, records, boosts, threshold)
