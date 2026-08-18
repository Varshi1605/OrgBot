## Purpose

Keeps the knowledge base current by re-syncing each source on a schedule, fetching only data newer than the connector's last-synced cursor, processing it through the ingestion pipeline, and resolving newly encountered entities against the existing graph.

## ADDED Requirements

### Requirement: Scheduled incremental sync
The system SHALL run incremental syncs for connectors on a schedule: Slack every 15 minutes, Git every hour, and incidents daily.

#### Scenario: Connector sync runs on schedule
- **WHEN** the configured interval elapses for a connector
- **THEN** the connector syncs only data newer than its stored `last_synced` cursor

### Requirement: Cursor-based delta fetch
The system SHALL persist a `last_synced` cursor per connector and fetch only records created after that cursor, then advance the cursor to the newest processed record.

#### Scenario: Only new data is processed
- **WHEN** a connector syncs after a previous sync
- **THEN** only records newer than the stored cursor are processed through the pipeline and the cursor is advanced to cover them

#### Scenario: First sync processes everything
- **WHEN** a connector syncs with no stored cursor
- **THEN** all available records are processed and a cursor is created

### Requirement: Entity resolution for new entities
The system SHALL resolve entities from newly synced data against existing graph nodes by normalized identity, creating a node only when no existing node matches.

#### Scenario: New data references a known entity
- **WHEN** a newly synced record references an entity already in the graph
- **THEN** the existing node is reused and enriched rather than duplicated

#### Scenario: New data references an unknown entity
- **WHEN** a newly synced record references an entity not present in the graph
- **THEN** a new node is created for that entity

### Requirement: Idempotent incremental re-runs
The system SHALL produce the same store state when a connector syncs the same data range more than once, without duplicating chunks or graph nodes.

#### Scenario: Re-running a sync over the same data
- **WHEN** a connector syncs a data range it has already synced
- **THEN** no duplicate chunks or graph nodes are created
