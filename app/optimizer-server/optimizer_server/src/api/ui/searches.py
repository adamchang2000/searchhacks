"""Read-only view of historical searches."""

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from ninja import Router, Schema
from django.db.models import Q

from optimizer_server.src.apps.searches.models import Search
from optimizer_server.src.api.optimizer import FeedbackRecord

router = Router()


class SearchOut(Schema):
    id: UUID
    created_at: datetime
    query: str
    available_providers: List[str]
    provider: str
    category_l1: Optional[int]
    category_l2: Optional[int]
    category_source: str
    feedback: Optional[FeedbackRecord]
    feedback_at: Optional[datetime]

    @staticmethod
    def resolve_feedback(obj: Search):
        feedback = getattr(obj, "feedback", None)
        return {key: getattr(feedback, key) for key in ("purchase_conversion", "user_confirmed_outcome", "user_stopped_following_up")} if feedback is not None else None

    @staticmethod
    def resolve_feedback_at(obj: Search) -> Optional[datetime]:
        feedback = getattr(obj, "feedback", None)
        return feedback.created_at if feedback is not None else None


class SearchPageOut(Schema):
    items: List[SearchOut]
    total: int


FeedbackFilter = Literal["good", "bad", "none"]


@router.get("", response=SearchPageOut)
def list_searches(
    request,
    limit: int = 50,
    offset: int = 0,
    provider: Optional[str] = None,
    feedback: Optional[FeedbackFilter] = None,
    category_l1: Optional[int] = None,
    q: Optional[str] = None,
):
    """Newest first. `category_l1=-1` selects unclassified searches."""
    qs = Search.objects.select_related("feedback")
    if provider:
        qs = qs.filter(provider=provider)
    positive = Q(feedback__purchase_conversion=True) | Q(feedback__user_confirmed_outcome=True) | Q(feedback__user_stopped_following_up=True)
    observed = Q(feedback__purchase_conversion__isnull=False) | Q(feedback__user_confirmed_outcome__isnull=False) | Q(feedback__user_stopped_following_up__isnull=False)
    if feedback == "good":
        qs = qs.filter(positive)
    elif feedback == "bad":
        qs = qs.filter(observed).exclude(positive)
    elif feedback == "none":
        qs = qs.exclude(observed)
    if category_l1 is not None:
        qs = qs.filter(category_l1__isnull=True) if category_l1 == -1 else qs.filter(category_l1=category_l1)
    if q:
        qs = qs.filter(query__icontains=q)

    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    return {"items": list(qs[offset : offset + limit]), "total": qs.count()}
