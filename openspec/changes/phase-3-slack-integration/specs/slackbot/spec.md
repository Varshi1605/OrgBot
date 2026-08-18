## Purpose

Provides a Slack-native interface for the OrgBot knowledge agent — mention-triggered Q&A with confidence badges and citations, plus inline SME feedback (approvals and corrections) that flows into the feedback loop.

## ADDED Requirements

### Requirement: Mention-triggered Q&A
The system SHALL respond to `@OrgBot` mentions in any channel where the app is installed, answering in-thread with the generated answer, source citations, and a confidence badge.

#### Scenario: Engineer mentions the bot with a question
- **WHEN** a user mentions the bot with a question in a channel
- **THEN** the bot posts a threaded reply containing the answer, its source citations, and a confidence badge

#### Scenario: Confidence badge reflects the score
- **WHEN** the answer's confidence score is computed
- **THEN** the badge is green (>= 0.7) for high, yellow (0.4 to 0.7) for medium, and red (< 0.4) for low confidence

### Requirement: Feedback actions on answers
The system SHALL attach feedback actions (✅ correct, ❌ incorrect, 📝 needs correction) to each bot answer, and an ✅ action SHALL submit an approval to the feedback loop using the posted answer as the original answer.

#### Scenario: SME approves an answer
- **WHEN** a user clicks ✅ on a bot answer
- **THEN** an approval is recorded for the question, boosting confidence for subsequent similar queries

### Requirement: Correction modal
The system SHALL open a modal when ❌ or 📝 is clicked, asking the SME for the correct answer or additional context, and submit it to the feedback loop tied to the Slack user's identity.

#### Scenario: SME corrects an answer
- **WHEN** a user clicks ❌ and submits the correct answer in the modal
- **THEN** a correction is recorded and processed as a golden answer retrievable for the same query

#### Scenario: SME adds context
- **WHEN** a user clicks 📝 and submits additional context in the modal
- **THEN** an annotation is recorded and embedded as a supplementary chunk

### Requirement: Self-message exclusion
The system SHALL ignore the bot's own messages and exclude bot-authored messages from ingestion so the bot's answers are never treated as source ground truth.

#### Scenario: Bot's own message is ignored
- **WHEN** a message authored by the bot arrives
- **THEN** it is not ingested and does not trigger a bot response

### Requirement: Secure credential configuration
The system SHALL configure Slack credentials from environment variables (bot token, app token) and support both Socket Mode and an HTTP Events API endpoint, without persisting or logging the tokens.

#### Scenario: Bot starts with valid credentials
- **WHEN** the bot starts with the configured environment tokens
- **THEN** it connects and is able to receive mentions and interactions

#### Scenario: Missing credentials fail startup
- **WHEN** the bot starts without required tokens
- **THEN** startup fails with a clear error and no partial connection is left running
