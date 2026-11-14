import { useQuery } from "@tanstack/react-query";
import { api, REFRESH_MS } from "@/lib/api";

const SLOTS = 7;
export const OTHER = "Other";

export function useProviderStats() {
  return useQuery({
    queryKey: ["stats", "providers"],
    queryFn: async () => (await api.GET("/api/ui/stats/providers")).data ?? [],
    refetchInterval: REFRESH_MS,
  });
}

/**
 * Palette slots go to providers by all-time search volume (ties by name), so the busiest
 * providers get their own color. All-time volume changes slowly and doesn't depend on
 * the time window or filters, so switching views never repaints a provider. Past 7
 * providers, the tail shares "Other".
 */
export function useProviderColors() {
  const stats = useProviderStats();
  const names = [...(stats.data ?? [])]
    .sort((a, b) => b.num_searches - a.num_searches || a.provider.localeCompare(b.provider))
    .map((s) => s.provider);
  const colored = names.slice(0, names.length > SLOTS ? SLOTS - 1 : SLOTS);
  const index = new Map(colored.map((p, i) => [p, i]));
  return {
    /** Providers that get their own series, in slot order. */
    series: colored,
    hasOther: names.length > colored.length,
    /** Series key a provider is drawn under. */
    keyOf: (p: string) => (index.has(p) ? p : OTHER),
    color: (p: string) =>
      index.has(p) ? `var(--series-${index.get(p)! + 1})` : "var(--series-other)",
  };
}
