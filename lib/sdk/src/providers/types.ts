export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
}

/** A backend that can actually execute a web search (telem, mocks, ...). */
export interface SearchProvider {
  /** Stable identifier; this is what the optimizer routes on. */
  readonly name: string;
  search(query: string): Promise<SearchResult[]>;
}
