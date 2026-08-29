# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The RFB (VNC) client Reliquary implements itself, instead of a dependency.

Kept deliberately minimal and implemented directly in this codebase,
because Reliquary always launches the server it connects to (D110), so
it controls both ends of the connection and only needs to support what
it itself uses: the RFB 3.8 version handshake, security type None, a
forced 32-bit true-colour pixel format (so the framebuffer always has
one fixed in-memory layout), Raw-encoded framebuffer updates (both
full and incremental), and the ``KeyEvent`` and ``PointerEvent``
messages (F66).

This module knows nothing about QEMU or about "a machine": it only
speaks the wire protocol, and :mod:`backend_qemu` is what decides
which VM is on the other end. Verifying identity is never this
module's job — RFB itself carries no machine identity, so a caller
must verify the VM through its management interface before using this
connection for anything.
"""

import re
import socket
import struct

from PIL import Image

from .errors import RunFailure


#: The one protocol version this client speaks. The server states its
#: highest supported version first, and must accept a client that
#: answers with a lower one — so replying 3.8 to any 3.8-or-later
#: greeting is exactly the handshake the RFB specification requires.
_VERSION = b"RFB 003.008\n"

#: RFB security type 1 is "None". The endpoint is loopback-only, and
#: identity is verified separately over the management interface, so
#: VNC's own authentication would not actually protect anything here
#: (D110).
_SECURITY_NONE = 1


def _read_exact(sock, count, where):
    """Read exactly ``count`` bytes, or raise if the server hung up."""
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
    """Read the server's stated reason for a refusal, as text."""
    (length,) = struct.unpack(">I", _read_exact(sock, 4, where))
    return _read_exact(sock, length, where).decode("latin-1",
                                                   errors="replace")


def _version_handshake(sock, where):
    """Exchange protocol versions; reject a server below RFB 3.8."""
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
    """The security types the server offers, or its stated refusal."""
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
    """Check that a usable RFB server is answering at this endpoint.

    Used as a launch readiness check: connect over TCP, run the
    version and security-type handshake, then just close the
    connection — no session is actually opened and no security type
    is selected. Raises ``OSError`` while nothing is listening yet
    (the case the caller retries on), and
    :class:`~reliquary.errors.RunFailure` if whatever answered isn't a
    server this client's session handshake could succeed against.
    """
    where = f"{host}:{port}"
    with socket.create_connection((host, port), timeout=timeout) as sock:
        _version_handshake(sock, where)
        _require_security_none(_security_types(sock, where), where)


class RfbClient:
    """One RFB connection: the framebuffer, and key events into it.

    The constructor connects and runs the entire handshake — version,
    security None, ``ClientInit``/``ServerInit``, setting the forced
    pixel format, and declaring Raw as the only accepted encoding —
    so a constructed client is immediately ready to use.
    ``refresh()`` pulls one framebuffer update into the client's
    local copy, ``image()`` renders that copy as an image, and
    ``key_event()`` presses one key.

    The forced pixel format is 32 bits per pixel, true colour,
    little-endian, with red at bit offset 16, green at 8, and blue at
    0 — so each pixel's bytes in memory are B, G, R, pad, which is
    Pillow's raw ``BGRX`` mode.
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
        # ClientInit: request a shared session. Reliquary opens one
        # session per operation, and requesting an exclusive one would
        # make each new session disconnect the previous one mid-teardown.
        sock.sendall(b"\x01")
        server_init = _read_exact(sock, 24, where)
        self.width, self.height = struct.unpack(">HH", server_init[:4])
        (name_length,) = struct.unpack(">I", server_init[20:24])
        self.name = _read_exact(sock, name_length, where).decode(
            "latin-1", errors="replace")
        # SetPixelFormat: force one fixed in-memory layout, regardless
        # of whatever pixel format the server natively uses.
        sock.sendall(struct.pack(
            ">BxxxBBBBHHHBBBxxx", 0, 32, 24, 0, 1, 255, 255, 255,
            16, 8, 0))
        # SetEncodings: advertise only Raw. Every RFB server must
        # support sending Raw, and advertising nothing else is what
        # guarantees the update format handled below.
        sock.sendall(struct.pack(">BxHi", 2, 1, 0))
        self._pixels = bytearray(self.width * self.height * 4)

    def refresh(self, incremental=False):
        """Request one framebuffer update and apply it to the local copy.

        A full request (the default) gets back the whole framebuffer.
        An incremental one gets back only what changed since the last
        update — and the server may hold that request open until
        something actually changes, so a caller polling a screen that
        might be idle should use the full request instead.
        """
        self._sock.sendall(struct.pack(
            ">BBHHHH", 3, 1 if incremental else 0, 0, 0,
            self.width, self.height))
        while True:
            kind = _read_exact(self._sock, 1, self._where)[0]
            if kind == 0:  # FramebufferUpdate
                self._apply_update()
                return
            if kind == 1:  # SetColourMapEntries: can't happen under
                # the forced true-colour format, but read and discard
                # it if a server sends it anyway.
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

        ``(x, y)`` is always in framebuffer pixel coordinates (F66) —
        RFB has no other kind of coordinate. A caller that needs to
        move, press, or release the pointer just calls this repeatedly
        with different arguments, rather than this module adding a
        second message type.
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
