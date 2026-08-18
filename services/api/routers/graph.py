from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from services.api.deps import AppState, get_state
from services.api.models import GraphExploreResponse

router = APIRouter(tags=["graph"])


@router.get("/graph/explore", response_model=GraphExploreResponse)
def explore(entity: str = Query(min_length=1), state: AppState = Depends(get_state)) -> GraphExploreResponse:
    try:
        result = state.graph_store.entity_neighborhood(entity)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"graph exploration failed: {exc}") from exc
    if not result.get("found"):
        raise HTTPException(status_code=404, detail=f"entity not found: {entity}")
    return GraphExploreResponse(**result)
