# The core loop API endpoints:

/api/which_search:
- takes in a natural language query
- returns a tuple of (search_provider, feedback_token)

/api/submit_feedback:
- takes in a feedback_token and feedback

# Business Logic

The core thesis is something like:
- For each query that comes in, we classify it into one of the google trends categories.
-- Hypothesis: Different search providers get better outcomes for different categories.

- For each category, we track statistics on the feedback given for each search provider for queries within that category.

- We run some explore-exploit optimization that tries to:
-- Once we have a statistically significant measurement that one search provider is better for a category, we try to route
a majority of traffic to it.
-- While also keeping some part of the population always trying out the other search providers to explore.

# Implementation

**Categories** (`src/lib/optimizer/categories.py`): we route on two levels of the Google Trends
hierarchy: the 25 top-level categories (L1) and their direct subcategories (L2). Category data
comes from `lib/types` (`QueryCategory`, `QUERY_CATEGORY_PARENTS`, `QUERY_CATEGORY_PATHS`).
Any category id resolves to `(L1, L2)` via its canonical path; a top-level id resolves to
`(L1, None)`.

**Classification** (`src/lib/classifier/jev.py`): TypeSafe's jev decision model, two `choice`
questions in sequence: which L1, then which L2 among that L1's subcategories (a choice question
caps at 255 options, so all 1133 can't go in one). ~100-150ms per call. Needs `TYPESAFE_API_KEY`
in `config/dev-secrets.env`. If jev is unconfigured or fails, the query is routed unclassified
(global stats) instead of failing. `which_search`'s `override_query_category` skips classification.

Each `Search` row stores `category_l1`, `category_l2`, and `category_source` (`override`, the jev
model version, or `unclassified`), so stats can be recomputed if the classifier changes.

**Policy** (`src/lib/optimizer/policy.py`): hierarchical Thompson sampling. See
[POLICY_PRIMERS.md](POLICY_PRIMERS.md) for a worked example and how it learns over time.
- P(`is_good`) per (cell, provider) is a Beta posterior. Cells nest: global -> L1 -> L2.
- A cell's prior is its parent's posterior, scaled down to at most `PRIOR_STRENGTH` (20)
  pseudo-observations. A sparse subcategory therefore behaves like its parent category (most
  traffic to the parent's best providers: the "narrow to the top few" idea, without a hard
  cut), and diverges only as its own evidence accumulates.
- Route by drawing one sample per available provider and taking the max. With probability
  `EXPLORE_FLOOR` (5%), pick uniformly instead, so every provider keeps getting some traffic.

**Precomputed snapshot** (`src/lib/optimizer/distribution.py`): `which_search` does no feedback
aggregation. It looks up the precomputed Betas for its cell in memory and samples from them.
- `optimizer-recompute` (a separate process) aggregates all feedback once, computes every cell's
  posterior (global, each L1, each (L1, L2), times each provider with feedback), and writes a
  `SearchDistribution` snapshot with its `SearchDistributionCell` rows. It skips the write when
  no feedback changed and keeps the last 20 snapshots. Then it POSTs
  `/api/admin/reload-search-distribution`, and the server swaps the new snapshot in.
- `GET /api/admin/search-distribution` shows the snapshot being routed with. A fresh server
  loads the latest snapshot on its first request. With no snapshot, routing is uniform.
- Routing therefore lags feedback by up to one interval (10s on the VM). Thompson sampling keeps
  drawing per request, so this costs almost nothing. The sample is still drawn per request; only
  the Betas are cached.
- `POST /api/admin/reset-search-distribution` starts over: it writes a uniform Beta(1, 1)
  snapshot and sets `counts_since` to now. Every later recompute counts only searches created
  after that cutoff and carries it forward, so the reset isn't undone on the next run. History
  and Search/Feedback rows are kept.
- In-memory state is per process. The server runs as one uvicorn process, so one reload call is
  enough; with more workers, each would need to poll for the latest snapshot id.

```bash
uv run optimizer-recompute --config config/dev.json                         # once
uv run optimizer-recompute --config config/dev.json --loop --interval 10    # what the VM runs
```

**Known limits**
- SQLite runs in WAL mode with immediate transactions so concurrent drivers don't hit
  "database is locked"; writes are still serialized.
