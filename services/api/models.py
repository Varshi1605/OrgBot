from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class SourceCitation(BaseModel):
    origin: str
    kind: str
    excerpt: str
    score: float


class Confidence(BaseModel):
    score: float
    signals: dict[str, float]
    low_confidence: bool
    high_confidence: bool
    threshold: float


class QueryResponse(BaseModel):
    question: str
    answer: str
    confidence: Confidence
    sources: list[SourceCitation]
    graph_path: list[str]


class FeedbackRequest(BaseModel):
    query: str = Field(min_length=1)
    original_answer: str = ""
    sme_answer: str = ""
    feedback_type: Literal["correction", "approval", "annotation"]
    sme_id: str = Field(min_length=1)
    source_origins: list[str] = []


class FeedbackResponse(BaseModel):
    id: int
    query: str
    original_answer: str
    sme_answer: str
    feedback_type: str
    sme_id: str
    created_at: str
    processing: dict | None = None


class GraphExploreResponse(BaseModel):
    found: bool
    entity: str | None = None
    labels: list[str] = []
    outbound: list[dict] = []
    inbound: list[dict] = []


class IngestRequest(BaseModel):
    source: Literal["git", "slack", "incident", "docs"]


class IngestResponse(BaseModel):
    source: str
    records: int
    chunks: int
    entities: int


class DependencyStatus(BaseModel):
    vector: str
    graph: str
    feedback: str


class HealthResponse(BaseModel):
    status: str
    service: str
    dependencies: DependencyStatus
