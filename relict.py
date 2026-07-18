# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""relict - generic QEMU guest automation harness.

Boot a caller-supplied guest in QEMU and drive it from scripts: send
keystrokes, read the text screen (scraped from VGA memory - no OCR),
take screenshots, and issue monitor commands. Talks QMP (QEMU's JSON
control protocol) on 127.0.0.1. The guest machine's drives are
whatever the user declares in the drives/ directory under the home,
each entry named for what it is: image files floppy[_<n>].<ext>,
hdd[_<n>].<ext>, and cdrom[_<n>].<ext> mount as that medium in any
QEMU-supported image format under its idiomatic extension (*.img
and *.iso are raw, any other extension is left to QEMU to
identify); bare directories floppy[_<n>] and hdd[_<n>] mount as
virtual FAT drives. <n> is the slot (unindexed means 0); image
content is never interrogated. When nothing bootable is declared,
the freely distributable FreeDOS 1.4 boot floppy is downloaded and
used (a minimal kernel + FreeCOM system - stage any external DOS
utilities you need on a staged drive along with your programs).

Built on QEMU's official Python QMP library (qemu.qmp) — relict fills
the machine-lifecycle role of QEMU's in-tree QEMUMachine (which is not
published to PyPI) and adds the DOS-specific layer on top. Install
with pip; prerequisites are QEMU and Python 3.

All on-disk state lives under the relict **home** directory - user
data (downloaded and possibly user-customized boot images, staged
guest drives), never written next to the installation. It defaults to
a visible relict/ under the user's Documents folder (falling back
to ~/relict when no Documents folder can be determined); override
with the RELICT_HOME environment variable, --home on the command
line, or relict.set_home() from Python. Layout under home:
drives/ (the machine's declared drives and download artifacts; the
FreeDOS fallback is fetched from download.freedos.org)
and screenshots/ (screenshots).

Guest-agnostic by default. DOS behavior is enabled only when callers
explicitly select ``platform="dos"``. That adapter supplies FreeDOS
provisioning, DOS prompt detection, command execution, and one-shot
8.3 executable runs. Generic callers use ``run_task()`` with a
callable that drives a running ``Machine`` through the mechanisms
appropriate to their guest.

Project-agnostic by design:
nothing here knows about any host project's binaries or tests.
Callers stage a directory of DOS programs (by convention drives/hdd
under the home, mounted as a virtual FAT hard disk) and
project-specific test drivers import this module or shell out to
it.

Commands:
  download            ensure something bootable is declared under
                      drives/, downloading the FreeDOS boot floppy
                      when nothing is
  start [--display] [--qemu-args ...]
                      boot DOS, mounting everything declared under
                      drives/. Memory defaults to 16 MB and the
                      boot order to a best guess from the mounted
                      media (slot-0 floppy image, else slot-0 hard
                      disk image, else cdrom); pass -m or -boot in
                      the extra QEMU arguments to override either.
                      Re-start after changing staged contents.
  stop                shut the VM down
  boot-to-dos         wait out the boot sequence to a DOS prompt
  type "text"         type text into the guest, followed by Enter
  run "command"       type a command and wait for the DOS prompt to
                      return (agentless completion detection)
  keys k1 k2 ...      send raw QEMU key names (e.g. down ret)
  text                print the guest's 80x25 text screen (via 0xB8000)
  wait "regex"        poll the text screen until it matches (--timeout)
  screenshot NAME     save a screenshot as screenshots/NAME.png
  hmp "command"       send a human-monitor command, print the reply
