import { NavLink, Route, Routes } from "react-router-dom";
import { useIsFetching, useQuery } from "@tanstack/react-query";
import { Overview } from "./pages/Overview";
import { Searches } from "./pages/Searches";
import { API_BASE_URL, REFRESH_MS } from "./lib/api";

function ServerStatus() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE_URL}/api/health`);
      if (!res.ok) throw new Error(String(res.status));
      return true;
    },
    refetchInterval: REFRESH_MS * 2,
    retry: false,
  });
  const fetching = useIsFetching() > 0;
  const ok = health.isSuccess && !health.isError;
  return (
    <span className="text-secondary flex items-center gap-2 text-xs" title={API_BASE_URL}>
      <span
        className="inline-block h-2 w-2 rounded-full"
        style={{
          background: ok ? "var(--status-good)" : "var(--status-bad)",
          opacity: fetching ? 0.5 : 1,
        }}
      />
      {ok ? "live" : "server unreachable"} · {API_BASE_URL.replace(/^https?:\/\//, "")}
    </span>
  );
}

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm ${isActive ? "font-medium" : "text-secondary hover:underline"}`;

function App() {
  return (
    <div className="min-h-screen">
      <header className="border-token border-b" style={{ background: "var(--surface-1)" }}>
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-3">
          <span className="font-semibold">SearchHacks Optimizer</span>
          <nav className="flex gap-1">
            <NavLink to="/" end className={navClass}>
              Traffic
            </NavLink>
            <NavLink to="/searches" className={navClass}>
              Searches
            </NavLink>
          </nav>
          <span className="ml-auto">
            <ServerStatus />
          </span>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/searches" element={<Searches />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
