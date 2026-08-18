## Purpose

Ingests simulated Git, Slack, incident, and documentation data through a processing pipeline that chunks content, extracts entities, generates embeddings, and persists records to the vector store and knowledge graph so the query engine can answer questions.

## ADDED Requirements

### Requirement: Pluggable connector interface
The system SHALL provide a common connector interface with `fetch()`, `transform()`, `chunk()`, `get_cursor()`, and `set_cursor()` operations.

#### Scenario: Connectors implement the common interface
- **WHEN** a new connector is registered
- **THEN** it SHALL implement fetch, transform, chunk, and cursor operations so the pipeline treats all sources uniformly

### Requirement: Source connectors
The system SHALL provide connectors for Git commits, Slack messages, incident reports, and documentation files.

#### Scenario: Git commits are read
- **WHEN** the git connector fetches data
- **THEN** commits are parsed into records containing author, files changed, message, timestamp, and repository

#### Scenario: Slack messages are read
- **WHEN** the Slack connector fetches data
- **THEN** messages are parsed into records containing author, channel, thread, timestamp, and mentions

#### Scenario: Incident reports are read
- **WHEN** the incident connector fetches data
- **THEN** incidents are parsed into records containing severity, affected services, responders, and RCA

#### Scenario: Documentation is read
- **WHEN** the documentation connector fetches data
- **THEN** markdown files are parsed into records containing path, component, and document type

### Requirement: Chunking
The system SHALL split source content into chunks using a sentence splitter configured at approximately 512 tokens with 50-token overlap, chunking by logical unit per source (commit, thread/conversation, or section).

#### Scenario: Content is chunked
- **WHEN** a connector record is processed
- **THEN** its content is split into overlapping chunks of approximately 512 tokens

### Requirement: Entity and relationship extraction
The system SHALL extract entities (Person, Service/Component, Repository, Team, Incident, Instrument, Strategy) and relationships from each chunk using LLM structured output.

#### Scenario: Entities are extracted from a chunk
- **WHEN** a chunk is processed
- **THEN** the extractor returns typed entities and relationships with their source chunk reference

### Requirement: Embedding and storage
The system SHALL embed each chunk and persist chunks with embeddings and metadata to the vector store, and entities with relationships to the graph store.

#### Scenario: Chunks are embedded and stored
- **WHEN** a chunk passes through the pipeline
- **THEN** its embedding and metadata are stored in the vector store and queryable by similarity

#### Scenario: Entities and relationships are stored in the graph
- **WHEN** a chunk's entities and relationships are extracted
- **THEN** they are persisted to the graph store with a link back to their source chunk

### Requirement: Cursor-based incremental sync
The system SHALL track a `last_synced` cursor per connector so that only data newer than the cursor is processed.

#### Scenario: Only new data is processed on resync
- **WHEN** a connector sync runs after a previous sync
- **THEN** only records newer than the stored cursor are fetched and processed, and the cursor is advanced

### Requirement: Programmatic ingestion trigger
The system SHALL expose a programmatic entry point to trigger ingestion for a specific source.

#### Scenario: Ingestion is triggered for a source
- **WHEN** ingestion is invoked for a source type
- **THEN** the connector for that source syncs and processes data through the full pipeline
