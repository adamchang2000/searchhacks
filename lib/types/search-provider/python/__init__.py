"""Search providers that Telem can route a search to.

Values are Telem's provider slugs, as accepted by `search.providers.include`.
Source: https://docs.telem.ai/resources/search-parameters/#providers
Keep in sync with ../typescript/index.ts.
"""

from enum import StrEnum


class SearchProvider(StrEnum):
    BRAVE = "brave"
    CERAMIC = "ceramic"
    EXA = "exa"
    LINKUP = "linkup"
    PARALLEL = "parallel"
    PERPLEXITY = "perplexity"
    SELTZ = "seltz"
    SERPAPI = "serpapi"
    TAVILY = "tavily"
    TINYFISH = "tinyfish"
    YOU = "you"


__all__ = ["SearchProvider"]
