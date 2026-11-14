import { useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, REFRESH_MS } from "@/lib/api";
import { OTHER, useProviderColors, useProviderStats } from "@/lib/providers";
import { TrafficChart } from "@/components/TrafficChart";
import { int, pct, ratio } from "@/lib/format";

const WINDOWS = [
  { label: "15m", minutes: 15, bucket: 15 },
  { label: "1h", minutes: 60, bucket: 60 },
  { label: "6h", minutes: 360, bucket: 300 },
  { label: "24h", minutes: 1440, bucket: 900 },
] as const;

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card px-4 py-3">
      <div className="text-secondary text-xs font-medium uppercase tracking-wide">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {sub && <div className="text-muted mt-0.5 text-xs">{sub}</div>}
    </div>
  );
}

export function Overview() {
  const [win, setWin] = useState<(typeof WINDOWS)[number]>(WINDOWS[1]);
  const colors = useProviderColors();
  const stats = useProviderStats();

  const traffic = useQuery({
    queryKey: ["traffic", win.minutes, win.bucket],
    queryFn: async () =>
      (
        await api.GET("/api/ui/stats/traffic", {
          params: { query: { minutes: win.minutes, bucket_seconds: win.bucket } },
        })
      ).data,
    refetchInterval: REFRESH_MS,
    placeholderData: keepPreviousData,
  });

  const buckets = traffic.data?.buckets ?? [];
  const sum = (f: (b: (typeof buckets)[number]) => number) => buckets.reduce((a, b) => a + f(b), 0);
  const total = sum((b) => b.good + b.bad + b.pending);
  const good = sum((b) => b.good);
  const bad = sum((b) => b.bad);
  const perProviderInWindow: Record<string, number> = {};
  for (const b of buckets)
    for (const [p, n] of Object.entries(b.by_provider))
      perProviderInWindow[p] = (perProviderInWindow[p] ?? 0) + n;

  const providers = [...(stats.data ?? [])].sort((a, b) => b.num_searches - a.num_searches);
  const allTime = providers.reduce((a, p) => a + p.num_searches, 0);
  const legendKeys = [...colors.series, ...(colors.hasOther ? [OTHER] : [])];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Traffic</h1>
        <div className="seg" role="group" aria-label="Time window">
          {WINDOWS.map((w) => (
            <button key={w.label} aria-pressed={w === win} onClick={() => setWin(w)}>
              {w.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label={`Searches · ${win.label}`} value={int(total)} sub={`${int(allTime)} all time`} />
        <Stat
          label="Searches / min"
          value={total ? (total / win.minutes).toFixed(1) : "0"}
          sub={`average over ${win.label}`}
        />
        <Stat
          label="Feedback received"
          value={pct(ratio(good + bad, total))}
          sub={`${int(good + bad)} of ${int(total)}`}
        />
        <Stat label="Good rate" value={pct(ratio(good, good + bad))} sub={`${int(good)} good · ${int(bad)} bad`} />
      </div>

      <section className="card p-4">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-semibold">
            Searches per {win.bucket < 60 ? `${win.bucket}s` : `${win.bucket / 60} min`}, by provider
          </h2>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
            {legendKeys.map((k) => (
              <span key={k} className="text-secondary flex items-center gap-1.5">
                <span className="swatch" style={{ background: colors.color(k) }} />
                <span className="font-mono">{k}</span>
              </span>
            ))}
          </div>
        </div>
        {traffic.isError ? (
          <div className="text-muted py-16 text-center text-sm">Can't reach the optimizer server.</div>
        ) : (
          <TrafficChart
            buckets={buckets}
            bucketSeconds={traffic.data?.bucket_seconds ?? win.bucket}
            series={colors.series}
            keyOf={colors.keyOf}
            color={colors.color}
          />
        )}
      </section>

      <section className="card overflow-x-auto">
        <h2 className="px-4 pt-4 font-semibold">Providers</h2>
        <table className="mt-2 w-full text-left text-sm">
          <thead className="text-secondary text-xs">
            <tr className="border-token border-b">
              <th className="px-4 py-2 font-medium">Provider</th>
              <th className="px-2 py-2 text-right font-medium">{win.label}</th>
              <th className="px-2 py-2 text-right font-medium">All time</th>
              <th className="px-2 py-2 font-medium">Share</th>
              <th className="px-2 py-2 text-right font-medium">Feedback</th>
              <th className="px-2 py-2 text-right font-medium">Good</th>
              <th className="px-4 py-2 text-right font-medium">Good rate</th>
            </tr>
          </thead>
          <tbody>
            {providers.map((p) => {
              const share = ratio(p.num_searches, allTime) ?? 0;
              return (
                <tr key={p.provider} className="border-token border-b last:border-0">
                  <td className="px-4 py-2">
                    <Link
                      to={`/searches?provider=${encodeURIComponent(p.provider)}`}
                      className="flex items-center gap-2 font-mono hover:underline"
                    >
                      <span className="swatch" style={{ background: colors.color(p.provider) }} />
                      {p.provider}
                    </Link>
                  </td>
                  <td className="px-2 py-2 text-right">{int(perProviderInWindow[p.provider] ?? 0)}</td>
                  <td className="px-2 py-2 text-right">{int(p.num_searches)}</td>
                  <td className="w-40 px-2 py-2">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 flex-1 rounded-full" style={{ background: "var(--grid)" }}>
                        <div
                          className="h-1.5 rounded-full"
                          style={{ width: `${share * 100}%`, background: colors.color(p.provider) }}
                        />
                      </div>
                      <span className="text-secondary w-9 text-right text-xs">{pct(share)}</span>
                    </div>
                  </td>
                  <td className="px-2 py-2 text-right">{int(p.num_feedback)}</td>
                  <td className="px-2 py-2 text-right">{int(p.num_good)}</td>
                  <td className="px-4 py-2 text-right">{pct(p.good_rate, 1)}</td>
                </tr>
              );
            })}
            {providers.length === 0 && (
              <tr>
                <td colSpan={7} className="text-muted px-4 py-6 text-center">
                  No searches yet. Run <code>make mock-driver</code> to generate traffic.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
