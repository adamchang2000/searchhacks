# Chatbot

The Python driver serves the chatbot at /chat and model turns at /api/chat/message.
It uses the VM's LLM integration (LLM_BASE_URL defaults to https://llm.int.exe.xyz/v1,
LLM_MODEL defaults to router/auto). Conversations and tool messages persist in
chat.sqlite3, which is excluded from Git.

The model receives search and search_feedback tools. Its system prompt
in mock_driver_server/chat.py instructs it to wait for the subsequent user response and grade an outcome only when there is evidence of success or failure. The server permits feedback only for prior-turn search tokens; ambiguous outcomes remain pending.
Feedback describes whether the search led to the user goal, using evidence from the subsequent user response.
There are no manual feedback buttons. The model calls search_feedback with outcome evidence.

Each search sends available underlying provider slugs to the optimizer.
SEARCH_PROVIDERS defaults to exa,brave,parallel. The chosen slug is pinned using
Telem search.providers.include; Telem does not independently auto-route this call.
The UI shows provider selection, sources, and model feedback per search.

TELEM_BASE_URL defaults to https://hack.telem.ai/api. The Telem key is loaded from
the private VM environment file outside the repository and never sent to browsers.
The TypeScript SDK exposes TelemProvider with a required provider option naming
the underlying provider slug. Register one adapter per provider with SearchHacksClient.

Simulation and chatbot use /assets/shared.css for their common theme.

The UI consumes /api/chat/stream (newline-delimited JSON) to display optimizer routing, provider execution, sources, feedback submission/acceptance, errors, and completion as they happen.
