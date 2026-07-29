# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the NBD client (nbd.py).

Against a server written here from the protocol rather than from the
client, for the reason ``fat_image`` exists: two halves written from
one reading agree about their shared mistakes. This one also
*scripts* its answers -- a refusal code, a handle that does not
match, a connection dropped mid-reply -- because those are the
answers a real server gives rarely and a drive read must survive
exactly.

No ``qemu-nbd`` runs here. The suite launches no backend.
"""

import socket
import struct
import threading
import unittest

from reliquary import nbd
from reliquary.errors import RunFailure

# Spelled from the ASCII the protocol names them by, so this server
# owes the client nothing -- not even a shared constant.
NBDMAGIC = int.from_bytes(b"NBDMAGIC", "big")
IHAVEOPT = int.from_bytes(b"IHAVEOPT", "big")
REQUEST_MAGIC = 0x25609513
REPLY_MAGIC = 0x67446698


class ScriptedServer:
    """An NBD server over a bytearray, with a scriptable next answer."""

    def __init__(self, size=1 << 20, *, read_only=False,
                 handshake=None, flags=None):
        self.store = bytearray(size)
        self.size = size
        self.read_only = read_only
        #: Override the greeting's magic, to test a wrong one.
        self.handshake = handshake
        #: Override the transmission flags the export reports.
        self.flags = flags
        #: One-shot faults, each consumed by the next command.
        self.next_error = None
        self.next_handle = None
        self.drop_after_header = False
        self.commands = []
        self._listener = socket.socket()
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(1)
        self.port = self._listener.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def close(self):
        try:
            self._listener.close()
        except OSError:
            pass
        self._thread.join(timeout=5)

    def _serve(self):
        try:
            connection, _peer = self._listener.accept()
        except OSError:
            return
        with connection:
            try:
                self._session(connection)
            except (OSError, struct.error):
                pass

    def _session(self, connection):
        magic = self.handshake if self.handshake is not None else NBDMAGIC
        connection.sendall(struct.pack(">QQH", magic, IHAVEOPT, 1))
        _client_flags = _exactly(connection, 4)
        header = _exactly(connection, 16)
        _opt_magic, _option, length = struct.unpack(">QII", header)
        _exactly(connection, length)
        flags = self.flags
        if flags is None:
            flags = 1 | (2 if self.read_only else 0)
        connection.sendall(struct.pack(">QH", self.size, flags) + bytes(124))
        while True:
            request = _exactly(connection, 28)
            (_magic, _cmd_flags, kind, handle, offset,
             count) = struct.unpack(">IHHQQI", request)
            payload = _exactly(connection, count) if kind == 1 else b""
            self.commands.append((kind, offset, count))
            if kind == 2:
                return
            error = self.next_error or 0
            self.next_error = None
            reply_handle = handle if self.next_handle is None \
                else self.next_handle
            self.next_handle = None
            if kind == 1 and not error:
                # Applied *before* the reply, which is what the reply
                # means: a client that has been told its write
                # succeeded may look at the result immediately. Doing
                # it afterwards made this server race its own client.
                self.store[offset:offset + len(payload)] = payload
            connection.sendall(
                struct.pack(">IIQ", REPLY_MAGIC, error, reply_handle))
            if self.drop_after_header:
                self.drop_after_header = False
                return
            if error or kind != 0:
                continue
            connection.sendall(bytes(self.store[offset:offset + count]))


def _exactly(connection, count):
    chunks = []
    while count:
        chunk = connection.recv(count)
        if not chunk:
            raise OSError("closed")
        chunks.append(chunk)
        count -= len(chunk)
    return b"".join(chunks)


class _ServerCase(unittest.TestCase):
    def _server(self, **kwargs):
        server = ScriptedServer(**kwargs)
        self.addCleanup(server.close)
        return server

    def _device(self, server, **kwargs):
        device = nbd.NbdDevice(port=server.port, **kwargs)
        self.addCleanup(device.close)
        return device


class HandshakeTests(_ServerCase):
    """What the client learns before it moves a byte."""

    def test_the_export_size_comes_from_the_server(self):
        device = self._device(self._server(size=64 << 20))
        self.assertEqual(device.size, 64 << 20)

    def test_a_read_only_export_is_known_before_the_first_write(self):
        device = self._device(self._server(read_only=True))
        self.assertTrue(device.read_only)
        with self.assertRaises(RunFailure) as caught:
            device.write_at(0, b"nope")
        self.assertEqual(caught.exception.rule_id, "image.read-only")

    def test_a_stranger_on_the_port_is_refused_by_name(self):
        with self.assertRaises(RunFailure) as caught:
            self._device(self._server(handshake=0x1234567812345678))
        self.assertEqual(caught.exception.rule_id, "image.server-unrecognized")

    def test_an_export_with_no_flags_is_refused(self):
        """Without them the client cannot tell writable from not, and
        guessing writable is how a read-only image gets written."""
        with self.assertRaises(RunFailure) as caught:
            self._device(self._server(flags=0))
        self.assertEqual(caught.exception.rule_id, "image.server-no-flags")

    def test_nothing_listening_is_refused_by_name(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        listener.close()
        with self.assertRaises(RunFailure) as caught:
            nbd.NbdDevice(port=port, timeout=2.0)
        self.assertEqual(caught.exception.rule_id, "image.server-unreachable")


class TransferTests(_ServerCase):
    """Bytes in and out, at the offsets asked for."""

    def test_a_write_is_readable_back_at_its_offset(self):
        server = self._server()
        device = self._device(server)
        device.write_at(4096, b"RELIQUARY")
        device.flush()
        self.assertEqual(device.read_at(4096, 9), b"RELIQUARY")

    def test_a_write_lands_in_the_servers_own_store(self):
        """Checked through the server rather than the client, so a
        client that agreed with itself about an offset is caught."""
        server = self._server()
        device = self._device(server)
        device.write_at(1024, b"ABCD")
        self.assertEqual(bytes(server.store[1024:1028]), b"ABCD")

    def test_a_small_write_is_one_command_and_not_a_whole_cluster(self):
        server = self._server()
        device = self._device(server)
        device.write_at(96, b"D" * 32)
        writes = [entry for entry in server.commands if entry[0] == 1]
        self.assertEqual(writes, [(1, 96, 32)])

    def test_an_empty_read_asks_the_server_nothing(self):
        server = self._server()
        device = self._device(server)
        self.assertEqual(device.read_at(0, 0), b"")
        self.assertEqual(server.commands, [])

    def test_a_flush_is_sent_before_anything_relies_on_the_write(self):
        server = self._server()
        device = self._device(server)
        device.write_at(0, b"x")
        device.flush()
        self.assertIn(3, [kind for kind, _offset, _count in server.commands])

    def test_a_read_only_device_sends_no_flush(self):
        server = self._server(read_only=True)
        device = self._device(server)
        device.flush()
        self.assertEqual(server.commands, [])


class RefusalTests(_ServerCase):
    """The answers a real server gives rarely and a disk read must
    survive exactly."""

    def test_a_server_error_is_reported_and_never_read_past(self):
        server = self._server()
        device = self._device(server)
        server.next_error = 5
        with self.assertRaises(RunFailure) as caught:
            device.read_at(0, 512)
        self.assertEqual(caught.exception.rule_id, "image.server-refused")

    def test_a_mismatched_handle_stops_rather_than_returns_bytes(self):
        """The dangerous case: the stream is out of step, so the next
        bytes on it belong to another request. Returning them would
        hand the caller someone else's sector."""
        server = self._server()
        device = self._device(server)
        server.next_handle = 999
        with self.assertRaises(RunFailure) as caught:
            device.read_at(0, 512)
        self.assertEqual(caught.exception.rule_id, "image.server-out-of-step")

    def test_a_connection_dropped_mid_reply_is_not_a_short_read(self):
        server = self._server()
        device = self._device(server)
        server.drop_after_header = True
        with self.assertRaises(RunFailure) as caught:
            device.read_at(0, 512)
        self.assertEqual(caught.exception.rule_id, "image.server-truncated")

    def test_a_read_past_the_export_is_refused_before_it_is_sent(self):
        server = self._server(size=8192)
        device = self._device(server)
        with self.assertRaises(RunFailure) as caught:
            device.read_at(8000, 512)
        self.assertEqual(caught.exception.rule_id, "image.out-of-bounds")
        self.assertEqual(server.commands, [])

    def test_a_write_past_the_export_is_refused_before_it_is_sent(self):
        server = self._server(size=8192)
        device = self._device(server)
        with self.assertRaises(RunFailure) as caught:
            device.write_at(8180, b"x" * 32)
        self.assertEqual(caught.exception.rule_id, "image.out-of-bounds")
        self.assertEqual(server.commands, [])

    def test_a_negative_offset_is_refused(self):
        server = self._server()
        device = self._device(server)
        with self.assertRaises(RunFailure):
            device.read_at(-1, 512)


if __name__ == "__main__":
    unittest.main()
