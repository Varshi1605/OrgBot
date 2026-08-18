



# Plan: Organizational Knowledge Bot (OrgBot)


## TL;DR


Build a RAG-based organizational knowledge agent trained on the internal data of a **mock trading platform** (NSE-connected). It ingests git commit history, Slack conversations, and incident reports from five independently owned and version-tracked trading platform components, builds a knowledge graph of entity relationships, provides answers with confidence scores, learns from SME feedback, and incrementally updates its knowledge. Phase 1 uses fully simulated data; Phase 2 connects to live Slack for Q&A.


**Stack**: Python (FastAPI + LlamaIndex), Anthropic Claude, Neo4j, ChromaDB, Docker Compose


---


## Trading Platform: Component Overview


The simulated trading platform consists of five components, each with its own repository, documentation, versioning, and owning team. All communication patterns mirror real NSE-connected systems.


| # | Component | Protocol | Role | Owning Team | Repo |
|---|-----------|----------|------|-------------|------|
| 1 | **Public Feed Listener** | UDP multicast (NSE) | Receives raw market data (quotes, depth, trades) from NSE broadcast; normalizes and distributes internally | Market Data Team | `public-feed-listener` |
| 2 | **Exchange Adapter** | TCP / FIX 4.2 (NSE) | Manages FIX sessions with NSE; routes orders and receives order acknpwowledgements, fills, and rejections | Connectivity Team | `exchange-adapter` |
| 3 | **ORMS** | Internal TCP/IPC | Order and Risk Management System; enforces pre-trade risk limits, manages order lifecycle (new → acked → filled / rejected / cancelled) | Risk & Order Team | `orms` |
| 4 | **Trade Listener** | Internal TCP/IPC | Receives confirmed trade fills from ORMS; enriches and distributes to downstream consumers (PnL engine, position manager, reporting) | Trade Processing Team | `trade-listener` |
| 5 | **Strategy Interface** | Internal TCP/IPC | API gateway between trading strategies and ORMS; translates strategy signals into orders, manages strategy state and configuration | Strategy Team | `strategy-interface` |


**Data flow between components:**


```
NSE Exchange
  │  UDP multicast (market data)
  ▼
Public Feed Listener ──→ Strategy Interface ──→ ORMS ──→ Exchange Adapter ──→ NSE Exchange
                                                 │                              │ (TCP/FIX)
                                                 ▼                              ▼
                                          Trade Listener              Order Ack / Fill / Reject
                                                 │
                                                 ▼
                                    Downstream (PnL, Position, Reporting)
```


Each component is:
- Tracked in its own **dedicated Git repository** with independent versioning and changelogs
- Documented in its own **README + architecture docs** (simulated as markdown files)
- Owned by a **dedicated team** with named on-call engineers
- The source of **component-specific incidents** (feed drops, FIX disconnects, risk breaches, trade gaps, signal failures)


---


## Architecture


```
┌─────────────────────────────────────────────────────────────────┐
│                        SLACK BOT INTERFACE                      │
│              (Slack Bolt SDK — Q&A + Feedback UI)               │
└────────────────────────────┬────────────────────────────────────┘
                            │
┌────────────────────────────▼────────────────────────────────────┐
│                     QUERY ENGINE (FastAPI)                       │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │ RAG      │  │ Graph Query  │  │ Confidence Scorer         │  │
│  │ Pipeline │  │ Engine       │  │ (source count, recency,   │  │
│  │ (Claude) │  │ (Neo4j +     │  │  graph connectivity,      │  │
│  │          │  │  Cypher)     │  │  embedding similarity)    │  │
│  └──────────┘  └──────────────┘  └───────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                            │
┌────────────────────────────▼────────────────────────────────────┐
│                      KNOWLEDGE STORES                           │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Vector Store  │  │ Graph Store   │  │ Feedback Store       │  │
│  │ (ChromaDB)   │  │ (Neo4j)       │  │ (PostgreSQL)         │  │
│  │ Embeddings   │  │ Entities &    │  │ SME corrections,     │  │
│  │ + metadata   │  │ relationships │  │ upvotes, annotations │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
└────────────────────────────▲────────────────────────────────────┘
                            │
┌────────────────────────────┴────────────────────────────────────┐
│                   DATA INGESTION PIPELINE                        │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐  │
│  │ Git        │  │ Slack      │  │ Incident   │  │ Future    │  │
│  │ Connector  │  │ Connector  │  │ Connector  │  │ Connectors│  │
│  │ (commits,  │  │ (messages, │  │ (PagerDuty/│  │ (Jira,    │  │
│  │  diffs,    │  │  threads,  │  │  custom    │  │  Confluence│  │
│  │  authors)  │  │  channels) │  │  reports)  │  │  etc.)    │  │
│  └────────────┘  └────────────┘  └────────────┘  └───────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Processing: Chunking → Entity Extraction → Embedding     │   │
│  │             → Graph Construction → Metadata Tagging      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```


