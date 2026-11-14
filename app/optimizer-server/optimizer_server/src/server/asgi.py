from optimizer_server.src.server.config import load

import os

if not (config_file := os.getenv("CONFIG")):
    raise RuntimeError("Please set the [CONFIG] environment variable.")

load(config_file=config_file)

from django.core.asgi import get_asgi_application

application = get_asgi_application()
