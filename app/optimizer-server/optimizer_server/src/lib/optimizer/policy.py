"""Routing policy: hierarchical Thompson sampling over (category, provider).

Each provider's chance of `is_good` feedback is modelled per routing cell with a Beta
distribution. Cells are nested:

    global (per provider)  ->  level-1 category  ->  level-2 subcategory

A cell's prior is its parent cell's posterior, scaled down to at most PRIOR_STRENGTH
pseudo-observations. So a sparse subcategory behaves like its parent category (which routes
most traffic to that category's best providers), and drifts away only as its own evidence
accumulates. No hand-tuned pruning or significance thresholds.

To route: draw one sample from each available provider's Beta and pick the max. With
probability EXPLORE_FLOOR, pick uniformly instead, so every provider keeps getting some
traffic (catches providers that change over time).

Posteriors are not computed per request. `optimizer-recompute` builds every cell's posterior
(see distribution.py) into a SearchDistribution snapshot; the server holds the latest one in
memory and `choose_provider` only looks up Betas and draws from them. The draw must stay per
request: caching one choice per cell between refreshes would turn this into greedy routing.
"""

import random
from dataclasses import dataclass
from typing import List, Mapping, Optional, Tuple

PRIOR_STRENGTH = 20.0
EXPLORE_FLOOR = 0.05


@dataclass(frozen=True)
class Counts:
    good: int = 0
    bad: int = 0

    @property
    def n(self) -> int:
        return self.good + self.bad

    def __add__(self, other: "Counts") -> "Counts":
        return Counts(self.good + other.good, self.bad + other.bad)


@dataclass
class ProviderStats:
    provider: str
    num_searches: int
    num_feedback: int
    num_good: int

    @property
    def good_rate(self) -> float | None:
        return self.num_good / self.num_feedback if self.num_feedback else None


@dataclass(frozen=True)
class Beta:
    alpha: float
    beta: float

    def shrink(self, strength: float = PRIOR_STRENGTH) -> "Beta":
        """Same mean, at most `strength` total pseudo-observations."""
        total = self.alpha + self.beta
        scale = min(1.0, strength / total)
        return Beta(self.alpha * scale, self.beta * scale)

    def update(self, c: Counts) -> "Beta":
        return Beta(self.alpha + c.good, self.beta + c.bad)

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)


UNIFORM = Beta(1.0, 1.0)

# (category_l1, category_l2, provider) -> counts
CellCounts = Mapping[Tuple[Optional[int], Optional[int], str], Counts]


def posterior(
    counts: CellCounts, provider: str, l1: Optional[int], l2: Optional[int]
) -> Beta:
    """Posterior for `provider` at the finest cell given, built down the hierarchy."""
    global_c = Counts()
    l1_c = Counts()
    l2_c = Counts()
    for (c1, c2, p), c in counts.items():
        if p != provider:
            continue
        global_c += c
        if l1 is not None and c1 == l1:
            l1_c += c
            if l2 is not None and c2 == l2:
                l2_c += c

    return chain(global_c, l1_c if l1 is not None else None, l2_c if l2 is not None else None)


def chain(global_c: Counts, l1_c: Optional[Counts], l2_c: Optional[Counts]) -> Beta:
    """Posterior down the hierarchy: global, then the level-1 cell, then the level-2 cell.
    Pass None for a level the cell does not go down to."""
    post = UNIFORM.update(global_c)
    if l1_c is not None:
        post = post.shrink().update(l1_c)
        if l2_c is not None:
            post = post.shrink().update(l2_c)
    return post


# Precomputed posteriors for one routing cell: provider -> Beta. A provider missing from it has
# no feedback anywhere, so its posterior is UNIFORM.
CellPosteriors = Mapping[str, Beta]


def choose_provider(
    available_providers: List[str],
    cell: CellPosteriors,
    rng: random.Random = random._inst,
) -> str:
    """Thompson-sample one provider using precomputed posteriors. No counting happens here."""
    if not available_providers:
        raise ValueError("available_providers must be non-empty")
    if rng.random() < EXPLORE_FLOOR:
        return rng.choice(available_providers)

    def draw(provider: str) -> float:
        b = cell.get(provider, UNIFORM)
        return rng.betavariate(b.alpha, b.beta)

    return max(available_providers, key=draw)
