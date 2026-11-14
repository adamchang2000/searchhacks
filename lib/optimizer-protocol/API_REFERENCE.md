# Optimizer server API reference

HTTP API exported by `app/optimizer-server`. Everything is JSON under `/api`.

- **Source of truth:** [`schema.json`](schema.json) (OpenAPI, exported from the server by
  `make generate-api`). The typed TS client in [`src/`](src/) is generated from it. If this
  page and the schema disagree, the schema wins; please fix this page.
- **Interactive docs:** `GET /api/docs` on a running server (local: http://localhost:8000/api/docs,
  deployed: https://searchhacks-optimizer.exe.xyz/api/docs, exe.dev login required).
- **Base URLs:** local `http://localhost:8000`; from the driver VM `https://optimizer.int.exe.xyz`.
- **Auth:** none. The deployed server is reachable only through exe.dev (login-gated proxy or
  peer integration).

| Group | Endpoints | Stability |
|---|---|---|
| [Protocol](#protocol) | `POST /api/which_search`, `POST /api/submit_feedback` | Core contract with the SDK / drivers |
| [Health](#health) | `GET /api/health` | Stable |
| [Admin](#admin) | `/api/admin/*` | Operational; may change |
| [Dashboard](#dashboard-apiui) | `/api/ui/*` | Backs `app/optimizer-ui` only; free to change with the UI |

## Conventions

- Timestamps are ISO 8601 UTC (`2026-11-14T22:48:09.267Z`).
- **Providers** are Telem provider slugs from `lib/types` `SearchProvider`:
  `brave`, `ceramic`, `exa`, `linkup`, `parallel`, `perplexity`, `seltz`, `serpapi`, `tavily`,
  `tinyfish`, `you`. The schema carries this as the `SearchProvider` enum.
- **Categories** are Google Trends category ids from `lib/types` `QueryCategory`. The optimizer
  routes on two levels: `category_l1` (one of the 25 top-level categories) and `category_l2` (a
  child of it). Both are `null` for an unclassified query.
- **Errors:** validation failures return `422` with `{"detail": [...]}` (pydantic errors) or
  `{"detail": "<message>"}`. Unknown ids return `404` `{"detail": "Not Found"}`.

---

## Protocol

The hot loop. The caller asks which provider to use, dispatches the search itself, then reports
how it went.

```
caller                          optimizer
  │  POST /api/which_search        │
  │ ─────────────────────────────▶ │  classify query, Thompson-sample a provider
  │ ◀───────────────────────────── │  {provider, feedback_token}
  │  (caller runs the search on    │
  │   `provider` itself)           │
  │  POST /api/submit_feedback     │
  │ ─────────────────────────────▶ │  append feedback row
```

### `POST /api/which_search`

Pick a provider for a query.

**Request** `WhichSearchRequest`

| Field | Type | Required | Notes |
|---|---|---|---|
| `query` | string | yes | Natural-language query. Classified into a category unless overridden. |
| `available_providers` | `SearchProvider[]` | yes, ≥ 1 | Providers the caller can dispatch to. The answer is always one of these. |
| `override_query_category` | int \| null | no | `QueryCategory` id to use instead of classifying (e.g. mock drivers that already know the category). Any level works; it's placed at its level-1 / level-2 path. |

**Response** `WhichSearchResponse`

| Field | Type | Notes |
|---|---|---|
| `provider` | `SearchProvider` | The provider to use. |
| `feedback_token` | uuid | Opaque. Pass it to `submit_feedback`. (It's also the search's id.) |

**Errors:** `422` if `available_providers` is empty or contains a name that isn't a
`SearchProvider`, or if `override_query_category` isn't a known category.

How the pick is made: the server holds the latest routing snapshot in memory (see
[Admin](#admin)) and Thompson-samples from the posterior Beta for the query's cell (finest of
level-2 → level-1 → global that exists). With 5% probability it picks uniformly at random instead
(exploration floor). Providers with no feedback anywhere are treated as Beta(1, 1).

```bash
curl -s localhost:8000/api/which_search -H 'content-type: application/json' \
  -d '{"query": "best hiking trails near sf", "available_providers": ["exa", "brave", "tavily"]}'
# {"provider": "exa", "feedback_token": "2f0c6c8e-..."}
```

### `POST /api/submit_feedback`

Report the outcome of a search.

**Request** `SubmitFeedbackRequest`

| Field | Type | Required | Notes |
|---|---|---|---|
| `feedback_token` | uuid | yes | From `which_search`. |
| `feedback` | `FeedbackRecord` | yes | See below. |

`FeedbackRecord` (no other fields allowed). Each is a strict boolean. Include only the outcomes you
actually observed and omit the rest; don't send `null`. At least one is required.

| Field | Meaning |
|---|---|
| `purchase_conversion` | The user went on to purchase. |
| `user_confirmed_outcome` | The user confirmed the answer worked for them. |
| `user_stopped_following_up` | The user stopped asking follow-ups (a proxy for satisfaction). |

A search counts as **good** if any reported outcome is `true`, and **bad** if outcomes were
reported but none is `true`.

**Response** `SubmitFeedbackResponse`: `{"ok": true}`

**Semantics:** feedback is append-only. Every call adds a row. Only the **latest** submission per
search counts (for routing and the dashboard). A later submission replaces earlier ones; it
doesn't merge with them.

**Errors:** `404` for an unknown `feedback_token`; `422` if `feedback` is empty, contains `null`,
or has unknown fields.

```bash
curl -s localhost:8000/api/submit_feedback -H 'content-type: application/json' \
  -d '{"feedback_token": "2f0c6c8e-...", "feedback": {"user_confirmed_outcome": true}}'
# {"ok": true}
```

---

## Health

### `GET /api/health`

`{"status": "ok"}` when the server is up.

---

## Admin

Routing snapshots. `which_search` never aggregates feedback itself. A separate process,
`optimizer-recompute` (every 10s on the VM), aggregates feedback into a **SearchDistribution**
snapshot: a posterior Beta(α, β) per provider for every cell (global, each level-1 category,
each level-1 / level-2 pair). Then it calls `reload-search-distribution`. The server routes
from the snapshot in memory.

All three endpoints return `SearchDistributionStatus`:

| Field | Type | Notes |
|---|---|---|
| `distribution_id` | int \| null | Snapshot in use. `null` if none has been computed (routing is uniform). |
| `computed_at` | datetime \| null | When that snapshot was written. |
| `num_feedback` | int | Feedback rows the snapshot was computed from. |
| `num_cells` | int | Cells loaded. |
| `counts_since` | datetime \| null | Only searches created at or after this count, set by the last reset. `null` means all searches count. |

### `GET /api/admin/search-distribution`

The snapshot the server is currently routing with.

### `POST /api/admin/reload-search-distribution`

Load the latest snapshot from the database into memory. `optimizer-recompute` calls this after
writing one. Call it yourself after writing snapshots out of band.

### `POST /api/admin/reset-search-distribution`

Start routing from scratch. This does three things:

1. Writes a uniform snapshot: Beta(1, 1) for every provider in every cell, flagged `is_reset`.
2. Sets the cutoff (`counts_since`) to now. Later recomputes count only searches created after
   the reset and carry the cutoff forward, so the reset sticks; it isn't undone on the next
   recompute.
3. Loads the new snapshot.

Nothing is deleted. Search and Feedback rows and earlier snapshots stay, so the dashboard keeps
the full history (and the reset shows up in it). To count everything again, run another reset
later or clear `counts_since` in the database.

```bash
curl -s -X POST localhost:8000/api/admin/reset-search-distribution
# {"distribution_id": 2, "computed_at": "...", "num_feedback": 0, "num_cells": 314,
#  "counts_since": "2026-11-14T22:48:09.267Z"}
```

---

## Dashboard (`/api/ui`)

Read-only endpoints for `app/optimizer-ui`. Not part of the protocol; shapes change with the UI.

### `GET /api/ui/searches`

Historical searches, newest first, filtered and paginated. Returns `SearchPageOut`
`{items: SearchOut[], total: int}`, where `total` counts all matches across pages.

| Query param | Default | Notes |
|---|---|---|
| `limit` | 50 | Clamped to 1 to 500. |
| `offset` | 0 | |
| `provider` | | Exact provider slug. |
| `feedback` | | `good`, `bad`, or `none` (no feedback yet), judged on the latest submission. |
| `category_l1` | | Level-1 category id; `-1` selects unclassified searches. |
| `q` | | Case-insensitive substring of the query text. |

`SearchOut`: `id` (= feedback token), `created_at`, `query`, `available_providers`, `provider`,
`category_l1`, `category_l2`, `category_source` (`override`, a classifier version like
`jev-1.14.0`, or `unclassified`), `feedback` (latest `FeedbackRecord`, or `null`), and
`feedback_at`.

### `GET /api/ui/stats/providers`

All-time totals per provider: `ProviderStatsOut[]` with `provider`, `num_searches`,
`num_feedback`, `num_good`, `good_rate` (`num_good / num_feedback`, `null` with no feedback).
These ignore any reset cutoff.

### `GET /api/ui/stats/traffic`

Searches per time bucket over a trailing window, oldest first, including empty buckets.

| Query param | Default | Notes |
|---|---|---|
| `minutes` | 60 | Window length, 1 to 10080 (7 days). |
| `bucket_seconds` | 60 | Bucket width. Widened automatically to keep ≤ 720 buckets. Buckets align to wall-clock multiples. |

Returns `TrafficOut` `{start, end, bucket_seconds, buckets[]}`. Each bucket is
`{start, by_provider: {slug: count}, good, bad, pending}`. `good` / `bad` / `pending` give the
current feedback state of the searches started in that bucket.

### `GET /api/ui/distribution/history`

One cell across snapshots, for the Optimizer tab.

| Query param | Default | Notes |
|---|---|---|
| `l1` | | Level-1 category id; omit for the global cell. |
| `max_points` | 240 | Evenly thinned to at most this many snapshots; the latest is always included. |

Returns `DistributionHistoryOut` `{l1, snapshots[]}`. Each snapshot is
`{id, created_at, by_provider: {slug: ProviderPosteriorOut}}`.

`ProviderPosteriorOut`:

| Field | Notes |
|---|---|
| `alpha`, `beta` | The posterior Beta, with the parent cell's prior folded in. |
| `p_best` | Share of Thompson picks this provider wins in the cell, before the 5% exploration. Sums to 1 over the cell. |
| `n_obs` | Feedback observed in exactly this cell (not inherited). |

Snapshots older than the newest 20 keep only the global and level-1 cells. That covers this
endpoint and the next one.

### `GET /api/ui/distribution/{distribution_id}/categories`

One snapshot's global cell plus every level-1 cell, for the category heatmap. Returns
`SnapshotCategoriesOut` `{id, created_at, cells: [{l1, by_provider}]}`; `l1` is `null` for the
global cell. `404` for an unknown snapshot.

---

## Changing the API

1. Edit the ninja schemas / routes in `app/optimizer-server/optimizer_server/src/api/`.
2. `make generate-api` to refresh `schema.json` and `src/generated/api.ts`, then `make typecheck`.
3. Update this page.
4. Commit all of it together.
