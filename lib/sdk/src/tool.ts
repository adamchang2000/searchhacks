import type { SearchHacksClient } from "./client.ts";

/**
 * Provider-agnostic tool definition for a chatbot harness. The shape matches the
 * common `{ name, description, input_schema }` convention used by LLM tool-use APIs.
 */
export const webSearchToolDefinition = {
  name: "web_search",
  description:
    "Search the web. Returns a list of results with title, url, and snippet, plus a search_id. " +
    "After using the results, call web_search_feedback with the search_id and a 0-1 usefulness score.",
  input_schema: {
    type: "object",
    properties: {
      query: { type: "string", description: "The search query." },
    },
    required: ["query"],
  },
} as const;

export const webSearchFeedbackToolDefinition = {
  name: "web_search_feedback",
  description: "Rate how useful a previous web_search was, from 0 (useless) to 1 (exactly what was needed).",
  input_schema: {
    type: "object",
    properties: {
      search_id: { type: "string" },
      score: { type: "number", minimum: 0, maximum: 1 },
      comment: { type: "string" },
    },
    required: ["search_id", "score"],
  },
} as const;

/** Dispatch a tool call from the harness to the SDK client. */
export async function handleToolCall(
  client: SearchHacksClient,
  name: string,
  input: Record<string, unknown>,
): Promise<unknown> {
  switch (name) {
    case webSearchToolDefinition.name: {
      const res = await client.search(String(input.query));
      return { search_id: res.searchId, results: res.results };
    }
    case webSearchFeedbackToolDefinition.name: {
      await client.feedback(
        String(input.search_id),
        Number(input.score),
        input.comment === undefined ? undefined : String(input.comment),
      );
      return { ok: true };
    }
    default:
      throw new Error(`unknown tool: ${name}`);
  }
}
