# OrgBot

RAG-based organizational knowledge agent for a mock NSE-connected trading platform. Ingests git history, Slack conversations, and incident reports into a knowledge graph, then answers questions with confidence scores and source citations via a Slack bot interface.

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
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
└────────────────────────────▲────────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                   DATA INGESTION PIPELINE                        │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐  │
│  │ Git        │  │ Slack      │  │ Incident   │  │ Docs      │  │
│  │ Connector  │  │ Connector  │  │ Connector  │  │ Connector │  │
│  └────────────┘  └────────────┘  └────────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Trading Platform Components

The simulated trading platform consists of five independently owned components:

| # | Component | Protocol | Role | Owning Team |
|---|-----------|----------|------|-------------|
| 1 | **Public Feed Listener** | UDP multicast (NSE) | Receives and normalizes raw market data from NSE broadcast | Market Data Team |
| 2 | **Exchange Adapter** | TCP / FIX 4.2 (NSE) | Manages FIX sessions with NSE; routes orders and receives fills | Connectivity Team |
| 3 | **ORMS** | Internal TCP/IPC | Order and Risk Management System; enforces pre-trade risk limits | Risk & Order Team |
| 4 | **Trade Listener** | Internal TCP/IPC | Receives confirmed trade fills; enriches and distributes downstream | Trade Processing Team |
| 5 | **Strategy Interface** | Internal TCP/IPC | API gateway between trading strategies and ORMS | Strategy Team |

## Tech Stack

- **Language:** Python 3.11+
- **API:** FastAPI + Uvicorn
- **LLM:** Anthropic Claude (via LlamaIndex)
- **Vector Store:** ChromaDB
- **Graph Store:** Neo4j 7.x (with APOC plugin)
- **Feedback Store:** PostgreSQL 16
- **Slack Integration:** Slack Bolt SDK
- **Containerization:** Docker Compose

## Project Structure

```
orgbot/
├── docker-compose.yml          # Neo4j, ChromaDB, PostgreSQL, FastAPI
├── config/                     # Application configuration
├── core/
│   ├── connectors/             # Git, Slack, Incident, Docs connectors
│   ├── processing/             # Chunking, embedding, entity extraction
│   ├── graph/                  # Neo4j graph operations & Cypher templates
│   ├── rag/                    # RAG pipeline with LlamaIndex
│   ├── confidence/             # Confidence scoring module
│   ├── feedback/               # SME feedback loop
│   ├── storage/                # PostgreSQL storage
│   └── sync/                   # Incremental sync scheduler
├── ingestion/                  # Data ingestion pipeline & graph builder
├── services/
│   ├── api/                    # FastAPI query engine
│   └── slackbot/               # Slack Bolt bot
├── simulators/                 # Synthetic data generators
├── scripts/                    # Benchmark & demo scripts
└── tests/                      # Test suite
```

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- An Anthropic API key

### Setup

1. Clone the repository:

```bash
git clone https://github.com/Varshi1605/OrgBot.git
cd OrgBot
```

2. Create a `.env` file with your credentials:

```env
ANTHROPIC_API_KEY=your-api-key
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
CHROMA_HOST=localhost
CHROMA_PORT=8000
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=orgbot
POSTGRES_USER=orgbot
POSTGRES_PASSWORD=your-password
SLACK_BOT_TOKEN=your-slack-bot-token
SLACK_APP_TOKEN=your-slack-app-token
```

3. Start infrastructure services:

```bash
docker compose up -d
```

4. Install Python dependencies:

```bash
pip install -e ".[dev]"
```

### Generate Simulated Data

```bash
python -m simulators.generate_all
```

This produces synthetic git repos, Slack conversations, incident reports, and documentation under `data/simulated/`.

### Ingest Data

```bash
python -m ingestion.ingest_all
```

### Run the API Server

```bash
uvicorn services.api.main:app --reload --port 8080
```

### Run the Slack Bot

```bash
python -m services.slackbot.app
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/query` | Ask a question → answer + confidence + sources + graph path |
| `POST` | `/feedback` | SME submits correction or approval |
| `GET` | `/graph/explore?entity=X` | Explore entity neighborhood in the knowledge graph |
| `POST` | `/ingest` | Trigger ingestion for a data source |
| `GET` | `/health` | Health check |

## Confidence Scoring

Each answer includes a composite confidence score (0.0–1.0) based on:

| Signal | Weight | Description |
|--------|--------|-------------|
| Source diversity | 0.25 | Number of distinct source types confirming the answer |
| Recency | 0.20 | Exponential decay on document timestamps |
| Embedding similarity | 0.25 | Average cosine similarity of retrieved chunks to query |
| Graph connectivity | 0.15 | PageRank / degree centrality of answer entities |
| SME validation | 0.15 | Prior SME approvals for similar queries |

Confidence badges: 🟢 ≥ 0.7 | 🟡 0.4–0.7 | 🔴 < 0.4

## Slack Bot Usage

1. Mention `@OrgBot` with a question in any channel
2. Bot responds in-thread with the answer, confidence badge, and source citations
3. React with ✅ (correct), ❌ (incorrect), or 📝 (needs correction)
4. Incorrect/needs correction triggers a modal for SME feedback

## Sample Queries

- *"Who should I contact about a FIX session disconnect?"*
- *"What caused the P1 incident on the feed listener last month?"*
- *"What risk limits does ORMS enforce?"*
- *"Which instruments have had the most trading incidents?"*
- *"What changed in the trade listener in the last 3 releases?"*

## Development

```bash
# Run tests
pytest

# Lint
ruff check .

# Format
ruff format .
```

## License

Internal project — not licensed for external distribution.
