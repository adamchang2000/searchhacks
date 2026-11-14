"""The optimizer protocol proper: what the SDK / drivers call.

    which_search     query -> provider to use + feedback_token
    submit_feedback  feedback_token + optional outcome record
"""

from typing import List, Optional
from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Field, Router, Schema
from ninja.errors import HttpError
from pydantic import ConfigDict, StrictBool

from searchhacks_types.search_provider import SearchProvider

from optimizer_server.src.apps.searches.models import Feedback, Search
from optimizer_server.src.lib.classifier import classify
from optimizer_server.src.lib.optimizer import categories, choose_provider, distribution

router = Router(tags=["optimizer"])


class WhichSearchRequest(Schema):
    query: str
    # Providers the caller is able to dispatch to; the optimizer picks one of these.
    # Typed with lib/types SearchProvider, so the OpenAPI schema (and the generated TS in
    # lib/optimizer-protocol) carries the provider enum and unknown names are rejected (422).
    available_providers: List[SearchProvider] = Field(..., min_length=1)
    # Google Trends category id (lib/types QueryCategory) to use instead of classifying the
    # query. For callers that already know the category, e.g. the mock driver, so that
    # synthetic traffic doesn't pay for classification.
    override_query_category: Optional[int] = None


class WhichSearchResponse(Schema):
    provider: SearchProvider
    # Opaque; pass it back to submit_feedback.
    feedback_token: UUID


class FeedbackRecord(Schema):
    model_config = ConfigDict(extra="forbid")
    purchase_conversion: Optional[StrictBool] = None
    user_confirmed_outcome: Optional[StrictBool] = None
    user_stopped_following_up: Optional[StrictBool] = None


class SubmitFeedbackRequest(Schema):
    feedback_token: UUID
    feedback: FeedbackRecord


class SubmitFeedbackResponse(Schema):
    ok: bool


@router.post("/which_search", response=WhichSearchResponse)
def which_search(request, body: WhichSearchRequest):
    if body.override_query_category is not None:
        if not categories.is_known(body.override_query_category):
            raise HttpError(422, f"unknown query category: {body.override_query_category}")
        path = categories.resolve(body.override_query_category)
        source = "override"
    else:
        classification = classify(body.query)
        if classification is None:
            path, source = None, "unclassified"
        else:
            path = categories.CategoryPath(classification.l1, classification.l2)
            source = classification.source

    l1, l2 = (path.l1, path.l2) if path is not None else (None, None)
    # Hot path: look up the precomputed posteriors (in memory) and Thompson-sample. No feedback
    # aggregation here; `optimizer-recompute` refreshes the snapshot out of band.
    cell = distribution.current().cell(l1, l2)
    available = [p.value for p in body.available_providers]
    provider = choose_provider(available, cell)
    search = Search.objects.create(
        query=body.query,
        available_providers=available,
        provider=provider,
        category_l1=l1,
        category_l2=l2,
        category_source=source,
    )
    return {"provider": provider, "feedback_token": search.id}


@router.post("/submit_feedback", response=SubmitFeedbackResponse)
def submit_feedback(request, body: SubmitFeedbackRequest):
    search = get_object_or_404(Search, id=body.feedback_token)
    updates = body.feedback.model_dump(exclude_unset=True)
    if not updates or any(value is None for value in updates.values()):
        raise HttpError(422, "Supply at least one observed boolean outcome; omit unknown fields")
    # Append-only: every submission is a new row; readers use the latest one per search.
    Feedback.objects.create(search=search, **updates)
    return {"ok": True}
