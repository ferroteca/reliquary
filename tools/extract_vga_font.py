# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Extract the VGA 8×16 CP437 glyph bank from a local QEMU vgabios.

The agentless-display recognizer (F51/F52) must match the glyphs a
DOS guest actually paints. Those bit patterns live in the VGA BIOS
the host's QEMU already ships (``vgabios-stdvga.bin``). This tool
locates the classic 8×16 bank by its well-known ``A`` glyph and
writes ``src/reliquary/fonts/cp437_8x16.bin``.

The bytes are an interoperability fact of the IBM PC text mode,
curated into Reliquary so backends without a text-memory scrape can
read the same screens. Re-run after a QEMU upgrade if the guest
font drifts.

    uv run python tools/extract_vga_font.py
"""

from __future__ import annotations

import os
import sys

# Classic IBM VGA 8×16 capital A — the search key into vgabios.
_CLASSIC_A = bytes([
    0x00, 0x00, 0x10, 0x38, 0x6c, 0xc6, 0xc6, 0xfe,
    0xc6, 0xc6, 0xc6, 0xc6, 0x00, 0x00, 0x00, 0x00,
])


def _candidates():
    roots = [
        os.environ.get("RELIQUARY_QEMU_HOME"),
        os.environ.get("QEMU_HOME"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     "qemu"),
        "/usr/share/qemu",
        "/usr/share/seabios",
    ]
    names = ("vgabios-stdvga.bin", "vgabios.bin")
    for root in roots:
        if not root:
            continue
        share = os.path.join(root, "share")
        for base in (root, share, os.path.join(share, "qemu")):
            for name in names:
                path = os.path.join(base, name)
                if os.path.isfile(path):
                    yield path


def extract(vgabios_path):
    data = open(vgabios_path, "rb").read()
    idx = data.find(_CLASSIC_A)
    if idx < 0:
        raise SystemExit(
            f"classic VGA 'A' glyph not found in {vgabios_path}")
    base = idx - 0x41 * 16
    if base < 0 or base + 4096 > len(data):
        raise SystemExit(
            f"font base {base} is out of range in {vgabios_path}")
    return data[base:base + 4096]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    source = argv[0] if argv else None
    if source is None:
        found = list(_candidates())
        if not found:
            raise SystemExit(
                "no vgabios-stdvga.bin found; pass its path or set "
                "RELIQUARY_QEMU_HOME")
        source = found[0]
    font = extract(source)
    dest = os.path.join(
        os.path.dirname(__file__), "..", "src", "reliquary", "fonts",
        "cp437_8x16.bin")
    dest = os.path.normpath(dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as handle:
        handle.write(font)
    print(f"wrote {dest} from {source} ({len(font)} bytes)")


if __name__ == "__main__":
    main()
