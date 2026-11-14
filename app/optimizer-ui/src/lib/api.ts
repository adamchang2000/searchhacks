import { createOptimizerClient } from "@searchhacks/optimizer-protocol";

export const api = createOptimizerClient(
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
);
