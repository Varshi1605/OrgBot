from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from services.api.deps import AppState, get_state
from services.api.models import Confidence, QueryRequest, QueryResponse, SourceCitation

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest, state: AppState = Depends(get_state)) -> QueryResponse:
    try:
        result = state.pipeline.answer(payload.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"query failed: {exc}") from exc
    confidence = result["confidence"]
    return QueryResponse(
        question=result["question"],
        answer=result["answer"],
        confidence=Confidence(**confidence),
        sources=[SourceCitation(**source) for source in result["sources"]],
        graph_path=result["graph_path"],
    )
