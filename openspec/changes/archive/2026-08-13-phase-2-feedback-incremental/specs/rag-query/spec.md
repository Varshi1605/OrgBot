## ADDED Requirements

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
