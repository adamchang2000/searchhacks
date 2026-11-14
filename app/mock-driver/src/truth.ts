import type { QueryCategory } from "@searchhacks/types/query-category";
import type { SearchProvider } from "@searchhacks/types/search-provider";
import { canonicalSubcategories, TOP_LEVEL } from "./categories.ts";
import { pick } from "./rng.ts";

/**
 * The hidden ground truth the optimizer is supposed to discover: P(is_good) for each
 * (top-level category, subcategory, provider).
 *
 *   - Each top-level category has one clear winner (WINNER_QUALITY); the rest are mediocre.
 *   - Subcategories inherit their category's qualities, plus a little noise...
 *   - ...except SPECIALIST_RATE of them, where the category's winner is mediocre and a
 *     different provider is best, in that subcategory only. These test whether routing
 *     can deviate from the parent category.
 */
export const WINNER_QUALITY = 0.85;
export const SPECIALIST_QUALITY = 0.92;
export const SPECIALIST_RATE = 0.25;
// The category winner's quality inside a specialist subcategory.
export const MEDIOCRE_IN_SPECIALIST = 0.4;

export interface Cell {
  top: QueryCategory;
  sub: QueryCategory | null;
}

export class TruthTable {
  readonly winner = new Map<QueryCategory, SearchProvider>();
  readonly specialist = new Map<QueryCategory, SearchProvider>();
  private readonly quality = new Map<string, number>();

  constructor(rand: () => number, readonly providers: readonly SearchProvider[]) {
    for (const top of TOP_LEVEL) {
      const winner = pick(rand, providers);
      this.winner.set(top, winner);
      const base = new Map<SearchProvider, number>();
      for (const p of providers) {
        base.set(p, p === winner ? WINNER_QUALITY : 0.3 + rand() * 0.3);
        this.quality.set(key(top, null, p), base.get(p)!);
      }
      for (const sub of canonicalSubcategories(top)) {
        const specialist =
          rand() < SPECIALIST_RATE ? pick(rand, providers.filter((p) => p !== winner)) : null;
        if (specialist) this.specialist.set(sub, specialist);
        for (const p of providers) {
          const q =
            p === specialist
              ? SPECIALIST_QUALITY
              : specialist && p === winner
                ? MEDIOCRE_IN_SPECIALIST
                : Math.min(0.95, Math.max(0.05, base.get(p)! + (rand() - 0.5) * 0.1));
          this.quality.set(key(top, sub, p), q);
        }
      }
    }
  }

  probGood(cell: Cell, provider: SearchProvider): number {
    return this.quality.get(key(cell.top, cell.sub, provider))!;
  }

  best(cell: Cell): SearchProvider {
    return this.providers.reduce((a, b) => (this.probGood(cell, b) > this.probGood(cell, a) ? b : a));
  }
}

function key(top: QueryCategory, sub: QueryCategory | null, p: SearchProvider): string {
  return `${top}/${sub ?? "-"}/${p}`;
}
