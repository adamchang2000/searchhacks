from django.conf import settings
from ninja import NinjaAPI
from django.urls import path
from mock_driver_server.api import health_router, runs_router
api = NinjaAPI(title="Mock Driver API", version="1.0.0", docs_url="/docs" if settings.DEBUG else None)
api.add_router("/health", health_router)
api.add_router("/runs", runs_router)
urlpatterns = [path("api/", api.urls)]
