# Policy primer

How the optimizer decides which search provider gets a query, and how that decision improves
as feedback comes in. Code: `optimizer_server/src/lib/optimizer/policy.py`.

Every number below came from running that code (`PRIOR_STRENGTH = 20`, `EXPLORE_FLOOR = 0.05`).

## The problem

Each query arrives with a category (e.g. Finance › Investing) and a list of providers we may use.
We pick one, and later get feedback on how the search went. We want to:

- **exploit**: send most traffic to whichever provider is best for this kind of query, and
- **explore**: keep trying the others, because we might be wrong, especially early on.

This is a *multi-armed bandit*: each provider is an "arm" with an unknown success rate, and
every query is one pull. The policy is **Thompson sampling**, with one twist for the category
hierarchy.

## 1. One belief per provider: the Beta distribution

For a provider in some context, we track `good` and `bad` evidence and turn it into a belief
about its true success rate: **Beta(1 + good, 1 + bad)**.

**Where good and bad come from.** Feedback reports up to three outcomes, and each one adds
weighted evidence (`lib/optimizer/outcomes.py`):

| outcome | true | false |
|---|---|---|
| `purchase_conversion` | +2 good | +0.5 bad |
| `user_confirmed_outcome` | +1 good | +1 bad |
| `user_stopped_following_up` | +0.25 good | +0.25 bad |

