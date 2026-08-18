## MODIFIED Requirements

### Requirement: Feedback endpoint
The system SHALL expose `POST /feedback` accepting SME feedback records (correction, approval, or annotation) with the query, original answer, SME answer, SME identifier, and timestamp, persist them to the feedback store, and process them through the feedback loop so that corrections become golden answers, approvals boost supporting evidence, and annotations become supplementary chunks.

#### Scenario: SME submits a correction
- **WHEN** an SME POSTs a correction to `/feedback`
- **THEN** the record is validated, stored in the feedback store, and processed as a golden answer embedded as a high-priority chunk

#### Scenario: SME submits an approval
- **WHEN** an SME POSTs an approval to `/feedback`
- **THEN** the record is validated, stored, and applied as a confidence boost to the cited source chunks

#### Scenario: SME submits an annotation
- **WHEN** an SME POSTs an annotation to `/feedback`
- **THEN** the record is validated, stored, and processed as a supplementary chunk

#### Scenario: Invalid feedback is rejected
- **WHEN** an SME POSTs feedback with an invalid type or missing required fields
- **THEN** the service returns a validation error and stores nothing
