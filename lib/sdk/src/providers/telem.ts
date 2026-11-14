import type { SearchProvider, SearchResult } from "./types.ts";

export interface TelemProviderOptions {
  apiKey: string;
  baseUrl?: string;
}

export class TelemProvider implements SearchProvider {
  readonly name = "telem";

  constructor(private readonly options: TelemProviderOptions) {}

  async search(query: string): Promise<SearchResult[]> {
    // TODO: wire up the real telem search API and map its response to SearchResult[].
    void this.options;
    void query;
    throw new Error("TelemProvider.search is not implemented yet");
  }
}
