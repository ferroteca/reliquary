# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Agentless DOS provisioning and guest interaction.

Reliquary uses the same names a DOS guest uses, but only for the
drives it actually manages. The drive-letter map and the
guest-address parsing that used to live in this file moved out along
with volume mapping and the in-band file family (D108): Reliquary
declares a machine's drives and moves media into them, but what is
inside a volume is the caller's business (the file-content carve-out
in P16). So this file no longer translates a host path into a drive
letter.
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
