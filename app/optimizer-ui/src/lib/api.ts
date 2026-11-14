import { createOptimizerClient } from "@searchhacks/optimizer-protocol";

/**
 * In `vite dev` the API is a separate server (default localhost:8000). A production build
 * is served by the optimizer server itself, so it calls the API on its own origin.
 */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

export const api = createOptimizerClient(API_BASE_URL);

/** Every dashboard query polls at this interval. */
export const REFRESH_MS = 2000;
