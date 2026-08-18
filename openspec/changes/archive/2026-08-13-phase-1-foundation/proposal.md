## Why

OrgBot is a RAG-based organizational knowledge agent for a mock NSE-connected trading platform. Today, knowledge about the platform's five components (commits, Slack discussions, incidents, docs) is fragmented across separate repos and channels, so engineers cannot answer operational questions like "who owns the FIX session?" or "what caused last week's P1?" without manual hunting. Phase 1 builds the foundation: a fully simulated knowledge base, ingestion pipeline, knowledge graph, RAG query engine with confidence scoring, and a FastAPI API — enabling questions about the trading platform to be answered with confidence scores and cited sources.

## What Changes

- Scaffold the OrgBot monorepo: `services/`, `core/`, `simulators/`, `tests/`, `config/`, plus `docker-compose.yml` (Neo4j, ChromaDB, PostgreSQL, FastAPI) and `pyproject.toml`.
- Add data simulation producing cross-referenced synthetic data for the 5 trading components: Git commits (~800), Slack messages (~2000), incidents (~60-80), and per-component docs (README, ARCHITECTURE, RUNBOOK, CHANGELOG).
- Add an ingestion pipeline with pluggable connectors (Git, Slack, Incident, Docs) that chunk, extract entities, embed, and persist to ChromaDB and Neo4j.
- Build a Neo4j knowledge graph: node labels (Person, Component, Repository, Team, Incident, Commit, Conversation, Instrument, Strategy, Document), relationships, derived/expertise edges, and a set of Cypher query templates.
- Add a RAG pipeline: hybrid retrieval (vector + graph), fusion/re-ranking, answer generation via Claude, and a composite confidence score (source diversity, recency, embedding similarity, graph connectivity, SME validation signal).
- Add a FastAPI query engine with endpoints `/query`, `/feedback`, `/graph/explore`, `/ingest`, `/health`, all using Pydantic models.
- Deliver verification: healthy docker services, populated stores, graph sanity checks, and five representative sample queries demonstrating confidence scores and citations.

## Capabilities

### New Capabilities

- `data-simulation`: Generators for a shared org ontology and synthetic Git/Slack/Incident/Doc data, cross-referenced by entity IDs so the same person, component, instrument, and incident appear consistently across all sources.
- `data-ingestion`: Pluggable connectors (Git, Slack, Incident, Docs) with cursor-based sync, plus a processing pipeline (chunk → extract entities → embed → persist to vector and graph stores).
- `knowledge-graph`: Neo4j node/relationship schema, entity resolution across sources, derived/enrichment edges (EXPERT_IN, FREQUENTLY_CO_AUTHORED, HISTORICALLY_INCIDENT_PRONE), and pre-built Cypher query templates.
- `rag-query`: Hybrid retrieval (vector + graph) with fusion/re-ranking, Claude-based answer generation, and composite confidence scoring with per-signal weights.
- `query-api`: FastAPI service exposing query, feedback, graph exploration, and ingestion-trigger endpoints with Pydantic request/response models.

### Modified Capabilities

- None (greenfield project; no existing specs).

## Impact

- **New code**: `services/api`, `core/connectors`, `core/processing`, `core/graph`, `core/rag`, `core/confidence`, `simulators/` — new Python package structure.
- **Infrastructure**: Docker Compose services (Neo4j 7.x + APOC, ChromaDB, PostgreSQL 16, FastAPI); dependencies added to `pyproject.toml` (`llama-index`, `anthropic`, `neo4j`, `chromadb`, `fastapi`, `uvicorn`, `faker`, etc.).
- **External dependencies**: Anthropic Claude API for entity extraction and answer generation; embedding model (`voyage-3` or `text-embedding-3-small`, chosen at implementation).
- **No breaking changes**: greenfield project; nothing existing is modified or removed.
