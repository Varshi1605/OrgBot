## 1. Config & Dependency Setup

- [x] 1.1 Add `slack-bolt>=1.18.0` to `pyproject.toml` dependencies
- [x] 1.2 Add `slack` section to `config/config.yaml` (`source`, `socket_mode`, `bot_token_env`, `app_token_env`, `signing_secret_env`, `channels` allowlist, `messages_fetch_limit`)
- [x] 1.3 Add `core/config.py` fields and helpers for the `slack` section (source, token env names, channels, fetch limit)

## 2. Slack Bot Brain (transport-independent)

- [x] 2.1 Define a `SlackClient` protocol (post message, update message, open view, fetch channel history) plus a `FakeSlackClient` for tests
- [x] 2.2 Implement confidence badge rendering from config thresholds (🟢 >= 0.7, 🟡 0.4–0.7, 🔴 < 0.4)
- [x] 2.3 Implement answer message formatting: threaded reply with answer, source citations, and Block Kit feedback buttons (✅/❌/📝) carrying the query in the action value
- [x] 2.4 Implement mention handling: extract question from `@OrgBot` mention, call `RagPipeline.answer`, post in-thread reply, and record answer context
- [x] 2.5 Implement an answer-context store (LRU keyed by channel + message ts) with truncated-query fallback in the action value
- [x] 2.6 Implement action routing: ✅ submits an approval via `FeedbackHandler.submit` (original answer from context); ❌/📝 open the correction modal
- [x] 2.7 Implement modal open and submission handling, submitting correction/annotation with the Slack user id as `sme_id`
- [x] 2.8 Implement self-message exclusion: the bot ignores its own messages and never responds to or ingests them

## 3. Live Slack Ingestion

- [x] 3.1 Extend `core/connectors/slack_connector.py` with a live mode: fetch `conversations.history` per allowlisted channel, filter out `bot_id`/`subtype=="bot_message"`, group threads, reuse existing transform
- [x] 3.2 Implement per-channel cursors (`slack:<channel_id>` in the cursor store) that advance per channel and keep the source-level max cursor for scheduler bookkeeping
- [x] 3.3 Wire live Slack ingestion into the scheduler/`ingestion/scheduler.py`: use live mode when configured, skip with a logged warning when tokens are missing

## 4. Bolt App & Wiring

- [x] 4.1 Implement `services/slackbot/app.py`: slack-bolt App supporting Socket Mode and an HTTP Events endpoint, wiring mention/action/modal listeners to the brain
- [x] 4.2 Add entry point `python -m services.slackbot.app` (and `orgbot-slackbot` console script); fail startup loudly on missing tokens
- [x] 4.3 Confine `slack_sdk`/`slack_bolt` imports to `app.py` and the live client implementation; ensure tokens are never logged

## 5. Tests & Verification

- [x] 5.1 Unit tests: confidence badge bands (high/medium/low)
- [x] 5.2 Unit tests: mention triggers an in-thread reply with answer, citations, and buttons (via `FakeSlackClient`)
- [x] 5.3 Unit tests: ✅ button records an approval/boost; ❌/📝 buttons open the modal
- [x] 5.4 Unit tests: modal submission creates a correction (golden chunk) or annotation through the feedback loop
- [x] 5.5 Unit tests: bot-authored messages are ignored (no reply, not ingested)
- [x] 5.6 Unit tests: live Slack ingestion — allowlist filtering, bot_id exclusion, per-channel cursor advance and resume
- [x] 5.7 Integration test: ingest → query → feedback (via bot flow) → re-query returns improved answer
- [x] 5.8 Demo script with 5–10 representative queries printing answer, confidence, and sources
- [x] 5.9 Golden-pair benchmark: 20 Q&A pairs, confidence-vs-correctness correlation reported (target >70%)
- [x] 5.10 Document live setup in `developement.md` (app creation, scopes, socket mode, env vars, manual smoke test)

## 6. Lint & Full Verification

- [x] 6.1 Run the full pytest suite and `ruff check` on all changed files
