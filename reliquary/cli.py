# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Command-line interface for reliquary."""

import argparse
import importlib
import sys

from .home import set_home


def _load_recipe(name):
    """Import the recipe module for a hyphenated recipe name."""
    module = name.replace("-", "_")
    if not module.isidentifier():
        raise ValueError(f"invalid recipe name: {name}")
    try:
        return importlib.import_module(f"reliquary.recipes.{module}")
    except ModuleNotFoundError as error:
        raise ValueError(f"unknown recipe: {name}") from error


def main(args=None):
    """Entry point for the reliquary CLI."""
    parser = argparse.ArgumentParser(
        prog="reliquary",
        description="Script OS installations onto disk images.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    install = subparsers.add_parser(
        "install", help="run an OS installation recipe")
    install.add_argument(
        "recipe", help="recipe name, e.g. freedos-plain")
    install.add_argument(
        "--home", help="override the reliquary home directory")
    options = parser.parse_args(args)

    if options.home:
        set_home(options.home)
    try:
        recipe = _load_recipe(options.recipe)
    except ValueError as error:
        print(f"reliquary: {error}", file=sys.stderr)
        return 2
    artifacts = recipe.install()
    for name, path in artifacts.items():
        print(f"{name}: {path}")
    return 0
