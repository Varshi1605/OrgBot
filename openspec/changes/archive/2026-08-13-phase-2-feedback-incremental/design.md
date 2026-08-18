## Context

See proposal.md - Why. Phase 1 delivered a working ingestion pipeline (chunk → extract → embed → persist), a hybrid RAG query engine with a configurable composite confidence scorer, a FastAPI API, and PostgreSQL-backed cursors plus a feedback table. Today `/feedback` only validates and stores records; the confidence scorer's SME signal is hardcoded to neutral (0.5); ingestion reads full datasets; nothing runs on a schedule. Phase 2 makes feedback actually influence answers and makes ingestion incremental and scheduled, reusing the existing stores and pipeline.

Current seams that this change builds on:
- `core/storage/postgres.py` already has `cursors` and `feedback` tables and cursor get/set.
- `core/connectors/base.py` already exposes `sync()` with cursor handling.
- `core/confidence/scorer.py` accepts an `sme_validation` signal (defaults neutral) and weights from config.
- ChromaDB upserts are idempotent by chunk ID; Neo4j `ingest_entities` uses normalized-identity MERGE.
- `core/rag/fusion.py` fuses vector + graph evidence and ranks by score.

## Goals / Non-Goals

**Goals:**
- Feedback (correction/approval/annotation) is persisted AND acted on: golden answers become high-priority chunks, approvals boost evidence, annotations add context.
- The SME confidence signal reflects real feedback when present; weights are calibratable from golden Q&A pairs.
- Ingestion runs incrementally on a schedule (Slack 15m, Git hourly, incidents daily), each connector processing only data newer than its cursor.
- New entities during incremental sync are resolved against existing graph nodes.
- Everything remains testable offline (offline embedding hash, stub extraction, no external services required for unit tests).

**Non-Goals:**
- Slack bot interaction / live Slack ingestion (Phase 3).
- Golden Q&A benchmark of 20 pairs and correlation measurement (Phase 3, Step 10).
- Feedback-driven graph changes (feedback writes to the graph store) — feedback affects vector store + confidence only in this phase.
- Multi-tenant or RBAC semantics for feedback.

## Decisions

### D1: Feedback is processed through a dedicated `FeedbackProcessor` before persistence
Extend `core/feedback/handler.py`: `submit()` keeps validation + persistence, then dispatches by type:
- correction → build a `SourceRecord` from the SME answer and run it through the existing `IngestionPipeline.process_record` with metadata `{source: "sme_feedback", priority: "high", feedback_id, query}`.
- approval → record the approved query+sources; a `boost` mapping (query key → boost factor) is stored in PostgreSQL and consumed by the scorer.
- annotation → same pipeline as correction but with `{source: "sme_feedback", priority: "normal", kind: "annotation"}`.
Rationale: reuses the exact same chunk/embed/vector pipeline, guaranteeing feedback chunks are retrievable and cited like any source. Alternative: separate feedback vector collection — rejected because fusion/citations assume one collection.

### D2: High-priority feedback chunks win ties via a fusion priority boost
`core/rag/fusion.py` gains a small score adjustment: chunks whose metadata has `source == "sme_feedback"` get a configurable priority bonus (e.g., +0.05) before the final sort, applied on top of their similarity score.
Rationale: ChromaDB returns by similarity only; the spec requires feedback chunks to outrank ordinary chunks of comparable relevance. Alternative: ChromaDB `where` filters per priority — rejected as it would exclude ordinary chunks entirely.

### D3: SME confidence signal computed from the feedback store, not hardcoded
`ConfidenceScorer.score()` keeps its pure signature. A new `core/feedback/sme_signal.py` computes the signal by matching the current query against stored approvals/corrections (normalized query text similarity), returning >0.5 for approved-and-supported queries and ≤0.5 for queries with corrections (SME contradicted the prior answer), neutral 0.5 when no feedback matches.
Rationale: keeps the scorer pure/unit-testable and centralizes feedback semantics. Alternative: fetch feedback inside the scorer — rejected (I/O in a pure module).
Note: in Phase 2 the signal is query-similarity-based; source-chunk approval boosting (per-D1 approval) is stored and used as an additional input where source metadata is available.

