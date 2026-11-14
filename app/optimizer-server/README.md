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

**Policy** (`src/lib/optimizer/policy.py`): hierarchical Thompson sampling.
- P(`is_good`) per (cell, provider) is a Beta posterior. Cells nest: global -> L1 -> L2.
- A cell's prior is its parent's posterior, scaled down to at most `PRIOR_STRENGTH` (20)
  pseudo-observations. A sparse subcategory therefore behaves like its parent category (most
  traffic to the parent's best providers: the "narrow to the top few" idea, without a hard
  cut), and diverges only as its own evidence accumulates.
- Route by drawing one sample per available provider and taking the max. With probability
  `EXPLORE_FLOOR` (5%), pick uniformly instead, so every provider keeps getting some traffic.

**Known limits**
- `which_search` re-aggregates all feedback per request. Fine at hackathon scale; cache the
  counts in memory if it gets slow.
- SQLite runs in WAL mode with immediate transactions so concurrent drivers don't hit
  "database is locked"; writes are still serialized.
