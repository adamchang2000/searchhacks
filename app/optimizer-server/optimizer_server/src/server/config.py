from optimizer_server.src.config.db.db import DBConfig, load as load_db_config
from optimizer_server.src.config.initialize import initialize_django
from optimizer_server.src.config.logging.logging import load as load_logging_config
from optimizer_server.src.config.secret_key import load as load_secret_key_config
from optimizer_server.src.config.web.web import load as load_web_config

from pydantic import BaseModel, Field

import json
from pathlib import Path
from typing import Optional


class ServerConfig(BaseModel):
    env_file: Optional[str] = Field(default=None)

    db_config: DBConfig = Field(...)


def load(config_file: str) -> None:
    with open(config_file, "r") as f:
        config = ServerConfig.model_validate(json.load(f))

    if config.env_file:
        from dotenv import load_dotenv

        env_file_path = Path(config.env_file)
        if not env_file_path.is_absolute():
            config_dir = Path(config_file).parent
            env_file_path = config_dir / env_file_path
        load_dotenv(env_file_path)

    load_secret_key_config(secret_key_override=None)
    load_logging_config()
    load_db_config(config.db_config)
    load_web_config()

    initialize_django()
