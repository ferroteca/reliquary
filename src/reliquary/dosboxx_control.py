# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The in-tree DOSBox-X control-channel client: the wire.

Deliberately minimal and in-tree, the same reasoning :mod:`rfb` gives for
the VNC client: Reliquary launches the server it connects to and controls
both ends of the wire, so there is exactly one protocol to speak rather
than a general client library's worth. The protocol itself lives on a
personal fork of DOSBox-X (``pgalbraith/dosbox-x``, branch
``control-channel``, ``src/hardware/hostcontrol.cpp``) — a loopback,
line-oriented TCP socket: one command per line in, ``OK ...``/``ERR ...``
back, except ``SCREENSHOT`` whose reply carries a length-prefixed binary
tail.

Nothing here knows a machine or a launch: the client speaks the wire and
:mod:`backend_dosbox_x` owns which VM is behind it and what the recorded
identity means. Identity is this protocol's job in one specific sense
unlike RFB's: a wrong ``AUTH`` token is refused and the connection is
dropped by the server, so a successful :meth:`ControlClient.auth` *is*
this backend's ownership proof (the seam's per-start-token doctrine, here
enforced by the server itself rather than by a caller cross-checking a
query reply).
"""

import socket

from .errors import RunFailure, StaticError

#: Seam key names (the QEMU qcode set every backend translates from, per
#: D103) -> this control channel's ``key_names[]`` vocabulary
#: (``hostcontrol.cpp``). Digits and single-letter names pass through
#: unlisted, exactly as :func:`backend_qemu.keysym_for` and
#: :func:`backend_virtualbox.scancodes_for` leave them to fall through to
#: their own identity/character-code cases.
_KEY_NAMES = {
    "ret": "enter", "spc": "space", "backspace": "bspace",
    "alt": "lalt", "ctrl": "lctrl", "shift": "lshift",
    "equal": "equals", "bracket_left": "lbracket",
    "bracket_right": "rbracket", "apostrophe": "quote",
    "grave_accent": "grave", "dot": "period",
    "pgup": "pageup", "pgdn": "pagedown",
}


def key_name_for(name):
    """This channel's key name for one seam key name, or fail closed.

    Letters and digits are their own name in both vocabularies; every
    other seam name not listed in :data:`_KEY_NAMES` and not a bare
    letter/digit has no known counterpart in ``hostcontrol.cpp``'s
    ``key_names[]`` table.
    """
    if len(name) == 1 and (name.islower() or name.isdigit()):
        return name
    if name in _KEY_NAMES:
        return _KEY_NAMES[name]
    if name in ("esc", "tab", "home", "up", "left", "right", "end",
               "down", "insert", "delete", "semicolon", "minus",
               "backslash", "comma", "slash"):
        # Same spelling in both vocabularies.
        return name
    if len(name) <= 3 and name[0] == "f" and name[1:].isdigit():
        return name  # f1..f12
    raise StaticError(f"no DOSBox-X control-channel key for {name!r}",
                      rule_id="key.no-mapping")


class ControlClient:
    """One control-channel connection.

    The constructor only opens the TCP connection; :meth:`auth` is a
    separate step because a caller needs :meth:`identify` (to
    cross-check the recorded ``backend-id`` before trusting the
    connection at all) and :meth:`ping` available pre-auth, matching
    what the protocol itself allows unauthenticated.
    """

    def __init__(self, host, port, timeout=10.0):
        self._where = f"{host}:{port}"
        self._sock = socket.create_connection((host, port),
                                              timeout=timeout)
        self._buf = b""

    def _send(self, line):
        self._sock.sendall((line + "\n").encode("latin-1"))

    def _read_line(self):
        while b"\n" not in self._buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise RunFailure(
                    f"the control channel at {self._where} closed the "
                    "connection", rule_id="dosboxx.connection-closed")
            self._buf += chunk
        line, _, self._buf = self._buf.partition(b"\n")
        return line.decode("latin-1", errors="replace").rstrip("\r")

    def _read_exact(self, count):
        while len(self._buf) < count:
            chunk = self._sock.recv(max(4096, count - len(self._buf)))
            if not chunk:
                raise RunFailure(
                    f"the control channel at {self._where} closed the "
                    "connection", rule_id="dosboxx.connection-closed")
            self._buf += chunk
        data, self._buf = self._buf[:count], self._buf[count:]
        return bytes(data)

    def _command(self, line):
        self._send(line)
        return self._read_line()

    def _expect_ok(self, line):
        reply = self._command(line)
        if not reply.startswith("OK"):
            raise RunFailure(
                f"{line.split(' ', 1)[0]} refused at {self._where}: "
                f"{reply}", rule_id="dosboxx.command-refused")
        return reply

    def ping(self):
        """Plumbing check: works before ``AUTH``."""
        reply = self._command("PING")
        if reply != "PONG":
            raise RunFailure(
                f"the control channel at {self._where} did not answer "
                f"PING: {reply}", rule_id="dosboxx.protocol")

    def identify(self):
        """The ``backend-id``/auth-state triple, parsed into a dict.

        Works before ``AUTH`` — this is how a caller confirms it has
        reached the *recorded* instance (matching ``backend-id``)
        before spending the one guess a wrong ``AUTH`` allows.
        """
        reply = self._command("IDENTIFY")
        if not reply.startswith("OK "):
            raise RunFailure(
                f"IDENTIFY failed at {self._where}: {reply}",
                rule_id="dosboxx.protocol")
        fields = {}
        for token in reply[3:].split():
            key, _, value = token.partition("=")
            fields[key] = value
        return fields

    def auth(self, token):
        """Authenticate; a wrong token closes the connection (no retry).

        This success *is* the ownership proof the seam's per-start
        token doctrine asks for: only a caller holding the token
        minted at launch can reach this far, so nothing beyond a
        successful ``AUTH`` needs separate verification.
        """
        self._send(f"AUTH {token}")
        try:
            reply = self._read_line()
        except RunFailure:
            raise RunFailure(
                f"AUTH failed at {self._where}: the connection was "
                "closed (wrong token)",
                rule_id="dosboxx.auth-failed") from None
        if reply != "OK":
            raise RunFailure(f"AUTH failed at {self._where}: {reply}",
                             rule_id="dosboxx.auth-failed")

    def key(self, name):
        self._expect_ok(f"KEY {key_name_for(name)}")

    def keydown(self, name):
        self._expect_ok(f"KEYDOWN {key_name_for(name)}")

    def keyup(self, name):
        self._expect_ok(f"KEYUP {key_name_for(name)}")

    def _dims(self, reply, command):
        if not reply.startswith("OK "):
            raise RunFailure(f"{command} failed at {self._where}: {reply}",
                             rule_id="dosboxx.command-refused")
        width, _, height = reply[3:].partition("x")
        return int(width), int(height)

    def screen(self):
        """The text screen as a tuple of right-stripped rows."""
        reply = self._command("SCREEN")
        _, height = self._dims(reply, "SCREEN")
        return tuple(self._read_line() for _ in range(height))

    def attributes(self):
        """The same cell grid's attribute byte, one tuple of ints per row."""
        reply = self._command("ATTR")
        width, height = self._dims(reply, "ATTR")
        rows = []
        for _ in range(height):
            line = self._read_line()
            cells = tuple(int(token, 16) for token in line.split())
            if len(cells) != width:
                raise RunFailure(
                    f"ATTR row at {self._where} carried {len(cells)} "
                    f"cells, expected {width}", rule_id="dosboxx.protocol")
            rows.append(cells)
        return tuple(rows)

    def screenshot(self):
        """The framebuffer as ``(width, height, raw RGB24 bytes)``."""
        reply = self._command("SCREENSHOT")
        if not reply.startswith("OK "):
            raise RunFailure(
                f"SCREENSHOT failed at {self._where}: {reply}",
                rule_id="dosboxx.command-refused")
        dims, fmt, length = reply[3:].split()
        if fmt != "RGB24":
            raise RunFailure(
                f"SCREENSHOT at {self._where} answered in unexpected "
                f"format {fmt!r}", rule_id="dosboxx.protocol")
        width, height = (int(part) for part in dims.split("x"))
        data = self._read_exact(int(length))
        return width, height, data

    def mount(self, drive, path):
        """Append ``path`` to a drive that already has one image mounted."""
        self._expect_ok(f"MOUNT {drive} {path}")

    def swap(self, drive, position=None):
        """Cycle a swappable drive to ``position`` (1-based), or the next."""
        line = f"SWAP {drive}"
        if position is not None:
            line += f" {position}"
        self._expect_ok(line)

    def eject(self, drive):
        """Bring a mounted CD-ROM drive back to empty."""
        self._expect_ok(f"EJECT {drive}")

    def stop(self):
        """Ask for a clean, fail-closed shutdown."""
        self._send("STOP")
        try:
            reply = self._read_line()
        except RunFailure:
            return  # the process tearing down the socket is an OK answer
        if not reply.startswith("OK"):
            raise RunFailure(f"STOP refused at {self._where}: {reply}",
                             rule_id="dosboxx.command-refused")

    def close(self):
        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