"""

import argparse
import asyncio
import contextlib
import dataclasses
import hashlib
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.request
import uuid
import zipfile
import zlib

from qemu.qmp import ConnectError, ExecuteError, QMPClient

_home = os.environ.get("RELICT_HOME")


def set_home(path):
    """Configure the relict work directory (overrides RELICT_HOME)."""
    global _home
    _home = os.path.abspath(path)


def _documents_dir():
    """The user's Documents folder, or None if it cannot be determined."""
    if sys.platform == "win32":
        # SHGetKnownFolderPath, not %USERPROFILE%\Documents: the folder
        # may be redirected (OneDrive, roaming profiles, group policy)
        import ctypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", ctypes.c_ulong),
                        ("Data2", ctypes.c_ushort),
                        ("Data3", ctypes.c_ushort),
                        ("Data4", ctypes.c_ubyte * 8)]

        folderid_documents = GUID(
            0xFDD39AD0, 0x238F, 0x46AF,
            (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
        path = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(folderid_documents), 0, None, ctypes.byref(path)):
            return None
        try:
            return path.value
        finally:
            ctypes.windll.ole32.CoTaskMemFree(path)
    if sys.platform == "darwin":
        return os.path.expanduser(os.path.join("~", "Documents"))
    try:  # xdg-user-dir prints $HOME itself when no Documents dir is set
        documents = subprocess.run(
            ["xdg-user-dir", "DOCUMENTS"], capture_output=True, text=True,
        ).stdout.strip()
        if os.path.isabs(documents):
            return documents
    except OSError:
        pass
    return None


_home_announced = False


def home():
    global _home, _home_announced
    if not _home:
        # visible user data (customized images, staged drives, logs,
        # screenshots), so Documents, not AppData/XDG
        base = _documents_dir() or os.path.expanduser("~")
        _home = os.path.join(base, "relict")
    if not _home_announced:
        _home_announced = True
        # stderr: stdout of some commands (e.g. `text`) is parsed
        print(f"using relict home: {_home}", file=sys.stderr)
    return _home


def _effective_home(explicit):
    """The home directory one operation works in: the caller's
    explicit choice, or the process-global home. Explicit homes are
    how concurrent, independent runs coexist in one process (see
    Runner); every path helper and lifecycle function threads this
    through."""
    return os.path.abspath(explicit) if explicit else home()


def drives_dir(home=None):
    """The machine's drive configuration: the drives/ directory
    under home. Every entry named for a medium is mounted by
    start() - image files (floppy[_<n>].<ext>, hdd[_<n>].<ext>,
    cdrom[_<n>].<ext>) as that medium, bare directories
    (floppy[_<n>], hdd[_<n>]) as virtual FAT drives; <n> is the
    slot, 0 when unindexed. download() installs the FreeDOS floppy
    as floppy.img here when nothing bootable is declared."""
    return os.path.join(_effective_home(home), "drives")


def _check_staged_drive(letter):
    """Validate and normalize a staged-drive letter: a single letter
    from C to Z (A: and B: are the floppies). The guest assigns
    letters by disk order, so this is the caller declaring where the
    staged drive appears — C: with the default floppy boot image and
    the vvfat drive as the only hard disk, D: behind a hard-disk
    boot image that claims C:. Returns the letter uppercased."""
    normalized = str(letter).upper()
    if len(normalized) != 1 or not "C" <= normalized <= "Z":
        raise ValueError(
            f"staged_drive={letter!r}: the staged guest drive needs "
            "a single drive letter from C to Z (A: and B: are the "
            "floppies)")
    return normalized


def _staged_hdd_plan(media, drives):
    """Where run_guest_program() stages, resolved against the
    machine's declared hard-disk slots: the highest staged
    directory already declared among them, otherwise the first free
    slot (its conventional directory created on demand). Returns
    (path, default_letter); the default guest letter assumes each
    lower hard-disk slot contributes one drive letter - the guest
    assigns letters by disk order, beyond relict's control, so an
    explicit staged_drive is the caller's correction."""
    staged = [slot for slot, (_, is_dir) in media["hdd"].items()
              if is_dir]
    if staged:
        slot = max(staged)
        path = media["hdd"][slot][0]
    else:
        slot = 0
        while slot in media["hdd"]:
            slot += 1
        if slot >= _IDE_SLOTS:
            raise RuntimeError(
                "no free hard-disk slot to stage on: all "
                f"{_IDE_SLOTS} IDE slots are declared under "
                f"{drives}")
        path = os.path.join(drives,
                            "hdd" if slot == 0 else f"hdd_{slot}")
    lower = sum(1 for s in media["hdd"] if s < slot)
    return path, chr(ord("C") + lower)

_QEMU_BIN = "qemu-system-i386.exe" if os.name == "nt" else "qemu-system-i386"
_VM_STATE_FILE = "vm.json"


def _qemu_fallback_dirs():
    if os.name == "nt":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        scoop = os.environ.get("SCOOP", os.path.expanduser(r"~\scoop"))
        choco = os.environ.get("ChocolateyInstall",
                               r"C:\ProgramData\chocolatey")
        return [
            os.path.join(pf, "qemu"),
            os.path.join(pf86, "qemu"),
            os.path.join(scoop, "apps", "qemu", "current"),
            os.path.join(choco, "bin"),
            r"C:\msys64\ucrt64\bin",
            r"C:\msys64\mingw64\bin",
        ]
    dirs = ["/usr/bin", "/usr/local/bin", "/opt/qemu/bin"]
    if sys.platform == "darwin":
        dirs += ["/opt/homebrew/bin",    # Homebrew on Apple silicon
                 "/opt/local/bin"]       # MacPorts
    return dirs


def find_qemu():
    """Locate the QEMU binary: the RELICT_QEMU_HOME (or generic
    QEMU_HOME) directory if set (the install directory, not the binary
    path), then the system PATH, then well-known per-platform install
    locations."""
    for var in ("RELICT_QEMU_HOME", "QEMU_HOME"):
        qemu_home = os.environ.get(var)
        if not qemu_home:
            continue
        for d in (qemu_home, os.path.join(qemu_home, "bin")):
            cand = os.path.join(d, _QEMU_BIN)
            if os.path.isfile(cand):
                return cand
        raise FileNotFoundError(
            f"{_QEMU_BIN} not found under {var}={qemu_home}")
    found = shutil.which(_QEMU_BIN)
    if found:
        return found
    for d in _qemu_fallback_dirs():
        cand = os.path.join(d, _QEMU_BIN)
        if os.path.isfile(cand):
            return cand
    raise FileNotFoundError(
        f"{_QEMU_BIN} not found: install QEMU, add it to PATH, or set "
        "RELICT_QEMU_HOME to its install directory")

# characters that need shift on the QEMU (US) keyboard
_SHIFTED = {
    ":": "semicolon", "_": "minus", "?": "slash", '"': "apostrophe",
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6",
    "&": "7", "*": "8", "(": "9", ")": "0", "+": "equal",
    "<": "comma", ">": "dot", "{": "bracket_left", "}": "bracket_right",
    "|": "backslash", "~": "grave_accent",
}
_PLAIN = {
    " ": "spc", ".": "dot", "-": "minus", "=": "equal", "\\": "backslash",
    "/": "slash", ";": "semicolon", ",": "comma", "'": "apostrophe",
    "[": "bracket_left", "]": "bracket_right", "`": "grave_accent",
    "\n": "ret",
}


class Qmp:
    """Synchronous facade over the official asyncio qemu.qmp library."""

    def __init__(self, port):
        self._loop = asyncio.new_event_loop()
        self._client = QMPClient("relict")
        self._loop.run_until_complete(
            self._client.connect(("127.0.0.1", port)))

    def cmd(self, name, **arguments):
        return self._loop.run_until_complete(
            self._client.execute(name, arguments or None))

    def hmp(self, command_line):
        return self.cmd("human-monitor-command",
                        **{"command-line": command_line})

    def close(self):
        try:
            self._loop.run_until_complete(self._client.disconnect())
        except Exception:
            pass
        self._loop.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _state_path(home=None):
    return os.path.join(_effective_home(home), _VM_STATE_FILE)


def _read_vm_state(home=None):
    path = _state_path(home)
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        port = state["port"]
        name = state["name"]
        if (not isinstance(port, int) or isinstance(port, bool)
                or not 1 <= port <= 65535
                or not isinstance(name, str) or not name):
            raise ValueError("invalid port or name")
        return state
    except FileNotFoundError:
        return None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"invalid relict VM state file: {path}: {e}") from e


