# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The in-tree RFB client: the VNC control plane's wire.

Deliberately minimal, and in-tree rather than a dependency, because
Reliquary launches the server it connects to (D110) and so controls
both ends of the wire: the RFB 3.8 version handshake, security type
None, a forced 32-bit true-colour pixel format so the framebuffer
has exactly one in-memory shape, Raw-encoding framebuffer updates
(full and incremental), ``KeyEvent`` and ``PointerEvent`` (F66).

Nothing here knows QEMU or a machine: the client speaks the wire and
:mod:`backend_qemu` owns which VM is behind it. Identity is never
this protocol's job — RFB carries no machine identity, so a caller
verifies the VM over its management interface before using this
connection for anything.
"""

import re
import socket
import struct

from PIL import Image

from .errors import RunFailure


#: The one protocol version this client speaks. The server states its
#: highest version first and must accept a client answering with a
#: lower one, so replying 3.8 to any 3.8-or-later greeting is the
#: handshake the specification prescribes.
_VERSION = b"RFB 003.008\n"

#: RFB security type 1 is "None". The endpoint is loopback-only and
#: identity is verified over the management interface, so VNC
#: authentication would guard nothing (D110).
_SECURITY_NONE = 1


def _read_exact(sock, count, where):
    """Read exactly ``count`` bytes, or say the server hung up."""
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise RunFailure(
                f"the VNC server at {where} closed the connection "
                "mid-message", rule_id="vnc.connection-closed")
        data.extend(chunk)
    return bytes(data)


def _reason(sock, where):
    """The server's stated reason for a refusal, as text."""
    (length,) = struct.unpack(">I", _read_exact(sock, 4, where))
    return _read_exact(sock, length, where).decode("latin-1",
                                                   errors="replace")


def _version_handshake(sock, where):
    """Exchange protocol versions, refusing a server below RFB 3.8."""
    greeting = _read_exact(sock, 12, where)
    match = re.fullmatch(rb"RFB (\d{3})\.(\d{3})\n", greeting)
    if match is None:
        raise RunFailure(
            f"{where} did not greet as an RFB server: {greeting!r}",
            rule_id="vnc.not-rfb")
    version = (int(match.group(1)), int(match.group(2)))
    if version < (3, 8):
        raise RunFailure(
            f"the VNC server at {where} speaks RFB "
            f"{version[0]}.{version[1]}; this client requires 3.8",
            rule_id="vnc.version")
    sock.sendall(_VERSION)


def _security_types(sock, where):
    """The server's offered security types, or its stated refusal."""
    count = _read_exact(sock, 1, where)[0]
    if count == 0:
        raise RunFailure(
            f"the VNC server at {where} refused the connection: "
            f"{_reason(sock, where)}", rule_id="vnc.refused")
    return _read_exact(sock, count, where)


def _require_security_none(types, where):
    if _SECURITY_NONE not in types:
        offered = ", ".join(str(one) for one in sorted(types))
        raise RunFailure(
            f"the VNC server at {where} does not offer security type "
            f"None (offered: {offered}); reliquary launches its VNC "
            "endpoints without authentication",
            rule_id="vnc.security")


def probe(host, port, timeout=2.0):
    """Prove an RFB server this client can use answers at the endpoint.

    The launch readiness probe: a TCP connect plus the version and
    security handshake, then a plain close — no session is consumed
    and no security type is selected. Raises ``OSError`` while
    nothing is listening (the caller's retry case) and
    :class:`~reliquary.errors.RunFailure` when whatever answered is
    not a server the session handshake could succeed against.
    """
    where = f"{host}:{port}"
    with socket.create_connection((host, port), timeout=timeout) as sock:
        _version_handshake(sock, where)
        _require_security_none(_security_types(sock, where), where)


