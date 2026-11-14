import createClient from "openapi-fetch";
import type { paths } from "./generated/api.ts";

export type OptimizerClient = ReturnType<typeof createOptimizerClient>;

/**
 * Typed HTTP client for the optimizer server. Paths, params, request bodies and
 * responses are all checked against the generated OpenAPI types.
 */
export function createOptimizerClient(baseUrl: string) {
  return createClient<paths>({ baseUrl });
}