---


## Phase 1: Foundation & Simulated Data (Steps 1–6)


### Step 1: Project Scaffolding & Docker Setup


Create monorepo structure:


```
orgbot/
├── docker-compose.yml          # Neo4j, ChromaDB, PostgreSQL, FastAPI
├── services/
│   ├── api/                    # FastAPI query engine
│   ├── ingestion/              # Data ingestion workers
│   └── slackbot/               # Slack Bolt app
├── core/
│   ├── connectors/             # Git, Slack, Incident connectors
│   ├── processing/             # Chunking, embedding, entity extraction
│   ├── graph/                  # Neo4j graph operations
│   ├── rag/                    # RAG pipeline with LlamaIndex
│   ├── confidence/             # Confidence scoring module
│   └── feedback/               # SME feedback loop
├── simulators/                 # Data generators for Git, Slack, Incidents
├── tests/
└── config/
```


- Docker Compose services: Neo4j 7.x (with APOC plugin), ChromaDB, PostgreSQL 16, FastAPI app
- `pyproject.toml` with deps: `llama-index`, `anthropic`, `neo4j`, `chromadb`, `slack-bolt`, `faker`, `fastapi`, `uvicorn`


---


### Step 2: Data Simulation Engine *(parallel with Step 1)*


#### 2a. Shared Org Ontology (`simulators/org_ontology.py`)


A single source of truth for all entity names used across every simulator. Ensures the same person, service, and instrument appear consistently in Git, Slack, and incidents.


**People (20 engineers, 4 per team):**


| Team | Engineers |
|------|-----------|
| Market Data | Arjun Sharma, Priya Nair, Ravi Iyer, Sneha Pillai |
| Connectivity | Vikram Das, Ananya Menon, Karan Mehta, Divya Rao |
| Risk & Order | Rohit Gupta, Meera Joshi, Aakash Singh, Pooja Verma |
| Trade Processing | Nikhil Bhat, Sunita Reddy, Amit Kulkarni, Lavanya Kumar |
| Strategy | Siddharth Patil, Deepa Nambiar, Varun Shetty, Ishaan Chopra |


**Instruments**: NIFTY50, BANKNIFTY, RELIANCE, INFY, TCS, HDFC, ICICIBANK, SBIN (8 instruments)


**Strategies**: `momentum_v1`, `mean_reversion_v2`, `arb_etf_v1`, `vwap_execution`, `pairs_nifty_banknifty`


---


#### 2b. Git Simulator (`simulators/git_simulator.py`)


Generates **5 independent git repos** (~150–200 commits each, ~800 total) with realistic trading-system commit patterns, branches, and version tags.


| Repo | Representative Commit Messages |
|------|--------------------------------|
| `public-feed-listener` | `Fix UDP sequence gap detection in market depth handler`, `Add instrument subscription filtering for NIFTY derivatives`, `Handle NSE broadcast restart gracefully`, `Improve packet loss recovery in feed buffer`, `Add latency histogram for feed processing` |
| `exchange-adapter` | `Handle FIX session recovery after TCP disconnect`, `Fix order cancel-replace race condition`, `Add support for IOC order type`, `Parse ExecutionReport for partial fill correctly`, `Implement heartbeat timeout detection` |
| `orms` | `Add pre-trade risk check for gross exposure limit`, `Fix order state machine transition for pending cancel`, `Implement position limit breach rejection`, `Add order throttle per instrument per second`, `Fix duplicate order ID generation under load` |
| `trade-listener` | `Fix trade deduplication when fill arrives out of order`, `Add trade enrichment with strategy metadata`, `Handle partial fill aggregation correctly`, `Add downstream consumer reconnect logic`, `Fix PnL calculation for multi-leg trades` |
| `strategy-interface` | `Add momentum strategy signal rate limiting`, `Fix position sizing calculation on config reload`, `Implement strategy state snapshot for recovery`, `Add hot reload for risk parameter changes`, `Fix signal drop during strategy restart` |


