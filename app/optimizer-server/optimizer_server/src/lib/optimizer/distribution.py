"""Precomputed routing posteriors: compute a snapshot offline, route from it in memory.

    compute_and_save()  run by `optimizer-recompute`. Aggregates all feedback once, computes
                        every cell's posterior with policy.chain(), writes a SearchDistribution.
    reload()            run by the server (POST /api/admin/reload-search-distribution, or lazily
                        on the first which_search). Loads the latest snapshot into memory.
    current()           the in-memory snapshot the hot path reads.

The server is a single uvicorn process, so one reload call updates the only copy. With several
workers, each would need to poll for the latest snapshot id instead.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, Optional, Set, Tuple

from django.db import transaction
from django.db.models import Count, Max, Q

from searchhacks_types.search_provider import SearchProvider

from optimizer_server.src.apps.searches.models import (
    Feedback,
    SearchDistribution,
    SearchDistributionCell,
)
from optimizer_server.src.lib.optimizer import categories
from optimizer_server.src.lib.optimizer.policy import Beta, CellPosteriors, Counts, chain
from optimizer_server.src.lib.optimizer.stats import CellKey, feedback_counts

logger = logging.getLogger(__name__)

Cell = Tuple[Optional[int], Optional[int]]  # (category_l1, category_l2)
GLOBAL: Cell = (None, None)
_KNOWN_PROVIDERS = frozenset(p.value for p in SearchProvider)


# ---- compute (offline) ----


def all_cells(extra: Iterable[Cell] = ()) -> Set[Cell]:
    """Global, every level-1 category, every (level-1, child) pair, plus any cell seen in data."""
    cells: Set[Cell] = {GLOBAL}
    for l1 in categories.top_level():
        cells.add((l1, None))
        for l2 in categories.children(l1):
            cells.add((l1, l2))
    cells.update(extra)
    return cells


def compute(counts: Dict[CellKey, Counts]) -> Dict[Cell, Dict[str, Beta]]:
    """Every cell's posterior per provider. Same result as policy.posterior() for each cell.

    Feedback for providers outside SearchProvider (e.g. old test rows) is ignored: which_search
    no longer accepts them, so their posteriors could never be used.
    """
    counts = {k: c for k, c in counts.items() if k[2] in _KNOWN_PROVIDERS}
    global_c: Dict[str, Counts] = {}
    l1_c: Dict[Tuple[int, str], Counts] = {}
    l2_c: Dict[Tuple[int, int, str], Counts] = {}
    for (c1, c2, p), c in counts.items():
        global_c[p] = global_c.get(p, Counts()) + c
        if c1 is not None:
            l1_c[(c1, p)] = l1_c.get((c1, p), Counts()) + c
            if c2 is not None:
                l2_c[(c1, c2, p)] = l2_c.get((c1, c2, p), Counts()) + c

    seen = {(c1, c2) for (c1, c2, _) in counts} | {(c1, None) for (c1, _, _) in counts}
    out: Dict[Cell, Dict[str, Beta]] = {}
    for l1, l2 in all_cells(seen):
        if l1 is None and l2 is not None:
            continue  # not a routable cell
        out[(l1, l2)] = {
            p: chain(
                g,
                l1_c.get((l1, p), Counts()) if l1 is not None else None,
                l2_c.get((l1, l2, p), Counts()) if l2 is not None else None,
            )
            for p, g in global_c.items()
        }
    return out


def _fingerprint() -> Tuple[int, Optional[datetime]]:
    agg = Feedback.objects.aggregate(n=Count("id"), through=Max("created_at"))
    return agg["n"], agg["through"]


def compute_and_save(force: bool = False, keep: int = 20) -> Optional[SearchDistribution]:
    """Write a new snapshot, or return None if no feedback changed since the latest one."""
    n, through = _fingerprint()
    latest = SearchDistribution.objects.first()
    if (
        not force
        and latest is not None
        and (latest.num_feedback, latest.feedback_through) == (n, through)
    ):
        return None

    posteriors = compute(feedback_counts())
    with transaction.atomic():
        dist = SearchDistribution.objects.create(num_feedback=n, feedback_through=through)
        SearchDistributionCell.objects.bulk_create(
            [
                SearchDistributionCell(
                    distribution=dist,
                    category_l1=l1,
                    category_l2=l2,
                    provider=p,
                    alpha=b.alpha,
                    beta=b.beta,
                )
                for (l1, l2), by_provider in posteriors.items()
                for p, b in by_provider.items()
            ],
            batch_size=2000,
        )
        stale = SearchDistribution.objects.values_list("id", flat=True)[keep:]
        SearchDistribution.objects.filter(id__in=list(stale)).delete()
    return dist


# ---- serve (in memory) ----


@dataclass(frozen=True)
class LoadedDistribution:
    # None when no snapshot exists yet; every lookup then falls back to Beta(1, 1).
    id: Optional[int]
    created_at: Optional[datetime]
    num_feedback: int
    cells: Dict[Cell, Dict[str, Beta]] = field(default_factory=dict)

    def cell(self, l1: Optional[int], l2: Optional[int]) -> CellPosteriors:
        """The finest precomputed cell for (l1, l2), falling back up the hierarchy."""
        for key in ((l1, l2), (l1, None), GLOBAL):
            found = self.cells.get(key)
            if found is not None:
                return found
        return {}


EMPTY = LoadedDistribution(id=None, created_at=None, num_feedback=0)

_current: Optional[LoadedDistribution] = None
_lock = threading.Lock()


def _load_latest() -> LoadedDistribution:
    dist = SearchDistribution.objects.first()
    if dist is None:
        return EMPTY
    cells: Dict[Cell, Dict[str, Beta]] = {}
    for l1, l2, p, a, b in SearchDistributionCell.objects.filter(distribution=dist).values_list(
        "category_l1", "category_l2", "provider", "alpha", "beta"
    ):
        cells.setdefault((l1, l2), {})[p] = Beta(a, b)
    return LoadedDistribution(dist.id, dist.created_at, dist.num_feedback, cells)


def reload() -> LoadedDistribution:
    """Load the latest snapshot and swap it in. Requests in flight keep the one they read."""
    global _current
    loaded = _load_latest()
    with _lock:
        _current = loaded
    logger.info("loaded search distribution %s (%d cells)", loaded.id, len(loaded.cells))
    return loaded


def current() -> LoadedDistribution:
    """The in-memory snapshot. Loads it on first use, so a fresh server needs no reload call."""
    loaded = _current
    return loaded if loaded is not None else reload()
