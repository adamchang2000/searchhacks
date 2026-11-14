/**
 * Mock driver: stands in for the AI chatbot so we can generate lots of synthetic
 * search + feedback traffic against the optimizer without LLM or search-provider costs.
 *
 *   npm start -w @searchhacks/mock-driver -- --n 500 --concurrency 8
 */
import { parseArgs } from "node:util";
import { SearchHacksClient } from "@searchhacks/sdk";
import { defaultMockProviders, type MockProvider } from "./mockProviders.ts";
import { sampleQueries } from "./queries.ts";

const { values } = parseArgs({
  options: {
    server: { type: "string", default: "http://localhost:8000" },
    n: { type: "string", default: "100" },
    concurrency: { type: "string", default: "4" },
  },
});

const total = Number(values.n);
const concurrency = Number(values.concurrency);

const providers = new Map(defaultMockProviders.map((p) => [p.name, p]));
const client = new SearchHacksClient({
  optimizerUrl: values.server!,
  providers: defaultMockProviders,
  clientMetadata: { client: "mock-driver" },
});

/** Synthetic feedback: the provider's hidden quality plus noise, clamped to [0, 1]. */
function scoreFor(provider: MockProvider): number {
  const noise = (Math.random() - 0.5) * 0.3;
  return Math.min(1, Math.max(0, provider.trueQuality + noise));
}

let issued = 0;
const counts: Record<string, number> = {};

async function worker() {
  while (issued < total) {
    issued++;
    const query = sampleQueries[Math.floor(Math.random() * sampleQueries.length)];
    try {
      const res = await client.search(query);
      counts[res.provider] = (counts[res.provider] ?? 0) + 1;
      await client.feedback(res.searchId, scoreFor(providers.get(res.provider)!));
    } catch (e) {
      console.warn(String(e));
    }
  }
}

await Promise.all(Array.from({ length: concurrency }, worker));
console.log("searches routed per provider:", counts);
