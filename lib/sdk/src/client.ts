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
}

export interface SearchOptions {
  /**
   * Google Trends category id (@searchhacks/types QueryCategory) to use instead of having the
   * optimizer classify the query. For callers that already know it, e.g. the mock driver.
   */
  overrideQueryCategory?: number;
}

export interface SearchResponse {
  /** Pass this back to `submitFeedback()`. */
  feedbackToken: string;
  provider: string;
  results: SearchResult[];
}

/**
 * The SDK's core loop:
 *   1. which_search: ask the optimizer which provider to use for this query
 *   2. dispatch the query to that provider
 * The caller later reports result quality via `submitFeedback()`.
 */
export class SearchHacksClient {
  private readonly api: OptimizerClient;
  private readonly providers: Map<string, SearchProvider>;

  constructor(options: SearchHacksClientOptions) {
    if (options.providers.length === 0) {
      throw new Error("SearchHacksClient requires at least one provider");
    }
    this.api = createOptimizerClient(options.optimizerUrl);
    this.providers = new Map(options.providers.map((p) => [p.name, p]));
  }

  async search(query: string, options: SearchOptions = {}): Promise<SearchResponse> {
    const { data, error } = await this.api.POST("/api/which_search", {
      body: {
        query,
        available_providers: [...this.providers.keys()],
        override_query_category: options.overrideQueryCategory ?? null,
      },
    });
    if (!data) {
      throw new Error(`which_search failed: ${JSON.stringify(error)}`);
    }

    const provider = this.providers.get(data.provider);
    if (!provider) {
      throw new Error(`optimizer chose unknown provider: ${data.provider}`);
    }

    const results = await provider.search(query);
    return { feedbackToken: data.feedback_token, provider: provider.name, results };
  }

  /** Report whether a previous search's results were good. */
  async submitFeedback(feedbackToken: string, isGood: boolean): Promise<void> {
    const { error } = await this.api.POST("/api/submit_feedback", {
      body: { feedback_token: feedbackToken, is_good: isGood },
    });
    if (error) {
      throw new Error(`submit_feedback failed: ${JSON.stringify(error)}`);
    }
  }
}
