"""Aggregate views over historical searches, for the optimizer and the dashboard."""

from typing import List, Optional

from django.db.models import Count, Q
from ninja import Router, Schema

from optimizer_server.src.apps.searches.models import Feedback, Search
from optimizer_server.src.lib.optimizer import ProviderStats

router = Router(tags=["dashboard"])


class ProviderStatsOut(Schema):
    provider: str
    num_searches: int
    num_feedback: int
    num_good: int
    good_rate: Optional[float]


def compute_provider_stats() -> List[ProviderStats]:
    searches = {
        row["provider"]: row["n"]
        for row in Search.objects.values("provider").annotate(n=Count("id"))
    }
    feedback = {
        row["search__provider"]: row
        for row in Feedback.objects.values("search__provider").annotate(
            n=Count("id"), good=Count("id", filter=Q(is_good=True))
        )
    }
    return [
        ProviderStats(
            provider=provider,
            num_searches=n,
            num_feedback=feedback.get(provider, {}).get("n", 0),
            num_good=feedback.get(provider, {}).get("good", 0),
        )
        for provider, n in searches.items()
    ]


@router.get("/providers", response=List[ProviderStatsOut])
def provider_stats(request):
    return compute_provider_stats()
