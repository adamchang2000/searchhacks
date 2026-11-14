"""Read-only view of historical searches, for the dashboard."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from ninja import Router, Schema

from optimizer_server.src.apps.searches.models import Search

router = Router(tags=["dashboard"])


class SearchOut(Schema):
    id: UUID
    created_at: datetime
    query: str
    available_providers: List[str]
    provider: str
    is_good: Optional[bool]

    @staticmethod
    def resolve_is_good(obj: Search) -> Optional[bool]:
        feedback = getattr(obj, "feedback", None)
        return feedback.is_good if feedback is not None else None


@router.get("", response=List[SearchOut])
def list_searches(request, limit: int = 100):
    return Search.objects.select_related("feedback")[: min(limit, 1000)]
