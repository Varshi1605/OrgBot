## 1. Project Scaffolding & Docker Setup

- [x] 1.1 Create monorepo directory structure: `services/`, `core/`, `simulators/`, `tests/`, `config/`, `data/simulated/`
- [x] 1.2 Create `pyproject.toml` with dependencies: `llama-index`, `anthropic`, `neo4j`, `chromadb`, `fastapi`, `uvicorn`, `faker`, `pydantic`, `pydantic-settings`, `psycopg2-binary` (or `asyncpg`)
- [x] 1.3 Implement config loader: `config/config.yaml` (store URIs, model names, confidence weights, thresholds) with env-var overrides; never commit secrets
- [x] 1.4 Create `docker-compose.yml`: Neo4j 7.x with APOC, ChromaDB, PostgreSQL 16, FastAPI app
- [x] 1.5 Create Dockerfile for the FastAPI service
- [x] 1.6 Verify `docker compose up` brings all four services to healthy

## 2. Shared Org Ontology

- [x] 2.1 Implement `simulators/org_ontology.py`: 20 people (4 per team), 5 teams, 5 components, 8 instruments, 5 strategies, per plan.md tables
- [x] 2.2 Add canonical identity normalization (GitHub handle = Slack handle = incident responder name after normalization) used by simulators and entity resolution
- [x] 2.3 Add ontology validation helper: reject references to undefined entities

## 3. Data Simulation

- [x] 3.1 Implement `simulators/git_simulator.py`: 5 independent repos (~150-200 commits each) with main/develop branches, feature branches, `v1.x.x` tags, and `CHANGELOG.md`
- [x] 3.2 Implement `simulators/slack_simulator.py`: ~2000 messages across 7 channels with threads, reactions, mentions, and cross-component discussions
- [x] 3.3 Implement `simulators/incident_simulator.py`: ~60-80 incidents with P1-P4 distribution, affected components, engineers, instruments, timeline, RCA, action items, and linked commits that exist in the git dataset
- [x] 3.4 Implement `simulators/doc_simulator.py`: README, ARCHITECTURE, RUNBOOK, CHANGELOG markdown per component
- [x] 3.5 Implement `simulators/generate_all.py`: seeded entry point writing to `data/simulated/{git,slack,incidents,docs}/` plus a `manifest.json` cross-referencing entity IDs
- [x] 3.6 Add determinism test: same seed produces identical output

## 4. Knowledge Graph

- [x] 4.1 Implement `core/graph/schema.py`: node labels and properties (Person, Component, Repository, Team, Incident, Commit, Conversation, Instrument, Strategy, Document) and relationship definitions (AUTHORED, OWNS, WORKS_ON, CAUSED_BY, FIXED_BY, AFFECTS, RESPONDED_TO, MENTIONED_IN, DISCUSSED_IN, DEPENDS_ON, CONSUMES_FEED, ROUTES_ORDERS, DOCUMENTS, PARTICIPATED_IN)
- [x] 4.2 Implement `core/graph/operations.py`: node/edge creation, entity resolution via normalized identity MERGE, component dependency edges from the data-flow topology
- [x] 4.3 Implement graph enrichment job: EXPERT_IN (recency-weighted commits + incident responses), FREQUENTLY_CO_AUTHORED, HISTORICALLY_INCIDENT_PRONE; idempotent and runnable post-ingestion
- [x] 4.4 Implement `core/graph/cypher_templates.py`: templates for expert lookup, incidents per component + responders, commits linked to P1, Slack discussions by component/topic

## 5. Ingestion Pipeline

- [x] 5.1 Implement `core/connectors/base.py`: `fetch()`, `transform()`, `chunk()`, `get_cursor()`, `set_cursor()` interface
- [x] 5.2 Implement Git connector: parse commits (author, files changed, message, timestamp, repo), chunk by commit
- [x] 5.3 Implement Slack connector: parse messages (author, channel, thread, timestamp, mentions), chunk by thread/conversation
- [x] 5.4 Implement Incident connector: parse reports (severity, services, responders, RCA), chunk by section
- [x] 5.5 Implement Docs connector: parse markdown (path, component, doc_type), chunk by heading/section
- [x] 5.6 Implement `core/processing/chunker.py`: LlamaIndex SentenceSplitter wrapper (~512 tokens, 50 overlap)
- [x] 5.7 Implement `core/processing/entity_extractor.py`: Claude structured-output extraction of entities + relationships, with an offline stub for runs without an API key
- [x] 5.8 Implement `core/processing/embedder.py`: embedding interface + ChromaDB storage with chunk metadata
- [x] 5.9 Implement ingestion orchestration (`ingest_all`): per-connector cursor persistence to PostgreSQL, pipeline execution, idempotent re-runs
- [x] 5.10 Add ingestion verification: ChromaDB collection counts and Neo4j node/relationship counts after full ingest

## 6. RAG Pipeline & Confidence Scoring

- [x] 6.1 Implement `core/rag/pipeline.py` vector retriever: top-k similarity over ChromaDB
- [x] 6.2 Implement graph retriever: template-first with LLM-generated Cypher attempted for ad-hoc queries and fallback to templates + vector retrieval on failure/empty results
- [x] 6.3 Implement fusion/re-ranking: combine, deduplicate, and rank vector + graph evidence
- [x] 6.4 Implement `core/rag/prompts.py`: system prompts for answer generation and Cypher generation
- [x] 6.5 Implement answer generation via Claude with source citations
- [x] 6.6 Implement `core/confidence/scorer.py`: composite score (source diversity 0.25, recency 0.20, embedding similarity 0.25, graph connectivity 0.15, SME validation 0.15), SME signal neutral when absent, weights from config
- [x] 6.7 Implement response builder: answer + confidence score + source citations + graph path

## 7. FastAPI Query Engine

- [x] 7.1 Define Pydantic request/response models for all endpoints
- [x] 7.2 Implement `POST /query`: question → answer, confidence, sources, graph path
- [x] 7.3 Implement `POST /feedback`: validate and store SME feedback (correction/approval/annotation) in PostgreSQL
- [x] 7.4 Implement `GET /graph/explore?entity=X`: entity neighborhood with not-found handling
- [x] 7.5 Implement `POST /ingest`: trigger ingestion for a given source type
- [x] 7.6 Implement `GET /health`: service + dependency (vector/graph/feedback store) status
- [x] 7.7 Wire `services/api/main.py` with routers, config, and error handling; start via uvicorn in Docker

## 8. Verification & Sample Queries

- [x] 8.1 `docker compose up` — all 4 services healthy
- [x] 8.2 `python -m simulators.generate_all` — produces `data/simulated/{git,slack,incidents,docs}/`
- [x] 8.3 Run ingestion — data appears in ChromaDB (collection count) and Neo4j (`MATCH (n) RETURN labels(n), count(n)`)
- [x] 8.4 Graph sanity checks: all node types present; `EXPERT_IN` edges exist; incident distribution across components is non-empty
- [x] 8.5 Run the 5 sample queries (FIX session contact, P1 feed listener cause, ORMS risk limits, most incident-prone instruments, recent trade listener changes) — verify answer, confidence, citations, graph path
- [x] 8.6 Smoke-test `POST /feedback` and re-query path (confidences remain valid with no feedback present)
- [x] 8.7 Add unit tests for ontology validation, determinism, chunking, confidence scoring, and entity resolution; integration test for query → answer flow
