# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Reliquary home resolution and directory layout."""

import os

from relict import documents_dir

_home = os.environ.get("RELIQUARY_HOME")


def set_home(path):
    """Configure the reliquary work directory (overrides RELIQUARY_HOME)."""
    global _home
    _home = os.path.abspath(path)


def home():
    """Return the reliquary work directory, resolving it on first use."""
    global _home
    if not _home:
        base = documents_dir() or os.path.expanduser("~")
        _home = os.path.join(base, "reliquary")
    return _home


def install_media_dir(os_name):
    """Return the cached install media directory for one OS target."""
    return os.path.join(home(), "install-media", os_name)


def machine_dir(recipe_name):
    """Return the relict machine home for one recipe's guest state."""
    return os.path.join(home(), "machines", recipe_name)
