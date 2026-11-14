import { createOptimizerClient } from "@searchhacks/optimizer-protocol";

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const api = createOptimizerClient(API_BASE_URL);

/** Every dashboard query polls at this interval. */
export const REFRESH_MS = 2000;
