2026-11-14 SearchHacks Hackathon Demo

High-level: We're building some optimizer which optimizes which search provider that we route
web search queries to based on feedback provided by the user of the search (e.g. the AI chatbot).

The core components are:
1. Some form of SDK that implements some web search tool that the AI chatbot integrates into the harness. The SDK is responsible
for contacting our optimizer server as well as dispatching calls to the actual search provider (for the purposes of this hackathon,
the search provider we'll use is telem).
2. Some optimizer server that is responsible for:
- Instructing the SDK to direct a given query to a given search provider
- Receiving feedback from the SDK
- Tracking historical searches and feedback and optimizing over historical results.
3. Some mock driver which hooks into the optimizer server API and mocks out the AI chatbot (so that we can generate large
amounts of synthetic data without incurring LLM inference costs as well as search provider costs)
4. Some dashboard to visualize the current state of the optimizer.

Code structure:
1. lib/sdk
- probably typescript
2. app/optimizer-server
- probably python
3. app/mock-driver
- maybe all typescript, maybe some typescript some python.
- not sure if we're going to have a server here, or we just make it a full typescript frontend (adam: i advocate for full typescript only)
4. app/optimizer-ui
- typescript

5. lib/optimizer-protocol
- the HTTP protocol that the optimizer server exports

6. app/chatbot
- and then later, we'll need to mock out a chatbot harness, probably at app/chatbot, which actually uses lib/sdk and hooks
in telem properly. this is so we can generate real traces for the demo

## Layout

```
├── Makefile                      # install / generate-api / server / ui / mock-driver
├── package.json                  # npm workspaces for all TS packages
├── lib/
│   ├── optimizer-protocol/       # OpenAPI schema + generated TS types + typed client
│   └── sdk/                      # SearchHacksClient, SearchProvider interface, telem provider, tool defs
└── app/
    ├── optimizer-server/         # Django + django-ninja (uv); routing policy in src/lib/optimizer
    ├── optimizer-ui/             # Vite + React dashboard
    ├── mock-driver/              # Node CLI that generates synthetic search + feedback traffic
    └── chatbot/                  # TODO
```

Protocol flow (SDK ↔ optimizer server):

1. `POST /api/searches/route` `{query, available_providers}` → `{search_id, provider}`
2. SDK dispatches the query to `provider`
3. `POST /api/searches/{search_id}/outcome` `{latency_ms, num_results, error}`
4. `POST /api/searches/{search_id}/feedback` `{score ∈ [0,1], comment}` (from the chatbot)

Dashboard reads `GET /api/searches` and `GET /api/stats/providers`.

## Development

```bash
make install        # uv sync + npm install
make migrate
make server         # http://localhost:8000, API docs at /api/docs
make ui             # http://localhost:5173
make mock-driver ARGS="--n 500 --concurrency 8"
```

After changing any API schema on the server, run `make generate-api` and commit the updated
`lib/optimizer-protocol/schema.json` and `src/generated/api.ts`.
