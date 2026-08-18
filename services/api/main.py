from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.api.deps import get_state, reset_state
from services.api.routers import feedback, graph, health, ingest, query


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_state()
    yield
    reset_state()


app = FastAPI(title="OrgBot API", version="0.1.0", lifespan=lifespan)

app.include_router(query.router)
app.include_router(feedback.router)
app.include_router(graph.router)
app.include_router(ingest.router)
app.include_router(health.router)
