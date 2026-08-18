## 1. Config & Schema Extensions

- [x] 1.1 Add `feedback` config section (`priority_bonus`, `golden_priority`, `approval_match_threshold`) to `config/config.yaml`
- [x] 1.2 Add `sync` config section with per-connector `interval_minutes` (slack 15, git 60, incidents 1440)
- [x] 1.3 Add `confidence.calibrated_weights_path` config key
- [x] 1.4 Add PostgreSQL `feedback_boosts` table (query_key, boost_factor, created_at) via `PostgresStore.init_schema`
- [x] 1.5 Add `PostgresStore` methods: `add_boost`, `list_boosts`, `get_boost_for_query`; keep existing feedback API compatible

## 2. Feedback Processing

- [x] 2.1 Implement `core/feedback/processor.py` `FeedbackProcessor`: dispatch correction/approval/annotation
- [x] 2.2 Correction path: build `SourceRecord` from SME answer with metadata `{source: "sme_feedback", priority: "high", feedback_id, query}`, run through `IngestionPipeline.process_record`
- [x] 2.3 Annotation path: same as correction but `kind: "annotation"` and normal priority
- [x] 2.4 Approval path: store boost row for the query and, where source chunk metadata is available, record approved source origins
- [x] 2.5 Extend `FeedbackHandler.submit` to call the processor after persistence so `/feedback` round-trips end-to-end
- [x] 2.6 Make feedback chunk IDs deterministic (derived from feedback record id) so re-submission is idempotent

## 3. Confidence Signal & Calibration

- [x] 3.1 Implement `core/feedback/sme_signal.py`: compute SME validation signal from approvals/corrections matching the query (normalized query similarity), neutral 0.5 when no match
- [x] 3.2 Wire `sme_signal` output into the query pipeline's confidence computation (replaces hardcoded neutral when feedback exists)
- [x] 3.3 Add `priority_bonus` in `core/rag/fusion.py` so `source == "sme_feedback"` chunks outrank ordinary chunks of comparable relevance
- [x] 3.4 Implement `core/feedback/calibration.py`: run golden Q&A pairs through the query pipeline, fit adjusted weights via linear regression on per-signal values, clamp to valid ranges
- [x] 3.5 Persist calibrated weights to `calibrated_weights_path` and load them in `core/config.py` when present and enabled
- [x] 3.6 Fall back to configured default weights when calibration file missing or invalid

## 4. Incremental Sync

- [x] 4.1 Add `--incremental` flag to `ingestion/ingest_all.py` that runs per-connector `sync()` (cursor-based) instead of full fetch
- [x] 4.2 Verify first run with no stored cursor processes everything and creates a cursor
- [x] 4.3 Implement `core/sync/scheduler.py` with APScheduler: per-connector intervals from config, single-flight lock per source (skip if already running)
- [x] 4.4 Add entry point `python -m ingestion.scheduler` to start the scheduler independently of the API service
- [x] 4.5 Confirm new entities from delta records resolve via existing identity MERGE (no duplicate nodes); add test coverage

## 5. API Wiring & Feedback Endpoint

- [x] 5.1 Update `services/api/routers/feedback.py` to return processing results (golden chunk added, boost applied, annotation added) in `FeedbackResponse`
- [x] 5.2 Ensure invalid feedback still returns 4xx and stores nothing
- [x] 5.3 Verify `/query` returns feedback chunks with citations (`sme_feedback` origin) and confidence reflects the SME signal

## 6. Tests & Verification

- [x] 6.1 Unit tests: `FeedbackProcessor` per type, `sme_signal` (approval raises, no-feedback neutral), fusion priority bonus, calibration weight fitting + fallback
- [x] 6.2 Unit tests: incremental sync processes only delta records; re-running the same range creates no duplicates
- [x] 6.3 Integration test: ingest → query → POST /feedback correction → re-query returns the golden answer with higher confidence
- [x] 6.4 Integration test: approval round-trip boosts confidence of a subsequent matching query
- [x] 6.5 Verification: run scheduler once manually for each source interval; confirm cursor advances and only new data syncs
- [x] 6.6 Verification: golden pairs calibration produces valid weights file and scoring still works with defaults when it is absent
