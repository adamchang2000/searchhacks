from typing import List, Optional

from ninja import Router, Schema

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
