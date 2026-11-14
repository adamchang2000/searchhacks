import { useState } from "react";
import { OTHER } from "@/lib/providers";
import { clock, int, pct } from "@/lib/format";
import { useWidth } from "@/lib/useWidth";
import type { Colors, Snapshot } from "./types";

type Props = {
  snapshots: Snapshot[];
  selected: number;
  onSelect: (index: number) => void;
  colors: Colors;
};

const HEIGHT = 240;
const M = { top: 8, right: 12, bottom: 24, left: 40 };

/**
 * View 1: each provider's share of Thompson picks (P(best)) at every snapshot, as a 100%
 * stacked area. The x axis is snapshot order, so idle periods (no new feedback, no snapshot)
 * take no space. Click anywhere to move the scrubber there.
 */
export function ShareChart({ snapshots, selected, onSelect, colors }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);

  const rows = snapshots.map((s) => {
    const share: Record<string, number> = {};
    let n = 0;
    for (const [p, v] of Object.entries(s.by_provider)) {
      const k = colors.keyOf(p);
      share[k] = (share[k] ?? 0) + v.p_best;
      n += v.n_obs;
    }
    return { share, n, at: s.created_at, reset: s.is_reset };
  });
  const keys = [...colors.series, ...(rows.some((r) => r.share[OTHER]) ? [OTHER] : [])].filter((k) =>
    rows.some((r) => (r.share[k] ?? 0) > 0),
  );

  const w = Math.max(200, width);
  const iw = w - M.left - M.right;
  const ih = HEIGHT - M.top - M.bottom;
  const last = Math.max(1, rows.length - 1);
  const x = (i: number) => M.left + (i / last) * iw;
  const y = (v: number) => M.top + (1 - v) * ih;

  // Cumulative band edges, bottom of the stack first.
  const edges: number[][] = [rows.map(() => 0)];
  for (const k of keys) edges.push(rows.map((r, i) => edges[edges.length - 1][i] + (r.share[k] ?? 0)));

  // A reset is a jump, not a drift: hold the previous shares up to the reset snapshot, then
  // drop straight down to it (a vertical step instead of a slope across the gap).
  const pts = (col: number[]) =>
    col.flatMap((v, i) =>
      rows[i].reset && i > 0 ? [`${x(i)},${y(col[i - 1])}`, `${x(i)},${y(v)}`] : [`${x(i)},${y(v)}`],
    );
  const band = (j: number) => `M${pts(edges[j + 1]).join("L")}L${pts(edges[j]).reverse().join("L")}Z`;
  const resets = rows.flatMap((r, i) => (r.reset ? [i] : []));

  const indexAt = (clientX: number, el: SVGSVGElement) => {
    const px = clientX - el.getBoundingClientRect().left;
    return Math.round(Math.min(1, Math.max(0, (px - M.left) / iw)) * last);
  };

  // Deduped: with only a few snapshots, the quartiles round to the same index.
  const timeTicks =
    rows.length < 2 ? [] : [...new Set([0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * last)))];
  const h = hover != null ? rows[hover] : null;

  return (
    <div ref={ref} className="relative">
      {rows.length < 2 ? (
        <div className="text-muted flex items-center justify-center text-sm" style={{ height: HEIGHT }}>
          Waiting for a second snapshot to draw a trend.
        </div>
      ) : (
        <svg
          width={w}
          height={HEIGHT}
          role="img"
          aria-label="Share of Thompson-sampling picks per provider over time"
          onPointerMove={(e) => setHover(indexAt(e.clientX, e.currentTarget))}
          onPointerLeave={() => setHover(null)}
          onClick={(e) => onSelect(indexAt(e.clientX, e.currentTarget))}
          style={{ cursor: "pointer", display: "block" }}
        >
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t}>
              <line x1={M.left} x2={w - M.right} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
              <text x={M.left - 6} y={y(t)} dy="0.32em" textAnchor="end" fontSize={11} fill="var(--text-muted)">
                {pct(t)}
              </text>
            </g>
          ))}
          {keys.map((k, j) => (
            <path key={k} d={band(j)} fill={colors.color(k)} stroke="var(--surface-1)" strokeWidth={2} strokeLinejoin="round" />
          ))}
          {resets.map((i) => (
            <g key={`reset-${i}`}>
              <line
                x1={x(i)}
                x2={x(i)}
                y1={M.top}
                y2={M.top + ih}
                stroke="var(--text-primary)"
                strokeWidth={1.5}
                strokeDasharray="4 3"
              />
              <text
                x={x(i) - 4}
                y={M.top + 12}
                textAnchor="end"
                fontSize={11}
                fontWeight={600}
                fill="var(--text-primary)"
                paintOrder="stroke"
                stroke="var(--surface-1)"
                strokeWidth={3}
              >
                Reset
              </text>
            </g>
          ))}
          {timeTicks.map((i, n) => (
            <text
              key={n}
              x={x(i)}
              y={HEIGHT - 6}
              textAnchor={n === 0 ? "start" : n === timeTicks.length - 1 ? "end" : "middle"}
              fontSize={11}
              fill="var(--text-muted)"
            >
              {clock(rows[i].at, true)}
            </text>
          ))}
          <line x1={x(selected)} x2={x(selected)} y1={M.top - 4} y2={M.top + ih} stroke="var(--text-primary)" strokeWidth={2} />
          <circle cx={x(selected)} cy={M.top - 2} r={4} fill="var(--text-primary)" stroke="var(--surface-1)" strokeWidth={2} />
          {hover != null && (
            <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={M.top + ih} stroke="var(--text-muted)" strokeWidth={1} />
          )}
        </svg>
      )}
      {h && hover != null && (
        <div
          className="card pointer-events-none absolute z-10 px-3 py-2 text-xs shadow-sm"
          style={{
            top: M.top,
            left: x(hover) > w / 2 ? undefined : x(hover) + 12,
            right: x(hover) > w / 2 ? w - x(hover) + 12 : undefined,
            minWidth: 170,
          }}
        >
          <div className="text-secondary mb-1">
            {clock(h.at, true)} · {int(h.n)} feedback
          </div>
          {h.reset && <div className="mb-1 font-medium">Reset: uniform, counting starts afresh</div>}
          {[...keys].reverse().map((k) => (
            <div key={k} className="flex items-center gap-2 py-px">
              <span className="inline-block h-0.5 w-3 rounded" style={{ background: colors.color(k) }} />
              <span className="font-semibold">{pct(h.share[k] ?? 0, 1)}</span>
              <span className="text-secondary font-mono">{k}</span>
            </div>
          ))}
          <div className="text-muted mt-1">Click to inspect this snapshot</div>
        </div>
      )}
    </div>
  );
}