def _write_vm_state(port, name, pid, home=None):
    os.makedirs(_effective_home(home), exist_ok=True)
    path = _state_path(home)
    part = path + ".part"
    with open(part, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"port": port, "name": name, "pid": pid}, f, indent=2)
        f.write("\n")
    os.replace(part, path)


def _remove_vm_state(port=None, name=None, home=None):
    state = _read_vm_state(home)
    if not state:
        return
    if port is not None and state["port"] != port:
        return
    if name is not None and state["name"] != name:
        return
    try:
        os.remove(_state_path(home))
    except FileNotFoundError:
        pass


def _resolve_vm(port=None, home=None):
    state = _read_vm_state(home)
    if port is None:
        if not state:
            raise RuntimeError(
                "no active relict VM is recorded; run: relict start")
        return state["port"], state["name"]
    if not 1 <= port <= 65535:
        raise ValueError(f"QMP port must be between 1 and 65535: {port}")
    if not state or state["port"] != port:
        raise RuntimeError(
            f"QMP port {port} is not the recorded relict VM; "
            "start it with relict or omit --port to use the active VM")
    return port, state["name"]


def _verify_vm(q, port, expected_name):
    reply = q.cmd("query-name")
    actual_name = reply.get("name") if isinstance(reply, dict) else None
    if actual_name != expected_name:
        raise RuntimeError(
            "QMP identity mismatch; the unrelated VM was not modified\n"
            f"  expected: {expected_name} on 127.0.0.1:{port}\n"
            f"  found:    {actual_name or '<unnamed QMP server>'}")


@contextlib.contextmanager
def _qmp(port=None, home=None):
    """Yield an identity-verified QMP session.

    Every helper that takes `port` also accepts an already-open Qmp so
    callers doing many operations (or polling) can hold one connection.
    Otherwise the recorded VM identity is verified before yielding.
    """
    if isinstance(port, Qmp):
        yield port
    else:
        actual_port, expected_name = _resolve_vm(port, home)
        try:
            with Qmp(actual_port) as q:
                _verify_vm(q, actual_port, expected_name)
                yield q
        except (OSError, ConnectError) as e:
            _remove_vm_state(actual_port, expected_name, home)
            raise RuntimeError(
                "the recorded relict VM is no longer reachable\n"
                f"  expected: {expected_name} on "
                f"127.0.0.1:{actual_port}\n"
                "  stale VM state was removed") from e


def _char_keys(ch):
    """Map one character to a simultaneous QEMU qcode combination."""
    if ch in _PLAIN:
        return [_PLAIN[ch]]
    if ch in _SHIFTED:
        return ["shift", _SHIFTED[ch]]
    if ch.islower() or ch.isdigit():
        return [ch]
    if ch.isupper():
        return ["shift", ch.lower()]
    raise ValueError(f"no key mapping for {ch!r}")


def send_keys(combos, port=None, delay=0.06, home=None):
    """combos: list of key combinations, each a list of qcodes."""
    with _qmp(port, home) as q:
        for combo in combos:
            q.cmd("send-key",
                  keys=[{"type": "qcode", "data": k} for k in combo])
            time.sleep(delay)


def send_text(text, port=None, enter=True, home=None):
    combos = [_char_keys(c) for c in text]
    if enter:
        combos.append(["ret"])
    if home is None:
        send_keys(combos, port)
    else:
        send_keys(combos, port, home=home)


def screen_text(port=None, home=None):
    """The guest's 80x25 text screen: char/attr pairs at phys B8000h."""
    with _qmp(port, home) as q:
        raw = q.hmp("xp /4000bx 0xb8000")
    data = []
    for line in raw.splitlines():
        if not re.match(r"^[0-9a-f]+:", line):
            continue
        data.extend(int(tok, 16) for tok in line.split()[1:])
    rows = []
    for r in range(25):
        chars = data[r * 160:(r + 1) * 160:2]    # skip attribute bytes
        rows.append("".join(chr(b) if 32 <= b < 127 else " "
                            for b in chars).rstrip())
    return rows


_PROMPT_RE = re.compile(r"^[A-Z]:(\\[^>]*)?>$")


def run_command(command, timeout=120, port=None, home=None):
    """Type a command at the DOS prompt and wait for it to finish
    (agentless: polls the text screen until the bottom-most non-blank
    row is a bare DOS prompt again). Redirect output to a file on the
    staged C: drive (e.g. `foo -v > foo.log`) to retrieve it from the
    staging directory after `stop` - vvfat flushes guest writes back
    to the host directory."""
    with _qmp(port, home) as q:
        send_text(command, q)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rows = [r for r in screen_text(q) if r]
            if rows and _PROMPT_RE.match(rows[-1]):
                return
            time.sleep(2)
    raise TimeoutError(
        f"timed out after {timeout}s waiting for command to finish: "
        f"{command}")


def wait_screen(pattern, timeout=60, port=None, home=None):
    with _qmp(port, home) as q:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            screen = "\n".join(screen_text(q))
            if re.search(pattern, screen):
                return screen
            time.sleep(2)
    raise TimeoutError(
        f"timed out after {timeout}s waiting for screen to match: {pattern}")


