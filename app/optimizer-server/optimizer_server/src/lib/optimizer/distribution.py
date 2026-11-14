"""Precomputed routing posteriors: compute a snapshot offline, route from it in memory.

    compute_and_save()  run by `optimizer-recompute`. Aggregates all feedback once, computes
                        every cell's posterior with policy.chain(), writes a SearchDistribution.
                        Only counts searches since the latest reset (counts_since).
    reset()             writes a uniform snapshot and starts counting afresh from now
                        (POST /api/admin/reset-search-distribution).
    reload()            run by the server (POST /api/admin/reload-search-distribution, or lazily
                        on the first which_search). Loads the latest snapshot into memory.
    current()           the in-memory snapshot the hot path reads.

The server is a single uvicorn process, so one reload call updates the only copy. With several
workers, each would need to poll for the latest snapshot id instead.
"""

import logging
import threading

import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, Optional, Set, Tuple

from django.db import transaction
from django.utils import timezone
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
    counts = _known(counts)
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


def _known(counts: Dict[CellKey, Counts]) -> Dict[CellKey, Counts]:
    return {k: c for k, c in counts.items() if k[2] in _KNOWN_PROVIDERS}


def own_counts(counts: Dict[CellKey, Counts]) -> Dict[Tuple[Cell, str], int]:
    """Feedback observed at each cell itself, per provider: all of it for the global cell,
    the category's for a level-1 cell, the pair's for a level-2 cell. Not the inherited prior."""
    out: Dict[Tuple[Cell, str], int] = {}

    def add(cell: Cell, p: str, n: int) -> None:
        out[(cell, p)] = out.get((cell, p), 0) + n

    for (c1, c2, p), c in _known(counts).items():
        add(GLOBAL, p, c.n)
        if c1 is not None:
            add((c1, None), p, c.n)
            if c2 is not None:
                add((c1, c2), p, c.n)
    return out


_GRID = (np.arange(4096) + 0.5) / 4096  # bin midpoints on (0, 1)
_LOG_X, _LOG_1MX = np.log(_GRID), np.log1p(-_GRID)


def p_best(by_provider: Dict[str, Beta]) -> Dict[str, float]:
    """P(provider's draw is the highest) for one cell: the share of Thompson picks it gets
    (before EXPLORE_FLOOR). Numerical integration on a fixed grid, so it is deterministic and
    the dashboard's history doesn't jitter between snapshots.

        P(i best) = sum_x pdf_i(x) * prod_{j != i} CDF_j(x)
    """
    names = list(by_provider)
    if len(names) <= 1:
        return {p: 1.0 for p in names}
    a = np.array([by_provider[p].alpha for p in names])[:, None]
    b = np.array([by_provider[p].beta for p in names])[:, None]
    logpdf = (a - 1) * _LOG_X + (b - 1) * _LOG_1MX
    pmf = np.exp(logpdf - logpdf.max(axis=1, keepdims=True))
    pmf /= pmf.sum(axis=1, keepdims=True)
    cdf = np.cumsum(pmf, axis=1) - pmf / 2  # mass strictly below each midpoint, half of ties
    # prod_{j != i} cdf_j without dividing by zero: prefix and suffix products.
    ones = np.ones((1, cdf.shape[1]))
    prefix = np.cumprod(np.vstack([ones, cdf[:-1]]), axis=0)
    suffix = np.cumprod(np.vstack([ones, cdf[::-1][:-1]]), axis=0)[::-1]
    win = (pmf * prefix * suffix).sum(axis=1)
    win /= win.sum()
    return {p: float(w) for p, w in zip(names, win)}


def _fingerprint(since: Optional[datetime]) -> Tuple[int, Optional[datetime]]:
    qs = Feedback.objects.all() if since is None else Feedback.objects.filter(
        search__created_at__gte=since
    )
    agg = qs.aggregate(n=Count("id"), through=Max("created_at"))
    return agg["n"], agg["through"]


def _prune(keep: int, keep_history: int) -> None:
    """The newest `keep` snapshots stay full; older ones up to `keep_history` are thinned to the
    global and level-1 cells (the dashboard's history); anything older is deleted."""
    ids = list(SearchDistribution.objects.values_list("id", flat=True)[: keep_history + 1])
    if len(ids) > keep:
        thin = SearchDistribution.objects.filter(id__lte=ids[keep], full=True)
        SearchDistributionCell.objects.filter(
            distribution__in=thin, category_l2__isnull=False
        ).delete()
        thin.update(full=False)
    if len(ids) > keep_history:
        SearchDistribution.objects.filter(id__lte=ids[keep_history]).delete()


