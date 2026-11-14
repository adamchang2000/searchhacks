import { useLayoutEffect, useRef, useState } from "react";
import type { TrafficBucketOut } from "@searchhacks/optimizer-protocol";
import { OTHER } from "@/lib/providers";
import { clock, int } from "@/lib/format";

type Props = {
  buckets: TrafficBucketOut[];
  bucketSeconds: number;
  /** Series keys in palette order (bottom of the stack first). */
  series: string[];
  keyOf: (provider: string) => string;
  color: (key: string) => string;
};

const HEIGHT = 240;
const M = { top: 8, right: 8, bottom: 24, left: 40 };

/** Integer y-axis: ~4 ticks at a 1/2/5 step, max rounded up to a whole step. */
function yScale(v: number) {
  const raw = Math.max(1, v / 4);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw)!;
  const max = Math.max(step, Math.ceil(v / step) * step);
  const ticks: number[] = [];
  for (let t = 0; t <= max; t += step) ticks.push(t);
  return { max, ticks };
}

/** Rect with only the top corners rounded (data end), anchored to the baseline. */
function topRounded(x: number, y: number, w: number, h: number, r: number) {
  r = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

export function TrafficChart({ buckets, bucketSeconds, series, keyOf, color }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const [hover, setHover] = useState<number | null>(null);

  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    setWidth(el.getBoundingClientRect().width);
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Fold providers into series keys; keep keys in palette order, Other last.
  const rows = buckets.map((b) => {
    const counts: Record<string, number> = {};
    for (const [p, n] of Object.entries(b.by_provider)) {
      const k = keyOf(p);
      counts[k] = (counts[k] ?? 0) + n;
    }
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    return { start: b.start, counts, total };
  });
  const keys = [...series, ...(rows.some((r) => r.counts[OTHER]) ? [OTHER] : [])];

  const plotW = Math.max(10, width - M.left - M.right);
  const plotH = HEIGHT - M.top - M.bottom;
  const { max, ticks: yTicks } = yScale(Math.max(0, ...rows.map((r) => r.total)));
  const band = plotW / Math.max(1, rows.length);
  const gap = band >= 6 ? 2 : band >= 3 ? 1 : 0;
  const barW = Math.max(1, band - gap);
  const y = (v: number) => (v / max) * plotH;

  const xEvery = Math.max(1, Math.ceil(rows.length / Math.max(2, Math.floor(plotW / 90))));
  const withSeconds = bucketSeconds < 60;

  const h = hover != null ? rows[hover] : null;
  const tipLeft = hover != null ? M.left + (hover + 0.5) * band : 0;

  return (
    <div ref={wrap} className="relative w-full" onMouseLeave={() => setHover(null)}>
      <svg width={width} height={HEIGHT} role="img" aria-label="Searches per time bucket by provider">
        <g transform={`translate(${M.left},${M.top})`}>
          {yTicks.map((t) => (
            <g key={t} transform={`translate(0,${plotH - y(t)})`}>
              <line x1={0} x2={plotW} stroke="var(--grid)" />
              <text x={-8} dy="0.32em" textAnchor="end" fontSize={11} fill="var(--text-muted)">
                {t.toLocaleString()}
              </text>
            </g>
          ))}

          {rows.map((r, i) => {
            let acc = 0;
            const x = i * band + gap / 2;
            const present = keys.filter((k) => r.counts[k]);
            return (
              <g key={r.start} opacity={hover == null || hover === i ? 1 : 0.55}>
                {present.map((k, j) => {
                  const v = r.counts[k];
                  const y0 = plotH - y(acc + v);
                  const hh = y(v);
                  acc += v;
                  const isTop = j === present.length - 1;
                  // 2px surface gap between stacked segments.
                  const inset = j > 0 && hh > 3 ? 1 : 0;
                  const segH = Math.max(0.5, hh - inset * 2);
                  return isTop ? (
                    <path key={k} d={topRounded(x, y0 + inset, barW, segH + inset, 4)} fill={color(k)} />
                  ) : (
                    <rect key={k} x={x} y={y0 + inset} width={barW} height={segH} fill={color(k)} />
                  );
                })}
              </g>
            );
          })}

          <line x1={0} x2={plotW} y1={plotH} y2={plotH} stroke="var(--border)" />
          {rows.map((r, i) =>
            i % xEvery === 0 ? (
              <text
                key={r.start}
                x={i * band + band / 2}
                y={plotH + 16}
                textAnchor="middle"
                fontSize={11}
                fill="var(--text-muted)"
              >
                {clock(r.start, withSeconds)}
              </text>
            ) : null,
          )}

          {/* Hit targets: full-height columns, wider than the bars. */}
          {rows.map((r, i) => (
            <rect
              key={r.start}
              x={i * band}
              y={0}
              width={band}
              height={plotH}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
            />
          ))}
        </g>
      </svg>

      {h && (
        <div
          className="card pointer-events-none absolute z-10 px-3 py-2 text-xs shadow-lg"
          style={{
            top: 4,
            left: tipLeft,
            transform: `translateX(${tipLeft > width / 2 ? "calc(-100% - 12px)" : "12px"})`,
            minWidth: 160,
          }}
        >
          <div className="mb-1 font-medium">
            {clock(h.start, withSeconds)} · {int(h.total)} searches
          </div>
          {keys
            .filter((k) => h.counts[k])
            .slice()
            .reverse()
            .map((k) => (
              <div key={k} className="flex items-center gap-2">
                <span className="swatch" style={{ background: color(k) }} />
                <span className="text-secondary flex-1 font-mono">{k}</span>
                <span>{int(h.counts[k])}</span>
              </div>
            ))}
          {h.total === 0 && <div className="text-muted">No searches</div>}
        </div>
      )}
    </div>
  );
}
