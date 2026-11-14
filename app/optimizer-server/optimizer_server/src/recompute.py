"""Body of `optimizer-recompute` (see bin/recompute.py)."""

import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger("optimizer_server.recompute")


def run(
    config_file: str,
    loop: bool,
    interval_s: float,
    reload_url: Optional[str],
    force: bool,
    keep: int,
) -> None:
    from optimizer_server.src.config.initialize import initialize_django
    from optimizer_server.src.manage.config import load_for_db_administration
    from optimizer_server.src.config.secret_key import load as load_secret_key_config

    load_for_db_administration(config_file=config_file)
    load_secret_key_config(secret_key_override="UNUSED-BY-RECOMPUTE")
    initialize_django()

    from optimizer_server.src.lib.optimizer import distribution

    while True:
        started = time.monotonic()
        try:
            dist = distribution.compute_and_save(force=force, keep=keep)
            if dist is None:
                logger.info("no new feedback; snapshot unchanged")
            else:
                logger.info(
                    "wrote search distribution %s from %d feedback in %.2fs",
                    dist.id,
                    dist.num_feedback,
                    time.monotonic() - started,
                )
                if reload_url:
                    _notify(reload_url)
        except Exception:
            if not loop:
                raise
            logger.exception("recompute failed; retrying next interval")
        if not loop:
            return
        force = False
        time.sleep(max(0.0, interval_s - (time.monotonic() - started)))


def _notify(url: str) -> None:
    try:
        resp = httpx.post(url, timeout=10.0)
        resp.raise_for_status()
        logger.info("server reloaded: %s", resp.json())
    except httpx.HTTPError as e:
        # The server may be down or restarting; it loads the latest snapshot on first use.
        logger.warning("could not reach %s to reload: %s", url, e)
