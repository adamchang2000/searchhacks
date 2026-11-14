import uuid

from django.db import models
from django.db.models import BooleanField, Case, OuterRef, Q, Subquery, Value, When

# Outcome fields a feedback submission may report (see api/optimizer.py FeedbackRecord).
OUTCOME_FIELDS = ("purchase_conversion", "user_confirmed_outcome", "user_stopped_following_up")


class SearchQuerySet(models.QuerySet):
    def with_latest_feedback(self) -> "SearchQuerySet":
        """Annotate each search with its latest feedback submission:

            latest_<outcome>     that submission's value for each outcome field
            latest_feedback_at   when it was submitted
            latest_good          True if any outcome is true, False if outcomes were reported
                                 but none is true, None if the search has no feedback

        All null if the search has no feedback. Feedback is an append-only log, so readers
        should go through this rather than joining Feedback directly (a join would see every
        submission, and count a search once per submission). Filter good / bad / none with
        latest_good=True / latest_good=False / latest_good__isnull=True: CASE WHEN treats a
        NULL outcome as "not this branch", where a plain `NOT (a OR b)` would turn NULL and
        silently drop the row.
        """
        latest = Feedback.objects.filter(search=OuterRef("pk")).order_by("-id")
        positive = Q(*(Q(**{f"latest_{f}": True}) for f in OUTCOME_FIELDS), _connector=Q.OR)
        observed = Q(
            *(Q(**{f"latest_{f}__isnull": False}) for f in OUTCOME_FIELDS), _connector=Q.OR
        )
        return self.annotate(
            **{f"latest_{f}": Subquery(latest.values(f)[:1]) for f in OUTCOME_FIELDS},
            latest_feedback_at=Subquery(latest.values("created_at")[:1]),
        ).annotate(
            latest_good=Case(
                When(positive, then=Value(True)),
                When(observed, then=Value(False)),
                default=Value(None),
                output_field=BooleanField(null=True),
            )
        )


class Search(models.Model):
    """One `which_search` call: a query and the provider the optimizer chose for it."""

    # Also serves as the opaque `feedback_token` handed back to the caller.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    query = models.TextField()
    # Providers the caller said it could dispatch to for this query.
    available_providers = models.JSONField(default=list)
    # Provider the optimizer chose.
    provider = models.CharField(max_length=64, db_index=True)

    # Where the query sits in the Google Trends hierarchy (lib/types query-category ids).
    # Both null when unclassified; category_l2 null when classified only to top level.
    category_l1 = models.IntegerField(null=True, blank=True)
    category_l2 = models.IntegerField(null=True, blank=True)
    # What assigned the category: "override", a jev model version (e.g. "jev-1.14.0"),
    # or "unclassified".
    category_source = models.CharField(max_length=64, default="unclassified")

    objects = SearchQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]


class Feedback(models.Model):
    """One feedback submission for a search. Append-only: every submit_feedback call inserts
    a row and nothing is updated. The latest row per search (highest id) is the one that
    counts; read it via Search.objects.with_latest_feedback()."""

    search = models.ForeignKey(Search, on_delete=models.CASCADE, related_name="feedback_log")
    created_at = models.DateTimeField(auto_now_add=True)

    # Placeholder signal until we decide what feedback really is.
    legacy_is_good = models.BooleanField(null=True, blank=True)
    purchase_conversion = models.BooleanField(null=True, blank=True)
    user_confirmed_outcome = models.BooleanField(null=True, blank=True)
    user_stopped_following_up = models.BooleanField(null=True, blank=True)


class SearchDistribution(models.Model):
    """One snapshot of the routing posteriors, written by `optimizer-recompute`.

    The server routes from the latest snapshot held in memory (lib/optimizer/distribution.py),
    so `which_search` never aggregates feedback itself. Snapshots are immutable; a recompute
    writes a new one and old ones are pruned.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # What the snapshot was computed from: total feedback rows and the newest feedback write.
    # Recompute skips writing a snapshot when both are unchanged.
    num_feedback = models.IntegerField()
    feedback_through = models.DateTimeField(null=True, blank=True)
    # Only searches created at or after this count toward the snapshot. Set by a reset
    # (POST /api/admin/reset-search-distribution) and carried forward by every later
    # recompute, so a reset sticks. Null: all searches count.
    counts_since = models.DateTimeField(null=True, blank=True)
    # True for a snapshot written by a reset (uniform Beta(1, 1) everywhere).
    is_reset = models.BooleanField(default=False)
    # True while the snapshot has every cell. Older snapshots are thinned to the global and
    # level-1 cells (all the dashboard's history needs), so history can span a whole run.
    full = models.BooleanField(default=True)

    class Meta:
        ordering = ["-id"]


class SearchDistributionCell(models.Model):
    """Posterior Beta(alpha, beta) of `provider` being good in one routing cell.

    Cells: global (l1 and l2 null), each level-1 category (l2 null), each (l1, l2) pair.
    The hierarchy prior is already folded in. Providers with no feedback anywhere have no rows;
    their posterior is Beta(1, 1) everywhere.
    """

    distribution = models.ForeignKey(
        SearchDistribution, on_delete=models.CASCADE, related_name="cells"
    )
    category_l1 = models.IntegerField(null=True, blank=True)
    category_l2 = models.IntegerField(null=True, blank=True)
    provider = models.CharField(max_length=64)
    alpha = models.FloatField()
    beta = models.FloatField()
    # Chance this provider wins the Thompson draw in this cell, among the providers in the
    # snapshot (before EXPLORE_FLOOR). Sums to 1 over a cell's providers. For the dashboard.
    p_best = models.FloatField(default=0.0)
    # Feedback observed in exactly this cell for this provider (not inherited from parents).
    n_obs = models.IntegerField(default=0)
