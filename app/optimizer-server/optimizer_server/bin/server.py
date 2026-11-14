#!/usr/bin/env python

import argparse
import os
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Run the server.")
    parser.add_argument(
        "--config",
        type=str,
        required=False,
        help="Path to the config file. Either provide this flag or set the CONFIG envvar.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on (default: 8000)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--auto-reload",
        action="store_true",
        help="Enable auto-reload on file changes",
    )
    args = parser.parse_args()

    cli_config = args.config
    env_config = os.environ.get("CONFIG")

    if cli_config is not None and env_config is not None:
        raise RuntimeError("You can only provide one of --config and CONFIG envvar.")
    elif cli_config is not None:
        os.environ["CONFIG"] = args.config
    elif env_config is not None:
        pass
    else:
        raise RuntimeError("You must provide one of --config or the CONFIG envvar.")

    reload_flag = ["--reload"] if args.auto_reload else []

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "optimizer_server.src.server.asgi:application",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ] + reload_flag

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nServer stopped.")