Each repo has: `main`, `develop`, feature branches per engineer, version tags (`v1.x.x`), and a `CHANGELOG.md`.


#### 2c. Slack Simulator (`simulators/slack_simulator.py`)


Generates **~2000 messages** across **7 channels** with threads, reactions, and cross-component discussions.


| Channel | Purpose | Typical Discussions |
|---------|---------|---------------------|
| `#market-data` | Feed quality and NSE data ops | Sequence gaps, instrument subscription issues, feed latency |
| `#exchange-ops` | FIX session and connectivity | Session drops, order rejections, exchange maintenance windows |
| `#risk-alerts` | Risk limit and order safety | Limit breach alerts, stuck orders, throttle hits |
| `#trade-ops` | Trade reconciliation | Missing trades downstream, fill mismatches, PnL discrepancies |
| `#strategy-dev` | Strategy performance and signals | Signal quality, parameter tuning, strategy P&L |
| `#incidents` | Cross-component incident response | War-room threads, RCA discussions, action items |
| `#deployments` | Release and deployment notifications | Deployment announcements, rollback alerts, config changes |


---


#### 2d. Incident Simulator (`simulators/incident_simulator.py`)


Generates **~60–80 incidents** with trading-domain-specific root causes, severity levels, timelines, and RCAs.


| Severity | Count | Example Incidents |
|----------|-------|-------------------|
| P1 (Critical) | ~10 | NSE feed completely dropped, FIX session not recovered within SLA, risk system rejecting all orders due to stale position data |
| P2 (High) | ~20 | UDP packet loss >5% causing stale quotes, order acknowledgement latency >500ms, trade listener not receiving fills |
| P3 (Medium) | ~30 | Sequence gap in market depth for BANKNIFTY, strategy interface config reload failed, trade deduplication logic miss |
| P4 (Low) | ~20 | Minor feed latency spikes, non-critical log errors, config drift detected |


Each incident includes: `affected_components[]`, `involved_engineers[]`, `instruments[]`, `timeline` (detected → acknowledged → mitigated → resolved), `RCA`, `action_items[]`, `linked_commits[]` (commits that fixed or caused the incident).


---


#### 2e. Documentation Simulator (`simulators/doc_simulator.py`)


Generates per-component **README.md** and **architecture docs** as markdown files (treated as a separate ingestion source).


Each component gets:
- `README.md` — overview, protocol details, config parameters, startup guide
- `ARCHITECTURE.md` — data flow, threading model, failure modes, tuning guide
- `RUNBOOK.md` — on-call procedures, common incident responses, escalation path
- `CHANGELOG.md` — version history aligned with git tags


All generators use Faker + custom trading-domain templates. Output is structured JSON (for Git/Slack/Incidents) and markdown files (for docs), with cross-referenced entity IDs so the same person, service, instrument, and incident appear consistently across all sources.


---


### Step 3: Data Ingestion Pipeline *(depends on Step 1)*


Abstract connector interface: `fetch()`, `transform()`, `chunk()`, `get_cursor()`, `set_cursor()`


- **GitConnector**: Parse commits → extract (author, files_changed, message, timestamp, repo). Chunk by commit or PR.
- **SlackConnector**: Parse messages → extract (author, channel, thread_id, timestamp, mentions). Chunk by thread/conversation.
- **IncidentConnector**: Parse incident reports → extract (severity, services, responders, RCA). Chunk by section.


Processing pipeline per chunk:


1. **Chunk** via LlamaIndex `SentenceSplitter` (~512 tokens, 50-token overlap)
2. **Extract entities** via Claude structured output (Person, Service, Repository, Team, Incident + relationships)
3. **Embed** via `voyage-3` or `text-embedding-3-small`
4. **Store** embeddings + metadata → ChromaDB; entities + relationships → Neo4j


