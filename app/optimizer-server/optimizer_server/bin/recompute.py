#!/usr/bin/env python
"""optimizer-recompute: rebuild the routing snapshot from Search + Feedback, then tell the
server to reload it. Runs outside the server process (systemd unit or cron)."""

import argparse
import os


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Server config. Either this or the CONFIG envvar.")
    parser.add_argument(
        "--loop", action="store_true", help="Keep running, recomputing every --interval."
    )
    parser.add_argument(
        "--interval", type=float, default=10.0, help="Seconds between runs with --loop."
    )
    parser.add_argument(
        "--reload-url",
        default="http://localhost:8000/api/admin/reload-search-distribution",
        help="POSTed after each new snapshot. Pass '' to skip.",
    )
    parser.add_argument(
        "--force", action="store_true", help="Write a snapshot even if no feedback changed."
    )
    parser.add_argument(
        "--keep", type=int, default=20, help="Snapshots to keep in full (default 20)."
    )
    parser.add_argument(
        "--keep-history",
        type=int,
        default=2000,
        help="Snapshots to keep at all; older than --keep are thinned to global + level-1 cells.",
    )
    args = parser.parse_args()

    if args.config is not None and os.environ.get("CONFIG") is not None:
        raise RuntimeError("You can only provide one of --config and CONFIG envvar.")
    config_file = args.config or os.environ.get("CONFIG")
    if config_file is None:
        raise RuntimeError("You must provide one of --config or the CONFIG envvar.")

    from optimizer_server.src.recompute import run

    run(
        config_file=config_file,
        loop=args.loop,
        interval_s=args.interval,
        reload_url=args.reload_url or None,
        force=args.force,
        keep=args.keep,
        keep_history=args.keep_history,
    )


if __name__ == "__main__":
    main()