# ---- the drives directory ---------------------------------------------------
#
# drives/ declares the whole machine - every entry whose name is a
# medium is mounted, and the content of an image is never
# interrogated. Image files (floppy[_<n>].<ext>, hdd[_<n>].<ext>,
# cdrom[_<n>].<ext>) attach as that medium in any QEMU-supported
# format under its idiomatic extension: *.img and *.iso are raw
# (pinned, which avoids QEMU's format-probing warning); any other
# extension (hdd.qcow2, ...) is handed to QEMU to identify. Bare
# directories (floppy[_<n>], hdd[_<n>]) attach as virtual FAT
# drives. <n> is the slot - floppies 0-1 (A: and B:), hard disks
# 0-3 (the IDE bus), cdroms on the IDE slots after the hard disks
# (their <n> only orders them); an unindexed name means slot 0, so
# hdd.img and hdd_0.img clash. When nothing bootable is declared,
# the freely distributable FreeDOS 1.4 boot floppy is downloaded as
# drives/floppy.img.

_FREEDOS_ZIP_URL = "https://download.freedos.org/1.4/FD14-FloppyEdition.zip"
# from https://www.freedos.org/download/verify.txt
_FREEDOS_ZIP_SHA256 = ("45b1fa7c52dd996c3bfa5e352ffcd410781b952a6ad629f15a4"
                       "c9ec4bbaefc5a")
_FREEDOS_BOOT_IMG = "144m/x86BOOT.img"  # member name inside the zip


_MEDIA_STEM_RE = re.compile(r"(floppy|hdd|cdrom)(?:_(\d+))?")

_FLOPPY_SLOTS = 2      # A: and B:
_IDE_SLOTS = 4         # two IDE buses, a master and a slave each


def _scan_drives(drives):
    """The machine description declared by the drives directory:
    {"floppy" | "hdd" | "cdrom": {slot: (path, is_dir)}}. Names
    matching no medium are ignored (download artifacts and the
    like); slot clashes, out-of-range slots, and cdrom directories
    fail closed."""
    media = {"floppy": {}, "hdd": {}, "cdrom": {}}
    try:
        names = sorted(os.listdir(drives))
    except FileNotFoundError:
        return media
    for name in names:
        path = os.path.join(drives, name)
        is_dir = os.path.isdir(path)
        stem = name if is_dir else os.path.splitext(name)[0]
        match = _MEDIA_STEM_RE.fullmatch(stem)
        if not match:
            continue
        medium, slot = match.group(1), int(match.group(2) or 0)
        if is_dir and medium == "cdrom":
            raise RuntimeError(
                f"cannot mount {path}: a staged directory cannot "
                "be a cdrom (virtual FAT emulates no ISO9660); "
                "provide a cdrom image instead")
        limit = _FLOPPY_SLOTS if medium == "floppy" else _IDE_SLOTS
        if medium != "cdrom" and slot >= limit:
            raise RuntimeError(
                f"cannot mount {path}: {medium} slots run from "
                f"0 to {limit - 1}")
        if slot in media[medium]:
            other = os.path.basename(media[medium][slot][0])
            raise RuntimeError(
                f"drive slot clash under {drives}: {other} and "
                f"{name} both claim {medium} slot {slot} (an "
                "unindexed name means slot 0)")
        media[medium][slot] = (path, is_dir)
    return media


def _format_options(image):
    """The -drive format option for an image, declared by its
    extension: *.img and *.iso are raw by idiom (pinned, which
    avoids QEMU's format-probing warning); any other extension is
    left for QEMU to identify."""
    ext = os.path.splitext(image)[1].lower()
    return "format=raw," if ext in (".img", ".iso") else ""


def _drive_args(media):
    """-drive arguments realizing the scanned machine description:
    floppies and hard disks at their declared slots, cdroms on the
    IDE slots after the hard disks."""
    args = []
    for slot in sorted(media["floppy"]):
        path, is_dir = media["floppy"][slot]
        source = (f"fat:floppy:rw:{path},format=raw," if is_dir
                  else f"{path},{_format_options(path)}")
        args += ["-drive", f"file={source}if=floppy,index={slot}"]
    for slot in sorted(media["hdd"]):
        path, is_dir = media["hdd"][slot]
        source = (f"fat:rw:{path},format=raw," if is_dir
                  else f"{path},{_format_options(path)}")
        args += ["-drive", f"file={source}if=ide,index={slot}"]
    next_ide = max(media["hdd"], default=-1) + 1
    for ordinal, slot in enumerate(sorted(media["cdrom"])):
        path, _ = media["cdrom"][slot]
        index = next_ide + ordinal
        if index >= _IDE_SLOTS:
            raise RuntimeError(
                f"cannot mount {path}: the IDE bus is full "
                f"({_IDE_SLOTS} slots, shared by hard disks and "
                "cdroms)")
        args += ["-drive", f"file={path},{_format_options(path)}"
                           f"media=cdrom,if=ide,index={index}"]
    return args


def _boot_guess(media):
    """Best-guess -boot order for the mounted media: the slot-0
    floppy image, else the slot-0 hard-disk image, else any cdrom;
    None when nothing bootable is declared (staged virtual FAT
    directories are not bootable)."""
    floppy = media["floppy"].get(0)
    if floppy and not floppy[1]:
        return "a"
    hdd = media["hdd"].get(0)
    if hdd and not hdd[1]:
        return "c"
    if media["cdrom"]:
        return "d"
    return None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download(home=None):
    """Ensure something bootable is declared: keep the drives
    directory as-is when it already mounts a bootable image
    (user-provided or previously downloaded), otherwise fetch the
    FreeDOS 1.4 FloppyEdition, verify its SHA-256 digest, and
    install its 1.44M boot floppy as drives/floppy.img. The archive
    itself is not kept."""
    drives = drives_dir(home)
    media = _scan_drives(drives)
    if _boot_guess(media) is not None:
        print(f"already bootable: {drives}")
        return
    if 0 in media["floppy"]:
        raise RuntimeError(
            f"nothing bootable is declared under {drives}, and the "
            "FreeDOS boot floppy cannot be installed: floppy slot 0 "
            f"is taken by the staged directory "
            f"{media['floppy'][0][0]}")
    _download_boot_image(drives)


