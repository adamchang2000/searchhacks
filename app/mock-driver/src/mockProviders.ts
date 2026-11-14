import type { SearchProvider as ProviderSlug } from "@searchhacks/types/search-provider";
import type { SearchProvider, SearchResult } from "@searchhacks/sdk";

/**
 * Stand-in for a real search provider: returns canned results after a short delay.
 * Result *quality* isn't modelled here; the driver decides is_good from the TruthTable.
 */
export class MockProvider implements SearchProvider {
  constructor(
    readonly name: ProviderSlug,
    private readonly latencyMs: number,
  ) {}

  async search(query: string): Promise<SearchResult[]> {
    await new Promise((r) => setTimeout(r, this.latencyMs * (0.5 + Math.random())));
    return Array.from({ length: 3 }, (_, i) => ({
      title: `[${this.name}] result ${i + 1} for "${query}"`,
      url: `https://example.com/${this.name}/${i + 1}`,
      snippet: `Mock snippet from ${this.name}.`,
    }));
  }
}
