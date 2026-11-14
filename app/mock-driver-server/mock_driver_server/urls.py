from pathlib import Path
from django.conf import settings
from django.http import FileResponse, HttpResponseRedirect
from django.urls import path
from ninja import NinjaAPI
from mock_driver_server.api import health_router
from mock_driver_server.sim import router as sim_router

api = NinjaAPI(title="Mock Driver API", version="1.0.0", docs_url="/docs" if settings.DEBUG else None)
api.add_router("/health", health_router)
api.add_router("/sim", sim_router)

def simulation(request):
    return FileResponse(open(Path(__file__).with_name("simulation.html"), "rb"), content_type="text/html")

urlpatterns = [
    path("", lambda request: HttpResponseRedirect("/simulation")),
    path("simulation", simulation),
    path("api/", api.urls),
]
