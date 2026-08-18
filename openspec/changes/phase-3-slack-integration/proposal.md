## Why

OrgBot is only reachable through the HTTP API, but the engineers it serves live in Slack. Phase 3 makes the knowledge agent available where the team already communicates: an `@OrgBot` Slack bot for Q&A with confidence feedback, while also making Slack a live ingestion source so the knowledge base keeps pace with current conversations.

## What Changes

- Add a Slack bot service (`services/slackbot/`) built on slack-bolt with Socket Mode and an Events API endpoint:
  - Mention-triggered Q&A: `@OrgBot <question>` anywhere the app is installed answers **in-thread** with the answer, a confidence badge (🟢 >= 0.7 / 🟡 0.4-0.7 / 🔴 < 0.4), and source citations.
  - Block Kit feedback actions on each answer: ✅ correct (approval), ❌ incorrect, 📝 needs correction.
  - ❌ / 📝 open a modal asking the SME for the correct answer, which is submitted through the existing feedback loop (correction/annotation).
  - The bot reuses the in-process `RagPipeline.answer()` and `FeedbackHandler.submit()` rather than calling the HTTP API.
- Live Slack ingestion (dual role per plan Step 9): `SlackConnector` gains a live source that reads channel history via the same Slack client, excludes the bot's own messages by `bot_id`, and tracks per-channel cursors; the simulated JSON file path remains for offline use and tests.
- Scheduler integration: live Slack sync runs on the existing 15-minute interval with per-channel cursors.
- Configuration: `slack` section (bot/app tokens via env vars, Socket Mode on/off, channel allowlist) in `config/config.yaml` and `core/config.py`.
- New dependency `slack-bolt` added to `pyproject.toml`.
- End-to-end verification: ingest → query → feedback → re-query integration test, a demo script of representative queries, 20 golden Q&A pairs, and a confidence-calibration benchmark (target >70% correlation).

## Capabilities

### New Capabilities
- `slackbot`: Slack bot Q&A and SME feedback interface — mention handling, in-thread answers with confidence badges and citations, feedback buttons, correction modal, and exclusion of the bot's own messages.

### Modified Capabilities
- `data-ingestion`: Slack connector learns a live Slack ingestion source (channel history via the Slack API) alongside the simulated file, with `bot_id` filtering.
- `incremental-sync`: live Slack sync uses per-channel cursors so incremental fetches resume where the last sync left off per channel.

## Impact

- **New code**: `services/slackbot/app.py`, `services/slackbot/bot.py` (decoupled bot brain: mention handling, message formatting, action handlers, modal submission), `services/slackbot/client.py` (Slack transport adapter with a test fake), demo/benchmark scripts.
- **Modified code**: `core/connectors/slack_connector.py` (live source), `core/config.py` + `config/config.yaml` (slack section), `ingestion/scheduler.py` and `core/sync/scheduler.py` (live Slack wiring), `pyproject.toml` (slack-bolt).
- **Config/credentials**: Slack app tokens read from environment (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`) so no secrets are committed; Socket Mode for local dev, Events API endpoint for hosted.
- **Dependencies**: adds `slack-bolt>=1.18.0`.
- **Tests**: offline unit tests against a fake Slack client; live-workspace smoke tests are manual and documented.
- **Docs**: `developement.md` / demo notes updated with setup instructions and sample queries.
