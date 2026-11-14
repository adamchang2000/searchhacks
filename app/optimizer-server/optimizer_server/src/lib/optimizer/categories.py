"""The two levels of the Google Trends hierarchy the optimizer routes on.

Level 1 ("top-level"): the 25 direct children of the root, e.g. Sports, Finance.
Level 2 ("subcategory"): the direct children of a level-1 category, e.g. Sports > Team Sports.

The source hierarchy is a DAG (some categories have several parents), so a deeper category is
placed at its canonical path (first appearance in the source).
"""

from functools import cache
from typing import Dict, List, NamedTuple, Optional

from searchhacks_types.query_category import (
    QUERY_CATEGORY_LABELS,
    QUERY_CATEGORY_PARENTS,
    QUERY_CATEGORY_PATHS,
    QueryCategory,
)

ROOT = QueryCategory.ALL_CATEGORIES


class CategoryPath(NamedTuple):
    l1: int
    l2: Optional[int]  # None when the category is itself top-level


@cache
def top_level() -> List[int]:
    return [int(c) for c, parents in QUERY_CATEGORY_PARENTS.items() if ROOT in parents]


@cache
def _children() -> Dict[int, List[int]]:
    children: Dict[int, List[int]] = {}
    for c, parents in QUERY_CATEGORY_PARENTS.items():
        for p in parents:
            children.setdefault(int(p), []).append(int(c))
    return children


def children(category: int) -> List[int]:
    return _children().get(category, [])


def label(category: int) -> str:
    return QUERY_CATEGORY_LABELS[QueryCategory(category)]


def is_known(category: int) -> bool:
    return category in QueryCategory._value2member_map_


def resolve(category: int) -> Optional[CategoryPath]:
    """Place any category id at (level 1, level 2). None for the root (no category)."""
    if category == ROOT:
        return None
    if category in top_level():
        return CategoryPath(category, None)
    path = [int(c) for c in QUERY_CATEGORY_PATHS[QueryCategory(category)]]
    return CategoryPath(path[1], path[2])
