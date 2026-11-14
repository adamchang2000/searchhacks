import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def load_env_files(config_file: str, env_files: List[str]) -> None:
    """Load each env file (relative paths resolve against the config file's directory).

    Missing files are skipped, so optional ones like dev-secrets.env (gitignored) can be
    listed unconditionally. Later files don't override variables already set.
    """
    from dotenv import load_dotenv

    for env_file in env_files:
        path = Path(env_file)
        if not path.is_absolute():
            path = Path(config_file).parent / path
        if path.is_file():
            load_dotenv(path)
        else:
            logger.warning("env file %s not found; skipping", path)
