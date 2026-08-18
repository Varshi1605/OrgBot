from __future__ import annotations

import argparse

from core.config import Config
from core.connectors.base import BaseConnector
from core.connectors.docs_connector import DocsConnector
from core.connectors.git_connector import GitConnector
from core.connectors.incident_connector import IncidentConnector
from core.connectors.slack_connector import SlackConnector
from core.graph.operations import Neo4jGraphStore, enrich_graph, ingest_entities, seed_ontology
from ingestion.graph_builder import build_graph_payload
from ingestion.ingest_all import load_ontology

CONNECTORS: dict[str, type[BaseConnector]] = {
    "git": GitConnector,
    "slack": SlackConnector,
    "incident": IncidentConnector,
    "docs": DocsConnector,
}


def ingest_metadata(config: Config, sources: list[str]) -> dict:
    graph_cfg = config.stores.get("graph", {}).get("neo4j", {})
    graph_store = Neo4jGraphStore(
        uri=graph_cfg.get("uri", "bolt://localhost:7687"),
        user=graph_cfg.get("user", "neo4j"),
        password=graph_cfg.get("password", ""),
        database=graph_cfg.get("database", "neo4j"),
    )
    ontology = load_ontology(config)
    graph_store.ensure_constraints()
    seed_ontology(graph_store, ontology)

    data_dir = config.ingestion.get("data_dir", "data/simulated")
    results: dict[str, dict] = {}
    for source in sources:
        connector_cls = CONNECTORS[source]
        connector = connector_cls(data_dir=data_dir)
        raw_records = connector.fetch(None)
        entity_count = 0
        rel_count = 0
        for raw in raw_records:
            record = connector.transform(raw)
            entities, relationships = build_graph_payload(record, ontology)
            if entities or relationships:
                ingest_entities(graph_store, entities, relationships)
            entity_count += len(entities)
            rel_count += len(relationships)
        results[source] = {"records": len(raw_records), "entities": entity_count, "relationships": rel_count}
        print(f"[metadata] {source}: {results[source]}")
    enrich_graph(graph_store)
    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingest source metadata into Neo4j only (no vector store)")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    parser.add_argument("--source", type=str, choices=list(CONNECTORS), default=None, help="Ingest a single source")
    args = parser.parse_args(argv)
    config = Config.load(args.config)
    sources = [args.source] if args.source else list(CONNECTORS)
    results = ingest_metadata(config, sources)
    print(f"Metadata ingestion complete: {results}")


if __name__ == "__main__":
    main()
