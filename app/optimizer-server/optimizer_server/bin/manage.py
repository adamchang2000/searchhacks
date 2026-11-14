#!/usr/bin/env python

from optimizer_server.src.manage import main as main_internal

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Server management utilities.",
        usage="%(prog)s [--config CONFIG] -- <command> [command_args...]",
    )
    parser.add_argument(
        "--config",
        required=False,
        type=str,
        help="Server config, if the command requires it.",
    )
    parser.add_argument(
        "command_args",
        nargs="*",
        help="Django management command and its arguments",
    )
    args = parser.parse_args()

    if not args.command_args:
        parser.print_help()
        sys.exit(1)

    command = args.command_args[0]
    command_remaining_args = args.command_args[1:]

    cli_config = args.config
    env_config = os.environ.get("CONFIG")

    config_file = None

    if cli_config is not None and env_config is not None:
        raise RuntimeError("You can only provide one of --config and CONFIG envvar.")
    elif cli_config is not None:
        config_file = args.config
        os.environ["CONFIG"] = args.config
    elif env_config is not None:
        config_file = os.environ["CONFIG"]

    main_internal(
        command=command,
        command_remaining_args=command_remaining_args,
        config_file=config_file,
    )
