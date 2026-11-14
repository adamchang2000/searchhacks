import type { SearchProvider, SearchResult } from "@searchhacks/sdk";

/**
 * A fake provider with a hidden "true quality" and latency profile. The mock driver
 * scores results using that hidden quality, so we can check whether the optimizer
 * learns to prefer the better providers.
 */
export class MockProvider implements SearchProvider {
  constructor(
    readonly name: string,
    readonly trueQuality: number,
    readonly meanLatencyMs: number,
    readonly failureRate = 0,
  ) {}

  async search(query: string): Promise<SearchResult[]> {
    const latency = this.meanLatencyMs * (0.5 + Math.random());
    await new Promise((r) => setTimeout(r, latency));
    if (Math.random() < this.failureRate) {
      throw new Error(`${this.name}: simulated failure`);
    }
    return Array.from({ length: 5 }, (_, i) => ({
      title: `[${this.name}] result ${i + 1} for "${query}"`,
      url: `https://example.com/${this.name}/${i + 1}`,
      snippet: `Mock snippet from ${this.name}.`,
    }));
  }
}

export const defaultMockProviders = [
  new MockProvider("mock-good", 0.85, 300),
  new MockProvider("mock-fast", 0.6, 50),
  new MockProvider("mock-flaky", 0.75, 200, 0.2),
  new MockProvider("mock-bad", 0.3, 150),
];
