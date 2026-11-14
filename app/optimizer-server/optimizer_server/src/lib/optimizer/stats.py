"""Feedback counts over historical searches."""

from typing import Dict, List, Optional, Tuple

from django.db.models import Count, Q

from optimizer_server.src.apps.searches.models import Feedback, Search
from optimizer_server.src.lib.optimizer.policy import Counts, ProviderStats

CellKey = Tuple[Optional[int], Optional[int], str]  # (category_l1, category_l2, provider)


def feedback_counts() -> Dict[CellKey, Counts]:
    """good/bad counts per (category_l1, category_l2, provider), the finest level we route on."""
    observed = Q(purchase_conversion__isnull=False) | Q(user_confirmed_outcome__isnull=False) | Q(user_stopped_following_up__isnull=False)
    positive = Q(purchase_conversion=True) | Q(user_confirmed_outcome=True) | Q(user_stopped_following_up=True)
    rows = Feedback.objects.filter(observed).values(
        "search__category_l1", "search__category_l2", "search__provider"
    ).annotate(n=Count("id"), good=Count("id", filter=positive))
    return {
        (r["search__category_l1"], r["search__category_l2"], r["search__provider"]): Counts(
            good=r["good"], bad=r["n"] - r["good"]
        )
        for r in rows
    }


def compute_provider_stats() -> List[ProviderStats]:
    """Global per-provider stats (all categories), for the dashboard."""
    searches = {
        row["provider"]: row["n"]
        for row in Search.objects.values("provider").annotate(n=Count("id"))
    }
    totals: Dict[str, Counts] = {}
    for (_, _, provider), c in feedback_counts().items():
        totals[provider] = totals.get(provider, Counts()) + c
    return [
        ProviderStats(
            provider=provider,
            num_searches=n,
            num_feedback=totals.get(provider, Counts()).n,
            num_good=totals.get(provider, Counts()).good,
        )
        for provider, n in searches.items()
    ]
