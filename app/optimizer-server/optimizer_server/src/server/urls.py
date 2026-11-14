from optimizer_server.src.api import api
from optimizer_server.src.server.ui import ui

from django.urls import path, re_path

urlpatterns = [
    path("api/", api.urls),
    # Everything else is the dashboard (app/optimizer-ui build output).
    re_path(r"^(?P<path>.*)$", ui),
]
