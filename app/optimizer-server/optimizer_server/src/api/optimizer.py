"""The optimizer protocol proper: what the SDK / drivers call.

    which_search     query -> provider to use + feedback_token
    submit_feedback  feedback_token + is_good
"""

from typing import List
from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Field, Router, Schema

from optimizer_server.src.api.stats import compute_provider_stats
from optimizer_server.src.apps.searches.models import Feedback, Search
from optimizer_server.src.lib.optimizer import choose_provider

router = Router(tags=["optimizer"])


class WhichSearchRequest(Schema):
    query: str
    # Providers the caller is able to dispatch to; the optimizer picks one of these.
    available_providers: List[str] = Field(..., min_length=1)


class WhichSearchResponse(Schema):
    provider: str
    # Opaque; pass it back to submit_feedback.
    feedback_token: UUID


class SubmitFeedbackRequest(Schema):
    feedback_token: UUID
    is_good: bool


class SubmitFeedbackResponse(Schema):
    ok: bool


@router.post("/which_search", response=WhichSearchResponse)
def which_search(request, body: WhichSearchRequest):
    stats = {s.provider: s for s in compute_provider_stats()}
    provider = choose_provider(body.query, body.available_providers, stats)
    search = Search.objects.create(
        query=body.query,
        available_providers=body.available_providers,
        provider=provider,
    )
    return {"provider": provider, "feedback_token": search.id}


@router.post("/submit_feedback", response=SubmitFeedbackResponse)
def submit_feedback(request, body: SubmitFeedbackRequest):
    search = get_object_or_404(Search, id=body.feedback_token)
    Feedback.objects.update_or_create(search=search, defaults={"is_good": body.is_good})
    return {"ok": True}
