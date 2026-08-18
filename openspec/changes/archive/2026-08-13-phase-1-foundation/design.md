## Context

See proposal.md - Why. This is a greenfield project: no existing code, no existing specs. The repo currently contains only planning documents (`plan.md`, `SDD.md`, `developement.md`). Phase 1 builds, end to end, the ability to ask questions about a mock trading platform and get confident, cited answers. All source data is simulated locally; Phase 2 (Slack live integration, feedback loop, incremental scheduling) is out of scope but the design must leave seams for it.

Stack is fixed by plan.md: Python (FastAPI + LlamaIndex), Anthropic Claude, Neo4j, ChromaDB, Docker Compose.

## Goals / Non-Goals

**Goals:**
- A monorepo that runs entirely on `docker compose up` (Neo4j, ChromaDB, PostgreSQL, FastAPI) plus local Python for simulation and ingestion.
- Deterministic, cross-referenced synthetic data for 5 components across Git, Slack, incidents, and docs.
- A single ingestion pipeline (connectors → chunk → extract → embed → persist) shared by all sources.
- A Neo4j graph with schema, entity resolution, and derived edges, queryable via pre-built Cypher templates.
- A hybrid RAG pipeline (vector + graph) producing answers with confidence scores, citations, and graph paths.
- A FastAPI service covering query, feedback, graph exploration, ingestion trigger, and health.
- Everything testable: simulators run without external services; ingestion and query verification steps are defined.

**Non-Goals:**
- Live Slack ingestion or Slack bot interaction (Phase 2/3).
- SME feedback loop persistence beyond the schema + endpoint (Phase 2).
- Incremental sync scheduling (APScheduler) — cursor mechanism is built, scheduling is not.
- Fine-tuning, RBAC, multi-tenancy, production deployment.

## Decisions

### D1: Monorepo package layout (src-style, namespaced)
Structure per plan.md:
```
orgbot/
  docker-compose.yml
  pyproject.toml
  config/            # YAML/TOML config loaded by services
  simulators/        # org_ontology, git/slack/incident/doc simulators, generate_all
  core/
    connectors/      # base + git/slack/incident/docs
    processing/      # chunker, entity_extractor, embedder
    graph/           # schema, operations, cypher templates
    rag/             # pipeline, prompts, retrievers
    confidence/      # scorer
    feedback/        # handler (schema only in Phase 1)
  services/api/      # FastAPI app
  tests/
  data/simulated/    # generated datasets (git-repo-like + JSON)
```
Rationale: mirrors the plan, keeps `core/` framework-agnostic and unit-testable without services running.
Alternatives considered: single flat package — rejected for clarity; microservice split per module — overkill for a POC.

### D2: Simulation writes both filesystem artifacts and structured JSON
Git simulator produces real git repos (via `git` CLI or `dulwich`) under `data/simulated/git/<repo>/`; Slack/incident outputs are JSON with a normalized record shape; docs are markdown files. A `manifest.json` indexes cross-source entity IDs.
Rationale: connectors then operate on realistic inputs (real commit objects, real markdown, JSON payloads) rather than synthetic in-memory objects, which keeps Phase 1 ingestion honest and Phase 2 (real Slack) a connector swap.
Alternative: pure in-memory simulation — rejected because it wouldn't exercise the connectors realistically.

### D3: Determinism via seeded Faker + fixed randomness
All simulators accept `--seed` (default fixed) and route all randomness (Faker + `random`) through a seedable RNG. Cross-referencing is done by first sampling entities from `org_ontology`, then generating content that references only those sampled entities.
Rationale: reproducible dataset enables stable graph checks and deterministic tests. Alternative: non-deterministic generation — rejected.

### D4: One connector interface, four connectors, one pipeline
`BaseConnector` defines `fetch()`, `transform()`, `chunk()`, `get_cursor()`, `set_cursor()`. Git/Slack/Incident/Docs implement it. The processing pipeline (chunker → entity extractor → embedder → writers) is connector-agnostic.
Rationale: satisfies spec "pluggable connector interface" and keeps future connectors cheap. Alternatives considered: separate pipeline per source — rejected (duplication).

### D5: Chunking with LlamaIndex SentenceSplitter (512 / 50)
Chunk by logical unit: commits (Git), thread/conversation (Slack), section (Incidents), heading/section (Docs), then split to ~512 tokens with 50 overlap.
Rationale: plan.md specifies this; LlamaIndex is already a dependency. Alternative: rolling window splitting — rejected for poorer semantic boundaries.

### D6: Entity extraction via Claude structured output (not spaCy)
Entity + relationship extraction from each chunk uses Claude with structured tool output constrained to the ontology types (Person, Component, Repository, Team, Incident, Instrument, Strategy + relationships).
Rationale: plan.md's decision table; domain-specific entities (component names, strategies) extract far better with an LLM than NER. Alternative: spaCy — rejected for domain terms.

### D7: Graph querying = templates first, LLM Cypher with fallback
Pre-built Cypher templates cover the known common questions (expert lookup, incidents per component, commits after P1, Slack discussions). For ad-hoc queries, a Claude-generated Cypher is attempted; on failure or empty results, the system falls back to templates + vector retrieval.
Rationale: reliability (templates are correct) with flexibility (LLM for novel phrasing). Alternative: LLM-only Cypher — rejected as unreliable for a POC.