def _download_boot_image(drives):
    """Fetch and verify the FreeDOS 1.4 boot floppy, installing it
    as floppy.img inside the given drives directory."""
    os.makedirs(drives, exist_ok=True)
    img = os.path.join(drives, "floppy.img")
    zip_path = os.path.join(drives, "FD14-FloppyEdition.zip")
    if not os.path.exists(zip_path):
        print("downloading FreeDOS 1.4 FloppyEdition (~23 MB) "
              "from download.freedos.org...")
        # download to a .part name so an interrupted transfer is
        # never mistaken for a complete zip on the next run
        part = zip_path + ".part"
        urllib.request.urlretrieve(_FREEDOS_ZIP_URL, part)
        os.replace(part, zip_path)
    digest = _sha256(zip_path)
    if digest != _FREEDOS_ZIP_SHA256:
        os.remove(zip_path)
        raise ValueError(
            f"checksum mismatch for {zip_path}:\n"
            f"  expected {_FREEDOS_ZIP_SHA256}\n"
            f"  got      {digest}\n"
            "the corrupt download was removed; retry")
    print(f"extracting {_FREEDOS_BOOT_IMG}...")
    with zipfile.ZipFile(zip_path) as zf:
        try:
            with zf.open(_FREEDOS_BOOT_IMG) as src, \
                    open(img + ".part", "wb") as dst:
                dst.write(src.read())
        except KeyError:
            raise FileNotFoundError(
                f"{_FREEDOS_BOOT_IMG} not found in the archive")
        os.replace(img + ".part", img)
    os.remove(zip_path)
    print(f"ready: {img}")


