## Why

Phase 1 gave OrgBot a knowledge base it can query, but it is static: answers never improve, and the data never goes stale. SME feedback is collected but has no effect, and connectors re-read everything on every run. Phase 2 closes both loops — subject-matter experts correct, approve, and annotate answers so confidence and correctness improve over time, and ingestion re-syncs only new data on a schedule so the knowledge stays fresh.

## What Changes

- Add a full SME feedback loop: corrections become "golden answers" persisted in PostgreSQL and embedded as high-priority chunks in ChromaDB; approvals boost the confidence of supporting source chunks; annotations add supplementary context chunks.
- Make the `/feedback` endpoint process feedback end-to-end (persist + embed + boost), not just store it, and make the SME signal in the confidence scorer reflect real feedback instead of a neutral default.
- Add confidence weight calibration: run golden Q&A pairs through the pipeline and adjust scoring weights via linear regression on correctness, with weights still config-driven.
- Add scheduled incremental ingestion via APScheduler: Slack every 15 min, Git every hour, incidents daily, each connector fetching only data newer than its `last_synced` cursor, running it through the existing pipeline, and advancing the cursor.
- Resolve newly-encountered entities against existing graph nodes during incremental sync.
- Add verification: feedback loop round-trip (ingest → query → feedback → re-query with improved answer) and incremental sync idempotency checks.

## Capabilities

### New Capabilities

- `feedback-loop`: SME feedback processing — corrections stored as golden answers and embedded as high-priority chunks, approvals boosting confidence of source chunks, annotations stored as supplementary chunks, plus confidence weight calibration from golden Q&A pairs.
- `incremental-sync`: Scheduled incremental ingestion — per-connector `last_synced` cursors in PostgreSQL, sync schedules (Slack 15 min, Git hourly, incidents daily), pipeline execution over new data only, cursor advancement, and entity resolution for new entities.

### Modified Capabilities

- `rag-query`: The SME validation signal in the composite confidence score now reflects real feedback (approvals raise, corrections inform) instead of a neutral default when feedback exists; calibration tunes the scoring weights.
- `query-api`: The `/feedback` endpoint behavior changes from store-only to processing corrections, approvals, and annotations through the feedback loop (persist, embed, boost).

## Impact

- **New code**: `core/feedback/` extensions (golden answers, boosting, calibration), `core/sync/` scheduler, connector incremental-sync support.
- **Modified code**: `core/confidence/scorer.py` (SME signal from feedback store, calibrated weights), `core/rag/` retrieval and fusion (priority handling for feedback chunks, approval-boosted chunks), `core/connectors/*` (incremental fetch by cursor), `services/api/routers/feedback.py` (process feedback), `ingestion/` pipeline entry points (incremental mode), config for schedules and calibration settings.
- **Dependencies**: adds `apscheduler` to `pyproject.toml`.
- **Infrastructure**: no new services; reuses PostgreSQL (cursors + feedback), ChromaDB (high-priority feedback chunks), Neo4j.
- **No breaking changes**: existing endpoints, confidence scoring shape, and connector interface stay compatible; new behavior is additive.
