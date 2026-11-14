from optimizer_server.src.config.db.db import DBConfig, load as load_db_config
from optimizer_server.src.config.initialize import initialize_django
from optimizer_server.src.config.logging.logging import load as load_logging_config
from optimizer_server.src.config.secret_key import load as load_secret_key_config
from optimizer_server.src.config.web.web import load as load_web_config

from optimizer_server.src.config.env_files import load_env_files

from pydantic import BaseModel, Field

import json
from typing import List


class ServerConfig(BaseModel):
    env_files: List[str] = Field(default_factory=list)

    db_config: DBConfig = Field(...)


def load(config_file: str) -> None:
    with open(config_file, "r") as f:
        config = ServerConfig.model_validate(json.load(f))

    load_env_files(config_file, config.env_files)

    load_secret_key_config(secret_key_override=None)
    load_logging_config()
    load_db_config(config.db_config)
    load_web_config()

    initialize_django()
