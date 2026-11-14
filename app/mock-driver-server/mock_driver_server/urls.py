from pathlib import Path
from mock_driver_server.navigation import render_driver_page
from django.conf import settings
from django.http import FileResponse, HttpResponseRedirect
from django.urls import path
from ninja import NinjaAPI
from mock_driver_server.api import health_router
from mock_driver_server.sim import router as sim_router
from mock_driver_server.chat import router as chat_router, chat_stream

api = NinjaAPI(title="Mock Driver API", version="1.0.0", docs_url="/docs" if settings.DEBUG else None)
api.add_router("/health", health_router)
api.add_router("/sim", sim_router)
api.add_router("/chat", chat_router)

def simulation(request):
    return render_driver_page("simulation.html", "simulation")

def shared_styles(request):
    response = FileResponse(open(Path(__file__).with_name("shared.css"), "rb"), content_type="text/css")
    response["Cache-Control"] = "no-cache"
    return response

def chatbot(request):
    return render_driver_page("chatbot.html", "chat")

urlpatterns = [
    path("", lambda request: HttpResponseRedirect("/simulation")),
    path("simulation", simulation),
    path("chat", chatbot),
    path("assets/shared.css", shared_styles),
    path("api/chat/stream", chat_stream),
    path("api/", api.urls),
]
