import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, REFRESH_MS } from "@/lib/api";
import { useProviderColors } from "@/lib/providers";
import { clock, int } from "@/lib/format";
import { ShareChart } from "@/components/optimizer/ShareChart";
import { PosteriorCurves } from "@/components/optimizer/PosteriorCurves";
import { CategoryHeatmap, categoryLabel } from "@/components/optimizer/CategoryHeatmap";
import { orderProviders } from "@/components/optimizer/types";

const PLAY_MS = 8000; // a full replay takes about this long
const TICK_MS = 80;

export function Optimizer() {
  const colors = useProviderColors();
  const [l1, setL1] = useState<number | null>(null);
  // Snapshot the scrubber is on; null follows the latest one live.
  const [pinned, setPinned] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);

  const history = useQuery({
    queryKey: ["distribution", "history", l1],
    queryFn: async () =>
      (
        await api.GET("/api/ui/distribution/history", {
          params: { query: { ...(l1 != null ? { l1 } : {}), max_points: 240 } },
        })
      ).data,
    refetchInterval: REFRESH_MS,
    placeholderData: keepPreviousData,
  });
  const snapshots = history.data?.snapshots ?? [];
  const last = snapshots.length - 1;

  // The pinned snapshot may be thinned out of a newer history; use the nearest earlier one.
  let index = last;
  if (pinned != null && snapshots.length) {
    const i = snapshots.findIndex((s) => s.id > pinned);
    index = i === -1 ? last : Math.max(0, i - (snapshots[i].id === pinned ? 0 : 1));
  }
  const snap = snapshots[index];
  const live = pinned == null;

  const select = (i: number) => {
    setPlaying(false);
    setPinned(i >= last ? null : snapshots[i].id);
  };

  useEffect(() => {
    if (!playing || snapshots.length < 2) return;
    const step = Math.max(1, Math.round(snapshots.length / (PLAY_MS / TICK_MS)));
    const t = setTimeout(() => {
      const next = index + step;
      if (next >= last) {
        setPinned(null);
        setPlaying(false);
      } else setPinned(snapshots[next].id);
    }, TICK_MS);
    return () => clearTimeout(t);
  }, [playing, index, last, snapshots]);

  const play = () => {
    if (playing) return setPlaying(false);
    if (index >= last && snapshots.length) setPinned(snapshots[0].id);
    setPlaying(true);
  };

  // Snapshots are immutable, so each one is fetched once and cached for good.
  const categories = useQuery({
    queryKey: ["distribution", "categories", snap?.id],
    queryFn: async () =>
      (
        await api.GET("/api/ui/distribution/{distribution_id}/categories", {
          params: { path: { distribution_id: snap!.id } },
        })
      ).data,
    enabled: snap != null,
    staleTime: Infinity,
    placeholderData: keepPreviousData,
  });
  const latestCategories = useQuery({
    queryKey: ["distribution", "categories", snapshots[last]?.id],
    queryFn: async () =>
      (
        await api.GET("/api/ui/distribution/{distribution_id}/categories", {
          params: { path: { distribution_id: snapshots[last]!.id } },
        })
      ).data,
    enabled: snapshots.length > 0,
    staleTime: Infinity,
    placeholderData: keepPreviousData,
  });

  // Category picker: global, then categories with feedback (most first), then the rest.
  const feedbackIn = new Map(
    (latestCategories.data?.cells ?? []).map((c) => [c.l1, Object.values(c.by_provider).reduce((a, v) => a + v.n_obs, 0)]),
  );
  const options = [...feedbackIn.keys()]
    .filter((k): k is number => k != null)
    .sort((a, b) => (feedbackIn.get(b) ?? 0) - (feedbackIn.get(a) ?? 0) || categoryLabel(a).localeCompare(categoryLabel(b)));

  const legend = orderProviders(Object.keys(snap?.by_provider ?? {}), colors);
  const legendKeys = [...new Set(legend.map(colors.keyOf))];
  const nFeedback = snap ? Object.values(snap.by_provider).reduce((a, v) => a + v.n_obs, 0) : 0;

  // Keep showing the last good data through a failed poll; only an error before any data
  // replaces the page.
  if (history.isError && !history.data) {
    return <div className="text-muted py-16 text-center text-sm">Can't reach the optimizer server.</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Optimizer</h1>
        <p className="text-secondary mt-1 max-w-3xl text-sm">
          How the Thompson-sampling distribution evolves. Each search draws one sample per provider
          from its posterior and goes to the highest draw. Every view below reads the routing
          snapshots that <code>optimizer-recompute</code> writes as feedback arrives.
        </p>
      </div>

      {snapshots.length === 0 ? (
        <div className="card text-muted px-4 py-16 text-center text-sm">
          {history.isLoading ? "Loading…" : "No routing snapshots yet. One is written once feedback arrives and optimizer-recompute runs."}
        </div>
      ) : (
        <>
          <div className="card flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-3">
            <label className="flex items-center gap-2 text-sm">
              <span className="text-secondary">Cell</span>
              <select className="control" value={l1 ?? ""} onChange={(e) => setL1(e.target.value === "" ? null : Number(e.target.value))}>
                <option value="">{categoryLabel(null)}</option>
                {options.map((k) => (
                  <option key={k} value={k}>
                    {categoryLabel(k)}
                    {feedbackIn.get(k) ? ` (${int(feedbackIn.get(k))})` : ""}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex min-w-64 flex-1 items-center gap-3">
              <button className="control w-20" onClick={play} aria-label={playing ? "Pause replay" : "Replay from the start"}>
                {playing ? "❚❚ Pause" : "▶ Play"}
              </button>
              <input
                type="range"
                className="flex-1"
                min={0}
                max={Math.max(0, last)}
                value={index}
                onChange={(e) => select(Number(e.target.value))}
                aria-label="Snapshot"
                style={{ accentColor: "var(--accent)" }}
              />
              <div className="seg" role="group" aria-label="Follow latest">
                <button aria-pressed={live} onClick={() => select(last)}>
                  Live
                </button>
              </div>
            </div>
            <div className="text-secondary w-full text-xs">
              Snapshot {index + 1} of {snapshots.length}
              {snap && ` · ${clock(snap.created_at, true)} · ${int(nFeedback)} feedback in this cell`}
              {live ? " · following latest" : ""}
              {snap?.is_reset &&
                " · Reset: every provider is at the uniform prior, so routing is uniform until new feedback arrives"}
              {history.isError && " · can't reach the server, showing the last data received"}
            </div>
          </div>

          <section className="card p-4">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <h2 className="font-semibold">Share of picks over time · {categoryLabel(l1)}</h2>
                <p className="text-muted text-xs">How often each provider wins the Thompson draw (before 5% random exploration)</p>
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                {legendKeys.map((k) => (
                  <span key={k} className="text-secondary flex items-center gap-1.5">
                    <span className="swatch" style={{ background: colors.color(k) }} />
                    <span className="font-mono">{k}</span>
                  </span>
                ))}
              </div>
            </div>
            <ShareChart snapshots={snapshots} selected={index} onSelect={select} colors={colors} />
          </section>

          <section className="card p-4">
            <div className="mb-3">
              <h2 className="font-semibold">Posteriors · {categoryLabel(l1)}</h2>
              <p className="text-muted text-xs">
                Wide, overlapping curves: still exploring. One tall curve furthest right: settled on a winner.
                Hover a row to isolate its curve.
              </p>
            </div>
            {snap && <PosteriorCurves byProvider={snap.by_provider} colors={colors} />}
          </section>

          <section className="card p-4">
            <div className="mb-3">
              <h2 className="font-semibold">Share of picks by category</h2>
              <p className="text-muted text-xs">Different winners per row means routing has specialised. Click a row to inspect it above.</p>
            </div>
            {categories.data ? (
              <CategoryHeatmap
                cells={categories.data.cells}
                colors={colors}
                selectedL1={l1}
                onSelect={(k) => setL1(k)}
              />
            ) : (
              <div className="text-muted py-8 text-center text-sm">Loading…</div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