---


### Step 4: Knowledge Graph Construction *(depends on Step 3)*


**Neo4j schema — nodes:**


| Node Label | Key Properties | Source |
|------------|---------------|--------|
| `Person` | name, team, role, slack_handle, github_handle | Git, Slack, Incidents |
| `Component` | name, repo, protocol, version, owner_team | Org ontology, Git tags |
| `Repository` | name, component, current_version, language | Git |
| `Team` | name, on_call_rotation, slack_channel | Org ontology |
| `Incident` | id, severity, title, status, rca, resolution_time | Incidents |
| `Commit` | hash, message, timestamp, branch, version_tag | Git |
| `Conversation` | channel, thread_id, topic, timestamp | Slack |
| `Instrument` | symbol, exchange, type | Org ontology |
| `Strategy` | name, type, owner | Org ontology |
| `Document` | path, component, doc_type (README/RUNBOOK/ARCH) | Docs |


**Neo4j schema — relationships:**


| Relationship | From → To | Meaning |
|-------------|-----------|--------|
| `AUTHORED` | Person → Commit | Engineer made this commit |
| `OWNS` | Team → Component | Team is responsible for this component |
| `WORKS_ON` | Person → Component | Engineer has committed to this component |
| `CAUSED_BY` | Incident → Commit | This commit introduced the incident |
| `FIXED_BY` | Incident → Commit | This commit resolved the incident |
| `AFFECTS` | Incident → Component | Incident impacted this component |
| `RESPONDED_TO` | Person → Incident | Engineer was on the incident |
| `MENTIONED_IN` | Component → Conversation | Component was discussed in this thread |
| `DISCUSSED_IN` | Incident → Conversation | Incident war-room thread |
| `DEPENDS_ON` | Component → Component | Runtime data dependency (e.g., ORMS depends on Exchange Adapter) |
| `CONSUMES_FEED` | Component → Component | Strategy Interface consumes Public Feed Listener output |
| `ROUTES_ORDERS` | Component → Component | ORMS routes orders via Exchange Adapter |
| `DOCUMENTS` | Document → Component | Doc describes this component |
| `PARTICIPATED_IN` | Person → Conversation | Person wrote in this thread |


**Derived / enriched edges** (computed post-ingestion):
- `EXPERT_IN` (Person → Component): based on commit count + incident response count, weighted by recency
- `FREQUENTLY_CO_AUTHORED` (Person → Person): engineers who co-author commits on the same component
- `HISTORICALLY_INCIDENT_PRONE` (Component → Instrument): incidents frequently involve this instrument on this component


**Example Cypher queries (pre-built templates):**
```cypher
// Who is the expert on the Exchange Adapter?
MATCH (p:Person)-[:EXPERT_IN]->(c:Component {name: "exchange-adapter"})
RETURN p.name, p.team ORDER BY p.expert_score DESC LIMIT 3


// What incidents affected the ORMS and who responded?
MATCH (i:Incident)-[:AFFECTS]->(c:Component {name: "orms"})
MATCH (p:Person)-[:RESPONDED_TO]->(i)
RETURN i.title, i.severity, collect(p.name) ORDER BY i.timestamp DESC


// What commits were made after a P1 incident on the feed listener?
MATCH (i:Incident {severity: "P1"})-[:AFFECTS]->(c:Component {name: "public-feed-listener"})
MATCH (commit:Commit)-[:FIXED_BY]-(i)
RETURN i.title, commit.message, commit.timestamp


// What has been discussed about FIX session recovery in Slack?
MATCH (conv:Conversation)-[:MENTIONED_IN]-(c:Component {name: "exchange-adapter"})
WHERE conv.topic CONTAINS "FIX" OR conv.topic CONTAINS "session"
RETURN conv.channel, conv.thread_id, conv.timestamp
```


- Entity resolution: merge duplicate entities across sources using normalized identifiers (GitHub handle = Slack handle = incident responder name after normalization)
- Graph enrichment runs as a post-ingestion job, re-computing derived edges when new data arrives


---


