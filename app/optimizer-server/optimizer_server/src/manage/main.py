import sys
from typing import List, Literal, Optional, get_args

from typing_extensions import TypeIs

NON_DB_ADMINISTRATION_COMMAND = Literal[
    "check",
    "collectstatic",
    "makemigrations",
]

DB_ADMINISTRATION_COMMAND = Literal[
    "migrate",
    "showmigrations",
    "dbshell",
    "shell",
]

EXPORT_SCHEMA_COMMAND = Literal[
    "export_openapi_schema",
]


def is_non_db_administration_command(
    command: str,
) -> TypeIs[NON_DB_ADMINISTRATION_COMMAND]:
    return command in get_args(NON_DB_ADMINISTRATION_COMMAND)


def is_db_administration_command(command: str) -> TypeIs[DB_ADMINISTRATION_COMMAND]:
    return command in get_args(DB_ADMINISTRATION_COMMAND)


def is_export_schema_command(command: str) -> TypeIs[EXPORT_SCHEMA_COMMAND]:
    return command in get_args(EXPORT_SCHEMA_COMMAND)


def get_all_commands() -> List[str]:
    return list(
        get_args(NON_DB_ADMINISTRATION_COMMAND)
        + get_args(DB_ADMINISTRATION_COMMAND)
        + get_args(EXPORT_SCHEMA_COMMAND)
    )


def _set_secret_key() -> None:
    from optimizer_server.src.config.secret_key import load as load_secret_key_config

    load_secret_key_config(secret_key_override="FAKE-SECRET-KEY-DEVELOPMENT-ONLY")


def main(
    command: str,
    command_remaining_args: List[str],
    config_file: Optional[str],
) -> None:
    if is_non_db_administration_command(command):
        pass
    elif is_db_administration_command(command):
        if config_file is None:
            raise RuntimeError(
                "For DB administration commands, config must be provided."
            )

        from optimizer_server.src.manage.config import load_for_db_administration

        load_for_db_administration(config_file=config_file)
    elif is_export_schema_command(command):
        pass
    else:
        raise RuntimeError(
            f"Invalid [command]. Please see [manage/main.py] for supported commands: {get_all_commands()}"
        )

    _set_secret_key()

    from optimizer_server.src.config.initialize import initialize_django

    initialize_django()

    from django.core.management import execute_from_command_line

    argv = [sys.argv[0], command] + command_remaining_args
    execute_from_command_line(argv)
