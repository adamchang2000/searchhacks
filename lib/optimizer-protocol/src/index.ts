import type { components } from "./generated/api.ts";
import type { SearchProvider } from "@searchhacks/types/search-provider";

export type { paths, components, operations } from "./generated/api.ts";
export { createOptimizerClient, type OptimizerClient } from "./client.ts";

type Schemas = components["schemas"];

// Provider slugs come from lib/types. The server types its schema with the Python
// SearchProvider, so the generated enum must match the TS one exactly; if they drift
// (e.g. one side gains a provider), this fails `make typecheck`.
type Equal<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;
const _providersMatch: Equal<Schemas["SearchProvider"], SearchProvider> = true;
void _providersMatch;
export type { SearchProvider };

// Protocol
export type WhichSearchRequest = Schemas["WhichSearchRequest"];
export type WhichSearchResponse = Schemas["WhichSearchResponse"];
export type SubmitFeedbackRequest = Schemas["SubmitFeedbackRequest"];
export type SubmitFeedbackResponse = Schemas["SubmitFeedbackResponse"];

// Dashboard
export type SearchOut = Schemas["SearchOut"];
export type SearchPageOut = Schemas["SearchPageOut"];
export type TrafficOut = Schemas["TrafficOut"];
export type TrafficBucketOut = Schemas["TrafficBucketOut"];
export type ProviderStatsOut = Schemas["ProviderStatsOut"];
