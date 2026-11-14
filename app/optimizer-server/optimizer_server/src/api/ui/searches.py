"""Read-only view of historical searches."""

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from ninja import Router, Schema

from optimizer_server.src.apps.searches.models import OUTCOME_FIELDS, Search
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

    # Both come from the latest feedback submission (Search.objects.with_latest_feedback()).
    @staticmethod
    def resolve_feedback(obj: Search):
        if obj.latest_feedback_at is None:
            return None
        return {f: getattr(obj, f"latest_{f}") for f in OUTCOME_FIELDS}

    @staticmethod
    def resolve_feedback_at(obj: Search) -> Optional[datetime]:
        return obj.latest_feedback_at


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
    qs = Search.objects.with_latest_feedback()
    if provider:
        qs = qs.filter(provider=provider)
    # Good / bad / none judge each search by its latest feedback submission only.
    if feedback == "good":
        qs = qs.filter(latest_good=True)
    elif feedback == "bad":
        qs = qs.filter(latest_good=False)
    elif feedback == "none":
        qs = qs.filter(latest_good__isnull=True)
    if category_l1 is not None:
        qs = qs.filter(category_l1__isnull=True) if category_l1 == -1 else qs.filter(category_l1=category_l1)
    if q:
        qs = qs.filter(query__icontains=q)

    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    return {"items": list(qs[offset : offset + limit]), "total": qs.count()}
