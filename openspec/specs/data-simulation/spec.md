# data-simulation Specification

## Purpose

Generates a realistic, cross-referenced synthetic dataset of the mock trading platform's engineering knowledge (Git commits, Slack conversations, incidents, and documentation) so the ingestion and query pipelines can be built and verified without live systems.

## Requirements

### Requirement: Shared organization ontology
The system SHALL provide a single source of truth defining every entity used across all data simulators: 20 people (4 per team across 5 teams), 5 platform components, 5 owning teams, 8 instruments, and 5 strategies.

#### Scenario: All simulated entities resolve to the ontology
- **WHEN** any simulator references a person, component, team, instrument, or strategy
- **THEN** that entity SHALL be defined in the shared ontology, and simulators import entity definitions from it rather than hardcoding them

### Requirement: Git repository simulation
The system SHALL generate 5 independent git repositories (one per trading component), each with approximately 150-200 commits, `main` and `develop` branches, feature branches, version tags (`v1.x.x`), and a `CHANGELOG.md`.

#### Scenario: Git repos are generated per component
- **WHEN** the git simulator runs
- **THEN** one repository directory is produced per component, each containing commits authored by ontology people, branch structure, version tags, and a changelog

#### Scenario: Commits match the component's domain
- **WHEN** commits are inspected
- **THEN** commit messages reflect the component's trading-domain concerns (e.g., feed sequence gaps for the feed listener, FIX session handling for the exchange adapter, risk limits for ORMS)

### Requirement: Slack conversation simulation
The system SHALL generate approximately 2000 Slack messages across 7 trading channels, including threads, reactions, and mentions, involving ontology people.

#### Scenario: Slack channels and threads are generated
- **WHEN** the Slack simulator runs
- **THEN** messages are distributed across the 7 defined channels, are authored by ontology people, and form threaded conversations with reactions

#### Scenario: Slack content references platform entities
- **WHEN** messages are inspected
- **THEN** messages reference components, instruments, incidents, and engineers that exist in the shared ontology

### Requirement: Incident report simulation
The system SHALL generate approximately 60-80 incidents with severity distribution (P1 critical ~10, P2 high ~20, P3 medium ~30, P4 low ~20), each including affected components, involved engineers, instruments, a timeline (detected → acknowledged → mitigated → resolved), RCA, action items, and linked commits.

#### Scenario: Incidents have full metadata and linked commits
- **WHEN** the incident simulator runs
- **THEN** each incident references ontology components and engineers, and its linked commits SHALL exist in the generated git dataset

### Requirement: Documentation simulation
The system SHALL generate per-component markdown documentation: `README.md`, `ARCHITECTURE.md`, `RUNBOOK.md`, and `CHANGELOG.md`.

#### Scenario: Every component has all four documents
- **WHEN** the documentation simulator runs
- **THEN** each of the 5 components has README, ARCHITECTURE, RUNBOOK, and CHANGELOG markdown files describing its protocol, configuration, failure modes, and version history

### Requirement: Cross-source entity consistency
The system SHALL ensure the same entity (person, component, instrument, incident) is referenced consistently across Git, Slack, incident, and documentation outputs.

#### Scenario: Same engineer appears across all sources
- **WHEN** datasets from different simulators are compared
- **THEN** the same normalized engineer identity appears in commits, Slack messages, and incident responders for the same ontology person

### Requirement: Deterministic generation
The system SHALL support reproducible generation given a fixed seed.

#### Scenario: Identical output for the same seed
- **WHEN** `generate_all` runs twice with the same seed
- **THEN** the produced datasets are identical

### Requirement: Single entry point
The system SHALL provide a single entry point that runs all simulators and writes structured output to `data/simulated/` (organized by source type) with cross-referenced entity IDs.

#### Scenario: generate_all produces the full dataset
- **WHEN** the generation entry point runs
- **THEN** output exists under `data/simulated/` for git, slack, incidents, and docs, and the generated entity IDs cross-reference across sources
