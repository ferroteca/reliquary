# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the in-tree RFB client, run against a fake server instead of a real hypervisor.

The fake server is a scripted loopback socket. These tests cover the
wire protocol: the RFB 3.8 handshake, the forced pixel format, Raw-only
updates (both full and incremental), and key events. One test reads a
golden framebuffer back through the shared recognizer, to check that
the client's pixel format and the recognizer agree on what a
framebuffer looks like.
"""

import socket
import struct
import threading

import pytest

from reliquary import rfb
from reliquary import text_recognize
from reliquary.errors import RunFailure


def _bgrx(image):
    """Encode a Pillow RGB image the way the forced format wires it."""
    data = bytearray()
    for r, g, b in image.convert("RGB").get_flattened_data():
        data += bytes((b, g, r, 0))
    return bytes(data)


class _FakeVncServer:
    """One scripted RFB server connection on a loopback socket.

    The constructor opens the listener and starts the thread; the
    ``received`` map records what the client sent, which is what the
    handshake assertions read.
    """

    def __init__(self, *, version=b"RFB 003.008\n", security=(1,),
                 refusal=None, security_result=0, width=4, height=2,
                 frame=None, rects=None, before_update=(),
                 name=b"fake-vnc"):
        self.version = version
        self.security = bytes(security)
        self.refusal = refusal
        self.security_result = security_result
        self.width = width
        self.height = height
        #: Full-frame pixel bytes served on a non-incremental request.
        self.frame = frame if frame is not None else bytes(
            width * height * 4)
        #: Explicit ``(x, y, w, h, encoding, data)`` rectangles served
        #: instead of the full frame, when given.
        self.rects = rects
        #: Server messages injected before the first update reply.
        self.before_update = before_update
        self.name = name
        self.received = {"pixel_format": None, "encodings": None,
                         "keys": [], "updates": [], "pointers": []}
        self._listener = socket.create_server(("127.0.0.1", 0))
        self.port = self._listener.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _read(self, sock, count):
        data = bytearray()
        while len(data) < count:
            chunk = sock.recv(count - len(data))
            if not chunk:
                raise ConnectionError("client left")
            data.extend(chunk)
        return bytes(data)

    def _serve(self):
        try:
            sock, _ = self._listener.accept()
        except OSError:
            return
        sock.settimeout(5)
        try:
            self._session(sock)
        except (ConnectionError, OSError):
            pass
        finally:
            sock.close()
            self._listener.close()

    def _session(self, sock):
        sock.sendall(self.version)
        self._read(sock, 12)  # the client's version reply
        if self.refusal is not None:
            sock.sendall(b"\x00" + struct.pack(">I", len(self.refusal))
                         + self.refusal)
            return
        sock.sendall(bytes([len(self.security)]) + self.security)
        self._read(sock, 1)  # the chosen type
        sock.sendall(struct.pack(">I", self.security_result))
        if self.security_result != 0:
            reason = b"scripted refusal"
            sock.sendall(struct.pack(">I", len(reason)) + reason)
            return
        self._read(sock, 1)  # ClientInit
        sock.sendall(struct.pack(">HH", self.width, self.height)
                     + bytes(16)
                     + struct.pack(">I", len(self.name)) + self.name)
        while True:
            kind = self._read(sock, 1)[0]
            if kind == 0:  # SetPixelFormat
                self.received["pixel_format"] = self._read(sock, 19)[3:]
            elif kind == 2:  # SetEncodings
                header = self._read(sock, 3)
                (count,) = struct.unpack(">H", header[1:3])
                body = self._read(sock, count * 4)
                self.received["encodings"] = [
                    struct.unpack(">i", body[at:at + 4])[0]
                    for at in range(0, count * 4, 4)]
            elif kind == 3:  # FramebufferUpdateRequest
                body = self._read(sock, 9)
                incremental = body[0]
                self.received["updates"].append(incremental)
                for message in self.before_update:
                    sock.sendall(message)
                self._send_update(sock, incremental)
            elif kind == 4:  # KeyEvent
                body = self._read(sock, 7)
                (keysym,) = struct.unpack(">I", body[3:7])
                self.received["keys"].append((body[0], keysym))
            elif kind == 5:  # PointerEvent
                body = self._read(sock, 5)
                buttons, x, y = struct.unpack(">BHH", body)
                self.received["pointers"].append((x, y, buttons))
            else:
                return

    def _send_update(self, sock, incremental):
        if self.rects is not None:
            rects = self.rects
        else:
            rects = [(0, 0, self.width, self.height, 0, self.frame)]
        sock.sendall(struct.pack(">BxH", 0, len(rects)))
        for x, y, w, h, encoding, data in rects:
            sock.sendall(struct.pack(">HHHHi", x, y, w, h, encoding))
            sock.sendall(data)

    def join(self):
        self._thread.join(timeout=5)


def _connect(server, **kwargs):
    return rfb.RfbClient("127.0.0.1", server.port, **kwargs)


# -- the handshake -------------------------------------------------

def test_the_handshake_forces_the_one_pixel_format():
    server = _FakeVncServer()
    with _connect(server) as client:
        client.refresh()
    server.join()
    # 32bpp, depth 24, little-endian, true colour, 8 bits per
    # channel at shifts 16/8/0 — the one in-memory shape.
    assert server.received["pixel_format"] == struct.pack(
        ">BBBBHHHBBBxxx", 32, 24, 0, 1, 255, 255, 255, 16, 8, 0)


def test_the_client_advertises_raw_and_nothing_else():
    server = _FakeVncServer()
    with _connect(server) as client:
        client.refresh()
    server.join()
    assert server.received["encodings"] == [0]


def test_the_server_init_names_the_framebuffer():
    server = _FakeVncServer(width=6, height=3, name=b"reliquary-vm",
                            frame=bytes(6 * 3 * 4))
    with _connect(server) as client:
        assert (client.width, client.height) == (6, 3)
        assert client.name == "reliquary-vm"


def test_a_server_below_3_8_is_refused_naming_its_version():
    server = _FakeVncServer(version=b"RFB 003.003\n")
    with pytest.raises(RunFailure) as caught:
        _connect(server)
    assert caught.value.rule_id == "vnc.version"
    assert "3.3" in str(caught.value)


def test_a_greeting_that_is_not_rfb_is_refused():
    server = _FakeVncServer(version=b"HTTP/1.1 400\n")
    with pytest.raises(RunFailure) as caught:
        _connect(server)
    assert caught.value.rule_id == "vnc.not-rfb"


def test_a_server_without_security_none_is_refused():
    server = _FakeVncServer(security=(2, 16))
    with pytest.raises(RunFailure) as caught:
        _connect(server)
    assert caught.value.rule_id == "vnc.security"
    assert "2, 16" in str(caught.value)


def test_a_refused_connection_carries_the_servers_reason():
    server = _FakeVncServer(refusal=b"too many clients")
    with pytest.raises(RunFailure) as caught:
        _connect(server)
    assert caught.value.rule_id == "vnc.refused"
    assert "too many clients" in str(caught.value)


def test_a_failed_security_result_carries_the_servers_reason():
    server = _FakeVncServer(security_result=1)
    with pytest.raises(RunFailure) as caught:
        _connect(server)
    assert caught.value.rule_id == "vnc.refused"
    assert "scripted refusal" in str(caught.value)


def test_a_connection_closed_mid_message_is_named():
    server = _FakeVncServer(version=b"RFB 003.008\n", security=())
    # An empty security list with no reason: the server's session
    # ends, so the client's read of the reason length hits the close.
    with pytest.raises(RunFailure) as caught:
        _connect(server)
    assert caught.value.rule_id in ("vnc.connection-closed",
                                    "vnc.refused")


# -- framebuffer updates -------------------------------------------

def test_a_full_update_paints_the_framebuffer():
    # 2x1: a red pixel then a blue one, wired as B,G,R,X.
    frame = bytes((0, 0, 255, 0)) + bytes((255, 0, 0, 0))
    server = _FakeVncServer(width=2, height=1, frame=frame)
    with _connect(server) as client:
        client.refresh()
        image = client.image()
    assert image.getpixel((0, 0)) == (255, 0, 0)
    assert image.getpixel((1, 0)) == (0, 0, 255)


def test_an_incremental_update_applies_its_rectangle_in_place():
    green = bytes((0, 255, 0, 0))
    server = _FakeVncServer(
        width=2, height=2,
        rects=[(1, 1, 1, 1, 0, green)])
    with _connect(server) as client:
        client.refresh(incremental=True)
        image = client.image()
    assert server.received["updates"] == [1]
    assert image.getpixel((1, 1)) == (0, 255, 0)
    assert image.getpixel((0, 0)) == (0, 0, 0)


def test_an_encoding_other_than_raw_is_refused():
    server = _FakeVncServer(width=1, height=1,
                            rects=[(0, 0, 1, 1, 7, bytes(4))])
    with _connect(server) as client:
        with pytest.raises(RunFailure) as caught:
            client.refresh()
    assert caught.value.rule_id == "vnc.protocol"
    assert "7" in str(caught.value)


def test_a_rectangle_outside_the_framebuffer_is_refused():
    server = _FakeVncServer(width=2, height=2,
                            rects=[(1, 1, 2, 2, 0, bytes(16))])
    with _connect(server) as client:
        with pytest.raises(RunFailure) as caught:
            client.refresh()
    assert caught.value.rule_id == "vnc.protocol"


def test_bell_and_cut_text_before_an_update_are_skipped():
    cut = b"clipboard"
    server = _FakeVncServer(
        width=1, height=1, frame=bytes((0, 0, 255, 0)),
        before_update=(
            struct.pack(">B", 2),  # Bell
            struct.pack(">BxxxI", 3, len(cut)) + cut,  # ServerCutText
        ))
    with _connect(server) as client:
        client.refresh()
        assert client.image().getpixel((0, 0)) == (255, 0, 0)


# -- key events ----------------------------------------------------

def test_key_events_carry_the_keysym_and_the_direction():
    server = _FakeVncServer()
    with _connect(server) as client:
        client.key_event(0xff0d, True)
        client.key_event(0xff0d, False)
        client.refresh()  # a round trip so the server has read them
    server.join()
    assert server.received["keys"] == [(1, 0xff0d), (0, 0xff0d)]


# -- pointer events (F66) --------------------------------------------

def test_pointer_events_carry_the_position_and_the_button_mask():
    server = _FakeVncServer()
    with _connect(server) as client:
        client.pointer_event(50, 40, 1)   # move and press
        client.pointer_event(50, 40, 0)   # release at the same point
        client.pointer_event(0, 0, 0)     # park
        client.refresh()  # a round trip so the server has read them
    server.join()
    assert server.received["pointers"] == [
        (50, 40, 1), (50, 40, 0), (0, 0, 0)]


# -- the readiness probe -------------------------------------------

def test_the_probe_passes_a_server_it_could_session_against():
    server = _FakeVncServer()
    assert rfb.probe("127.0.0.1", server.port) is None


def test_the_probe_refuses_what_the_session_would_refuse():
    server = _FakeVncServer(security=(2,))
    with pytest.raises(RunFailure) as caught:
        rfb.probe("127.0.0.1", server.port)
    assert caught.value.rule_id == "vnc.security"


def test_the_probe_raises_oserror_while_nothing_listens():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        unserved = sock.getsockname()[1]
    with pytest.raises(OSError):
        rfb.probe("127.0.0.1", unserved)


# -- the recognition composition -----------------------------------

def test_a_golden_framebuffer_reads_back_through_the_recognizer():
    """Round-trip a text screen through render, the wire, and recognize.

    This is the one end-to-end test: a text screen drawn with the
    shipped fallback font, served to the client as a Raw framebuffer,
    and read back with the recognizer. It is the same composition the
    VNC plane's `text_screen` runs.
    """
    rows = ["C:\\>DIR", "", " Volume in drive C is RELIQUARY"]
    image = text_recognize.render(rows)
    server = _FakeVncServer(width=image.width, height=image.height,
                            frame=_bgrx(image))
    with _connect(server) as client:
        client.refresh()
        screen = text_recognize.recognize(client.image())
    assert screen[0][:3] == rows
    assert screen.unreadable == ()