### Step 5: RAG Pipeline with Confidence Scoring *(depends on Steps 3 & 4)*


**Hybrid retrieval:**


1. **Vector retrieval**: Semantic search against ChromaDB → top-k chunks
2. **Graph retrieval**: Translate question to Cypher query → structured entity/relationship results
3. **Fusion**: Combine, deduplicate, re-rank results from both retrievers


**Confidence scoring** (composite score 0.0–1.0):


| Signal | Weight | How |
|--------|--------|-----|
| Source diversity | 0.25 | How many distinct source types confirm the answer |
| Recency | 0.20 | Exponential decay on document timestamps |
| Embedding similarity | 0.25 | Average cosine similarity of retrieved chunks to query |
| Graph connectivity | 0.15 | PageRank / degree centrality of answer entities |
| SME validation | 0.15 | Prior SME approvals for similar queries (from feedback store) |


Response format: answer text + confidence score + source citations + graph path showing entity connections.




### Step 6: FastAPI Query Engine *(depends on Step 5)*


**Endpoints:**


| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/query` | Ask a question → answer + confidence + sources + graph path |
| `POST` | `/feedback` | SME submits correction or approval |
| `GET` | `/graph/explore?entity=X` | Explore entity neighborhood |
| `POST` | `/ingest` | Trigger ingestion for a source |
| `GET` | `/health` | Health check |


All request/response models use Pydantic.


---


## Phase 2: Feedback Loop & Incremental Learning (Steps 7–8)


### Step 7: SME Feedback Loop *(depends on Step 6)*


Three feedback types:


- **Correction**: SME provides correct answer → stored as "golden answer" in PostgreSQL, embedded as high-priority chunk in ChromaDB (`metadata: {source: "sme_feedback", priority: "high"}`)
- **Approval**: SME confirms answer → boosts confidence of supporting source chunks
- **Annotation**: SME adds context → stored as supplementary chunk


Feedback stored in PostgreSQL: `(query, original_answer, sme_answer, feedback_type, sme_id, timestamp)`


Confidence weight calibration: run golden Q&A pairs through the pipeline, adjust scoring weights via simple linear regression on correctness.


---


### Step 8: Incremental Embedding Updates *(parallel with Step 7)*


- Each connector stores a `last_synced` cursor in PostgreSQL
- Incremental sync: fetch only new data since cursor → process through same pipeline → update graph + vector store → advance cursor
- Scheduling via APScheduler: Slack every 15 min, Git every hour, Incidents daily
- Entity resolution for new entities against existing graph nodes


---


## Phase 3: Slack Integration (Steps 9–10)


### Step 9: Slack Bot *(depends on Steps 7 & 8)*


Slack app with scopes: `chat:write`, `app_mentions:read`, `channels:history`, `reactions:read`


**Interaction flow:**


1. User mentions `@OrgBot` with a question in any channel
2. Bot responds **in-thread** with: answer, confidence badge (🟢 ≥ 0.7 / 🟡 0.4–0.7 / 🔴 < 0.4), source citations
3. Bot adds reaction buttons: ✅ correct / ❌ incorrect / 📝 needs correction
4. If ❌ or 📝 → bot opens a modal for SME to provide the correct answer → feeds into feedback loop


**Dual role**: Bot both reads Slack (data source for ingestion) AND writes to Slack (Q&A interface). Exclude its own messages from ingestion by filtering on `bot_id`.


---


### Step 10: End-to-End Testing & Demo *(depends on Step 9)*


- Integration test: ingest → query → feedback → re-query with improved answer
- Demo script with 5–10 representative queries demonstrating confidence scores, graph connections, and the feedback loop
- Create 20 golden Q&A pairs from simulated data, benchmark confidence calibration (target: >70% correlation between confidence score and actual correctness)


---


## Key Files to Create


| File | Purpose |
|------|---------|
| `docker-compose.yml` | Neo4j, ChromaDB, PostgreSQL, FastAPI |
| `core/connectors/base.py` | Abstract connector interface |
| `core/connectors/git_connector.py` | Git commit ingestion |
| `core/connectors/slack_connector.py` | Slack message ingestion |
| `core/connectors/incident_connector.py` | Incident report ingestion |
| `core/processing/chunker.py` | LlamaIndex SentenceSplitter wrapper |
| `core/processing/entity_extractor.py` | Claude-based entity + relationship extraction |
| `core/processing/embedder.py` | Embedding generation + ChromaDB storage |
| `core/graph/schema.py` | Neo4j node/relationship definitions, Cypher templates |
| `core/graph/operations.py` | Graph CRUD, entity resolution, queries |
| `core/rag/pipeline.py` | Hybrid retrieval (vector + graph) + fusion |
| `core/rag/prompts.py` | System prompts for Claude |
| `core/confidence/scorer.py` | Composite confidence scoring |
| `core/feedback/handler.py` | SME feedback processing |
| `services/api/main.py` | FastAPI application |
| `services/slackbot/app.py` | Slack Bolt bot |
| `simulators/org_ontology.py` | Trading platform entity definitions (people, teams, components, instruments, strategies) |
| `simulators/git_simulator.py` | Synthetic git repos for all 5 trading components |
| `simulators/slack_simulator.py` | Synthetic Slack conversations across 7 trading channels |
| `simulators/incident_simulator.py` | Synthetic trading platform incidents with RCA and linked commits |
| `simulators/doc_simulator.py` | Per-component README, ARCHITECTURE, RUNBOOK, CHANGELOG markdown files |
| `simulators/generate_all.py` | Entry point: runs all simulators and writes output to `data/simulated/` |


---


## Verification


1. `docker compose up` — all 4 services healthy
2. `python -m simulators.generate_all` — produces `data/simulated/{git,slack,incidents,docs}/` with cross-referenced trading platform entities
3. `python -m ingestion.ingest_all` — data appears in ChromaDB (verify via collection count) and Neo4j (verify via `MATCH (n) RETURN labels(n), count(n)`)
4. **Graph sanity checks** in Neo4j Browser (`localhost:7474`):
  - `MATCH (n) RETURN labels(n), count(n)` — verify all node types present
  - `MATCH (p:Person)-[:EXPERT_IN]->(c:Component) RETURN p.name, c.name LIMIT 20` — verify expertise edges
  - `MATCH (i:Incident)-[:AFFECTS]->(c:Component) RETURN c.name, count(i) ORDER BY count(i) DESC` — verify incident distribution across components
5. **Sample queries to validate RAG pipeline:**
  - *"Who should I contact about a FIX session disconnect?"* — should return Connectivity Team engineers with high confidence
  - *"What caused the P1 incident on the feed listener last month?"* — should cite specific incident + RCA + linked commits
  - *"What risk limits does ORMS enforce?"* — should cite ORMS docs + related Slack discussions
  - *"Which instruments have had the most trading incidents?"* — should traverse graph and cite incidents
  - *"What changed in the trade listener in the last 3 releases?"* — should cite git commits + changelogs
6. `POST /feedback` with corrections — re-query shows updated confidence and improved answers
7. Slack bot mentions — threaded response with confidence badge (🟢/🟡/🔴), feedback buttons work
8. Confidence calibration: 20 golden Q&A pairs sourced from simulated data, target >70% correlation between confidence score and actual correctness


---


## Decisions


| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vector store | ChromaDB | Local, no API key, Docker-friendly — swappable later for Pinecone/Weaviate |
| LLM | Anthropic Claude | Answer generation + entity extraction via structured tool use |
| Entity extraction | Claude (not spaCy) | Better for domain-specific entities like service names |
| Embedding model | `voyage-3` (preferred) or `text-embedding-3-small` | Defer to implementation; `voyage-3` aligns with Anthropic ecosystem |
| Graph query translation | Hybrid: templates + Claude-generated Cypher | Templates for common patterns, Claude for ad-hoc, with template fallback |
| Slack ingestion isolation | Filter on `bot_id` | Prevent bot's own responses from being treated as ground truth |


**Scope IN (POC)**: Git commits, Slack messages, incident reports, knowledge graph, confidence scoring, SME feedback loop, incremental updates, Slack bot Q&A


**Scope OUT (POC)**: LLM fine-tuning, custom embedding model training, RBAC/permissions, multi-tenancy, production deployment (K8s, monitoring, observability)
