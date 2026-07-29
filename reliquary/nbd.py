# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The Network Block Device protocol: a served image as a device.

The transport half of at-rest access. An adapter whose image format
is not raw bytes needs *something* to turn it into them; the honest
tool is the one the backend already ships, so QEMU serves the image
with ``qemu-nbd`` and this speaks the wire protocol back at it.

**This module knows nothing about qcow2, and nothing about FAT.** It
moves bytes at offsets, which is the whole of what a device is. What
is inside them is :mod:`reliquary.at_rest`'s business, and which
format needed serving is the adapter's -- the two never meet.

Only the fixed-newstyle handshake and the four commands at-rest
access uses are implemented (read, write, flush, disconnect). Neither
TLS nor structured replies are negotiated: the server is a child
process this host started, on the loopback interface, for the length
of one operation.
"""

import socket
import struct

from .errors import RunFailure

#: The handshake's three constants, in the order they appear on the
#: wire. ``NBDMAGIC`` opens the greeting, ``IHAVEOPT`` marks every
#: option the client sends, and the request/reply magics frame the
#: transmission phase.
_NBDMAGIC = 0x4E42444D41474943
_IHAVEOPT = 0x49484156454F5054
_REQUEST_MAGIC = 0x25609513
_REPLY_MAGIC = 0x67446698

#: ``NBD_OPT_EXPORT_NAME``: the one option worth sending here. It
#: ends negotiation and moves straight to transmission, which is why
#: nothing after it needs a reply type.
_OPT_EXPORT_NAME = 1

_CMD_READ = 0
_CMD_WRITE = 1
_CMD_DISCONNECT = 2
_CMD_FLUSH = 3

#: ``NBD_FLAG_HAS_FLAGS`` and ``NBD_FLAG_READ_ONLY`` from the
#: transmission flags the server sends with the export size. The
#: second is checked rather than assumed: a server that exported the
#: image read-only must not be written through, and finding that out
#: at the first write would be finding it out too late.
_FLAG_HAS_FLAGS = 1 << 0
_FLAG_READ_ONLY = 1 << 1

#: A guard against a reply that claims more than any request asked
#: for. Nothing here reads more than a cluster at a time.
_MAX_REPLY = 1 << 24


class NbdDevice:
    """One NBD export, addressed by byte offset.

    The device shape :mod:`reliquary.at_rest` reads and writes
    through: ``size`` in bytes, ``read_at``, ``write_at``, ``flush``
    and ``close``. It is deliberately *not* file-like -- a seek
    cursor would be state two callers could disagree about, and every
    caller here already knows the offset it wants.
    """

    def __init__(self, host="127.0.0.1", port=10809, export="",
                 *, timeout=30.0):
        self.host = host
        self.port = port
        self.export = export
        self.size = 0
        self.read_only = True
        self._handle = 0
        try:
            self._socket = socket.create_connection((host, port),
                                                    timeout=timeout)
        except OSError as error:
            raise RunFailure(
                f"cannot reach the image server at {host}:{port} — {error}",
                rule_id="image.server-unreachable") from error
        try:
            self._socket.setsockopt(socket.IPPROTO_TCP,
                                    socket.TCP_NODELAY, 1)
            self._greet()
        except Exception:
            self._socket.close()
            raise

    # -- the handshake ------------------------------------------------

    def _greet(self):
        """Negotiate fixed-newstyle, and take the export's own terms."""
        magic, option, _flags = struct.unpack(">QQH", self._recv(18))
        if magic != _NBDMAGIC or option != _IHAVEOPT:
            raise RunFailure(
                f"{self.host}:{self.port} did not answer as an image "
                "server; reliquary will not read a drive through it",
                rule_id="image.server-unrecognized")
        # Client flags: none. Fixed-newstyle without structured
        # replies is what `NBD_OPT_EXPORT_NAME` below assumes.
        self._sendall(struct.pack(">I", 0))
        name = self.export.encode("utf-8")
        self._sendall(struct.pack(">QII", _IHAVEOPT, _OPT_EXPORT_NAME,
                                  len(name)) + name)
        self.size, flags = struct.unpack(">QH", self._recv(10))
        self._recv(124)          # the reserved tail, zero and ignored
        if not flags & _FLAG_HAS_FLAGS:
            raise RunFailure(
                f"{self.host}:{self.port} offered no transmission flags; "
                "reliquary cannot tell whether the export is writable",
                rule_id="image.server-no-flags")
        self.read_only = bool(flags & _FLAG_READ_ONLY)

    # -- the wire -----------------------------------------------------

    def _sendall(self, payload):
        try:
            self._socket.sendall(payload)
        except OSError as error:
            raise RunFailure(
                f"the image server at {self.host}:{self.port} stopped "
                f"listening — {error}", rule_id="image.server-lost") from error

    def _recv(self, count):
        chunks = []
        remaining = count
        while remaining:
            try:
                chunk = self._socket.recv(remaining)
            except OSError as error:
                raise RunFailure(
                    f"the image server at {self.host}:{self.port} stopped "
                    f"answering — {error}",
                    rule_id="image.server-lost") from error
            if not chunk:
                raise RunFailure(
                    f"the image server at {self.host}:{self.port} closed "
                    "the connection mid-answer; the drive was not read "
                    "whole", rule_id="image.server-truncated")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _command(self, kind, offset, length, payload=b""):
        """One request, and the reply that must carry its own handle.

        The handle is checked rather than trusted: this client has one
        request in flight at a time, so a reply carrying a different
        one means the stream is out of step, and reading the next
        bytes as data would hand the caller someone else's sector.
        """
        self._handle += 1
        expected = self._handle
        self._sendall(struct.pack(">IHHQQI", _REQUEST_MAGIC, 0, kind,
                                  expected, offset, length) + payload)
        magic, error, handle = struct.unpack(">IIQ", self._recv(16))
        if magic != _REPLY_MAGIC or handle != expected:
            raise RunFailure(
                "the image server answered out of step; reliquary "
                "stopped rather than read the wrong bytes",
                rule_id="image.server-out-of-step")
        if error:
            raise RunFailure(
                f"the image server refused a {_NAMES[kind]} of "
                f"{length} bytes at offset {offset} (error {error})",
                rule_id="image.server-refused")
        if kind != _CMD_READ:
            return b""
        if length > _MAX_REPLY:
            raise RunFailure(
                f"a {length}-byte read is larger than reliquary asks "
                "for; refusing it rather than buffering it",
                rule_id="image.server-oversized")
        return self._recv(length)

    # -- the device surface -------------------------------------------

    def read_at(self, offset, length):
        if not length:
            return b""
        self._bounded(offset, length, "read")
        return self._command(_CMD_READ, offset, length)

    def write_at(self, offset, data):
        if self.read_only:
            raise RunFailure(
                "the image was served read-only; reliquary will not "
                "write through it", rule_id="image.read-only")
        if not data:
            return
        self._bounded(offset, len(data), "write")
        self._command(_CMD_WRITE, offset, len(data), bytes(data))

    def flush(self):
        """Commit what was written, before anything relies on it.

        Not decoration: the server may hold writes in its own cache,
        and a snapshot or a process exit that happened first would
        take the disk without them.
        """
        if not self.read_only:
            self._command(_CMD_FLUSH, 0, 0)

    def close(self):
        if self._socket is None:
            return
        try:
            self._socket.sendall(struct.pack(">IHHQQI", _REQUEST_MAGIC, 0,
                                             _CMD_DISCONNECT, 0, 0, 0))
        except OSError:
            # The server is already gone; the disconnect was a
            # courtesy and there is nothing left to be courteous to.
            pass
        self._socket.close()
        self._socket = None

    def _bounded(self, offset, length, verb):
        """The export's own size is the last guard on an offset."""
        if offset < 0 or offset + length > self.size:
            raise RunFailure(
                f"a {verb} of {length} bytes at offset {offset} runs "
                f"past the {self.size}-byte drive",
                rule_id="image.out-of-bounds")

    def __enter__(self):
        return self

    def __exit__(self, *_exception):
        self.close()


#: Command names for the refusal message, so a server error says
#: which operation it refused rather than a number.
_NAMES = {_CMD_READ: "read", _CMD_WRITE: "write",
          _CMD_FLUSH: "flush", _CMD_DISCONNECT: "disconnect"}
