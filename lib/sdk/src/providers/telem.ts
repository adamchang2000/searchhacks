import type { SearchProvider, SearchResult } from "./types.ts";

export interface TelemProviderOptions {
  apiKey: string;
  baseUrl?: string;
  numResults?: number;
  /** Underlying Telem provider slug, such as exa or brave. */
  provider: string;
}

type TelemRun = { output_payload?: Record<string, unknown> | null };
type TelemResponse = { preprocessor_runs?: TelemRun[] };

export class TelemProvider implements SearchProvider {
  readonly name: string;

  constructor(private readonly options: TelemProviderOptions) {
    this.name = options.provider;
  }

  async search(query: string): Promise<SearchResult[]> {
    const base = (this.options.baseUrl ?? "https://hack.telem.ai/api").replace(/\/+$/, "");
    const response = await fetch(`${base}/v1/search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.options.apiKey}`,
      },
      body: JSON.stringify({
        user_input: { query },
        search: { providers: { include: [this.name] }, num_results: this.options.numResults ?? 5 },
      }),
    });
    if (!response.ok) {
      const detail = (await response.text()).slice(0, 500);
      throw new Error(`Telem search failed (HTTP ${response.status}): ${detail}`);
    }
    const data = (await response.json()) as TelemResponse;
    return (data.preprocessor_runs ?? [])
      .flatMap((run) => {
        const output = run.output_payload ?? {};
        const items = (output.results ?? output.organic ?? []) as Record<string, unknown>[];
        return items.map((item) => ({
          title: String(item.title ?? item.name ?? item.url ?? "Search result"),
          url: String(item.url ?? item.link ?? ""),
          snippet: String(item.snippet ?? item.description ?? item.content ?? ""),
        }));
      })
      .filter((result) => result.url.length > 0)
      .slice(0, this.options.numResults ?? 5);
  }
}
