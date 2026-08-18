from __future__ import annotations

import argparse
import os
from pathlib import Path

from core.config import Config
from core.connectors.base import BaseConnector
from core.connectors.docs_connector import DocsConnector
from core.connectors.git_connector import GitConnector
from core.connectors.incident_connector import IncidentConnector
from core.connectors.slack_connector import SlackConnector
from core.graph.operations import Neo4jGraphStore, enrich_graph, seed_ontology
from core.processing.chunker import Chunker
from core.processing.embedder import ChromaVectorStore, Embedder
from core.processing.entity_extractor import EntityExtractor
from core.storage.postgres import PostgresStore
from ingestion.pipeline import IngestionPipeline

CONNECTORS: dict[str, type[BaseConnector]] = {
    "git": GitConnector,
    "slack": SlackConnector,
    "incident": IncidentConnector,
    "docs": DocsConnector,
}


def load_ontology(config: Config) -> dict:
    from simulators.org_ontology import (
        COMPONENTS,
        DEPENDENCIES,
        INSTRUMENTS,
        PEOPLE,
        STRATEGIES,
        TEAMS,
    )

    return {
        "people": PEOPLE,
        "components": COMPONENTS,
        "teams": TEAMS,
        "instruments": INSTRUMENTS,
        "strategies": STRATEGIES,
        "dependencies": DEPENDENCIES,
    }


def build_stores(config: Config):
    vector_cfg = config.stores.get("vector", {}).get("chroma", {})
    vector_store = ChromaVectorStore(
        persist_dir=str(Path(config.paths.get("chroma", "data/chroma"))),
        collection=vector_cfg.get("collection", "orgbot_chunks"),
        host=vector_cfg.get("host"),
        port=vector_cfg.get("port"),
    )
    graph_cfg = config.stores.get("graph", {}).get("neo4j", {})
    graph_store = Neo4jGraphStore(
        uri=graph_cfg.get("uri", "bolt://localhost:7687"),
        user=graph_cfg.get("user", "neo4j"),
        password=graph_cfg.get("password", ""),
        database=graph_cfg.get("database", "neo4j"),
    )
    feedback_cfg = config.stores.get("feedback", {}).get("postgres", {})
    feedback_store = PostgresStore(feedback_cfg.get("dsn", ""))
    return vector_store, graph_store, feedback_store


def build_pipeline(
    config: Config,
    vector_store: ChromaVectorStore,
    graph_store: Neo4jGraphStore,
    ontology: dict,
) -> IngestionPipeline:
    chunker = Chunker(
        chunk_size=int(config.ingestion.get("chunk_size", 512)),
        overlap=int(config.ingestion.get("chunk_overlap", 50)),
    )
    embedder = Embedder(config.embedding)
    extractor = EntityExtractor(
        model=config.llm.get("model", "claude-sonnet-4-20250514"),
        api_key=None,
        ontology=ontology,
    )
    return IngestionPipeline(
        chunker=chunker,
        embedder=embedder,
        vector_store=vector_store,
        graph_store=graph_store,
        extractor=extractor,
        ontology=ontology,
    )


def collect_records(connector: BaseConnector, chunker, incremental: bool = False):
    if incremental:
        return connector.sync(chunker)
    records_with_chunks = []
    for raw in connector.fetch(None):
        record = connector.transform(raw)
        records_with_chunks.append((record, connector.chunk(record, chunker)))
    return records_with_chunks


def slack_connector_kwargs(config: Config) -> dict:
    if config.slack_source() != "live":
        return {}
    token = os.environ.get(config.slack_bot_token_env())
    if not token:
        return {}
    from services.slackbot.client import SlackClientAdapter

    return {
        "live": True,
        "channels": config.slack_channels(),
        "messages_fetch_limit": config.slack_messages_fetch_limit(),
        "client": SlackClientAdapter(token),
    }


def ingest_source(
    config: Config,
    source: str,
    pipeline: IngestionPipeline,
    cursor_store,
    ontology: dict,
    incremental: bool = False,
) -> dict:
    connector_cls = CONNECTORS[source]
    data_dir = Path(config.ingestion.get("data_dir", "data/simulated"))
    kwargs = slack_connector_kwargs(config) if source == "slack" else {}
    connector = connector_cls(cursor_store=cursor_store, data_dir=data_dir, **kwargs)
    records_with_chunks = collect_records(connector, pipeline.chunker, incremental=incremental)
    totals = pipeline.process_records(records_with_chunks)
    totals["source"] = source
    return totals


def ingest_all(config: Config, sources: list[str] | None = None, incremental: bool = False) -> dict:
    sources = sources or list(CONNECTORS)
    vector_store, graph_store, feedback_store = build_stores(config)
    feedback_store.init_schema()
    graph_store.ensure_constraints()
    ontology = load_ontology(config)
    seed_ontology(graph_store, ontology)
    pipeline = build_pipeline(config, vector_store, graph_store, ontology)
    results: dict[str, dict] = {}
    for source in sources:
        stats = ingest_source(
            config,
            source,
            pipeline,
            feedback_store,
            ontology,
            incremental=incremental,
        )
        results[source] = stats
        print(f"[ingest] {source}: {stats}")
    enrich_graph(graph_store)
    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingest simulated data into ChromaDB and Neo4j")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    parser.add_argument("--source", type=str, choices=list(CONNECTORS), default=None, help="Ingest a single source")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Sync only records newer than stored cursors instead of a full fetch",
    )
    args = parser.parse_args(argv)
    config = Config.load(args.config)
    sources = [args.source] if args.source else None
    results = ingest_all(config, sources, incremental=args.incremental)
    print(f"Ingestion complete: {results}")


if __name__ == "__main__":
    main()
