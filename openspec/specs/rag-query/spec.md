# rag-query Specification

## Purpose

Answers natural-language questions about the trading platform by combining vector retrieval and graph retrieval, generating answers via an LLM, and returning each answer with a confidence score, source citations, and an explanation of the underlying graph connections.

## Requirements

### Requirement: Hybrid retrieval
The system SHALL retrieve candidate evidence using both vector similarity search over the vector store and structured graph queries against the knowledge graph, then fuse and re-rank the combined results.

#### Scenario: Vector and graph results are combined
- **WHEN** a question is asked
- **THEN** the system retrieves top-k vector chunks and graph query results, deduplicates, and returns a ranked evidence set

### Requirement: Answer generation with citations
The system SHALL generate an answer from the retrieved evidence using an LLM, citing the specific source chunks used.

#### Scenario: Answer cites sources
- **WHEN** an answer is generated
- **THEN** the response includes the source chunks (with their origin, e.g., repo/commit, channel/thread, incident ID, or doc path) that support the answer

### Requirement: Composite confidence score
The system SHALL produce a confidence score between 0.0 and 1.0 for each answer, combining source diversity (0.25), recency (0.20), embedding similarity (0.25), graph connectivity (0.15), and SME validation signal (0.15), with scores below a configured threshold flagged as low confidence.

#### Scenario: Confidence reflects evidence quality
- **WHEN** a question is answered from multiple recent, highly similar sources with connected graph entities
- **THEN** the confidence score is high, and when evidence is sparse, stale, or dissimilar the score is low

### Requirement: Graph path in response
The system SHALL include a graph path showing the entity connections that support the answer.

#### Scenario: Response includes graph connections
- **WHEN** a question has a graph-supported answer
- **THEN** the response includes the entity path (e.g., Person EXPERT_IN Component AFFECTS Incident) underlying the answer

### Requirement: SME validation signal
The system SHALL incorporate prior SME feedback (approvals/corrections for similar queries) as a confidence input when available, and operate normally with a neutral signal when none exists.

#### Scenario: No feedback present
- **WHEN** no SME feedback exists for a query
- **THEN** confidence is computed from the remaining signals without error

### Requirement: SME signal reflects real feedback
The system SHALL drive the SME validation confidence signal from actual feedback records when any exist — approvals raising the signal for the queries they confirm — and fall back to a neutral signal only when no feedback exists.

#### Scenario: Approval raises the SME signal
- **WHEN** a query matches prior SME approvals
- **THEN** the SME validation signal for that query is higher than the neutral default

#### Scenario: No feedback leaves signal neutral
- **WHEN** no feedback records exist for a query
- **THEN** the SME validation signal remains at the neutral default and scoring completes without error

### Requirement: Calibrated confidence weights
The system SHALL apply confidence scoring weights that are configurable and calibratable, using the weights produced by feedback-loop calibration when available and the default weights otherwise.

#### Scenario: Calibrated weights are applied
- **WHEN** calibration has produced adjusted weights
- **THEN** the composite confidence score is computed with those weights

#### Scenario: Uncalibrated weights are defaulted
- **WHEN** no calibrated weights exist
- **THEN** the composite confidence score is computed with the configured default weights
