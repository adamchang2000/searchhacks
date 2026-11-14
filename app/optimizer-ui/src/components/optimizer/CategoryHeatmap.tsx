import { useState } from "react";
import { QUERY_CATEGORY_LABELS, type QueryCategory } from "@searchhacks/types/query-category";
import { mean } from "@/lib/beta";
import { int, pct } from "@/lib/format";
import { orderProviders, type ByProvider, type Colors } from "./types";

export type CategoryCell = { l1: number | null; by_provider: ByProvider };

type Props = {
  cells: CategoryCell[];
  colors: Colors;
  selectedL1: number | null;
  onSelect: (l1: number | null) => void;
};

export const categoryLabel = (l1: number | null) =>
  l1 == null ? "All queries (global)" : (QUERY_CATEGORY_LABELS[l1 as QueryCategory] ?? `Category ${l1}`);

/** One hue, light to dark: the accent mixed into the grid gray by P(best), so a 0% cell is
 * still a visible cell rather than a hole in the card. */
const fill = (p: number) => `color-mix(in oklab, var(--accent) ${Math.round(p * 100)}%, var(--grid))`;
const total = (by: ByProvider) => Object.values(by).reduce((a, v) => a + v.n_obs, 0);

/**
 * View 3: for each top-level category, each provider's share of Thompson picks. Rows with
 * their own feedback show whether the optimizer specialises (different winners per row).
 */
export function CategoryHeatmap({ cells, colors, selectedL1, onSelect }: Props) {
  const [tip, setTip] = useState<{ l1: number | null; p: string; x: number; y: number } | null>(null);

  const providers = orderProviders(
    cells.flatMap((c) => Object.keys(c.by_provider)),
    colors,
  );
  const global = cells.find((c) => c.l1 == null);
  const withData = cells.filter((c) => c.l1 != null && total(c.by_provider) > 0).sort((a, b) => total(b.by_provider) - total(a.by_provider));
  const empty = cells.filter((c) => c.l1 != null && total(c.by_provider) === 0).length;
  const rows = [...(global ? [global] : []), ...withData];

  const tipCell = tip && rows.find((r) => r.l1 === tip.l1)?.by_provider[tip.p];

  return (
    <div className="relative">
      <div className="overflow-x-auto">
        <table className="text-sm" style={{ borderCollapse: "separate", borderSpacing: 2 }}>
          <thead>
            <tr className="text-secondary text-xs">
              <th className="pr-3 text-left font-medium">Category</th>
              {providers.map((p) => (
                <th key={p} className="px-1 pb-1 text-center font-medium" style={{ width: 92 }}>
                  <span className="inline-flex items-center gap-1.5 font-mono">
                    <span className="swatch" style={{ background: colors.color(colors.keyOf(p)) }} />
                    {p}
                  </span>
                </th>
              ))}
              <th className="pl-3 text-right font-medium">Feedback</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const best = providers.reduce<string | null>(
                (b, p) => ((r.by_provider[p]?.p_best ?? 0) > (b ? r.by_provider[b]?.p_best ?? 0 : -1) ? p : b),
                null,
              );
              const selected = r.l1 === selectedL1;
              return (
                <tr key={r.l1 ?? "global"} onClick={() => onSelect(r.l1)} className="cursor-pointer">
                  <td className={`whitespace-nowrap pr-3 ${selected ? "font-semibold" : ""}`}>
                    <span className="flex items-center gap-2">
                      <span
                        className="inline-block h-4 w-1 rounded-full"
                        style={{ background: selected ? "var(--text-primary)" : "transparent" }}
                      />
                      {categoryLabel(r.l1)}
                    </span>
                  </td>
                  {providers.map((p) => {
                    const v = r.by_provider[p];
                    const share = v?.p_best ?? 0;
                    return (
                      <td
                        key={p}
                        tabIndex={0}
                        aria-label={`${categoryLabel(r.l1)}, ${p}: ${pct(share)} of picks`}
                        className="h-8 rounded text-center text-xs outline-offset-1"
                        width={92}
                        style={{
                          background: fill(share),
                          color: share > 0.55 ? "#fff" : "var(--text-primary)",
                          boxShadow: tip?.l1 === r.l1 && tip?.p === p ? "inset 0 0 0 2px var(--text-primary)" : undefined,
                        }}
                        onPointerEnter={(e) => {
                          const box = e.currentTarget.getBoundingClientRect();
                          const host = e.currentTarget.closest(".relative")!.getBoundingClientRect();
                          setTip({ l1: r.l1, p, x: box.left - host.left + box.width / 2, y: box.bottom - host.top });
                        }}
                        onFocus={(e) => {
                          const box = e.currentTarget.getBoundingClientRect();
                          const host = e.currentTarget.closest(".relative")!.getBoundingClientRect();
                          setTip({ l1: r.l1, p, x: box.left - host.left + box.width / 2, y: box.bottom - host.top });
                        }}
                        onPointerLeave={() => setTip(null)}
                        onBlur={() => setTip(null)}
                      >
                        {p === best && share > 0 ? pct(share) : ""}
                      </td>
                    );
                  })}
                  <td className="text-secondary pl-3 text-right">{int(total(r.by_provider))}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="text-secondary mt-3 flex flex-wrap items-center justify-between gap-3 text-xs">
        <span>
          {empty > 0 && `${empty} categories have no feedback yet and route like the global row. `}
          Only each row's top provider is labelled; hover a cell for its numbers.
        </span>
        <span className="flex items-center gap-2">
          Share of picks
          <span>0%</span>
          <span className="inline-block h-2.5 w-28 rounded-sm" style={{ background: `linear-gradient(to right, ${fill(0)}, ${fill(1)})`, border: "1px solid var(--border)" }} />
          <span>100%</span>
        </span>
      </div>

      {tip && tipCell && (
        <div
          className="card pointer-events-none absolute z-10 px-3 py-2 text-xs shadow-sm"
          style={{ left: tip.x, top: tip.y + 6, transform: "translateX(-50%)", minWidth: 180 }}
        >
          <div className="font-semibold">{pct(tipCell.p_best, 1)} of picks</div>
          <div className="text-secondary">
            <span className="font-mono">{tip.p}</span> · {categoryLabel(tip.l1)}
          </div>
          <div className="text-secondary mt-1">
            Est. rate {pct(mean(tipCell.alpha, tipCell.beta), 1)} · {int(tipCell.n_obs)} feedback here
          </div>
        </div>
      )}
    </div>
  );
}
