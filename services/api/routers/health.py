from __future__ import annotations

from fastapi import APIRouter, Depends

from services.api.deps import AppState, get_state
from services.api.models import DependencyStatus, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(state: AppState = Depends(get_state)) -> HealthResponse:
    dependencies = DependencyStatus(
        vector="ok" if state.vector_store.is_healthy() else "error",
        graph="ok" if state.graph_store.is_healthy() else "error",
        feedback="ok" if state.feedback_store.is_healthy() else "error",
    )
    overall = "ok" if all(
        status == "ok"
        for status in (dependencies.vector, dependencies.graph, dependencies.feedback)
    ) else "degraded"
    return HealthResponse(
        status=overall,
        service="orgbot-api",
        dependencies=dependencies,
    )