### D8: Confidence scoring as a pure, weighted composite
Score = 0.25·source_diversity + 0.20·recency + 0.25·embedding_similarity + 0.15·graph_connectivity + 0.15·sme_validation. Each sub-signal normalized to [0,1]; sme_validation defaults to neutral 0.5 when no feedback exists. Implemented as a stateless `ConfidenceScorer` with a `ConfidenceResult` dataclass.
Rationale: plan.md weights; making it pure (no I/O) keeps it unit-testable. Alternative: LLM-judged confidence — rejected as non-comparable.

### D9: Embedding model deferred (voyage-3 vs text-embedding-3-small)
Embeddings go through a thin `Embedder` interface so the model choice is a config value. Default to `text-embedding-3-small` unless a `VOYAGE_API_KEY` is present, then `voyage-3`.
Rationale: both are valid; the interface removes the decision cost. See Open Questions.

### D10: Entity resolution by normalized identity
Normalize GitHub handle, Slack handle, and incident-responder name to a canonical key (lowercased, punctuation-stripped) and MERGE on that key in Neo4j (`MERGE (p:Person {key: $key})`), merging property sets from each source.
Rationale: satisfies the "duplicate entities merge" requirement with Neo4j-native MERGE semantics. Alternative: external dedup pass — rejected as overkill for ~20 people.

### D11: Derived edges as a post-ingestion job
`enrich_graph()` computes EXPERT_IN (weighted commit count + incident responses with recency decay), FREQUENTLY_CO_AUTHORED (co-authorship co-occurrence), HISTORICALLY_INCIDENT_PRONE (component×instrument incident frequency). Run idempotently after each ingestion batch.
Rationale: keeps ingestion simple and makes enrichment recomputable. Alternative: real-time edge maintenance — rejected as premature.

### D12: FastAPI with router-per-capability, Pydantic everywhere
`services/api/main.py` mounts routers: `query`, `feedback`, `graph`, `ingest`, `health`. All request/response models are Pydantic; validation errors map to 422.
Rationale: clean separation matching spec capabilities. Alternative: single flat module — rejected.

### D13: PostgreSQL for cursors and feedback in Phase 1
PostgreSQL stores connector cursors (future Phase 2 incremental sync) and feedback records (schema ready, populated from Phase 2 UI). Phase 1 populates cursors during ingestion; feedback table exists but is only written via `/feedback`.
Rationale: keeps Phase 2 a wiring exercise rather than a data-model change. Alternative: SQLite — rejected; plan.md specifies PostgreSQL.

### D14: Config via YAML + env overrides
`config/config.yaml` holds store URIs, model names, thresholds, weights; env vars override (e.g., API keys). No secrets committed.
Rationale: one obvious place to tune pipeline behavior (confidence weights, chunk sizes) without code changes.

## Risks / Trade-offs

- [Simulated data may not reflect real trading-system nuance] → Generators use per-component domain templates (from plan.md) and cross-source consistency checks in tests; Phase 2 replaces simulators with live connectors.
- [Entity extraction via Claude requires API key/network at dev time] → Ingestion is runnable in a degraded mode? No — instead, provide an optional `--extract-locally` stub returning ontology-known entities for offline runs; full extraction requires the key. Mitigation: document that CI/offline runs use the stub or seed-based known entities.
- [LLM-generated Cypher may be wrong] → Templates first with LLM as an add-on and fallback to vector retrieval; empty/erroring Cypher never blocks an answer.
- [Deterministic simulators are complex to get right (cross-ref IDs)] → Central `org_ontology` + `manifest.json`; unit test asserts no dangling references.
- [Neo4j/Chroma schema drift between pipeline and query] → Single `graph/schema.py` and `vector` collection-name constants shared by ingestion and query code.
- [Confidence weights are uncalibrated in Phase 1] → Acceptable: calibration is a Phase 2 concern (golden Q&A pairs); weights are config-driven for easy tuning.
- [ChromaDB collections keep growing on re-ingestion] → Re-ingest is idempotent by document/chunk ID; cursor mechanism limits duplicates in Phase 2.

## Migration Plan

Greenfield: no migration of existing code or data. Rollout steps:
1. `docker compose up` (Neo4j, ChromaDB, PostgreSQL) — wait for health.
2. `python -m simulators.generate_all` → populate `data/simulated/`.
3. `python -m ingestion.ingest_all` (or `POST /ingest`) → populate ChromaDB + Neo4j + cursors.
4. Start FastAPI service; run verification queries.
Rollback: tear down docker volumes and delete `data/simulated/`; nothing irreversible.

## Open Questions

- Exact embedding model (voyage-3 vs text-embedding-3-small): deferred to implementation via the `Embedder` interface; does not change specs, approach, or task breakdown.
- Whether to drive Git simulation with the `git` CLI (real repos) or `dulwich` (pure-Python): implementation detail; both produce real git repos for ingestion.
- Anthropic model name for extraction/generation (e.g., claude-sonnet vs claude-haiku): config value; not spec-relevant.