So a confirmed search adds 1 good, a purchase adds 2 good (it's stronger evidence), and a search
with a purchase but a "didn't reach my goal" adds 2 good and 1 bad. Unreported outcomes add
nothing, and only a search's latest feedback submission counts. The examples below use whole
numbers for readability, as if every search were graded with `user_confirmed_outcome`.

- Its **mean**, `alpha / (alpha + beta)`, is roughly the observed good-rate.
- Its **width** shrinks as evidence grows. Beta(3, 1) and Beta(30, 10) both have mean 0.75,
  but the first is "probably good, who knows", and the second is "pretty sure it's ~75%".
- With no data, Beta(1, 1) is flat: any success rate is equally plausible.

## 2. Thompson sampling: draw, then pick the max

To route a query:

1. For each available provider, **draw one random sample** from its Beta belief.
2. Send the query to the provider with the **highest draw**.

Here are five real routing decisions for a Finance › Investing query (beliefs from section 3):

| draw | exa | brave | tavily | routed to |
|---|---|---|---|---|
| 1 | 0.50 | **0.69** | 0.27 | brave |
| 2 | **0.45** | 0.45 | 0.37 | exa |
| 3 | 0.47 | **0.69** | 0.52 | brave |
| 4 | 0.49 | 0.47 | **0.51** | tavily |
| 5 | **0.65** | 0.49 | 0.47 | exa |

Why this balances exploring and exploiting by itself:

- A provider that's **clearly best** has a tall, narrow belief, so it wins most draws.
- A provider we're **unsure about** has a wide belief. Sometimes it draws high and gets a turn.
  That's exploration, and it happens exactly where we lack information.
- Each provider gets traffic **roughly in proportion to the chance it's the best**. As evidence
  piles up, beliefs narrow and traffic concentrates. Nobody tunes "how much to explore".

## 3. The twist: categories borrow from their parents

We could keep a fully separate belief per subcategory, but most subcategories are rare. With
only a handful of queries, they'd spend ages exploring from scratch. So beliefs are **nested**:

```
global (all queries)  ->  L1 category (e.g. Finance)  ->  L2 subcategory (e.g. Investing)
```

Each level's starting belief (its *prior*) is its parent's belief, **shrunk** to count as at
most 20 observations. Then the level's own counts are added on top.

- Shrinking keeps the parent's *opinion* (its mean) but caps its *confidence*. A parent
  with 500 observations can't drown out a subcategory's own 10.
- So a brand-new subcategory acts like its parent category, and drifts away only as its own
  feedback accumulates.

### Worked example: Finance › Investing

Feedback so far (`good/bad`; "global" counts every query, Finance included):

| provider | global | Finance (all subcategories) | Investing only |
|---|---|---|---|
| exa | 298/190 | 28/10 | 2/6 |
| brave | 235/238 | 10/13 | 3/0 |
| tavily | 185/275 | 5/5 | none |

Building exa's belief, step by step:

| step | belief | mean |
|---|---|---|
| global: Beta(1 + 298, 1 + 190) | Beta(299.0, 191.0) | 0.61 |
| shrink to 20 observations | Beta(12.2, 7.8) | 0.61 |
| + Finance's 28/10 | Beta(40.2, 17.8) | 0.69 |
| shrink to 20 observations | Beta(13.9, 6.1) | 0.69 |
| + Investing's 2/6 | **Beta(15.9, 12.1)** | **0.57** |

All three providers at the end:

| provider | Finance belief (mean) | Investing belief (mean) | share of Investing traffic |
|---|---|---|---|
| exa | 0.69 | 0.57 | 52% |
| brave | 0.46 | 0.53 | 37% |
| tavily | 0.44 | 0.44 (no own data) | 11% |

What happened:

- **Finance overall** clearly favors exa. Finance queries with no subcategory route **95%** to
  exa, and the sibling subcategory Retirement & Pension (where exa went 26/4) routes **97%**.
- **Investing** inherited that preference, but its own evidence disagrees: exa went 2/6 and
  brave went 3/0. Eight bad-ish results aren't proof, so Investing is now **split** between exa
  and brave while it gathers more data. That's the hedging you want with this little evidence.
- **tavily** has no Investing data, so it carries Finance's opinion (0.44) and gets the
  occasional look.

## 4. The exploration floor

Thompson sampling can starve a provider it's confident is bad. That's correct today, but
providers change (new index, outage fixed). So with probability **5%**, the policy ignores the
beliefs and picks uniformly at random. Every provider always keeps a trickle of traffic
(with 3 providers, at least ~1.7% each), so a provider that improves can be noticed.

## 5. Learning over time

A simulation using the real policy from a fresh start: one category, 75% of queries in a
typical subcategory **A**, 25% in a specialist subcategory **B** where the category's winner
is bad.

True success rates (hidden from the policy):

| subcategory | exa | brave | tavily |
|---|---|---|---|
| A (typical) | **0.80** | 0.55 | 0.50 |
| B (specialist) | 0.40 | **0.85** | 0.50 |

Share of recent traffic over time:

| queries so far | A → exa | B → brave |
|---|---|---|
| 25 | 30% | 50% |
| 100 | 100% | 90% |
| 300 | 96% | 95% |
| 600 | 98% | 95% |
| 1500 | 99% | 98% |

Across 20 random seeds, the final share was **97%** (A → exa) and **96%** (B → brave).

- **Early (first ~25)**: beliefs are wide, so traffic is spread out. That's exploration.
- **By ~100**: both subcategories have found their winner. B broke away from the category's
  favorite (exa) because its own bad exa results outweighed the 20-observation prior.
- **After that**: traffic stays concentrated, minus the exploration floor.

One quirk: at the end, B's belief about **exa** is still ~0.63, though its true rate there is
0.40. Once exa looked worse in B, it stopped getting B traffic, so B never collected enough
exa data to correct the inherited prior. That's fine: the policy only needs to know exa
*isn't the best* in B, not its exact rate. But don't read these beliefs as accurate estimates
for providers that rarely get traffic.

## Knobs

| knob | default | raise it | lower it |
|---|---|---|---|
| `PRIOR_STRENGTH` | 20 | subcategories follow their parent longer; steadier, slower to specialize | subcategories trust their own (noisy) data sooner |
| `EXPLORE_FLOOR` | 0.05 | notices changing providers faster, but wastes more traffic | less waste, slower to notice change |

## What it doesn't do (yet)

- **Forget.** Counts never decay, so a provider that was bad last week stays penalized by old
  data. Fix: decay or window the counts.
- **Weigh cost or latency.** It maximizes P(good) only.
- **Merge DAG parents.** A subcategory under two categories (e.g. Sports News under News and
  Sports) learns separately under each.
