from optimizer_server.src.api import api

from django.urls import path

urlpatterns = [
    path("api/", api.urls),
]
