# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Relict home resolution and containment."""

import os
import subprocess
import sys


_home = os.environ.get("RELICT_HOME")
_home_announced = False


def set_home(path):
    """Configure the relict work directory (overrides RELICT_HOME)."""
    global _home
    _home = os.path.abspath(path)


def documents_dir():
    """The user's Documents folder, or None if it cannot be determined."""
    if sys.platform == "win32":
        import ctypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", ctypes.c_ulong),
                        ("Data2", ctypes.c_ushort),
                        ("Data3", ctypes.c_ushort),
                        ("Data4", ctypes.c_ubyte * 8)]

        folderid_documents = GUID(
            0xFDD39AD0, 0x238F, 0x46AF,
            (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85,
                                 0x48, 0x03, 0x69, 0xC7))
        path = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(folderid_documents), 0, None,
                ctypes.byref(path)):
            return None
        try:
            return path.value
        finally:
            ctypes.windll.ole32.CoTaskMemFree(path)
    if sys.platform == "darwin":
        return os.path.expanduser(os.path.join("~", "Documents"))
    try:
        documents = subprocess.run(
            ["xdg-user-dir", "DOCUMENTS"], capture_output=True, text=True,
        ).stdout.strip()
        if os.path.isabs(documents):
            return documents
    except OSError:
        pass
    return None


def home():
    global _home, _home_announced
    if not _home:
        base = documents_dir() or os.path.expanduser("~")
        _home = os.path.join(base, "relict")
    if not _home_announced:
        _home_announced = True
        print(f"using relict home: {_home}", file=sys.stderr)
    return _home


def effective_home(explicit):
    """Return the explicit operation home or the process-global home."""
    return os.path.abspath(explicit) if explicit else home()


def drives_dir(home=None):
    """Return the declared-drive directory under the effective home."""
    return os.path.join(effective_home(home), "drives")
