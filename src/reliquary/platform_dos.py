# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Agentless DOS provisioning and guest interaction.

What a DOS guest names, reliquary names the same way — but only for
what it actually drives. The drive-letter map and the guest-address
grammar that once lived here went with the volume mapping and the
in-band file family (D108): reliquary declares a machine's drives and
moves their media, and what is *inside* a volume is the caller's
(P16's file-content carve-out), so nothing here translates a host
path into a letter any more.
"""

import os
import re

from .errors import StaticError


def program_name(path):
    """Return the DOS command name for a supported executable path."""
    name = os.path.basename(path)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,8}\.[Ee][Xx][Ee]", name):
        raise StaticError(f"guest executable needs a DOS 8.3 name: {name}",
            rule_id="name.not-dos-8-3")
    return name
