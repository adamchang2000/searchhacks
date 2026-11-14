import { useState } from "react";
import { curve, interval, mean, pAbove } from "@/lib/beta";
import { int, pct } from "@/lib/format";
import { useWidth } from "@/lib/useWidth";
import { orderProviders, type ByProvider, type Colors } from "./types";

type Props = {
  byProvider: ByProvider;
  colors: Colors;
};

const HEIGHT = 260;
const M = { top: 8, right: 12, bottom: 28, left: 12 };

/**
 * View 2: every provider's Beta posterior for one cell at one snapshot. Thompson sampling
 * draws one value from each curve per search and routes to the highest, so wide overlapping
 * curves mean exploration and one tall curve to the right means the optimizer has settled.
 */
export function PosteriorCurves({ byProvider, colors }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hoverX, setHoverX] = useState<number | null>(null);
  const [focus, setFocus] = useState<string | null>(null);

  const providers = orderProviders(Object.keys(byProvider), colors);
  const curves = providers.map((p) => ({ p, ...byProvider[p], c: curve(byProvider[p].alpha, byProvider[p].beta) }));
  const yMax = Math.max(1, ...curves.flatMap((c) => c.c.pdf));

  const w = Math.max(200, width);
  const iw = w - M.left - M.right;
  const ih = HEIGHT - M.top - M.bottom;
  const x = (v: number) => M.left + v * iw;
  const y = (d: number) => M.top + (1 - d / yMax) * ih;

  // Draw the most-picked provider last so it sits on top.
  const drawOrder = [...curves].sort((a, b) => a.p_best - b.p_best);
  const line = (c: (typeof curves)[number]) => c.c.xs.map((v, i) => `${x(v)},${y(c.c.pdf[i])}`).join("L");

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
      <div ref={ref} className="relative min-w-0">
        {providers.length === 0 ? (
          <div className="text-muted flex items-center justify-center text-sm" style={{ height: HEIGHT }}>
            No feedback in this snapshot yet.
          </div>
        ) : (
          <svg
            width={w}
            height={HEIGHT}
            role="img"
            aria-label="Posterior distribution of each provider's good-result rate"
            onPointerMove={(e) => {
              const px = e.clientX - e.currentTarget.getBoundingClientRect().left;
              setHoverX(Math.min(1, Math.max(0, (px - M.left) / iw)));
            }}
            onPointerLeave={() => setHoverX(null)}
            style={{ display: "block" }}
          >
            {[0, 0.25, 0.5, 0.75, 1].map((t) => (
              <g key={t}>
                <line x1={x(t)} x2={x(t)} y1={M.top} y2={M.top + ih} stroke="var(--grid)" />
                <text x={x(t)} y={HEIGHT - 10} textAnchor={t === 0 ? "start" : t === 1 ? "end" : "middle"} fontSize={11} fill="var(--text-muted)">
                  {pct(t)}
                </text>
              </g>
            ))}
            <line x1={M.left} x2={w - M.right} y1={M.top + ih} y2={M.top + ih} stroke="var(--border)" />
            {drawOrder.map((c) => {
              const dim = focus != null && focus !== c.p;
              const col = colors.color(colors.keyOf(c.p));
              return (
                <g key={c.p} opacity={dim ? 0.15 : 1}>
                  <path d={`M${x(0)},${y(0)}L${line(c)}L${x(1)},${y(0)}Z`} fill={col} fillOpacity={0.1} />
                  <path d={`M${line(c)}`} fill="none" stroke={col} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                </g>
              );
            })}
            {hoverX != null && <line x1={x(hoverX)} x2={x(hoverX)} y1={M.top} y2={M.top + ih} stroke="var(--text-muted)" />}
          </svg>
        )}
        <div className="text-muted mt-1 text-center text-xs">Good-result rate (each curve: where that provider's true rate probably is)</div>
        {hoverX != null && (
          <div
            className="card pointer-events-none absolute z-10 px-3 py-2 text-xs shadow-sm"
            style={{
              top: M.top,
              left: x(hoverX) > w / 2 ? undefined : x(hoverX) + 12,
              right: x(hoverX) > w / 2 ? w - x(hoverX) + 12 : undefined,
              minWidth: 160,
            }}
          >
            <div className="text-secondary mb-1">Chance true rate &gt; {pct(hoverX)}</div>
            {[...curves]
              .sort((a, b) => pAbove(b.alpha, b.beta, hoverX) - pAbove(a.alpha, a.beta, hoverX))
              .map((c) => (
                <div key={c.p} className="flex items-center gap-2 py-px">
                  <span className="inline-block h-0.5 w-3 rounded" style={{ background: colors.color(colors.keyOf(c.p)) }} />
                  <span className="font-semibold">{pct(pAbove(c.alpha, c.beta, hoverX))}</span>
                  <span className="text-secondary font-mono">{c.p}</span>
                </div>
              ))}
          </div>
        )}
      </div>

      <table className="w-full self-start whitespace-nowrap text-left text-sm">
        <thead className="text-secondary text-xs">
          <tr className="border-token border-b">
            <th className="py-1.5 pr-2 font-medium">Provider</th>
            <th className="px-2 py-1.5 text-right font-medium" title="Share of Thompson picks (before 5% exploration)">
              Picks
            </th>
            <th className="px-2 py-1.5 text-right font-medium">Est. rate</th>
            <th className="px-2 py-1.5 text-right font-medium" title="90% credible interval">
              90% range
            </th>
            <th className="py-1.5 pl-2 text-right font-medium" title="Feedback observed in this cell itself">
              Feedback
            </th>
          </tr>
        </thead>
        <tbody>
          {[...curves]
            .sort((a, b) => b.p_best - a.p_best)
            .map((c) => {
              const [lo, hi] = interval(c.alpha, c.beta);
              return (
                <tr
                  key={c.p}
                  className="border-token border-b last:border-0"
                  onPointerEnter={() => setFocus(c.p)}
                  onPointerLeave={() => setFocus(null)}
                  onFocus={() => setFocus(c.p)}
                  onBlur={() => setFocus(null)}
                  tabIndex={0}
                >
                  <td className="py-1.5 pr-2">
                    <span className="flex items-center gap-2 font-mono">
                      <span className="swatch" style={{ background: colors.color(colors.keyOf(c.p)) }} />
                      {c.p}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 text-right font-semibold">{pct(c.p_best, 1)}</td>
                  <td className="px-2 py-1.5 text-right">{pct(mean(c.alpha, c.beta), 1)}</td>
                  <td className="text-secondary px-2 py-1.5 text-right">
                    {pct(lo)}–{pct(hi)}
                  </td>
                  <td className="py-1.5 pl-2 text-right">{int(c.n_obs)}</td>
                </tr>
              );
            })}
        </tbody>
      </table>
    </div>
  );
}
