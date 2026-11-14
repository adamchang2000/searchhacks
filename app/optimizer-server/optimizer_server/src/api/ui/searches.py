"""Read-only view of historical searches."""

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from ninja import Router, Schema

from optimizer_server.src.apps.searches.models import Search

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
    is_good: Optional[bool]
    feedback_at: Optional[datetime]

    @staticmethod
    def resolve_is_good(obj: Search) -> Optional[bool]:
        feedback = getattr(obj, "feedback", None)
        return feedback.is_good if feedback is not None else None

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
    if feedback == "good":
        qs = qs.filter(feedback__is_good=True)
    elif feedback == "bad":
        qs = qs.filter(feedback__is_good=False)
    elif feedback == "none":
        qs = qs.filter(feedback__isnull=True)
    if category_l1 is not None:
        qs = qs.filter(category_l1__isnull=True) if category_l1 == -1 else qs.filter(category_l1=category_l1)
    if q:
        qs = qs.filter(query__icontains=q)

    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    return {"items": list(qs[offset : offset + limit]), "total": qs.count()}
