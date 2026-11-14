"""Routing policy: pick which search provider a query should go to.

Starts as epsilon-greedy over each provider's fraction of `is_good` feedback. This is the
piece we'll iterate on (per-query features, contextual bandits, cost/latency tradeoffs, ...).
"""

import random
from dataclasses import dataclass
from typing import Dict, List

EPSILON = 0.1


@dataclass
class ProviderStats:
    provider: str
    num_searches: int
    num_feedback: int
    num_good: int

    @property
    def good_rate(self) -> float | None:
        return self.num_good / self.num_feedback if self.num_feedback else None


def choose_provider(
    query: str,
    available_providers: List[str],
    stats: Dict[str, ProviderStats],
) -> str:
    if not available_providers:
        raise ValueError("available_providers must be non-empty")

    # Explore: any provider with no feedback yet, or with probability EPSILON.
    unexplored = [
        p for p in available_providers if p not in stats or stats[p].num_feedback == 0
    ]
    if unexplored:
        return random.choice(unexplored)
    if random.random() < EPSILON:
        return random.choice(available_providers)

    # Exploit: highest fraction of good feedback.
    return max(available_providers, key=lambda p: stats[p].good_rate or 0.0)
