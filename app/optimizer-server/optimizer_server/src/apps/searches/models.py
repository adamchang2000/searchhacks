import uuid

from django.db import models


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

    class Meta:
        ordering = ["-created_at"]


class Feedback(models.Model):
    """Feedback on one search's results. At most one per search; resubmitting overwrites."""

    search = models.OneToOneField(Search, on_delete=models.CASCADE, related_name="feedback")
    created_at = models.DateTimeField(auto_now=True)

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
