from optimizer_server.src.api.health import router as health_router
from optimizer_server.src.api.searches import router as searches_router
from optimizer_server.src.api.stats import router as stats_router

from django.conf import settings
from ninja import NinjaAPI

api = NinjaAPI(
    title="Optimizer API",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
)

api.add_router("/health", health_router)
api.add_router("/searches", searches_router)
api.add_router("/stats", stats_router)
