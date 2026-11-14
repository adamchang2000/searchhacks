import type { SearchProvider as ProviderSlug } from "@searchhacks/types/search-provider";

export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
}

/** A backend that can actually execute a web search (telem, mocks, ...). */
export interface SearchProvider {
  /** Telem provider slug (lib/types SearchProvider); this is what the optimizer routes on. */
  readonly name: ProviderSlug;
  search(query: string): Promise<SearchResult[]>;
}
