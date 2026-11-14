import { Fragment, useEffect, useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import type { SearchOut } from "@searchhacks/optimizer-protocol";
import { api, REFRESH_MS } from "@/lib/api";
import { useProviderColors, useProviderStats } from "@/lib/providers";
import { TOP_LEVEL_CATEGORIES, UNCLASSIFIED, categoryLabel } from "@/lib/categories";
import { int, timeAgo } from "@/lib/format";

const PAGE_SIZE = 50;
type FeedbackFilter = "good" | "bad" | "none";

function FeedbackBadge({ isGood }: { isGood: boolean | null }) {
  const [label, icon, color] =
    isGood == null
      ? ["pending", "○", "var(--status-pending)"]
      : isGood
        ? ["good", "✓", "var(--status-good)"]
        : ["bad", "✕", "var(--status-bad)"];
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium" style={{ color }}>
      <span aria-hidden>{icon}</span>
      {label}
    </span>
  );
}

function Category({ s }: { s: SearchOut }) {
  const l1 = categoryLabel(s.category_l1);
  if (!l1) return <span className="text-muted">unclassified</span>;
  const l2 = categoryLabel(s.category_l2);
  return (
    <span>
      {l1}
      {l2 && <span className="text-secondary"> › {l2}</span>}
    </span>
  );
}

function Detail({ s }: { s: SearchOut }) {
  const rows: [string, React.ReactNode][] = [
    ["Feedback token", <code className="text-xs">{s.id}</code>],
    ["Created", new Date(s.created_at).toLocaleString()],
    ["Query", <span className="whitespace-pre-wrap">{s.query}</span>],
    ["Chosen provider", <code>{s.provider}</code>],
    ["Available providers", <code>{s.available_providers.join(", ") || "—"}</code>],
    [
      "Category",
      s.category_l1 == null
        ? "—"
        : `${categoryLabel(s.category_l1)} (${s.category_l1})${
            s.category_l2 != null ? ` › ${categoryLabel(s.category_l2)} (${s.category_l2})` : ""
          }`,
    ],
    ["Category source", <code>{s.category_source}</code>],
    [
      "Feedback",
      <span className="inline-flex items-center gap-2">
        <FeedbackBadge isGood={s.is_good} />
        {s.feedback_at && <span className="text-muted text-xs">{new Date(s.feedback_at).toLocaleString()}</span>}
      </span>,
    ],
  ];
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1.5 text-sm">
      {rows.map(([k, v]) => (
        <Fragment key={k}>
          <dt className="text-secondary">{k}</dt>
          <dd className="min-w-0 break-words">{v}</dd>
        </Fragment>
      ))}
    </dl>
  );
}

export function Searches() {
  const [params, setParams] = useSearchParams();
  const provider = params.get("provider") ?? "";
  const feedback = (params.get("feedback") ?? "") as FeedbackFilter | "";
  const category = params.get("category") ?? "";
  const q = params.get("q") ?? "";
  const page = Math.max(0, Number(params.get("page") ?? 0) || 0);

  const [qDraft, setQDraft] = useState(q);
  const [open, setOpen] = useState<string | null>(null);
  const colors = useProviderColors();
  const providerNames = (useProviderStats().data ?? []).map((p) => p.provider).sort();

  function set(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next, { replace: true });
  }

  // Debounce the free-text filter.
  useEffect(() => {
    if (qDraft === q) return;
    const t = setTimeout(() => set("q", qDraft), 300);
    return () => clearTimeout(t);
  }, [qDraft]); // eslint-disable-line react-hooks/exhaustive-deps

  const searches = useQuery({
    queryKey: ["searches", provider, feedback, category, q, page],
    queryFn: async () =>
      (
        await api.GET("/api/ui/searches", {
          params: {
            query: {
              limit: PAGE_SIZE,
              offset: page * PAGE_SIZE,
              provider: provider || undefined,
              feedback: feedback || undefined,
              category_l1: category ? Number(category) : undefined,
              q: q || undefined,
            },
          },
        })
      ).data,
    refetchInterval: REFRESH_MS,
    placeholderData: keepPreviousData,
  });

  const items = searches.data?.items ?? [];
  const total = searches.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const filtered = provider || feedback || category || q;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Searches</h1>
        <span className="text-secondary text-sm">{int(total)} matching</span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <input
          className="control w-64"
          placeholder="Filter query text…"
          value={qDraft}
          onChange={(e) => setQDraft(e.target.value)}
        />
        <select className="control" value={provider} onChange={(e) => set("provider", e.target.value)}>
          <option value="">All providers</option>
          {providerNames.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select className="control" value={feedback} onChange={(e) => set("feedback", e.target.value)}>
          <option value="">Any feedback</option>
          <option value="good">Good</option>
          <option value="bad">Bad</option>
          <option value="none">Pending</option>
        </select>
        <select className="control" value={category} onChange={(e) => set("category", e.target.value)}>
          <option value="">All categories</option>
          <option value={UNCLASSIFIED}>Unclassified</option>
          {TOP_LEVEL_CATEGORIES.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
        {filtered && (
          <button
            className="text-secondary text-sm hover:underline"
            onClick={() => {
              setQDraft("");
              setParams({}, { replace: true });
            }}
          >
            Clear
          </button>
        )}
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-secondary text-xs">
            <tr className="border-token border-b">
              <th className="px-4 py-2 font-medium">When</th>
              <th className="px-2 py-2 font-medium">Query</th>
              <th className="px-2 py-2 font-medium">Provider</th>
              <th className="px-2 py-2 font-medium">Category</th>
              <th className="px-4 py-2 font-medium">Feedback</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <Fragment key={s.id}>
                <tr
                  className="border-token cursor-pointer border-b hover:bg-[var(--surface-0)]"
                  onClick={() => setOpen(open === s.id ? null : s.id)}
                  aria-expanded={open === s.id}
                >
                  <td className="text-secondary whitespace-nowrap px-4 py-2" title={new Date(s.created_at).toLocaleString()}>
                    {timeAgo(s.created_at)}
                  </td>
                  <td className="max-w-md truncate px-2 py-2" title={s.query}>
                    {s.query}
                  </td>
                  <td className="whitespace-nowrap px-2 py-2">
                    <span className="flex items-center gap-2 font-mono">
                      <span className="swatch" style={{ background: colors.color(s.provider) }} />
                      {s.provider}
                    </span>
                  </td>
                  <td className="px-2 py-2">
                    <Category s={s} />
                  </td>
                  <td className="px-4 py-2">
                    <FeedbackBadge isGood={s.is_good} />
                  </td>
                </tr>
                {open === s.id && (
                  <tr className="border-token border-b" style={{ background: "var(--surface-0)" }}>
                    <td colSpan={5} className="px-4 py-3">
                      <Detail s={s} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={5} className="text-muted px-4 py-8 text-center">
                  {searches.isError
                    ? "Can't reach the optimizer server."
                    : searches.isLoading
                      ? "Loading…"
                      : "No searches match."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-end gap-3 text-sm">
        <span className="text-secondary">
          Page {page + 1} of {pages}
        </span>
        <button className="control disabled:opacity-40" disabled={page === 0} onClick={() => set("page", String(page - 1))}>
          ← Newer
        </button>
        <button
          className="control disabled:opacity-40"
          disabled={page + 1 >= pages}
          onClick={() => set("page", String(page + 1))}
        >
          Older →
        </button>
      </div>
    </div>
  );
}
