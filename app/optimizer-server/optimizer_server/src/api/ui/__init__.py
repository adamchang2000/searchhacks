"""Endpoints backing app/optimizer-ui (the dashboard). Mounted at /api/ui/.
Not part of the core optimizer protocol; free to change with the UI."""

from ninja import Router

from optimizer_server.src.api.ui.distribution import router as distribution_router
from optimizer_server.src.api.ui.searches import router as searches_router
from optimizer_server.src.api.ui.stats import router as stats_router

router = Router(tags=["ui"])
router.add_router("/searches", searches_router)
router.add_router("/stats", stats_router)
router.add_router("/distribution", distribution_router)
