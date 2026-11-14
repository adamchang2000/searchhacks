"""Classify a search query into the category hierarchy with TypeSafe's jev decision model.

Two sequential `choice` questions (a choice question takes at most 255 options):
  1. which of the 25 top-level categories
  2. which of that category's subcategories (if it has any)
Each call is ~100-150ms. Docs: https://docs.typesafe.ai/primitives/choice
"""

import logging
import os
from dataclasses import dataclass
from typing import List, Optional

import httpx

from optimizer_server.src.lib.optimizer import categories

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
TIMEOUT_S = 3.0
INSTRUCTIONS = "Which topic category best describes what this web search query is about?"

_client = httpx.Client(timeout=TIMEOUT_S)


@dataclass
class Classification:
    l1: int
    l2: Optional[int]
    # Model version that answered, e.g. "jev-1.14.0".
    source: str


def _ask(api_key: str, query: str, options: List[int]) -> tuple[int, str]:
    resp = _client.post(
        ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": MODEL,
            "state": query,
            "questions": {
                "category": {
                    "type": "choice",
                    "instructions": INSTRUCTIONS,
                    "criteria": {str(c): categories.label(c) for c in options},
                }
            },
        },
    )
    resp.raise_for_status()
    body = resp.json()
    return int(body["answers"]["category"]["choice"]), body["model"]


def classify(query: str) -> Optional[Classification]:
    """Returns None (never raises) if jev is unconfigured or fails, so routing can fall back."""
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        logger.warning("TYPESAFE_API_KEY not set; skipping classification")
        return None
    try:
        l1, model = _ask(api_key, query, categories.top_level())
        subs = categories.children(l1)
        l2 = _ask(api_key, query, subs)[0] if subs else None
        return Classification(l1=l1, l2=l2, source=model)
    except Exception:
        logger.exception("jev classification failed")
        return None
