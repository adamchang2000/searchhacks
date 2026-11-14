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

    class Meta:
        ordering = ["-created_at"]


class Feedback(models.Model):
    """Feedback on one search's results. At most one per search; resubmitting overwrites."""

    search = models.OneToOneField(Search, on_delete=models.CASCADE, related_name="feedback")
    created_at = models.DateTimeField(auto_now=True)

    # Placeholder signal until we decide what feedback really is.
    is_good = models.BooleanField()
