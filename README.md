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
│   ├── types/                    # shared cross-language types (Python + TS), see lib/types/README.md
│   └── sdk/                      # SearchHacksClient, SearchProvider interface, telem provider, tool defs
└── app/
    ├── optimizer-server/         # Django + django-ninja (uv); routing policy in src/lib/optimizer
    ├── optimizer-ui/             # Vite + React dashboard
    ├── mock-driver/              # Node CLI that generates synthetic search + feedback traffic
    └── chatbot/                  # TODO
```

Optimizer protocol (SDK / drivers ↔ optimizer server):

| Endpoint | Request | Response |
|---|---|---|
| `POST /api/which_search` | `{query, available_providers: string[], override_query_category?: int}` | `{provider, feedback_token}` |
| `POST /api/submit_feedback` | `{feedback_token, feedback: {purchase_conversion?, user_confirmed_outcome?, user_stopped_following_up?}}` (bools) | `{ok}` |

1. The caller sends the query and the providers it can dispatch to. The optimizer classifies the
   query into a Google Trends category (via jev), picks a provider for that category, and returns
   an opaque `feedback_token` linking later feedback to this call. Callers that already know the
   category (the mock driver) pass `override_query_category` to skip classification.
   `available_providers` must be Telem slugs from `lib/types` `SearchProvider`; any other name
   returns 422.
2. The caller dispatches the query to `provider` itself.
3. The caller reports whichever outcomes it observed with that token (at least one). A search
   counts as good if any reported outcome is `true`. A token can receive feedback any number of
   times: every submission is appended as a new row, and **only the latest one counts** (outcomes
   it omits are not carried over from earlier submissions). An unknown token returns 404.

Full endpoint reference (protocol, admin, dashboard): [`lib/optimizer-protocol/API_REFERENCE.md`](lib/optimizer-protocol/API_REFERENCE.md).

Dashboard endpoints live under `/api/ui/` (`GET /api/ui/searches` (filterable, paginated), `GET /api/ui/stats/providers`,
`GET /api/ui/stats/traffic` (searches per time bucket by provider)).
They back `app/optimizer-ui` only, aren't part of the core protocol, and are free to change with the UI.

## Development

```bash
make install        # uv sync + npm install
make migrate
make server         # http://localhost:8000, API docs at /api/docs
make ui             # http://localhost:5173 (set VITE_API_BASE_URL to point at another server)
make mock-driver ARGS="--n 500 --concurrency 8"
make typecheck      # tsc across every TS workspace
```

After changing any API schema on the server, run `make generate-api` and commit the updated
`lib/optimizer-protocol/schema.json` and `src/generated/api.ts`.

### Secrets

Secrets go in `app/optimizer-server/config/dev-secrets.env`, which is gitignored (`*secrets.env`)
and loaded after `dev.env`. The server runs without it, but then can't classify queries (they're
routed as unclassified). Create it once per machine:

```bash
printf 'TYPESAFE_API_KEY=%s\n' "<key>" > app/optimizer-server/config/dev-secrets.env
```

On the optimizer VM, write the same file at `~/searchhacks/app/optimizer-server/config/dev-secrets.env`
(e.g. over ssh). `make deploy` never touches it.

### Make targets

| Target | What it does |
|---|---|
| `make` / `make all` | Same as `make generate-api` |
| `make install` | `uv sync` the optimizer server + `npm install` all workspaces |
| `make generate-api` | Export the OpenAPI schema from the server, regenerate TS types in `lib/optimizer-protocol` |
| `make typecheck` | Typecheck every TS workspace |
| `make check-types` | Check that every `lib/types` type is identical in Python and TypeScript |
| `make migrate` | Apply Django migrations to the local dev DB |
| `make server` | Run the optimizer server locally with auto-reload (port 8000) |
| `make ui` | Run the dashboard dev server (port 5173) |
| `make mock-driver ARGS="..."` | Run the mock driver; `ARGS` go to the CLI (`--server`, `--n`, `--concurrency`, `--seed`, `--categories`) |
| `make bootstrap HOST=<vm>` | One-time, idempotent setup of a VM (see Deployment) |
| `make deploy HOST=<vm>` | Pull `main` on a VM, sync deps, restart its enabled services |
| `make enable HOST=<vm> UNIT=<unit>` | Enable + start a systemd service on a VM |
| `make logs HOST=<vm> UNIT=<unit>` | Tail a service's logs on a VM |

`<vm>` is `optimizer` or `driver` and is **required**: VM targets act on exactly one VM at a time.

## Deployment

Two exe.dev VMs, set up **identically** (Ubuntu 24.04, user `exedev`, repo at `~/searchhacks`,
`uv` + Node 22, every Python and JS package synced). They differ only in which
`searchhacks-*` systemd services each one has enabled.

| VM | Role | Reachable from the other VM at |
|---|---|---|
| `searchhacks-optimizer.exe.xyz` | long-lived optimizer server (`searchhacks-optimizer`, port 8000) + routing recompute loop (`searchhacks-optimizer-recompute`) | `https://optimizer.int.exe.xyz/` |
| `searchhacks-driver.exe.xyz` | drivers: mock driver now, chatbot / driver server later | `https://driver.int.exe.xyz/` |

**Cross-VM traffic:** exe.dev VMs share no private network. Each direction uses an exe.dev
**peer integration** (already attached both ways). The calling VM hits `https://<name>.int.exe.xyz/`
and exe.dev injects credentials at the network edge, so both VMs stay private and hold no API keys.
Integrations target port **8000** by default, so any server we run on either VM should listen on
`0.0.0.0:8000`.

