import type { SearchHacksClient } from "./client.ts";

/**
 * Provider-agnostic tool definition for a chatbot harness. The shape matches the
 * common `{ name, description, input_schema }` convention used by LLM tool-use APIs.
 */
export const webSearchToolDefinition = {
  name: "search",
  description:
    "Search the web. Returns a list of results with title, url, and snippet, plus a feedback_token. " +
    "Wait for the user response before calling search_feedback to assess whether this search led to their goal.",
  input_schema: {
    type: "object",
    properties: {
      query: { type: "string", description: "The search query." },
    },
    required: ["query"],
  },
} as const;

export const webSearchFeedbackToolDefinition = {
  name: "search_feedback",
  description: "After the user responds, grade whether a prior-turn search led to their goal. Leave ambiguous outcomes pending.",
  input_schema: {
    type: "object",
    properties: {
      feedback_token: { type: "string" },
      feedback: { type: "object", properties: {
        purchase_conversion: { type: "boolean" },
        user_confirmed_outcome: { type: "boolean" },
        user_stopped_following_up: { type: "boolean" },
      }, additionalProperties: false, minProperties: 1 },
      evidence: { type: "string", description: "Evidence from the subsequent user response." },
    },
    required: ["feedback_token", "feedback", "evidence"],
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
      return { feedback_token: res.feedbackToken, provider: res.provider, results: res.results };
    }
    case webSearchFeedbackToolDefinition.name: {
      await client.submitFeedback(String(input.feedback_token), input.feedback as import("./client.ts").FeedbackRecord);
      return { ok: true };
    }
    default:
      throw new Error(`unknown tool: ${name}`);
  }
}
