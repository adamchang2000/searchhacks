"""Per-provider aggregates over historical searches + feedback."""

from typing import List

from django.db.models import Count, Q

from optimizer_server.src.apps.searches.models import Feedback, Search
from optimizer_server.src.lib.optimizer.policy import ProviderStats


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
