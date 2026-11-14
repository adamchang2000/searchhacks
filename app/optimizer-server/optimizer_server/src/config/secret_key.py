from typing import Optional

SECRET_KEY: str = ""


def load(secret_key_override: Optional[str]) -> None:
    global SECRET_KEY

    if secret_key_override is not None:
        SECRET_KEY = secret_key_override
    else:
        import os

        value = os.environ.get("SECRET_KEY")
        if value is None:
            raise RuntimeError("SECRET_KEY environment variable must be set.")
        SECRET_KEY = value
