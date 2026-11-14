"""Operational endpoints. Mounted at /api/admin/. Not part of the SDK protocol."""

from datetime import datetime
from typing import Optional

from ninja import Router, Schema

from optimizer_server.src.lib.optimizer import distribution

router = Router(tags=["admin"])


class SearchDistributionStatus(Schema):
    # None when no snapshot has been computed yet (routing is then uniform).
    distribution_id: Optional[int]
    computed_at: Optional[datetime]
    num_feedback: int
    num_cells: int
    # Searches created before this don't count (set by the last reset). Null: all count.
    counts_since: Optional[datetime]


def _status(d: distribution.LoadedDistribution) -> dict:
    return {
        "distribution_id": d.id,
        "computed_at": d.created_at,
        "num_feedback": d.num_feedback,
        "num_cells": len(d.cells),
        "counts_since": d.counts_since,
    }


@router.post("/reload-search-distribution", response=SearchDistributionStatus)
def reload_search_distribution(request):
    """Load the latest SearchDistribution snapshot into memory. Called by optimizer-recompute."""
    return _status(distribution.reload())


@router.post("/reset-search-distribution", response=SearchDistributionStatus)
def reset_search_distribution(request):
    """Route uniformly from now on: write a Beta(1, 1) snapshot, start counting feedback afresh
    (only searches after now), and load it. History and Search/Feedback rows are kept."""
    distribution.reset()
    return _status(distribution.reload())


@router.get("/search-distribution", response=SearchDistributionStatus)
def search_distribution(request):
    """The snapshot the server is currently routing with."""
    return _status(distribution.current())
