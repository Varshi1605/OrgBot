## ADDED Requirements

### Requirement: Per-channel Slack sync cursors
The system SHALL track live Slack ingestion progress with a cursor per channel so each sync resumes from the last fetched message per channel while running on the configured schedule.

#### Scenario: Live Slack sync resumes per channel
- **WHEN** a live Slack sync runs after a previous sync
- **THEN** only messages newer than each channel's stored cursor are fetched and processed, and the cursor is advanced to cover them

#### Scenario: First live sync processes all allowed channels
- **WHEN** a live Slack sync runs with no stored channel cursors
- **THEN** history for every allowlisted channel is processed and a cursor is created for each
