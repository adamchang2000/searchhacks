/**
 * Beta-distribution helpers for the Optimizer tab. Everything is computed on a fixed grid in
 * log space (no gamma function needed), the same way the server computes P(best).
 */

export const GRID = 600;
const XS = Array.from({ length: GRID }, (_, i) => (i + 0.5) / GRID);

export type Curve = {
  /** Grid midpoints on (0, 1). */
  xs: number[];
  /** Probability density at each midpoint. */
  pdf: number[];
  /** P(rate < x) at each midpoint. */
  cdf: number[];
};

const cache = new Map<string, Curve>();

export function curve(alpha: number, beta: number): Curve {
  const key = `${alpha}|${beta}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const log = XS.map((x) => (alpha - 1) * Math.log(x) + (beta - 1) * Math.log1p(-x));
  const top = Math.max(...log);
  const pmf = log.map((l) => Math.exp(l - top));
  const total = pmf.reduce((a, b) => a + b, 0);
  let run = 0;
  const cdf = pmf.map((p) => {
    run += p / total;
    return run - p / total / 2;
  });
  const out = { xs: XS, pdf: pmf.map((p) => (p / total) * GRID), cdf };
  if (cache.size > 5000) cache.clear();
  cache.set(key, out);
  return out;
}

export const mean = (alpha: number, beta: number) => alpha / (alpha + beta);

/** Central credible interval holding `mass` of the probability. */
export function interval(alpha: number, beta: number, mass = 0.9): [number, number] {
  const { xs, cdf } = curve(alpha, beta);
  const lo = (1 - mass) / 2;
  const at = (q: number) => xs[Math.min(xs.length - 1, cdf.findIndex((c) => c >= q))] ?? 1;
  return [at(lo), at(1 - lo)];
}

/** P(true good-rate > x). */
export function pAbove(alpha: number, beta: number, x: number): number {
  const { cdf } = curve(alpha, beta);
  const i = Math.min(GRID - 1, Math.max(0, Math.floor(x * GRID)));
  return 1 - cdf[i];
}
