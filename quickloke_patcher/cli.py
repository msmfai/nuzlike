# Copyright (C) 2026 Quicklocke contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .patcher import PatchError, apply_recipe, inspect_input


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="quickloke-patcher")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)

    apply = commands.add_parser("apply", help="validate and apply a structured recipe")
    apply.add_argument("--input", required=True, type=Path)
    apply.add_argument("--recipe", required=True, type=Path)
    apply.add_argument("--output", required=True, type=Path)

    inspect = commands.add_parser("inspect", help="print hashes for an owned input")
    inspect.add_argument("--input", required=True, type=Path)
    return root


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "apply":
            result = apply_recipe(arguments.input, arguments.recipe, arguments.output)
        else:
            result = inspect_input(arguments.input)
    except PatchError as error:
        print(f"quickloke-patcher: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
