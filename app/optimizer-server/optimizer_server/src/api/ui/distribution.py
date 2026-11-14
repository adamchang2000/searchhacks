"""Routing snapshots over time, for the dashboard's Optimizer tab.

    GET /api/ui/distribution/history?l1=<id>     one cell (global, or a level-1 category)
                                                  across snapshots: Beta + P(best) per provider
    GET /api/ui/distribution/{id}/categories      one snapshot: the global cell and every
                                                  level-1 cell, for the category heatmap
"""

from datetime import datetime
from typing import Dict, List, Optional

from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from optimizer_server.src.apps.searches.models import SearchDistribution, SearchDistributionCell

router = Router()


class ProviderPosteriorOut(Schema):
    alpha: float
    beta: float
    # Share of Thompson picks this provider wins in the cell (before the 5% exploration).
    p_best: float
    # Feedback observed in exactly this cell (not inherited from the parent category).
    n_obs: int


class SnapshotOut(Schema):
    id: int
    created_at: datetime
    # Written by POST /api/admin/reset-search-distribution: uniform, counting starts afresh.
    is_reset: bool
    by_provider: Dict[str, ProviderPosteriorOut]


class DistributionHistoryOut(Schema):
    # The cell: l1 null means the global cell.
    l1: Optional[int]
    snapshots: List[SnapshotOut]  # oldest first


def _rows(ids, **cell):
    out: Dict[int, Dict[str, dict]] = {i: {} for i in ids}
    rows = SearchDistributionCell.objects.filter(distribution_id__in=ids, **cell).values_list(
        "distribution_id", "provider", "alpha", "beta", "p_best", "n_obs"
    )
    for d, p, a, b, w, n in rows:
        out[d][p] = {"alpha": a, "beta": b, "p_best": w, "n_obs": n}
    return out


@router.get("/history", response=DistributionHistoryOut)
def history(request, l1: Optional[int] = None, max_points: int = 240):
    """Evenly thinned to at most `max_points` snapshots. The latest and every reset snapshot are
    always included (the dashboard replays from the last reset)."""
    snaps = list(
        SearchDistribution.objects.order_by("id").values_list("id", "created_at", "is_reset")
    )
    if len(snaps) > max_points > 1:
        step = (len(snaps) - 1) / (max_points - 1)
        keep = {round(i * step) for i in range(max_points)}
        keep |= {i for i, s in enumerate(snaps) if s[2]}
        snaps = [snaps[i] for i in sorted(keep)]
    rows = _rows([i for i, _, _ in snaps], category_l1=l1, category_l2__isnull=True)
    return {
        "l1": l1,
        "snapshots": [
            {"id": i, "created_at": t, "is_reset": r, "by_provider": rows[i]} for i, t, r in snaps
        ],
    }


class CategoryCellOut(Schema):
    l1: Optional[int]  # null for the global cell
    by_provider: Dict[str, ProviderPosteriorOut]


class SnapshotCategoriesOut(Schema):
    id: int
    created_at: datetime
    cells: List[CategoryCellOut]


@router.get("/{int:distribution_id}/categories", response=SnapshotCategoriesOut)
def categories(request, distribution_id: int):
    dist = get_object_or_404(SearchDistribution, id=distribution_id)
    cells: Dict[Optional[int], Dict[str, dict]] = {}
    for l1, p, a, b, w, n in SearchDistributionCell.objects.filter(
        distribution=dist, category_l2__isnull=True
    ).values_list("category_l1", "provider", "alpha", "beta", "p_best", "n_obs"):
        cells.setdefault(l1, {})[p] = {"alpha": a, "beta": b, "p_best": w, "n_obs": n}
    return {
        "id": dist.id,
        "created_at": dist.created_at,
        "cells": [{"l1": l1, "by_provider": by} for l1, by in cells.items()],
    }
