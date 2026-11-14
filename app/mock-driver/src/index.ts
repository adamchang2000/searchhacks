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
});

/** Synthetic feedback: results are "good" with probability equal to the provider's hidden quality. */
function isGood(provider: MockProvider): boolean {
  return Math.random() < provider.trueQuality;
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
      await client.submitFeedback(res.feedbackToken, isGood(providers.get(res.provider)!));
    } catch (e) {
      console.warn(String(e));
    }
  }
}

await Promise.all(Array.from({ length: concurrency }, worker));
console.log("searches routed per provider:", counts);
