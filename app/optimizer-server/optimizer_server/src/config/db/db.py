from pydantic import BaseModel, Field

import os
from typing import Any, Dict, Literal, Optional, assert_never

DATABASES: dict = {}


class PostgresConfig(BaseModel):
    name: str = Field(...)
    host: str = Field(...)
    port: int = Field(...)

    @classmethod
    def load(cls, config: Dict[str, Any]):
        global DATABASES

        db_username = os.environ.get("DB_USERNAME")
        db_password = os.environ.get("DB_PASSWORD")

        if db_username is None or db_password is None:
            raise RuntimeError(
                "DB_USERNAME and DB_PASSWORD environment variables must be set."
            )

        cfg = cls(**config)
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": cfg.name,
                "USER": db_username,
                "PASSWORD": db_password,
                "HOST": cfg.host,
                "PORT": cfg.port,
            }
        }


class SqliteConfig(BaseModel):
    type: Literal["memory", "file"] = Field(...)
    file: Optional[str] = Field(default=None)

    @classmethod
    def load(cls, config: Dict[str, Any]):
        global DATABASES

        cfg = cls(**config)

        if cfg.type == "memory":
            name = ":memory:"
        elif cfg.type == "file":
            if cfg.file is None:
                raise RuntimeError(
                    "SqliteConfig: For type=file, file must be provided."
                )
            name = cfg.file
        else:
            assert_never(cfg.type)

        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": name,
            }
        }


DB_TYPE = Literal["postgres", "sqlite"]


class DBConfig(BaseModel):
    type: DB_TYPE
    config: Dict[str, Any]


def load(db_config: DBConfig) -> None:
    db_type = db_config.type

    if db_type == "postgres":
        PostgresConfig.load(db_config.config)
    elif db_type == "sqlite":
        SqliteConfig.load(db_config.config)
    else:
        assert_never(db_type)
