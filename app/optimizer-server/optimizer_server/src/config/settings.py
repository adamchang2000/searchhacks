from optimizer_server.src.config.db.settings import *
from optimizer_server.src.config.logging.settings import *
from optimizer_server.src.config.secret_key import SECRET_KEY
from optimizer_server.src.config.web.settings import *

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django.contrib.auth",
    "ninja",
    "corsheaders",
    "optimizer_server",
    "optimizer_server.src.apps.searches",
]

ROOT_URLCONF = "optimizer_server.src.server.urls"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
