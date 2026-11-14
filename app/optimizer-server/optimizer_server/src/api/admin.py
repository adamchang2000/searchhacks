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


def _status(d: distribution.LoadedDistribution) -> dict:
    return {
        "distribution_id": d.id,
        "computed_at": d.created_at,
        "num_feedback": d.num_feedback,
        "num_cells": len(d.cells),
    }


@router.post("/reload-search-distribution", response=SearchDistributionStatus)
def reload_search_distribution(request):
    """Load the latest SearchDistribution snapshot into memory. Called by optimizer-recompute."""
    return _status(distribution.reload())


@router.get("/search-distribution", response=SearchDistributionStatus)
def search_distribution(request):
    """The snapshot the server is currently routing with."""
    return _status(distribution.current())
