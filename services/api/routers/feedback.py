from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from services.api.deps import AppState, get_state
from services.api.models import FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(payload: FeedbackRequest, state: AppState = Depends(get_state)) -> FeedbackResponse:
    try:
        record = state.feedback_handler.submit(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FeedbackResponse(**record)
