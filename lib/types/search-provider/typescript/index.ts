// Search providers that Telem can route a search to.
//
// Values are Telem's provider slugs, as accepted by `search.providers.include`.
// Source: https://docs.telem.ai/resources/search-parameters/#providers
// Keep in sync with ../python/__init__.py.

export const SearchProvider = {
  BRAVE: "brave",
  CERAMIC: "ceramic",
  EXA: "exa",
  LINKUP: "linkup",
  PARALLEL: "parallel",
  PERPLEXITY: "perplexity",
  SELTZ: "seltz",
  SERPAPI: "serpapi",
  TAVILY: "tavily",
  TINYFISH: "tinyfish",
  YOU: "you",
} as const;

export type SearchProvider = (typeof SearchProvider)[keyof typeof SearchProvider];

export const SEARCH_PROVIDERS: readonly SearchProvider[] = Object.values(SearchProvider);