def _available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _port_in_use(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _startup_error(proc, stderr_log, port, automatic, detail, args):
    try:
        with open(stderr_log, errors="replace") as f:
            stderr = f.read().strip()
    except OSError:
        stderr = ""
    selection = "automatic" if automatic else "explicit"
    message = (f"{detail}\n"
               f"  QMP port: 127.0.0.1:{port} ({selection})\n"
               f"  stderr log: {stderr_log}")
    if proc.returncode is not None:
        message += f"\n  QEMU exit status: {proc.returncode}"
    if stderr:
        message += f"\n  QEMU error: {stderr}"
    message += f"\n  command line: {subprocess.list2cmdline(args)}"
    return RuntimeError(message)


def _terminate_started_process(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def start(display=False, qemu=None, port=None, qemu_args=(), home=None,
          platform="dos"):
    """Start a relict-owned QEMU process and return its QMP port.

    With port=None, an available port is selected automatically. An
    explicit port must be free. The active VM's identity is persisted
    under the relict home (`home` overrides the process-global one)
    so later invocations can find and verify it before issuing
    commands.

    The machine's drives are whatever the drives/ directory under
    home declares (see drives_dir()); everything declared is
    mounted, and when nothing bootable is present the FreeDOS boot
    floppy is downloaded first. Memory defaults to 16 MB and the
    boot order to a best guess from the mounted media (slot-0
    floppy image, else slot-0 hard-disk image, else cdrom); pass
    -m or -boot in qemu_args to override either default.
    """
    automatic_port = port is None
    port = _available_port() if automatic_port else port
    if not 1 <= port <= 65535:
        raise ValueError(f"QMP port must be between 1 and 65535: {port}")
    if _port_in_use(port):
        selection = "automatically selected" if automatic_port else "explicit"
        raise RuntimeError(
            f"QMP port 127.0.0.1:{port} is already in use "
            f"({selection}); choose another --port or stop its owner")
    old_state = _read_vm_state(home)
    if old_state:
        try:
            with Qmp(old_state["port"]) as old_q:
                _verify_vm(old_q, old_state["port"], old_state["name"])
        except (OSError, ConnectError):
            _remove_vm_state(old_state["port"], old_state["name"], home)
        else:
            raise RuntimeError(
                "a relict VM is already active\n"
                f"  name: {old_state['name']}\n"
                f"  QMP port: 127.0.0.1:{old_state['port']}\n"
                "stop it before starting another VM in this home")
    qemu = qemu or find_qemu()
    print(f"using QEMU: {qemu}")
    drives = drives_dir(home)
    media = _scan_drives(drives)
    if platform == "dos" and _boot_guess(media) is None:
        print(f"nothing bootable under {drives}; fetching FreeDOS")
        download(home)
        media = _scan_drives(drives)
    vm_name = f"relict-{uuid.uuid4().hex[:12]}"
    qemu_args = list(qemu_args)
    args = [qemu, "-name", vm_name]
    if platform == "dos" and "-m" not in qemu_args:
        args += ["-m", "16"]
    args += _drive_args(media)
    boot = _boot_guess(media)
    if boot is not None and "-boot" not in qemu_args:
        args += ["-boot", boot]
    args += ["-qmp", f"tcp:127.0.0.1:{port},server,nowait"]
    if not display:
        args += ["-display", "none"]
    args += qemu_args
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = (subprocess.DETACHED_PROCESS
                                   | subprocess.CREATE_NEW_PROCESS_GROUP)
    # QEMU reports startup errors on stderr, which a detached process
    # would otherwise lose; keep it in a log file under home
    base = _effective_home(home)
    os.makedirs(base, exist_ok=True)
    stderr_log = os.path.join(base, "qemu-stderr.log")
    with open(stderr_log, "wb") as errf:
        proc = subprocess.Popen(args, stderr=errf, **kwargs)
    # wait until the QMP socket actually accepts connections, so
    # back-to-back start/stop cycles cannot race a slow QEMU startup
    deadline = time.monotonic() + 15
    while True:
        if proc.poll() is not None:
            raise _startup_error(
                proc, stderr_log, port, automatic_port,
                "QEMU exited during startup", args)
        try:
            with Qmp(port) as q:
                _verify_vm(q, port, vm_name)
            if proc.poll() is not None:
                raise _startup_error(
                    proc, stderr_log, port, automatic_port,
                    "QEMU exited while establishing its QMP connection",
                    args)
            break
        except (OSError, ConnectError):
            if time.monotonic() > deadline:
                _terminate_started_process(proc)
                raise _startup_error(
                    proc, stderr_log, port, automatic_port,
                    "QEMU did not come up; QMP was unreachable after 15s",
                    args)
            time.sleep(0.5)
        except RuntimeError:
            _terminate_started_process(proc)
            raise
    try:
        _write_vm_state(port, vm_name, proc.pid, home)
    except OSError as e:
        _terminate_started_process(proc)
        raise RuntimeError(
            "QEMU started but its identity could not be recorded; "
            "the new QEMU process was terminated\n"
            f"  state file: {_state_path(home)}\n"
            f"  error: {e}") from e
    print(f"QEMU started: {vm_name} (QMP on 127.0.0.1:{port})")
    return port


def stop(port=None, home=None):
    port, expected_name = _resolve_vm(port, home)
    try:
        with Qmp(port) as q:
            _verify_vm(q, port, expected_name)
            try:
                q.cmd("quit")  # QEMU may drop the link before replying
            except Exception:
                pass
    except (OSError, ConnectError):
        _remove_vm_state(port, expected_name, home)
        raise RuntimeError(
            "the recorded relict VM is no longer reachable\n"
            f"  expected: {expected_name} on 127.0.0.1:{port}\n"
            "  stale VM state was removed")
    # wait until QEMU has exited and released the port, so an
    # immediately following start() cannot collide with it
    deadline = time.monotonic() + 15
    while True:
        try:
            Qmp(port).close()
        except (OSError, ConnectError):
            break
        if time.monotonic() > deadline:
            raise RuntimeError(
                "QEMU is still holding the QMP port 15s after quit; "
                "a following start() on the same port would collide")
        time.sleep(0.5)
    print("VM stopped.")
    _remove_vm_state(port, expected_name, home)


def boot_to_dos(timeout=90, port=None, home=None):
    """Wait out the boot sequence to a DOS prompt (agentless: polls
    the text screen until the bottom-most non-blank row is a bare DOS
    prompt). If the FreeDOS installer's "Do you want to proceed"
    question comes up on the way, answer no to reach its `A:\\>`
    prompt; a user-provided boot image must reach its prompt
    unattended."""
    print("waiting for a DOS prompt...")
    installer_seen = False
    with _qmp(port, home) as q:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rows = [r for r in screen_text(q) if r]
            if rows and _PROMPT_RE.match(rows[-1]):
                print(f"at DOS prompt: {rows[-1]}")
                return
            if (not installer_seen
                    and any("Do you want to proceed" in r for r in rows)):
                installer_seen = True
                print("FreeDOS installer detected; declining the install...")
                send_text("n", q)
            time.sleep(2)
    raise TimeoutError(
        f"timed out after {timeout}s waiting for a DOS prompt")


def run_guest_program(exe_path, args="", timeout=180, staged_drive=None,
                      qemu_args=(), qemu=None, port=None, home=None,
                      platform="dos"):
    """Full agentless lifecycle for one guest program run: stage the
    DOS-built executable on the staged guest drive, boot DOS, run it
    (with any argument string) with output redirected to a log on
    that drive, shut down, retrieve the log from the staging
    directory, and return the log text.

    Staging targets the machine's staged hard-disk directory: the
    highest one already declared under drives/, or drives/hdd (the
    first free hard-disk slot) created on demand. `staged_drive`
    defaults to the letter matching the declared machine - C: with
    no hard disk before the staged drive, one letter later per
    hard-disk slot before it - and an explicit letter overrides
    the guess (letters lower than the default are rejected).

    relict attaches no meaning to the output; callers own its
    interpretation."""
    if platform != "dos":
        raise ValueError(
            "run_guest_program() is DOS-specific; pass platform='dos'")
    drives = drives_dir(home)
    stage, default_letter = _staged_hdd_plan(_scan_drives(drives),
                                             drives)
    if staged_drive is None:
        staged_drive = default_letter
    else:
        staged_drive = _check_staged_drive(staged_drive)
        if staged_drive < default_letter:
            claimed = ("C:" if default_letter == "D" else
                       f"C: to {chr(ord(default_letter) - 1)}:")
            raise ValueError(
                f"staged_drive={staged_drive!r}: the hard disks "
                f"before the staged drive already claim {claimed}; "
                f"it appears at {default_letter}: or later")
    exe_name = os.path.basename(exe_path)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,8}\.[Ee][Xx][Ee]", exe_name):
        raise ValueError(f"guest executable needs a DOS 8.3 name: {exe_name}")
    base = os.path.splitext(exe_name)[0]
    log_name = base + ".log"
    command = f"{base} {args}".strip() + f" > {log_name}"

    os.makedirs(stage, exist_ok=True)
    shutil.copy(exe_path, stage)
    log_path = os.path.join(stage, log_name)
    if os.path.exists(log_path):
        os.remove(log_path)

    port = start(qemu=qemu, port=port, qemu_args=qemu_args, home=home)
    try:
        with _qmp(port, home) as q:
            boot_to_dos(port=q)
            run_command(f"{staged_drive.lower()}:", 15, q)
            run_command(command, timeout, q)
    finally:
        stop(port, home)
    time.sleep(2)                    # let vvfat flush to the host dir

    if not os.path.exists(log_path):
        raise FileNotFoundError(
            f"guest did not write {log_name} (vvfat write-back failed?)")
    with open(log_path, errors="replace") as log_file:
        return log_file.read()


@dataclasses.dataclass(frozen=True)
class Machine:
    """A running, relict-owned VM passed to generic remote tasks.

    Methods retain the VM's explicit home so every operation verifies
    the same per-home identity before controlling QEMU.
    """

    port: int
    home: str
    deadline: "float | None" = None

    def qmp(self, name, **arguments):
        with _qmp(self.port, self.home) as q:
            return q.cmd(name, **arguments)

    def hmp(self, command_line):
        with _qmp(self.port, self.home) as q:
            return q.hmp(command_line)

    def send_keys(self, combos, delay=0.06):
        return send_keys(combos, self.port, delay, self.home)

    def send_text(self, text, enter=True):
        return send_text(text, self.port, enter, self.home)

    def screen_text(self):
        return screen_text(self.port, self.home)

    def wait_screen(self, pattern, timeout=60):
        return wait_screen(pattern, timeout, self.port, self.home)

    def screenshot(self, name="screen"):
        return screenshot(name, self.port, self.home)


def run_task(task, timeout=None, display=False, qemu=None, port=None,
             qemu_args=(), home=None, platform="dos"):
    """Boot one VM, invoke ``task(machine)``, then stop the VM.

    The task callable owns all guest-specific mechanics and its return
    value is passed through unchanged. ``timeout`` is exposed on the
    machine as a deadline helper only when the task chooses to use it;
    relict cannot safely interrupt arbitrary Python code.
    """
    if not callable(task):
        raise TypeError("task must be callable as task(machine)")
    base = _effective_home(home)
    actual_port = start(display, qemu, port, qemu_args, base, platform)
    deadline = (None if timeout is None
                else time.monotonic() + timeout)
    machine = Machine(actual_port, base, deadline)
    try:
        return task(machine)
    finally:
        stop(actual_port, base)


@dataclasses.dataclass(frozen=True)
class RunnerConfig:
    """What a Runner instance is constructed from. Every field has a
    working default: `boot_floppy_image` / `boot_hdd_image` (at most
    one) is the path of a ready bootable DOS image to use as-is —
    the field declares the media type and the file's extension the
    format (*.img is raw, others are left to QEMU), never
    interrogated from the content; either medium may be any
    QEMU-supported image format (default: install the FreeDOS
    floppy on first need). `staged_drive` declares the guest drive
    letter where the staged vvfat drive appears (default: match the
    declared machine — C: with no hard disk before the staged
    drive, one letter later per preceding hard-disk slot);
    `timeout` is the seconds allowed for one guest run (default
    180); `qemu` is the QEMU binary path (default: find_qemu());
    `qemu_args` are extra QEMU arguments."""

    platform: "str" = "dos"
    boot_floppy_image: "str | None" = None
    boot_hdd_image: "str | None" = None
    staged_drive: "str | None" = None
    timeout: "float | None" = None
    qemu: "str | None" = None
    qemu_args: "tuple" = ()

    def __post_init__(self):
        if not isinstance(self.platform, str) or not self.platform.strip():
            raise ValueError("platform must be a non-empty string")
        object.__setattr__(self, "platform", self.platform.lower())
        if self.platform != "dos" and self.staged_drive is not None:
            raise ValueError(
                "staged_drive is DOS-specific; use platform='dos'")
        if self.boot_floppy_image and self.boot_hdd_image:
            raise ValueError(
                "configure either boot_floppy_image or "
                "boot_hdd_image, not both")
        if self.staged_drive is not None:
            object.__setattr__(self, "staged_drive",
                               _check_staged_drive(self.staged_drive))
        if self.boot_hdd_image and self.staged_drive == "C":
            raise ValueError(
                "staged_drive='C': a hard-disk boot image claims C: "
                "as the system drive; the staged vvfat drive "
                "appears at D: or later")


class Runner:
    """A configured QEMU machine: the generic runner surface for
    callers embedding relict (a soft contract; the module-level
    functions and the CLI remain the direct-use surface).

    An instance carries configuration only — never per-run state,
    which lives under the home directory passed explicitly to each
    operation — so one instance may serve concurrent runs in
    distinct homes. Per-home state files (vm.json, logs) keep VM
    ownership sound across concurrent homes."""

    def __init__(self, config=None):
        self.config = RunnerConfig() if config is None else config

    @property
    def platform(self):
        return self.config.platform

    def provision(self, drives_dir):
        """Ensure something bootable is declared under drives_dir:
        keep a present bootable image untouched, else copy the
        configured ready image to its media-typed well-known stem
        (floppy or hdd, slot 0) keeping the image's own extension,
        else install the downloaded FreeDOS default floppy."""
        if _boot_guess(_scan_drives(drives_dir)) is not None:
            return
        for image, stem in ((self.config.boot_hdd_image, "hdd"),
                            (self.config.boot_floppy_image, "floppy")):
            if image:
                os.makedirs(drives_dir, exist_ok=True)
                ext = os.path.splitext(image)[1]
                shutil.copy(image,
                            os.path.join(drives_dir, stem + ext))
                return
        if self.platform == "dos":
            _download_boot_image(drives_dir)
            return
        raise ValueError(
            "no bootable drive is configured; declare media under "
            f"{drives_dir} or configure a boot image")

    def run(self, task, args="", home=None):
        """Run a DOS executable or a generic ``task(machine)``.

        DOS is the default platform and retains the executable-and-
        arguments interface. Other platform workflows are explicit
        stubs; low-level generic callers can use ``run_task()``.
        """
        if home is None:
            raise ValueError("Runner.run() requires an explicit home")
        if self.platform != "dos":
            raise NotImplementedError(
                f"platform {self.platform!r} task workflow is not "
                "implemented; use run_task() with an explicit callable")
        home = os.path.abspath(home)
        drives = os.path.join(home, "drives")
        if _boot_guess(_scan_drives(drives)) is None:
            self.provision(drives)
        timeout = (180 if self.config.timeout is None
                   else self.config.timeout)
        return run_guest_program(
            task, args, timeout=timeout,
            staged_drive=self.config.staged_drive,
            qemu_args=self.config.qemu_args, qemu=self.config.qemu,
            home=home)


def _write_png(path, width, height, rgb):
    def chunk(typ, payload):
        out = struct.pack(">I", len(payload)) + typ + payload
        return out + struct.pack(">I", zlib.crc32(typ + payload))

    raw = b"".join(b"\x00" + rgb[y * width * 3:(y + 1) * width * 3]
                   for y in range(height))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR",
                      struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw)))
        f.write(chunk(b"IEND", b""))


