import os


def initialize_django() -> None:
    os.environ["DJANGO_SETTINGS_MODULE"] = "optimizer_server.src.config.settings"

    import django

    django.setup()
