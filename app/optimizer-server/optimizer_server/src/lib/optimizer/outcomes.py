"""How much each feedback outcome counts as evidence that a search was good or bad.

A search's latest feedback submission adds, for each outcome it reports:

    true  -> GOOD_IF_TRUE  pseudo-observations of "good"
    false -> BAD_IF_FALSE  pseudo-observations of "bad"

The sums feed the Beta posteriors directly (fractional counts are fine), so a stronger signal
moves routing more. Fields a submission omits are unknown and add nothing. A search is
"good" overall (dashboard filters, traffic chart) when its good weight exceeds its bad weight.

    outcome                     true          false
    purchase_conversion         +2.0 good     +0.5 bad    very strong when true
    user_confirmed_outcome      +1.0 good     +1.0 bad    strong either way
    user_stopped_following_up   +0.25 good    +0.25 bad   mild
"""

from typing import Dict, NamedTuple


class OutcomeWeight(NamedTuple):
    good_if_true: float
    bad_if_false: float


OUTCOME_WEIGHTS: Dict[str, OutcomeWeight] = {
    "purchase_conversion": OutcomeWeight(good_if_true=2.0, bad_if_false=0.5),
    "user_confirmed_outcome": OutcomeWeight(good_if_true=1.0, bad_if_false=1.0),
    "user_stopped_following_up": OutcomeWeight(good_if_true=0.25, bad_if_false=0.25),
}
