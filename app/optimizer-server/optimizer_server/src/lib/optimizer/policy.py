"""Routing policy: pick which search provider a query should go to.

Starts as epsilon-greedy over mean feedback score per provider. This is the piece
we'll iterate on (per-query features, contextual bandits, cost/latency tradeoffs, ...).
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
    mean_score: float | None
    mean_latency_ms: float | None


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

    # Exploit: best mean feedback score.
    return max(available_providers, key=lambda p: stats[p].mean_score or 0.0)
