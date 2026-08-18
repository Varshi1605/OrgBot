from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from core.connectors.base import BaseConnector
from ingestion.ingest_all import CONNECTORS, collect_records
from services.api.deps import AppState, get_state
from services.api.models import IngestRequest, IngestResponse

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
def trigger_ingest(payload: IngestRequest, state: AppState = Depends(get_state)) -> IngestResponse:
    connector_cls: type[BaseConnector] = CONNECTORS[payload.source]
    data_dir = Path(state.config.ingestion.get("data_dir", "data/simulated"))
    connector = connector_cls(cursor_store=state.feedback_store, data_dir=data_dir)
    records_with_chunks = collect_records(connector, state.ingestion_pipeline.chunker)
    totals = state.ingestion_pipeline.process_records(records_with_chunks)
    return IngestResponse(
        source=payload.source,
        records=totals["records"],
        chunks=totals["chunks"],
        entities=totals["entities"],
    )
