export {
  SearchHacksClient,
  type SearchHacksClientOptions,
  type SearchOptions,
  type SearchResponse,
  type FeedbackRecord,
} from "./client.ts";
export type { SearchProvider, SearchResult } from "./providers/types.ts";
export { TelemProvider, type TelemProviderOptions } from "./providers/telem.ts";
export {
  webSearchToolDefinition,
  webSearchFeedbackToolDefinition,
  handleToolCall,
} from "./tool.ts";
