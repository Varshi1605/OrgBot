from __future__ import annotations

import argparse
from pathlib import Path

from core.config import Config
from core.graph.operations import Neo4jGraphStore
from core.processing.embedder import ChromaVectorStore
from ingestion.ingest_all import build_stores


def verify(config: Config) -> dict:
    vector_store, graph_store, _ = build_stores(config)
    report: dict = {}

    collection_count = vector_store.count()
    report["chroma"] = {"collection": vector_store.collection_name, "chunk_count": collection_count}

    node_counts = graph_store.node_counts()
    edge_counts = graph_store.edge_counts()
    report["neo4j_nodes"] = node_counts
    report["neo4j_edges"] = edge_counts

    expected_labels = {
        "Person",
        "Component",
        "Repository",
        "Team",
        "Incident",
        "Commit",
        "Conversation",
        "Instrument",
        "Strategy",
        "Document",
    }
    report["missing_labels"] = sorted(expected_labels - set(node_counts))
    report["expert_in_edges"] = edge_counts.get("EXPERT_IN", 0)
    report["incident_distribution"] = _incident_distribution(graph_store)
    return report


def _incident_distribution(graph_store: Neo4jGraphStore) -> dict[str, int]:
    rows = graph_store.run(
        "MATCH (i:Incident)-[:AFFECTS]->(c:Component) RETURN c.name AS component, count(i) AS count"
    )
    return {row["component"]: int(row["count"]) for row in rows}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Verify ingestion results in ChromaDB and Neo4j")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    args = parser.parse_args(argv)
    config = Config.load(args.config)
    report = verify(config)
    for key, value in report.items():
        print(f"{key}: {value}")
    ok = not report["missing_labels"] and report["expert_in_edges"] > 0 and bool(report["incident_distribution"])
    print("VERIFICATION " + ("PASSED" if ok else "FAILED"))


if __name__ == "__main__":
    main()
