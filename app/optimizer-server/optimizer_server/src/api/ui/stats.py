from datetime import datetime, timedelta
from typing import Dict, List, Optional

from django.utils import timezone
from ninja import Router, Schema

from optimizer_server.src.apps.searches.models import Search
from optimizer_server.src.lib.optimizer.stats import compute_provider_stats

router = Router()


class ProviderStatsOut(Schema):
    provider: str
    num_searches: int
    num_feedback: int
    num_good: int
    good_rate: Optional[float]


@router.get("/providers", response=List[ProviderStatsOut])
def provider_stats(request):
    return compute_provider_stats()


class TrafficBucketOut(Schema):
    start: datetime
    # Searches started in this bucket, per chosen provider.
    by_provider: Dict[str, int]
    # Feedback state of those searches (as of now, not as of the bucket).
    good: int
    bad: int
    pending: int


class TrafficOut(Schema):
    start: datetime
    end: datetime
    bucket_seconds: int
    buckets: List[TrafficBucketOut]


MAX_BUCKETS = 720


@router.get("/traffic", response=TrafficOut)
def traffic(request, minutes: int = 60, bucket_seconds: int = 60):
    """Searches per time bucket over the trailing `minutes`, oldest bucket first.

    Empty buckets are included so the series is continuous.
    """
    minutes = max(1, min(minutes, 7 * 24 * 60))
    bucket_seconds = max(1, bucket_seconds)
    # Keep the response bounded: widen buckets rather than return thousands.
    bucket_seconds = max(bucket_seconds, -(-minutes * 60 // MAX_BUCKETS))

    now = timezone.now()
    epoch_now = int(now.timestamp())
    # Align buckets to wall-clock multiples so they don't shift between polls.
    last_start = epoch_now - epoch_now % bucket_seconds
    n = -(-minutes * 60 // bucket_seconds)
    first_start = last_start - (n - 1) * bucket_seconds
    start = datetime.fromtimestamp(first_start, tz=now.tzinfo)

    buckets = [
        {"start": datetime.fromtimestamp(first_start + i * bucket_seconds, tz=now.tzinfo),
         "by_provider": {}, "good": 0, "bad": 0, "pending": 0}
        for i in range(n)
    ]
    # Latest feedback submission per search (a plain join would repeat a search per submission).
    rows = Search.objects.filter(created_at__gte=start).with_latest_feedback().values_list(
        "created_at", "provider", "latest_good"
    )
    for created_at, provider, success in rows.iterator():
        i = (int(created_at.timestamp()) - first_start) // bucket_seconds
        if not 0 <= i < n:
            continue
        b = buckets[i]
        b["by_provider"][provider] = b["by_provider"].get(provider, 0) + 1
        key = "pending" if success is None else ("good" if success else "bad")
        b[key] += 1

    return {"start": start, "end": now, "bucket_seconds": bucket_seconds, "buckets": buckets}
