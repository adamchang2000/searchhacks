"""Aggregate views over historical searches, for the optimizer and the dashboard."""

from typing import List, Optional

from django.db.models import Avg, Count
from ninja import Router, Schema

from optimizer_server.src.apps.searches.models import Feedback, Search
from optimizer_server.src.lib.optimizer import ProviderStats

router = Router(tags=["stats"])


class ProviderStatsOut(Schema):
    provider: str
    num_searches: int
    num_feedback: int
    mean_score: Optional[float]
    mean_latency_ms: Optional[float]


def compute_provider_stats() -> List[ProviderStats]:
    searches = {
        row["provider"]: row
        for row in Search.objects.values("provider").annotate(
            n=Count("id"), latency=Avg("latency_ms")
        )
    }
    feedback = {
        row["search__provider"]: row
        for row in Feedback.objects.values("search__provider").annotate(
            n=Count("id"), score=Avg("score")
        )
    }
    return [
        ProviderStats(
            provider=provider,
            num_searches=row["n"],
            num_feedback=feedback.get(provider, {}).get("n", 0),
            mean_score=feedback.get(provider, {}).get("score"),
            mean_latency_ms=row["latency"],
        )
        for provider, row in searches.items()
    ]


@router.get("/providers", response=List[ProviderStatsOut])
def provider_stats(request):
    return compute_provider_stats()