class RfbClient:
    """One RFB connection: the framebuffer, and key events into it.

    The constructor connects and completes the whole handshake —
    version, security None, ``ClientInit``/``ServerInit``, the forced
    pixel format, and the Raw-only encoding declaration — so a
    constructed client is ready to use. ``refresh()`` pulls one
    framebuffer update into the client's copy, ``image()`` renders
    that copy, and ``key_event()`` presses one key.

    The forced pixel format is 32 bits per pixel, true colour,
    little-endian, red shift 16 / green 8 / blue 0 — each pixel's
    bytes are B, G, R, pad, which is Pillow's raw ``BGRX`` mode.
    """

    def __init__(self, host, port, timeout=10.0):
        self._where = f"{host}:{port}"
        self._sock = socket.create_connection((host, port),
                                              timeout=timeout)
        try:
            self._handshake()
        except BaseException:
            self.close()
            raise

    def _handshake(self):
        sock, where = self._sock, self._where
        _version_handshake(sock, where)
        _require_security_none(_security_types(sock, where), where)
        sock.sendall(bytes([_SECURITY_NONE]))
        (result,) = struct.unpack(">I", _read_exact(sock, 4, where))
        if result != 0:
            raise RunFailure(
                f"the VNC server at {where} refused the connection: "
                f"{_reason(sock, where)}", rule_id="vnc.refused")
        # ClientInit: shared. Reliquary opens one session per
        # operation, and an exclusive request would have each new
        # session disconnect the last mid-teardown.
        sock.sendall(b"\x01")
        server_init = _read_exact(sock, 24, where)
        self.width, self.height = struct.unpack(">HH", server_init[:4])
        (name_length,) = struct.unpack(">I", server_init[20:24])
        self.name = _read_exact(sock, name_length, where).decode(
            "latin-1", errors="replace")
        # SetPixelFormat: one in-memory shape whatever the server's
        # native format is.
        sock.sendall(struct.pack(
            ">BxxxBBBBHHHBBBxxx", 0, 32, 24, 0, 1, 255, 255, 255,
            16, 8, 0))
        # SetEncodings: Raw alone. Raw is the encoding every server
        # must be able to send, and advertising nothing else is what
        # pins the update format below.
        sock.sendall(struct.pack(">BxHi", 2, 1, 0))
        self._pixels = bytearray(self.width * self.height * 4)

    def refresh(self, incremental=False):
        """Request one framebuffer update and apply it to the copy.

        A full request (the default) is answered with the whole
        framebuffer; an incremental one is answered with what changed
        since the last update — which a server may hold open until
        something does change, so a caller polling a possibly-idle
        screen wants the full form.
        """
        self._sock.sendall(struct.pack(
            ">BBHHHH", 3, 1 if incremental else 0, 0, 0,
            self.width, self.height))
        while True:
            kind = _read_exact(self._sock, 1, self._where)[0]
            if kind == 0:  # FramebufferUpdate
                self._apply_update()
                return
            if kind == 1:  # SetColourMapEntries: impossible under the
                # forced true-colour format, discarded if sent anyway.
                header = _read_exact(self._sock, 5, self._where)
                (colours,) = struct.unpack(">H", header[3:5])
                _read_exact(self._sock, colours * 6, self._where)
            elif kind == 2:  # Bell: nothing follows.
                pass
            elif kind == 3:  # ServerCutText: discarded.
                header = _read_exact(self._sock, 7, self._where)
                (length,) = struct.unpack(">I", header[3:7])
                _read_exact(self._sock, length, self._where)
            else:
                raise RunFailure(
                    f"the VNC server at {self._where} sent an unknown "
                    f"message type {kind}", rule_id="vnc.protocol")

    def _apply_update(self):
        header = _read_exact(self._sock, 3, self._where)
        (rects,) = struct.unpack(">H", header[1:3])
        for _ in range(rects):
            x, y, w, h, encoding = struct.unpack(
                ">HHHHi", _read_exact(self._sock, 12, self._where))
            if encoding != 0:
                raise RunFailure(
                    f"the VNC server at {self._where} sent encoding "
                    f"{encoding} where only Raw (0) was advertised",
                    rule_id="vnc.protocol")
            if x + w > self.width or y + h > self.height:
                raise RunFailure(
                    f"the VNC server at {self._where} sent a "
                    f"{w}x{h} rectangle at ({x}, {y}), outside the "
                    f"{self.width}x{self.height} framebuffer",
                    rule_id="vnc.protocol")
            data = _read_exact(self._sock, w * h * 4, self._where)
            for row in range(h):
                start = ((y + row) * self.width + x) * 4
                src = row * w * 4
                self._pixels[start:start + w * 4] = \
                    data[src:src + w * 4]

    def image(self):
        """The client's framebuffer copy as a Pillow RGB image."""
        return Image.frombytes(
            "RGB", (self.width, self.height), bytes(self._pixels),
            "raw", "BGRX")

    def key_event(self, keysym, down):
        """Press (``down=True``) or release one X11 keysym."""
        self._sock.sendall(struct.pack(
            ">BBHI", 4, 1 if down else 0, 0, keysym))

    def pointer_event(self, x, y, button_mask):
        """Move the pointer to ``(x, y)`` with ``button_mask`` held.

        Framebuffer pixel coordinates throughout (F66) — RFB carries
        no other kind, so a caller needing to move, press or release
        composes this primitive rather than the wire growing a
        second message.
        """
        self._sock.sendall(struct.pack(">BBHH", 5, button_mask, x, y))

    def close(self):
        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
