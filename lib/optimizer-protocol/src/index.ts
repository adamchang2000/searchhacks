import type { components } from "./generated/api.ts";

export type { paths, components, operations } from "./generated/api.ts";
export { createOptimizerClient, type OptimizerClient } from "./client.ts";

type Schemas = components["schemas"];

export type RouteRequest = Schemas["RouteRequest"];
export type RouteResponse = Schemas["RouteResponse"];
export type OutcomeRequest = Schemas["OutcomeRequest"];
export type FeedbackRequest = Schemas["FeedbackRequest"];
export type SearchOut = Schemas["SearchOut"];
export type ProviderStatsOut = Schemas["ProviderStatsOut"];