### D4: Confidence calibration as a standalone offline job with persisted weights
Add `core/feedback/calibration.py`: reads golden Q&A pairs (corrections with known-good answers), runs them through the query pipeline, compares predicted correctness (confidence) to actual correctness, and fits new weights via linear regression over the per-signal values. Writes a calibrated weights file consumed by config loading (config overrides defaults; calibration overrides config when present and enabled).
Rationale: satisfies the calibration requirement without coupling to request-time scoring. Alternative: gradient descent on live traffic — rejected as overkill for a POC.

### D5: Incremental sync reuses the existing connector `sync()` + cursor plumbing
APScheduler (`core/sync/scheduler.py`) runs `connector.sync(chunker)` on the configured interval per source. Cursors already persist in PostgreSQL; connectors already advance them. New `--incremental` flag on `ingestion.ingest_all` makes the orchestrator call per-connector `sync()` instead of full-fetch. First sync with no cursor naturally processes everything (already the behavior).
Rationale: zero new sync machinery; the Phase 1 design already built cursor-based sync. Alternative: separate sync service — rejected; a scheduler in-process with the API service is sufficient for a POC.

### D6: Schedules and priorities live in config
`config/config.yaml` gains `sync: {slack: {interval_minutes: 15}, git: {interval_minutes: 60}, incidents: {interval_minutes: 1440}}`, `feedback: {priority_bonus: 0.05, golden_priority: "high"}`, and `confidence.calibrated_weights_path`.
Rationale: one place to tune; mirrors D14 of Phase 1. Alternative: hardcoded — rejected.

### D7: New-entity resolution reuses existing identity MERGE
No new resolution code: `ingest_entities` already MERGEs on normalized identity (`core/identity.canonical_key`). Incremental sync simply runs the same pipeline on delta records, so new data references to known entities update existing nodes and unknown entities create new ones.
Rationale: satisfies the entity-resolution requirement for free. Alternative: a separate dedup pass — rejected as duplication.

## Risks / Trade-offs

- [Feedback chunks pollute ordinary retrieval (SME answers may be wrong)] → Corrections are curated golden answers; the priority bonus is small and configurable; annotations are marked `kind` so citations remain traceable.
- [Approval→boost mapping is query-text-based and can over/under-match] → Matching uses normalized query similarity with a configurable threshold; mismatch degrades to neutral, not to worse scoring.
- [Calibration regression may produce degenerate weights (e.g., negatives, >1)] → Calibration clamps weights to valid ranges and falls back to defaults on failure.
- [Scheduled sync overlaps with manual `/ingest` or a long-running sync] → Scheduler skips a source if a sync for it is already running (single-flight lock via in-memory flag; cursors make re-runs idempotent anyway).
- [APScheduler runs inside the API process; a crash loses scheduled runs] → Acceptable for POC; schedules restart on process start; note as a Phase 3 production concern (dedicated worker).

## Migration Plan

No data migration: Phase 1 schema already has `cursors` and `feedback` tables; feedback chunks and boost rows are additive. Rollout:
1. Extend config with sync/feedback/calibration sections (defaults preserve current behavior).
2. Deploy feedback processing + scorer signal + fusion bonus; verify `/feedback` round-trip (correction → re-query returns the golden answer with higher confidence).
3. Add calibration job; run once over golden pairs; verify weights load.
4. Add scheduler + `--incremental`; verify delta-only sync and idempotent re-run.
Rollback: disable scheduler and calibration in config; feedback processing is additive and reversible by deleting feedback chunks.

## Open Questions

- Exact similarity threshold for approval→query matching: implementation detail tunable in config; does not change specs or tasks.
- Whether calibration should use scipy/sklearn linear regression or a hand-rolled least-squares: depends on whether the project wants a new dependency; resolvable at implementation time without affecting behavior.
- Whether the scheduler lives in the API service process or a separate entry point: small decision affecting packaging only; default is a separate `python -m ingestion.scheduler` entry so tests and CI can run it independently.
