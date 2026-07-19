# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Agentless DOS provisioning and guest interaction."""

import os
import re


def program_name(path):
    """Return the DOS command name for a supported executable path."""
    name = os.path.basename(path)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,8}\.[Ee][Xx][Ee]", name):
        raise ValueError(f"guest executable needs a DOS 8.3 name: {name}")
    return name
