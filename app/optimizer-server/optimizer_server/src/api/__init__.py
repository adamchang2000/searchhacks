from optimizer_server.src.api.admin import router as admin_router
from optimizer_server.src.api.health import router as health_router
from optimizer_server.src.api.optimizer import router as optimizer_router
from optimizer_server.src.api.ui import router as ui_router

from django.conf import settings
from ninja import NinjaAPI

api = NinjaAPI(
    title="Optimizer API",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
)

api.add_router("/health", health_router)
# Core protocol (the hot loop): /api/which_search, /api/submit_feedback
api.add_router("", optimizer_router)
# Dashboard: /api/ui/*
api.add_router("/ui", ui_router)
# Operational: /api/admin/* (e.g. reload the routing snapshot)
api.add_router("/admin", admin_router)
