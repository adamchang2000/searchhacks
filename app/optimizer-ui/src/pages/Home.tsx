import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

const REFRESH_MS = 2000;

function fmt(n: number | null | undefined, digits = 2) {
  return n == null ? "—" : n.toFixed(digits);
}

export function Home() {
  const stats = useQuery({
    queryKey: ["stats", "providers"],
    queryFn: async () => (await api.GET("/api/stats/providers")).data ?? [],
    refetchInterval: REFRESH_MS,
  });
  const searches = useQuery({
    queryKey: ["searches"],
    queryFn: async () =>
      (await api.GET("/api/searches", { params: { query: { limit: 50 } } })).data ?? [],
    refetchInterval: REFRESH_MS,
  });

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-6">
      <h1 className="text-3xl font-bold">SearchHacks Optimizer</h1>

      <section>
        <h2 className="mb-2 text-xl font-semibold">Providers</h2>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b">
              <th className="py-1">Provider</th>
              <th>Searches</th>
              <th>Feedback</th>
              <th>Mean score</th>
              <th>Mean latency (ms)</th>
            </tr>
          </thead>
          <tbody>
            {stats.data?.map((s) => (
              <tr key={s.provider} className="border-b">
                <td className="py-1 font-mono">{s.provider}</td>
                <td>{s.num_searches}</td>
                <td>{s.num_feedback}</td>
                <td>{fmt(s.mean_score)}</td>
                <td>{fmt(s.mean_latency_ms, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2 className="mb-2 text-xl font-semibold">Recent searches</h2>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b">
              <th className="py-1">Time</th>
              <th>Query</th>
              <th>Provider</th>
              <th>Results</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody>
            {searches.data?.map((s) => (
              <tr key={s.id} className="border-b">
                <td className="py-1">{new Date(s.created_at).toLocaleTimeString()}</td>
                <td>{s.query}</td>
                <td className="font-mono">{s.provider}</td>
                <td>{s.error ? "error" : (s.num_results ?? "—")}</td>
                <td>{fmt(s.feedback[0]?.score)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
