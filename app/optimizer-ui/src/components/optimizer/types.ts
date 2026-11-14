import type { components } from "@searchhacks/optimizer-protocol";

type Schemas = components["schemas"];
export type Posterior = Schemas["ProviderPosteriorOut"];
export type Snapshot = Schemas["SnapshotOut"];
export type ByProvider = Record<string, Posterior>;

export type Colors = {
  /** Providers with their own palette slot, in slot order. */
  series: string[];
  keyOf: (p: string) => string;
  color: (key: string) => string;
};

/** Providers in a stable display order: palette slot first, then name. */
export function orderProviders(names: Iterable<string>, colors: Colors): string[] {
  const slot = (p: string) => {
    const i = colors.series.indexOf(p);
    return i < 0 ? Infinity : i;
  };
  return [...new Set(names)].sort((a, b) => slot(a) - slot(b) || a.localeCompare(b));
}
