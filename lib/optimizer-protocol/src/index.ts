import type { components } from "./generated/api.ts";

export type { paths, components, operations } from "./generated/api.ts";
export { createOptimizerClient, type OptimizerClient } from "./client.ts";

type Schemas = components["schemas"];

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
