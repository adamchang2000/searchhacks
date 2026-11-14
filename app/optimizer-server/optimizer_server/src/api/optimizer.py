"""The optimizer protocol proper: what the SDK / drivers call.

    which_search     query -> provider to use + feedback_token
    submit_feedback  feedback_token + is_good
"""

from typing import List, Optional
from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Field, Router, Schema
from ninja.errors import HttpError

from optimizer_server.src.apps.searches.models import Feedback, Search
from optimizer_server.src.lib.classifier import classify
from optimizer_server.src.lib.optimizer import categories, choose_provider
from optimizer_server.src.lib.optimizer.stats import feedback_counts

router = Router(tags=["optimizer"])


class WhichSearchRequest(Schema):
    query: str
    # Providers the caller is able to dispatch to; the optimizer picks one of these.
    available_providers: List[str] = Field(..., min_length=1)
    # Google Trends category id (lib/types QueryCategory) to use instead of classifying the
    # query. For callers that already know the category, e.g. the mock driver, so that
    # synthetic traffic doesn't pay for classification.
    override_query_category: Optional[int] = None


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
    provider = choose_provider(body.available_providers, feedback_counts(), l1, l2)
    search = Search.objects.create(
        query=body.query,
        available_providers=body.available_providers,
        provider=provider,
        category_l1=l1,
        category_l2=l2,
        category_source=source,
    )
    return {"provider": provider, "feedback_token": search.id}


@router.post("/submit_feedback", response=SubmitFeedbackResponse)
def submit_feedback(request, body: SubmitFeedbackRequest):
    search = get_object_or_404(Search, id=body.feedback_token)
    Feedback.objects.update_or_create(search=search, defaults={"is_good": body.is_good})
    return {"ok": True}