### Layout

```
deploy/
├── bootstrap.sh              # one-time, idempotent: install uv + node, clone, then update.sh
├── update.sh                 # git pull, uv sync every app/*/pyproject.toml, npm ci,
│                             #   install unit files, restart this VM's enabled searchhacks-* units
└── systemd/
    ├── searchhacks-optimizer.service             # runs migrations (ExecStartPre), then the server on :8000
    └── searchhacks-optimizer-recompute.service   # recomputes the routing snapshot every 10s, tells the server to reload
```

There is no prod config: the VMs run everything with the same committed `config/dev.json`
(and `config/dev.env`) used locally, `DEBUG` included. The only per-VM file is the gitignored
`config/dev-secrets.env` (see Secrets).

### One-time setup

From your laptop, after the repo is pushed to `main`:

```bash
make bootstrap HOST=optimizer
make bootstrap HOST=driver
make enable HOST=optimizer UNIT=searchhacks-optimizer
make enable HOST=optimizer UNIT=searchhacks-optimizer-recompute
```

Check from the driver VM:

```bash
ssh searchhacks-driver.exe.xyz curl -s https://optimizer.int.exe.xyz/api/health
```

To browse the dashboard and API docs yourself (exe.dev login required), point the public proxy at port 8000:
`ssh exe.dev share port searchhacks-optimizer 8000`, then open https://searchhacks-optimizer.exe.xyz/api/docs.

### Shipping changes

Push to `main`, then:

```bash
make deploy HOST=optimizer                             # update.sh on the optimizer VM
make deploy HOST=driver                                # update.sh on the driver VM
make logs HOST=optimizer UNIT=searchhacks-optimizer    # tail logs
```

### Adding a service (e.g. a Python driver server)

1. Put the app in `app/<name>/` with its own `pyproject.toml`. `update.sh` picks it up automatically.
2. Add `deploy/systemd/searchhacks-<name>.service`, listening on `0.0.0.0:8000`.
3. `make deploy HOST=driver && make enable HOST=driver UNIT=searchhacks-<name>`.

### Running the mock driver

On the driver VM, use `tmux` for long runs:

```bash
cd ~/searchhacks
npm start -w @searchhacks/mock-driver -- --server https://optimizer.int.exe.xyz --n 5000 --concurrency 8 --seed 1
```

### Notes / open questions

- The VMs clone the repo anonymously over HTTPS, which only works because the repo is public.
  If it goes private again, each VM needs a read-only deploy key or `gh auth login`.
- SQLite lives at `app/optimizer-server/db.sqlite3` on the optimizer VM. Back it up before
  doing anything destructive.
- The optimizer server also serves the dashboard: `update.sh` builds `app/optimizer-ui/dist`, and
  every non-`/api` path returns it (SPA fallback to `index.html`). With the public proxy on port
  8000 (see above) it's at https://searchhacks-optimizer.exe.xyz/. Locally, `make ui` still runs
  the Vite dev server against `localhost:8000`.

### Mock-driver backend

The driver VM runs a Python/Django control API at https://searchhacks-driver.exe.xyz/api/ and, from the optimizer VM, https://driver.int.exe.xyz/api/. It exposes GET /health, GET /runs, POST /runs to start a simulation, and POST /runs/{id}/pause, /resume, and /stop. Run records are stored in app/mock-driver-server/db.sqlite3 on the driver VM.

Enable it with: make enable HOST=driver UNIT=searchhacks-mock-driver

### Simulation bed

The driver VM serves the simulation UI at https://searchhacks-driver.exe.xyz/simulation.
Its Python backend stores scenarios, runs, and search events in SQLite. The default
scenario has Shopping, Travel, and Computer Science queries with weighted traffic and
provider success rates. Edit values in the UI, save, then start/pause/resume/stop a run.
The worker calls only the optimizer's which_search and submit_feedback endpoints.
The simulator's category is recorded with each event; the optimizer's current routing
policy still aggregates feedback across categories.

### Feedback outcomes

The existing /api/submit_feedback endpoint now accepts a feedback_token and a feedback
record with observed booleans: purchase_conversion, user_confirmed_outcome, and
user_stopped_following_up (after more than one query). Omit unknown fields. Partial
submissions merge observations; missing fields are not false. For routing, any observed
true currently counts as success; an observed record containing only false values counts
as failure. Historical binary feedback stays stored separately without invented labels.

The simulator has provider/category dropdowns and one probability slider per outcome.
Each query samples a uniform latent goodness: outcome probability p is met when
goodness >= 1-p. This correlates outcomes while preserving their marginal probabilities.
Cessation is sampled at the end of each synthetic three-query session. The chart plots
successful feedback submissions by time and latent goodness, with outcome fields on hover.
Latent goodness is simulator diagnostic data; it is not sent as optimizer feedback.

### Simulation configs and traffic

The first Simulation tab lists saved configs. Load one to restore its settings, or
name and save a new snapshot after editing. Existing saved snapshots are never overwritten.
Traffic has one QPS slider and runs continuously until paused or stopped. Changes apply
to the next run. Category mix lists all 1,132 non-root Google Trends categories, with
search and weights from 0 (disabled) to 100. Each category has a pregenerated three-query
corpus in query_corpus.json; query text appears only in the live feed.
