import {
  createOptimizerClient,
  type OptimizerClient,
} from "@searchhacks/optimizer-protocol";
import type { SearchProvider, SearchResult } from "./providers/types.ts";

export interface SearchHacksClientOptions {
  /** Base URL of the optimizer server, e.g. http://localhost:8000 */
  optimizerUrl: string;
  /** Providers this client can dispatch to. The optimizer picks among them. */
  providers: SearchProvider[];
  /** Free-form info attached to every routed search (client name, session id, ...). */
  clientMetadata?: Record<string, unknown>;
}

export interface SearchResponse {
  /** Pass this back to `feedback()`. */
  searchId: string;
  provider: string;
  results: SearchResult[];
}

/**
 * The SDK's core loop:
 *   1. ask the optimizer which provider to use for this query
 *   2. dispatch the query to that provider
 *   3. report the outcome (latency, result count, error) back to the optimizer
 * The caller later reports result quality via `feedback()`.
 */
export class SearchHacksClient {
  private readonly api: OptimizerClient;
  private readonly providers: Map<string, SearchProvider>;

  constructor(private readonly options: SearchHacksClientOptions) {
    if (options.providers.length === 0) {
      throw new Error("SearchHacksClient requires at least one provider");
    }
    this.api = createOptimizerClient(options.optimizerUrl);
    this.providers = new Map(options.providers.map((p) => [p.name, p]));
  }

  async search(query: string): Promise<SearchResponse> {
    const { data: route, error: routeError } = await this.api.POST(
      "/api/searches/route",
      {
        body: {
          query,
          available_providers: [...this.providers.keys()],
          client_metadata: this.options.clientMetadata ?? {},
        },
      },
    );
    if (!route) {
      throw new Error(`optimizer route failed: ${JSON.stringify(routeError)}`);
    }

    const provider = this.providers.get(route.provider);
    if (!provider) {
      throw new Error(`optimizer chose unknown provider: ${route.provider}`);
    }

    const start = performance.now();
    let results: SearchResult[] = [];
    let error: string | null = null;
    try {
      results = await provider.search(query);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
    const latencyMs = performance.now() - start;

    await this.api.POST("/api/searches/{search_id}/outcome", {
      params: { path: { search_id: route.search_id } },
      body: { latency_ms: latencyMs, num_results: results.length, error },
    });

    if (error !== null) {
      throw new Error(`provider ${provider.name} failed: ${error}`);
    }
    return { searchId: route.search_id, provider: provider.name, results };
  }

  /** Report result quality for a previous search. `score` is in [0, 1]. */
  async feedback(searchId: string, score: number, comment?: string): Promise<void> {
    const { error } = await this.api.POST("/api/searches/{search_id}/feedback", {
      params: { path: { search_id: searchId } },
      body: { score, comment: comment ?? null },
    });
    if (error) {
      throw new Error(`optimizer feedback failed: ${JSON.stringify(error)}`);
    }
  }
}
