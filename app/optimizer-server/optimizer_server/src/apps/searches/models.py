import uuid

from django.db import models


class Search(models.Model):
    """One web search query that the SDK asked us to route."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    query = models.TextField()
    # Providers the SDK said it could dispatch to for this query.
    available_providers = models.JSONField(default=list)
    # Provider the optimizer chose.
    provider = models.CharField(max_length=64, db_index=True)
    # Free-form client info (e.g. client name, session id).
    client_metadata = models.JSONField(default=dict, blank=True)

    # Filled in when the SDK reports the dispatch outcome.
    outcome_reported_at = models.DateTimeField(null=True, blank=True)
    latency_ms = models.FloatField(null=True, blank=True)
    num_results = models.IntegerField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Feedback(models.Model):
    """Feedback from the search consumer (e.g. the chatbot) on a search's results."""

    search = models.ForeignKey(Search, on_delete=models.CASCADE, related_name="feedback")
    created_at = models.DateTimeField(auto_now_add=True)

    # Normalized quality score in [0, 1].
    score = models.FloatField()
    comment = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
