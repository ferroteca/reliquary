# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""QgaClient (D128): the wire protocol against a scripted fake agent.

The protocol methods (`sync`, `ping`, `run`, and the incremental JSON
reader underneath them) only ever touch `self._sock` through
`sendall`/`recv`/`settimeout` — they never care what socket family
produced it. So they're tested here against one end of a
`socket.socketpair()`, which Python emulates over a loopback TCP
connection on hosts with no native implementation (Windows included,
per its own stdlib fallback) — the same reason this suite can test
this logic on every host, unlike the real UNIX-socket connection
`__enter__` opens, which is gated by `host_supports_guest_agent()` and
skipped here where that's false.
"""

import base64
import json
import os
import socket
import threading
from unittest import mock

import pytest

from reliquary import qga as qga_module
from reliquary.errors import PreflightError, RunFailure

_NO_AF_UNIX = not hasattr(socket, "AF_UNIX")


def _client_over(sock, timeout=2.0):
    """A QgaClient wired directly to an already-connected socket,
    bypassing `__enter__` — the connection itself is not what these
    protocol tests are about."""
    client = qga_module.QgaClient("unused", timeout=timeout)
    client._sock = sock
    return client


def _serve_once(server_sock, handle):
    """Accept one connection and hand it to `handle`, in a thread."""
    def _run():
        conn, _addr = server_sock.accept()
        try:
            handle(conn)
        finally:
            conn.close()
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


def _read_requests(conn, count):
    """Read exactly `count` back-to-back JSON requests off `conn`.

    `sync()` prefixes its request with QGA's raw 0xFF resync marker,
    which isn't valid UTF-8 on its own — real QGA discards it as a
    signal, never as data, so this does the same before decoding.
    """
    decoder = json.JSONDecoder()
    raw = b""
    requests = []
    while len(requests) < count:
        stripped = raw.lstrip(b"\xff").decode("utf-8", errors="strict")
        if stripped:
            try:
                value, end = decoder.raw_decode(stripped)
                requests.append(value)
                raw = stripped[end:].encode("utf-8")
                continue
            except json.JSONDecodeError:
                pass
        chunk = conn.recv(4096)
        assert chunk, "the client closed before sending everything expected"
        raw += chunk
    return requests


def _send(conn, payload):
    conn.sendall(json.dumps(payload).encode("utf-8"))


# -- protocol methods, over a socketpair (every host) ------------------

def test_sync_discards_a_stale_reply_and_waits_for_the_matching_id():
    host, guest = socket.socketpair()
    client = _client_over(host)

    def _respond(conn):
        requests = _read_requests(conn, 1)
        marker = requests[0]["arguments"]["id"]
        # A stale reply from some earlier, aborted request first —
        # sync must not mistake this for its own answer.
        _send(conn, {"return": marker - 1 if marker > 1 else marker + 1})
        _send(conn, {"return": marker})
    thread = _serve_once(_bound_pair_server(guest), _respond)
    try:
        client.sync(timeout=2)
    finally:
        thread.join(timeout=2)
        host.close()
        guest.close()


def test_ping_succeeds_on_an_empty_return():
    host, guest = socket.socketpair()
    client = _client_over(host)

    def _respond(conn):
        _read_requests(conn, 1)
        _send(conn, {"return": {}})
    thread = _serve_once(_bound_pair_server(guest), _respond)
    try:
        client.ping(timeout=2)
    finally:
        thread.join(timeout=2)
        host.close()
        guest.close()


def test_ping_raises_on_a_malformed_reply():
    host, guest = socket.socketpair()
    client = _client_over(host)

    def _respond(conn):
        _read_requests(conn, 1)
        _send(conn, {"error": {"desc": "nope"}})
    thread = _serve_once(_bound_pair_server(guest), _respond)
    try:
        with pytest.raises(RunFailure) as caught:
            client.ping(timeout=2)
        assert caught.value.rule_id == "guest-agent.protocol-error"
    finally:
        thread.join(timeout=2)
        host.close()
        guest.close()


def test_run_polls_exec_status_until_exited_and_decodes_output():
    host, guest = socket.socketpair()
    client = _client_over(host)

    def _respond(conn):
        exec_request, = _read_requests(conn, 1)
        assert exec_request["arguments"]["path"] == "/bin/echo"
        assert exec_request["arguments"]["arg"] == ["hi"]
        _send(conn, {"return": {"pid": 4242}})
        status_request, = _read_requests(conn, 1)
        assert status_request["arguments"]["pid"] == 4242
        # Not finished yet on the first poll — run() must keep asking.
        _send(conn, {"return": {"exited": False}})
        _read_requests(conn, 1)
        _send(conn, {"return": {
            "exited": True, "exitcode": 0,
            "out-data": base64.b64encode(b"hi\n").decode(),
            "err-data": base64.b64encode(b"").decode(),
        }})
    thread = _serve_once(_bound_pair_server(guest), _respond)
    try:
        result = client.run("/bin/echo", ["hi"], timeout=2)
    finally:
        thread.join(timeout=2)
        host.close()
        guest.close()
    assert result.exit_code == 0
    assert result.signal is None
    assert result.stdout == "hi\n"
    assert result.stderr == ""


def test_a_timed_out_reply_raises_run_failure():
    host, guest = socket.socketpair()
    client = _client_over(host)
    host.settimeout(0.2)
    with pytest.raises(RunFailure) as caught:
        client.ping(timeout=0.2)
    assert caught.value.rule_id == "guest-agent.timeout"
    guest.close()


def test_a_closed_connection_raises_run_failure():
    host, guest = socket.socketpair()
    client = _client_over(host)
    # Only the remote end hangs up — the client's own socket object
    # stays open and usable, the same as a real dropped connection:
    # sendall() may still succeed, but the next read gets EOF.
    guest.close()
    with pytest.raises(RunFailure) as caught:
        client.ping(timeout=2)
    assert caught.value.rule_id == "guest-agent.connection-lost"
    host.close()


def _bound_pair_server(existing_sock):
    """Adapt an already-connected socket to `_serve_once`'s
    accept()-based server helper, so the responder threads above can
    share one shape whether the connection came from a real listening
    socket or, here, directly from a socketpair."""
    class _Already:
        def accept(self):
            return existing_sock, None
    return _Already()


# -- host support and connection refusal --------------------------------

def test_construction_refuses_an_unsupported_host():
    with mock.patch.object(qga_module, "host_supports_guest_agent",
                           return_value=False):
        with pytest.raises(PreflightError) as caught:
            with qga_module.QgaClient("/does/not/matter"):
                pass
    assert caught.value.rule_id == "guest-agent.host-unsupported"


@pytest.mark.skipif(_NO_AF_UNIX, reason="this host has no socket.AF_UNIX")
def test_connect_refuses_a_missing_socket_file(tmp_path):
    missing = os.path.join(str(tmp_path), "nothing-here.sock")
    with pytest.raises(PreflightError) as caught:
        with qga_module.QgaClient(missing, timeout=1):
            pass
    assert caught.value.rule_id == "guest-agent.unreachable"


@pytest.mark.skipif(_NO_AF_UNIX, reason="this host has no socket.AF_UNIX")
def test_connect_and_ping_over_a_real_unix_socket(tmp_path):
    path = os.path.join(str(tmp_path), "qga.sock")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen(1)

    def _respond(conn):
        _read_requests(conn, 1)
        _send(conn, {"return": {}})
    thread = _serve_once(server, _respond)
    try:
        with qga_module.QgaClient(path, timeout=2) as client:
            client.ping()
    finally:
        thread.join(timeout=2)
        server.close()
