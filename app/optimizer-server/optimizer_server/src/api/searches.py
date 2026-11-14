"""Endpoints the SDK calls: route a query, report the dispatch outcome, submit feedback."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, Router, Schema

from optimizer_server.src.apps.searches.models import Feedback, Search
from optimizer_server.src.lib.optimizer import choose_provider
from optimizer_server.src.api.stats import compute_provider_stats

router = Router(tags=["searches"])


class RouteRequest(Schema):
    query: str
    available_providers: List[str] = Field(..., min_length=1)
    client_metadata: Dict[str, Any] = Field(default_factory=dict)


class RouteResponse(Schema):
    search_id: UUID
    provider: str


class OutcomeRequest(Schema):
    latency_ms: float
    num_results: int
    error: Optional[str] = None


class FeedbackRequest(Schema):
    score: float = Field(..., ge=0.0, le=1.0)
    comment: Optional[str] = None


class OkResponse(Schema):
    ok: bool


class FeedbackOut(Schema):
    score: float
    comment: Optional[str]
    created_at: datetime


class SearchOut(Schema):
    id: UUID
    created_at: datetime
    query: str
    available_providers: List[str]
    provider: str
    client_metadata: Dict[str, Any]
    latency_ms: Optional[float]
    num_results: Optional[int]
    error: Optional[str]
    feedback: List[FeedbackOut]


@router.post("/route", response=RouteResponse)
def route(request, body: RouteRequest):
    stats = {s.provider: s for s in compute_provider_stats()}
    provider = choose_provider(body.query, body.available_providers, stats)
    search = Search.objects.create(
        query=body.query,
        available_providers=body.available_providers,
        provider=provider,
        client_metadata=body.client_metadata,
    )
    return {"search_id": search.id, "provider": provider}


@router.post("/{search_id}/outcome", response=OkResponse)
def report_outcome(request, search_id: UUID, body: OutcomeRequest):
    search = get_object_or_404(Search, id=search_id)
    search.latency_ms = body.latency_ms
    search.num_results = body.num_results
    search.error = body.error
    search.outcome_reported_at = timezone.now()
    search.save()
    return {"ok": True}


@router.post("/{search_id}/feedback", response=OkResponse)
def submit_feedback(request, search_id: UUID, body: FeedbackRequest):
    search = get_object_or_404(Search, id=search_id)
    Feedback.objects.create(search=search, score=body.score, comment=body.comment)
    return {"ok": True}


@router.get("", response=List[SearchOut])
def list_searches(request, limit: int = 100):
    return Search.objects.prefetch_related("feedback")[: min(limit, 1000)]
