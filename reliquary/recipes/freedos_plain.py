# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""FreeDOS installation recipe (Milestone 1)."""


def install(media_dir, output_dir, runner):
    """Build a minimal FreeDOS bootable floppy from FloppyEdition media.

    Args:
        media_dir: Path to the extracted or mounted FreeDOS 1.4
                   FloppyEdition media directory.
        output_dir: Directory to write output artifacts (floppy image).
        runner: A relict Runner instance configured for the build
                environment.

    Returns:
        Path to the resulting floppy image.

    Raises:
        NotImplementedError: Recipe not yet implemented.
    """
    raise NotImplementedError("FreeDOS recipe not yet implemented")
