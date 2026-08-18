## ADDED Requirements

### Requirement: Live Slack ingestion source
The system SHALL support ingesting Slack conversations from the live Slack API (channel history) as a source in addition to the simulated JSON dataset, excluding messages authored by the bot (`bot_id`) and limiting ingestion to a configured channel allowlist.

#### Scenario: Live channel history is ingested
- **WHEN** the Slack connector runs in live mode against a channel in the allowlist
- **THEN** messages are parsed into records containing author, channel, thread, timestamp, and mentions

#### Scenario: Bot's own messages are excluded
- **WHEN** a channel contains messages authored by the bot
- **THEN** those messages are filtered out before records are created

#### Scenario: Channels outside the allowlist are ignored
- **WHEN** the connector encounters a channel not in the configured allowlist
- **THEN** no records are created from that channel
