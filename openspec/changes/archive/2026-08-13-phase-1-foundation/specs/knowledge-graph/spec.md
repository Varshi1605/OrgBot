## Purpose

Maintains a Neo4j knowledge graph of trading-platform entities and their relationships derived from ingested sources, resolves duplicate entities across sources, computes derived expertise edges, and exposes pre-built Cypher query templates for common organizational questions.

## ADDED Requirements

### Requirement: Graph node schema
The system SHALL support graph nodes for the labels Person, Component, Repository, Team, Incident, Commit, Conversation, Instrument, Strategy, and Document, with properties per the defined schema (e.g., Person has name/team/role/slack_handle/github_handle; Incident has id/severity/title/status/rca/resolution_time).

#### Scenario: All node types can be created
- **WHEN** ingestion persists extracted entities
- **THEN** each entity is stored under its corresponding node label with its schema properties

### Requirement: Graph relationship schema
The system SHALL support the relationships AUTHORED, OWNS, WORKS_ON, CAUSED_BY, FIXED_BY, AFFECTS, RESPONDED_TO, MENTIONED_IN, DISCUSSED_IN, DEPENDS_ON, CONSUMES_FEED, ROUTES_ORDERS, DOCUMENTS, and PARTICIPATED_IN between the appropriate node types.

#### Scenario: Relationships are persisted
- **WHEN** ingestion extracts a relationship between two entities
- **THEN** the corresponding edge is created between the resolved graph nodes

#### Scenario: Component dependency edges exist
- **WHEN** the graph is populated
- **THEN** DEPENDS_ON / CONSUMES_FEED / ROUTES_ORDERS edges reflect the runtime data flow between components (e.g., ORMS routes orders via Exchange Adapter)

### Requirement: Entity resolution
The system SHALL merge duplicate entities across sources using normalized identifiers so the same real-world entity maps to a single graph node.

#### Scenario: Duplicate entities merge
- **WHEN** the same person arrives from git, Slack, and incident sources
- **THEN** they resolve to one Person node whose properties are merged

### Requirement: Derived enrichment edges
The system SHALL compute derived edges as a post-ingestion job: EXPERT_IN (Person → Component weighted by commit and incident response recency), FREQUENTLY_CO_AUTHORED (Person → Person), and HISTORICALLY_INCIDENT_PRONE (Component → Instrument).

#### Scenario: Expertise edges are computed
- **WHEN** the enrichment job runs
- **THEN** each Person receives EXPERT_IN edges to the components they commit to or respond to incidents for, weighted by recency

#### Scenario: Incident-prone pairs are computed
- **WHEN** the enrichment job runs
- **THEN** HISTORICALLY_INCIDENT_PRONE edges link components to instruments that frequently appear in their incidents

### Requirement: Cypher query templates
The system SHALL provide pre-built Cypher templates for common questions, including: expert lookup per component, incidents affecting a component with responders, commits linked to a P1 incident, and Slack discussions mentioning a component or topic.

#### Scenario: Expert query returns ranked engineers
- **WHEN** the expert template runs for a component
- **THEN** it returns the top engineers ordered by expertise score

#### Scenario: Incident query returns affected incidents and responders
- **WHEN** the incident template runs for a component
- **THEN** it returns incident titles, severities, and the engineers who responded
