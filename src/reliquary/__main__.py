# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Run the reliquary command-line interface as a module."""

import sys

from . import main

if __name__ == "__main__":
    sys.exit(main())
