## Context

See proposal.md — Why. The codebase already provides everything the bot consumes: `RagPipeline.answer()` returns `{answer, confidence, sources, ...}` (core/rag/pipeline.py), `FeedbackHandler.submit()` accepts correction/approval/annotation payloads (core/feedback/handler.py), and config carries the confidence thresholds used for badges (`confidence.thresholds.low=0.4`, `high=0.7`). Connectors expose `fetch(cursor)`/`transform()`/`sync()` with a single cursor keyed by `self.source` (core/connectors/base.py). No `services/slackbot/` exists yet; Slack ingestion currently reads `data/simulated/slack/slack_messages.json`.

## Goals / Non-Goals

**Goals:**
- A slack-bolt app (Socket Mode + Events API) whose mention flow, badge rendering, buttons, and modal all reuse the existing pipeline and feedback loop in-process.
- All conversation logic unit-testable offline via a fake Slack client; live-workspace smoke tests are manual and documented.
- Slack ingestion from live channel history with bot-message exclusion and per-channel cursors, integrated with the existing scheduler.

**Non-Goals:**
- RBAC/approval workflows for who may submit corrections (any member may, as in the HTTP API).
- Multi-workspace/multi-tenant Slack app support.
- Re-architecting the existing simulated Slack ingestion path (it remains the default).
- Persisting bot conversation context across restarts.

## Decisions

1. **Decoupled bot brain + thin Bolt adapter.** `services/slackbot/bot.py` holds pure, testable logic (mention → answer formatting → badge → citations → buttons; action routing; modal open/submit) and takes a `SlackClient` protocol (post message, update message, open view, list channels, read history). `services/slackbot/app.py` is the thin slack-bolt `App` wiring listeners to the brain. Tests inject a `FakeSlackClient`.
   - *Why:* the full conversation flow is testable without a workspace; Bolt stays a transport detail. *Alternative:* inline handlers in Bolt — hard to test, couples to a live app.
2. **In-process reuse of `RagPipeline` and `FeedbackHandler`** via the existing `services/api/deps.init_state()` wiring, not HTTP calls to `/query` and `/feedback`.
   - *Why:* single source of truth (calibrated weights, priority bonus, SME signal already wired), no network hop, no dependency on the API process. *Alternative:* HTTP calls — extra coupling, latency, and a hard runtime dependency.
3. **Confidence badge from config thresholds.** 🟢 score >= high (0.7), 🟡 low <= score < high, 🔴 < low (0.4). Same bands as the API's low-confidence flag.
4. **Block Kit buttons over emoji reactions.** ✅/❌/📝 are buttons in an `actions` block (`feedback:approve`, `feedback:incorrect`, `feedback:annotate`) carrying the query in the action value; Slack buttons reliably open modals, which reactions cannot.
   - *Note:* plan.md listed `reactions:read` in scopes; the button-based design uses `chat:write`, `app_mentions:read`, `channels:history`, `conversations:history`, `commands`, and `interactive` scopes instead. `reactions:read` is not needed.
5. **Short-lived in-memory answer context.** When the bot posts an answer it stores `{query, answer}` keyed by `(channel_id, ts)` in an LRU map; action/modal handlers look it up to fill `query`/`original_answer` for `FeedbackHandler.submit`. The action value also carries a truncated query as a fallback when context has been evicted (e.g., after restart).
   - *Trade-off:* context is lost on restart; fallback covers the common case and the modal lets the SME edit the question.
6. **Live Slack ingestion as a connector mode.** `SlackConnector` gains `source="live"` (config `slack.source: live|simulated`, default `simulated`). In live mode `fetch()` reads each allowlisted channel with `conversations.history`, filters out bot-authored messages (`bot_id`/`subtype=="bot_message"`), groups threads, and transforms them with the existing logic. Per-channel cursors are stored as `slack:<channel_id>` in the cursor store (keys are arbitrary strings today); `sync()` still updates the source-level cursor to the max thread ts for scheduler bookkeeping.
7. **Scheduler stays source-agnostic.** `ingestion/scheduler.py` calls the SlackConnector in live mode when configured; if required tokens are absent it logs a warning and skips live Slack rather than crashing the scheduler.
8. **New dependency** `slack-bolt>=1.18.0`. The `SlackClient` protocol keeps tests independent of the live SDK; import of `slack_sdk`/`slack_bolt` is confined to `app.py` and the live client implementation.
9. **Config section** `slack:` added to `config/config.yaml` and `core/config.py`: `source`, `socket_mode`, `bot_token_env`, `app_token_env`, `signing_secret_env`, `channels` (allowlist), and a `messages_fetch_limit` for pagination safety.
10. **Benchmark reuses the existing calibrator.** The golden-pair benchmark (20 pairs, target >70% correlation) builds on `core/feedback/calibration.py`'s `Calibrator`; a script runs the pairs through the pipeline, computes confidence-vs-correctness correlation, and prints the result.

## Risks / Trade-offs

- **Slack rate limits on `conversations.history`** → per-channel pagination with `next_cursor`, an upper cap per sync, and backoff on `ratelimited`; ingestion intervals already give headroom.
- **Bot double-delivery of events (Socket Mode retries)** → handlers dedupe on `(team_id, event_ts)` where cheap; submissions via `FeedbackHandler` are idempotent for corrections (deterministic chunk IDs).
- **Live workspace required to fully exercise the bot** → offline tests cover the brain with a fake client; a documented manual smoke script covers live behavior. CI stays offline.
- **In-memory answer context lost on restart** → truncated query in the action value as fallback; documented limitation.
- **Credentials leaked via logs** → tokens only ever read from env vars; never logged; startup fails loudly on missing tokens.
- **Live ingestion could pull unintended channels** → explicit channel allowlist; only allowlisted channels are fetched.

## Migration Plan

- Config and dependency changes are additive; default `slack.source: simulated` keeps existing behavior and the test suite untouched.
- To enable live: set `SLACK_BOT_TOKEN`/`SLACK_APP_TOKEN` env vars, set `slack.source: live`, populate `slack.channels`, and run `python -m services.slackbot.app` (or `orgbot-slackbot` script entry).
- Rollback: set `slack.source: simulated` (or unset tokens); the scheduler skips live Slack gracefully.

## Open Questions

- Exact Slack app manifest details (bot name, icon, scope list) — deferred to live setup and documented in `developement.md`; no spec or task impact.
