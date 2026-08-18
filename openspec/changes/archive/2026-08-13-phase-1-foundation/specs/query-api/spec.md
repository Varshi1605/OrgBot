## Purpose

Exposes the OrgBot query engine as an HTTP service with endpoints for asking questions, submitting SME feedback, exploring the knowledge graph, triggering ingestion, and checking service health, using validated Pydantic request and response models.

## ADDED Requirements

### Requirement: Question endpoint
The system SHALL expose `POST /query` accepting a natural-language question and returning the answer, confidence score, source citations, and graph path.

#### Scenario: Ask a question
- **WHEN** a client POSTs a question to `/query`
- **THEN** the service returns the generated answer with confidence score, sources, and graph path

### Requirement: Feedback endpoint
The system SHALL expose `POST /feedback` accepting SME feedback records (correction, approval, or annotation) with the query, original answer, SME answer, SME identifier, and timestamp, and persist them to the feedback store.

#### Scenario: SME submits a correction
- **WHEN** an SME POSTs a correction to `/feedback`
- **THEN** the record is validated and stored in the feedback store

### Requirement: Graph exploration endpoint
The system SHALL expose `GET /graph/explore` accepting an entity name and returning its neighborhood (connected nodes and edges).

#### Scenario: Explore an entity
- **WHEN** a client requests `/graph/explore?entity=<name>`
- **THEN** the service returns the entity's connected nodes and relationships, or a not-found response for unknown entities

### Requirement: Ingestion trigger endpoint
The system SHALL expose `POST /ingest` accepting a source type and triggering ingestion for that source.

#### Scenario: Trigger ingestion
- **WHEN** a client POSTs `/ingest` with a source type
- **THEN** the service runs ingestion for that source and returns a confirmation

### Requirement: Health endpoint
The system SHALL expose `GET /health` reporting service status and the status of its dependencies.

#### Scenario: Health check
- **WHEN** a client GETs `/health`
- **THEN** the service returns status including availability of the vector store, graph store, and feedback store

### Requirement: Validated request/response models
The system SHALL validate all request payloads and serialize all responses using Pydantic models.

#### Scenario: Invalid request is rejected
- **WHEN** a client sends an invalid payload (e.g., missing required field)
- **THEN** the service returns a validation error with a 4xx status
