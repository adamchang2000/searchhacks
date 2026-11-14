from optimizer_server.src.config.web import settings as web_settings

import os


def load() -> None:
    web_settings.DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
    web_settings.CORS_ALLOW_ALL_ORIGINS = web_settings.DEBUG
