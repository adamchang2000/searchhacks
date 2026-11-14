import type { SearchHacksClient } from "./client.ts";

/**
 * Provider-agnostic tool definition for a chatbot harness. The shape matches the
 * common `{ name, description, input_schema }` convention used by LLM tool-use APIs.
 */
export const webSearchToolDefinition = {
  name: "web_search",
  description:
    "Search the web. Returns a list of results with title, url, and snippet, plus a feedback_token. " +
    "After using the results, call web_search_feedback with the feedback_token and whether the results were good.",
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
  description: "Report whether a previous web_search returned good results.",
  input_schema: {
    type: "object",
    properties: {
      feedback_token: { type: "string" },
      is_good: { type: "boolean" },
    },
    required: ["feedback_token", "is_good"],
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
      return { feedback_token: res.feedbackToken, results: res.results };
    }
    case webSearchFeedbackToolDefinition.name: {
      await client.submitFeedback(String(input.feedback_token), Boolean(input.is_good));
      return { ok: true };
    }
    default:
      throw new Error(`unknown tool: ${name}`);
  }
}