def _validate_screenshot_name(name):
    """Return a filename-only screenshot name that cannot escape home."""
    name = os.fspath(name)
    if (not isinstance(name, str) or not name or name in (".", "..")
            or os.path.basename(name) != name
            or "/" in name or "\\" in name):
        raise ValueError(
            "screenshot name must be a non-empty filename, not a path")
    return name


def screenshot(name="screen", port=None, home=None):
    name = _validate_screenshot_name(name)
    screenshots = os.path.join(_effective_home(home), "screenshots")
    os.makedirs(screenshots, exist_ok=True)
    ppm = os.path.join(screenshots, f"{name}.ppm")
    with _qmp(port) as q:
        try:
            png = os.path.join(screenshots, f"{name}.png")
            q.cmd("screendump", filename=png.replace("\\", "/"),
                  format="png")
            print(f"saved {png}")
            return
        except ExecuteError:
            pass    # QEMU < 7.1: no png support, use PPM + own converter
        q.cmd("screendump", filename=ppm.replace("\\", "/"))
    time.sleep(0.3)
    with open(ppm, "rb") as f:
        data = f.read()
    tokens = []
    pos = 0
    while len(tokens) < 4:                       # P6, width, height, maxval
        while chr(data[pos]).isspace():
            pos += 1
        end = pos
        while not chr(data[end]).isspace():
            end += 1
        tokens.append(data[pos:end].decode())
        pos = end
    pos += 1                                     # single ws after header
    if tokens[0] != "P6":
        raise ValueError("unexpected screendump format")
    width, height = int(tokens[1]), int(tokens[2])
    png = os.path.join(screenshots, f"{name}.png")
    _write_png(png, width, height, data[pos:pos + width * height * 3])
    os.remove(ppm)
    print(f"saved {png}")


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="relict", description="QEMU guest automation harness "
                                    "(DOS by default)")
    p.add_argument("--home", help="relict home directory (drives/, "
                   "screenshots/); default: $RELICT_HOME, then "
                   "Documents/relict")
    p.add_argument("--port", type=int, help="QMP port (start: choose one "
                   "automatically; other commands: use the active VM)")
    p.add_argument("--qemu", help="path to the QEMU binary (default: "
                   "$RELICT_QEMU_HOME, then $QEMU_HOME, then PATH, "
                   "then well-known install locations)")
    p.add_argument("--platform", default="dos",
                   help="guest platform adapter (default: dos; other "
                        "platform workflows are not implemented yet)")
    p.add_argument("--timeout", type=int, help="seconds to wait "
                   "(defaults: boot-to-dos 90, run 120, wait 60)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("download")
    sp = sub.add_parser("start")
    sp.add_argument("--display", action="store_true")
    sp.add_argument("qemu_args", nargs="*")
    sub.add_parser("stop")
    sub.add_parser("boot-to-dos")
    sp = sub.add_parser("type")
    sp.add_argument("text")
    sp = sub.add_parser("run")
    sp.add_argument("dos_command")
    sp = sub.add_parser("keys")
    sp.add_argument("names", nargs="+")
    sub.add_parser("text")
    sp = sub.add_parser("wait")
    sp.add_argument("pattern")
    sp = sub.add_parser("screenshot")
    sp.add_argument("name", nargs="?", default="screen")
    sp = sub.add_parser("hmp")
    sp.add_argument("line")

    a = p.parse_args(argv)
    if a.home:
        set_home(a.home)
    try:
        return _dispatch(a)
    except (ConnectError, ConnectionError) as e:
        target = f"127.0.0.1:{a.port}" if a.port else "the active VM"
        print(f"relict: cannot reach QMP on {target}: {e}\n"
              "is the VM running? (relict start)", file=sys.stderr)
        return 1
    except (RuntimeError, TimeoutError, FileNotFoundError,
            NotImplementedError,
            ValueError, OSError) as e:
        print(f"relict: error: {e}", file=sys.stderr)
        return 1


def _dispatch(a):
    if a.command == "download":
        if a.platform != "dos":
            raise NotImplementedError(
                f"platform {a.platform!r} provisioning is not implemented")
        download()
    elif a.command == "start":
        start(a.display, a.qemu, a.port, a.qemu_args,
              platform=a.platform)
    elif a.command == "stop":
        stop(a.port)
    elif a.command == "boot-to-dos":
        if a.platform != "dos":
            raise NotImplementedError(
                "boot-to-dos requires platform='dos'")
        boot_to_dos(a.timeout or 90, a.port)
    elif a.command == "type":
        send_text(a.text, a.port)
    elif a.command == "run":
        if a.platform != "dos":
            raise NotImplementedError("run requires platform='dos'")
        run_command(a.dos_command, a.timeout or 120, a.port)
    elif a.command == "keys":
        send_keys([[k] for k in a.names], a.port)
    elif a.command == "text":
        print("\n".join(screen_text(a.port)))
    elif a.command == "wait":
        wait_screen(a.pattern, a.timeout or 60, a.port)
        print("matched.")
    elif a.command == "screenshot":
        screenshot(a.name, a.port)
    elif a.command == "hmp":
        with _qmp(a.port) as q:
            print(q.hmp(a.line))
    return 0


if __name__ == "__main__":
    sys.exit(main())
