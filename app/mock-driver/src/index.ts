/**
 * Mock driver: stands in for the AI chatbot so we can generate lots of synthetic search +
 * feedback traffic against the optimizer without LLM, classification or search-provider costs.
 *
 * Each synthetic query has a known (top-level category, subcategory), sent to the optimizer as
 * override_query_category. Feedback is drawn from a hidden TruthTable (seeded), so we can check
 * whether the optimizer learns each category's best provider.
 *
 *   npm start -w @searchhacks/mock-driver -- --n 5000 --concurrency 8 --seed 1
 */
import { parseArgs } from "node:util";
import { SEARCH_PROVIDERS, type SearchProvider } from "@searchhacks/types/search-provider";
import type { QueryCategory } from "@searchhacks/types/query-category";
import { SearchHacksClient } from "@searchhacks/sdk";
import { canonicalSubcategories, label, TOP_LEVEL } from "./categories.ts";
import { MockProvider } from "./mockProviders.ts";
import { pick, seededRandom } from "./rng.ts";
import { type Cell, TruthTable } from "./truth.ts";

const { values } = parseArgs({
  options: {
    server: { type: "string", default: "http://localhost:8000" },
    n: { type: "string", default: "1000" },
    concurrency: { type: "string", default: "8" },
    // Seeds the hidden truth table. Keep it fixed across runs against the same DB.
    seed: { type: "string", default: "1" },
    // Use only the N most popular top-level categories (traffic is Zipf-skewed).
    categories: { type: "string", default: String(TOP_LEVEL.length) },
    "latency-ms": { type: "string", default: "20" },
  },
});

const total = Number(values.n);
const concurrency = Number(values.concurrency);

const truth = new TruthTable(seededRandom(Number(values.seed)), SEARCH_PROVIDERS);
const providers = SEARCH_PROVIDERS.map((p) => new MockProvider(p, Number(values["latency-ms"])));
const client = new SearchHacksClient({ optimizerUrl: values.server!, providers });

// Popularity order is part of the seeded world too, so it's stable across runs.
const shuffle = seededRandom(Number(values.seed) + 1);
const categories = [...TOP_LEVEL]
  .sort(() => shuffle() - 0.5)
  .slice(0, Number(values.categories));
const zipf = categories.map((_, i) => 1 / (i + 1));
const zipfTotal = zipf.reduce((a, b) => a + b, 0);

function sampleCell(): Cell {
  let r = Math.random() * zipfTotal;
  let top = categories[0];
  for (let i = 0; i < categories.length; i++) {
    if ((r -= zipf[i]) <= 0) {
      top = categories[i];
      break;
    }
  }
  const subs = canonicalSubcategories(top);
  return { top, sub: subs.length ? pick(Math.random, subs) : null };
}

// routed[cellKey][provider] over the second half of the run, when routing should have converged.
const routed = new Map<string, Map<SearchProvider, number>>();
let issued = 0;
let good = 0;
let errors = 0;

async function worker() {
  while (issued < total) {
    const i = issued++;
    const cell = sampleCell();
    const category = cell.sub ?? cell.top;
    try {
      const res = await client.search(`synthetic ${label(category)} query #${i}`, {
        overrideQueryCategory: category,
      });
      const provider = res.provider;
      const isGood = Math.random() < truth.probGood(cell, provider);
      good += Number(isGood);
      await client.submitFeedback(res.feedbackToken, { user_confirmed_outcome: isGood });
      if (i >= total / 2) {
        const k = `${cell.top}/${cell.sub ?? ""}`;
        const m = routed.get(k) ?? new Map();
        m.set(provider, (m.get(provider) ?? 0) + 1);
        routed.set(k, m);
      }
    } catch (e) {
      errors++;
      if (errors <= 5) console.warn(String(e));
    }
  }
}

const start = Date.now();
await Promise.all(Array.from({ length: concurrency }, worker));
const secs = (Date.now() - start) / 1000;

// ---- Report: did routing in the second half find each category's true best provider? ----
function summarize(filter: (top: QueryCategory, sub: QueryCategory | null) => boolean) {
  let hits = 0;
  let n = 0;
  for (const [k, m] of routed) {
    const [topS, subS] = k.split("/");
    const cell: Cell = {
      top: Number(topS) as QueryCategory,
      sub: subS ? (Number(subS) as QueryCategory) : null,
    };
    if (!filter(cell.top, cell.sub)) continue;
    const best = truth.best(cell);
    for (const [p, c] of m) {
      n += c;
      if (p === best) hits += c;
    }
  }
  return n ? `${((100 * hits) / n).toFixed(1)}% of ${n}` : "n/a";
}

console.log(
  `\n${total} searches in ${secs.toFixed(1)}s (${(total / secs).toFixed(0)}/s), ` +
    `${errors} errors, overall good rate ${((100 * good) / Math.max(1, total - errors)).toFixed(1)}%`,
);
console.log(`Routed to the true best provider (second half of run):`);
console.log(`  all cells:                ${summarize(() => true)}`);
console.log(`  specialist subcategories: ${summarize((_, s) => s !== null && truth.specialist.has(s))}`);
console.log(`  random-choice baseline:   ${(100 / SEARCH_PROVIDERS.length).toFixed(1)}%`);
console.log(`\nTop categories (popularity order): true winner -> most-routed in second half`);
for (const top of categories.slice(0, 8)) {
  const m = new Map<SearchProvider, number>();
  for (const [k, pm] of routed) {
    if (!k.startsWith(`${top}/`)) continue;
    for (const [p, c] of pm) m.set(p, (m.get(p) ?? 0) + c);
  }
  const n = [...m.values()].reduce((a, b) => a + b, 0);
  const [mostP, mostC] = [...m].sort((a, b) => b[1] - a[1])[0] ?? ["-", 0];
  console.log(
    `  ${label(top).padEnd(26)} ${truth.winner.get(top)!.padEnd(10)} -> ${String(mostP).padEnd(10)} ` +
      `(${n ? ((100 * mostC) / n).toFixed(0) : 0}% of ${n})`,
  );
}