def compute_and_save(
    force: bool = False, keep: int = 20, keep_history: int = 2000
) -> Optional[SearchDistribution]:
    """Write a new snapshot, or return None if no feedback changed since the latest one.

    Counts only searches since the latest snapshot's `counts_since` (the last reset), and
    carries that cutoff forward. See _prune() for retention.
    """
    latest = SearchDistribution.objects.first()
    since = latest.counts_since if latest is not None else None
    n, through = _fingerprint(since)
    if (
        not force
        and latest is not None
        and (latest.num_feedback, latest.feedback_through) == (n, through)
    ):
        return None

    counts = feedback_counts(since)
    posteriors = compute(counts)
    observed = own_counts(counts)
    wins = {cell: p_best(by_provider) for cell, by_provider in posteriors.items()}
    with transaction.atomic():
        # A reset may have landed while we were computing; don't overwrite it with a snapshot
        # built from the pre-reset cutoff. The next run picks up the new cutoff.
        newest = SearchDistribution.objects.first()
        if (newest.id if newest else None) != (latest.id if latest else None):
            return None
        dist = SearchDistribution.objects.create(
            num_feedback=n, feedback_through=through, counts_since=since
        )
        SearchDistributionCell.objects.bulk_create(
            [
                SearchDistributionCell(
                    distribution=dist,
                    category_l1=l1,
                    category_l2=l2,
                    provider=p,
                    alpha=b.alpha,
                    beta=b.beta,
                    p_best=wins[(l1, l2)][p],
                    n_obs=observed.get(((l1, l2), p), 0),
                )
                for (l1, l2), by_provider in posteriors.items()
                for p, b in by_provider.items()
            ],
            batch_size=2000,
        )
        _prune(keep, keep_history)
    return dist


def reset(keep: int = 20, keep_history: int = 2000) -> SearchDistribution:
    """Write a uniform snapshot (Beta(1, 1) for every provider in every cell) and set the
    feedback cutoff to now, so routing starts from scratch and later recomputes only count
    searches made after the reset. Older snapshots and all Search/Feedback rows are kept."""
    now = timezone.now()
    providers = [p.value for p in SearchProvider]
    share = 1.0 / len(providers)
    with transaction.atomic():
        # num_feedback/feedback_through describe "nothing since the cutoff", so recompute
        # leaves this snapshot alone until feedback for a post-reset search arrives.
        dist = SearchDistribution.objects.create(
            num_feedback=0, feedback_through=None, counts_since=now, is_reset=True
        )
        SearchDistributionCell.objects.bulk_create(
            [
                SearchDistributionCell(
                    distribution=dist,
                    category_l1=l1,
                    category_l2=l2,
                    provider=p,
                    alpha=1.0,
                    beta=1.0,
                    p_best=share,
                    n_obs=0,
                )
                for l1, l2 in all_cells()
                for p in providers
            ],
            batch_size=2000,
        )
        _prune(keep, keep_history)
    return dist


# ---- serve (in memory) ----


@dataclass(frozen=True)
class LoadedDistribution:
    # None when no snapshot exists yet; every lookup then falls back to Beta(1, 1).
    id: Optional[int]
    created_at: Optional[datetime]
    num_feedback: int
    cells: Dict[Cell, Dict[str, Beta]] = field(default_factory=dict)
    counts_since: Optional[datetime] = None

    def cell(self, l1: Optional[int], l2: Optional[int]) -> CellPosteriors:
        """The finest precomputed cell for (l1, l2), falling back up the hierarchy."""
        for key in ((l1, l2), (l1, None), GLOBAL):
            found = self.cells.get(key)
            if found is not None:
                return found
        return {}


EMPTY = LoadedDistribution(id=None, created_at=None, num_feedback=0)

_current: Optional[LoadedDistribution] = None
_lock = threading.RLock()  # reentrant: current() holds it while calling reload()


def _load_latest() -> LoadedDistribution:
    dist = SearchDistribution.objects.first()
    if dist is None:
        return EMPTY
    cells: Dict[Cell, Dict[str, Beta]] = {}
    for l1, l2, p, a, b in SearchDistributionCell.objects.filter(distribution=dist).values_list(
        "category_l1", "category_l2", "provider", "alpha", "beta"
    ):
        cells.setdefault((l1, l2), {})[p] = Beta(a, b)
    return LoadedDistribution(dist.id, dist.created_at, dist.num_feedback, cells, dist.counts_since)


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
    if loaded is not None:
        return loaded
    with _lock:  # concurrent first requests: load once, not once per request
        return _current if _current is not None else reload()
