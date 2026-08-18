from __future__ import annotations

from core.confidence.scorer import similarity_from_distance


def origin_for_chunk(metadata: dict) -> str:
    source = metadata.get("source") or metadata.get("_source") or "unknown"
    if source == "git":
        repo = metadata.get("repo") or "repo"
        record_id = metadata.get("record_id") or metadata.get("hash") or "?"
        return f"commit {repo}:{record_id}"
    if source == "slack":
        channel = metadata.get("channel") or "channel"
        thread = metadata.get("thread_id") or metadata.get("record_id") or "?"
        return f"slack #{channel}:{thread}"
    if source == "incident":
        return f"incident {metadata.get('record_id') or metadata.get('id') or '?'}"
    if source == "docs":
        return f"doc {metadata.get('path') or '?'}"
    return f"{source}:{metadata.get('record_id') or '?'}"


def render_facts(fact_group: dict) -> str:
    rows = fact_group.get("facts") or []
    rendered: list[str] = []
    for row in rows:
        parts = [f"{key}={value}" for key, value in row.items() if value not in (None, [], {}, "")]
        if parts:
            rendered.append(" ".join(parts))
    return "\n".join(rendered)


def fuse(
    vector_results: list[dict],
    graph_facts: list[dict],
    top_k: int = 8,
    priority_bonus: float = 0.0,
) -> list[dict]:
    combined: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for item in vector_results:
        text = item.get("text") or ""
        origin = origin_for_chunk(item.get("metadata") or {})
        score = similarity_from_distance(item.get("distance", 1.0))
        if (item.get("metadata") or {}).get("source") == "sme_feedback":
            score = min(1.0, score + float(priority_bonus))
        key = ("vector", origin)
        if key in seen or not text:
            continue
        seen.add(key)
        combined.append(
            {
                "kind": "vector",
                "origin": origin,
                "text": text,
                "score": score,
                "metadata": item.get("metadata") or {},
            }
        )

    for fact_group in graph_facts:
        text = render_facts(fact_group)
        if not text:
            continue
        kind = fact_group.get("kind") or "graph"
        origin = f"graph:{kind}"
        key = ("graph", origin)
        if key in seen:
            continue
        seen.add(key)
        score = 0.8 if kind == "llm_cypher" else 1.0
        combined.append(
            {
                "kind": "graph",
                "origin": origin,
                "text": text,
                "score": score,
                "metadata": {"source": "graph", "kind": kind},
            }
        )

    combined.sort(key=lambda item: item["score"], reverse=True)
    return combined[:top_k]
