# feedback-loop Specification

## Purpose

Processes subject-matter-expert (SME) feedback — corrections, approvals, and annotations — so that answers improve over time and confidence reflects expert validation, persisting golden answers and supplementary knowledge into the stores.

## Requirements

### Requirement: Correction creates a golden answer
The system SHALL accept a correction (SME-provided correct answer for a query), persist it as a golden answer record in the feedback store, and embed it into the vector store as a high-priority chunk tagged with `source: sme_feedback` and `priority: high`.

#### Scenario: SME submits a correction
- **WHEN** an SME submits a correction with a query, original answer, SME answer, and SME identifier
- **THEN** the correction is persisted in the feedback store and a high-priority chunk containing the SME answer is added to the vector store and retrievable for the same query

### Requirement: Approval boosts supporting evidence
The system SHALL treat an SME approval as confirmation of an answer and raise the confidence contribution of the source chunks that supported that answer in subsequent queries.

#### Scenario: SME approves an answer
- **WHEN** an SME approves a previously given answer
- **THEN** the source chunks cited in that answer receive a confidence boost on subsequent similar queries

### Requirement: Annotation adds supplementary knowledge
The system SHALL store an SME annotation (added context not tied to a specific answer correction) as a supplementary chunk retrievable in subsequent queries.

#### Scenario: SME adds an annotation
- **WHEN** an SME submits an annotation with context text
- **THEN** the annotation is persisted and embedded as a supplementary chunk that can be retrieved and cited for related questions

### Requirement: Feedback record persistence
The system SHALL persist every feedback record with the query, original answer, SME answer, feedback type, SME identifier, and timestamp.

#### Scenario: Feedback record is stored
- **WHEN** any feedback record is submitted
- **THEN** the full record is stored in the feedback store with its timestamp and can be listed

### Requirement: Golden answer prioritization
The system SHALL rank high-priority feedback chunks above ordinary source chunks of comparable relevance when retrieving evidence for a query.

#### Scenario: Feedback chunk outranks ordinary chunks
- **WHEN** a query retrieves both a high-priority feedback chunk and ordinary source chunks with similar similarity scores
- **THEN** the feedback chunk is ranked above the ordinary chunks in the evidence set

### Requirement: Confidence weight calibration
The system SHALL support calibrating confidence scoring weights by running golden Q&A pairs through the pipeline and adjusting the weights to improve agreement between confidence scores and actual correctness.

#### Scenario: Weights are calibrated from golden pairs
- **WHEN** calibration runs over a set of golden Q&A pairs
- **THEN** the system produces adjusted scoring weights that better align confidence scores with answer correctness, without breaking scoring when no calibration has run
