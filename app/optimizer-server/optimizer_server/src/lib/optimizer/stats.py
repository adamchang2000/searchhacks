"""Feedback counts over historical searches."""

from typing import Dict, List, Optional, Tuple

from django.db.models import Count, Q

from optimizer_server.src.apps.searches.models import Search
from optimizer_server.src.lib.optimizer.policy import Counts, ProviderStats

CellKey = Tuple[Optional[int], Optional[int], str]  # (category_l1, category_l2, provider)


def feedback_counts() -> Dict[CellKey, Counts]:
    """good/bad counts per (category_l1, category_l2, provider), the finest level we route on.

    One vote per search, from its latest feedback submission; earlier submissions are ignored.
    """
    rows = (
        Search.objects.with_latest_feedback()
        .filter(latest_good__isnull=False)
        .values("category_l1", "category_l2", "provider")
        .annotate(n=Count("id"), good=Count("id", filter=Q(latest_good=True)))
        .order_by()
    )
    return {
        (r["category_l1"], r["category_l2"], r["provider"]): Counts(
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
