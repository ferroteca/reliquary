# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""A minimal client for QEMU Guest Agent's (QGA) JSON wire protocol.

This module is deliberately narrow, the same way `rfb.py` is (D110's
"no new dependency" rule): a raw socket and just enough JSON framing
to prove a channel is alive and run one command. It verifies no
identity of its own — that happens one layer up, in
`Machine.guest_agent()`, the same way RFB's own identity check lives
in `backend_qemu.py` rather than in `rfb.py` itself.

QGA is not a Reliquary invention and never will be one
(ARCHITECTURE.md P3): this client only speaks a protocol QEMU's own
guest agent already publishes, over a channel
`backend-settings.qemu.guest-agent` declares (D128). It stays
QEMU-specific because that setting is QEMU-specific — there is no
equivalent seam on another backend today.

This is not `interaction.GuestExec`: that protocol's `execute()`
returns nothing, and a guest agent's whole value is the richer result
(exit status, captured output) `run()` returns instead. Growing a
shared interface across the agentless DOS workflow and QGA is exactly
the follow-up work `planning/design/guest-communication.md` already
flags as open; this client stays separate until that happens.

**Host support:** the channel is a UNIX domain socket, which means
this client only works on a host whose Python actually has one
(`socket.AF_UNIX`) — Linux and macOS today, not Windows (D128). A
Windows host fails closed with a clear error rather than a bare
`AttributeError`.
"""

import base64
import dataclasses
import json
import random
import socket
import time

from .errors import PreflightError, RunFailure

#: How long a socket operation waits before giving up, when the
#: caller states no timeout of its own.
DEFAULT_TIMEOUT = 10.0


def host_supports_guest_agent():
    """Whether this host's Python can open the UNIX socket a guest-agent
    channel needs (D128) — Linux and macOS today, not Windows."""
    return hasattr(socket, "AF_UNIX")


@dataclasses.dataclass(frozen=True)
class GuestAgentResult:
    """One `run()` call's outcome, as QGA's own `guest-exec-status` reports it.

    `signal` is `None` unless the guest process was killed by one;
    `exit_code` is `None` in that case instead of a made-up value
    standing in for a real one (P11).
    """

    exit_code: "int | None"
    signal: "int | None"
    stdout: str
    stderr: str


class QgaClient:
    """A connection to one guest-agent socket, and QGA's smallest useful
    command set: `sync`, `ping`, `run`.

    Used as a context manager — the socket opens on `__enter__` and
    closes on `__exit__`, the same shape `Qmp` already uses.
    """

    def __init__(self, path, timeout=DEFAULT_TIMEOUT):
        self._path = path
        self._timeout = timeout
        self._sock = None
        self._buffer = ""

    def __enter__(self):
        if not host_supports_guest_agent():
            raise PreflightError(
                "this host's Python has no UNIX domain socket support "
                "(socket.AF_UNIX), which a guest-agent channel needs — "
                "Windows hosts aren't covered yet (D128, "
                "planning/design/guest-communication.md)",
                rule_id="guest-agent.host-unsupported")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self._timeout)
        try:
            sock.connect(self._path)
        except OSError as failed:
            sock.close()
            raise PreflightError(
                f"could not reach the guest-agent channel at "
                f"{self._path!r}: {failed} — is the machine running with "
                "a guest-agent channel configured, and is "
                "qemu-guest-agent listening inside the guest?",
                rule_id="guest-agent.unreachable") from failed
        self._sock = sock
        return self

    def __exit__(self, *exc_info):
        if self._sock is not None:
            self._sock.close()
            self._sock = None
        return False

    def _send(self, payload):
        try:
            self._sock.sendall(json.dumps(payload).encode("utf-8"))
        except OSError as failed:
            raise RunFailure(
                "the guest agent channel failed while sending a request: "
                f"{failed}",
                rule_id="guest-agent.connection-lost") from failed

    def _read_value(self, deadline):
        """Read the next complete JSON value off the wire.

        QGA places raw JSON values back to back with no delimiter of
        its own — there is no newline guarantee to lean on — so this
        decodes incrementally instead of assuming a framing convention
        the protocol never promised.
        """
        decoder = json.JSONDecoder()
        while True:
            stripped = self._buffer.lstrip()
            if stripped:
                try:
                    value, end = decoder.raw_decode(stripped)
                    self._buffer = stripped[end:]
                    return value
                except json.JSONDecodeError:
                    pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RunFailure(
                    "the guest agent channel timed out waiting for a "
                    "reply", rule_id="guest-agent.timeout")
            self._sock.settimeout(remaining)
            try:
                chunk = self._sock.recv(4096)
            except TimeoutError:
                raise RunFailure(
                    "the guest agent channel timed out waiting for a "
                    "reply", rule_id="guest-agent.timeout") from None
            except OSError as failed:
                raise RunFailure(
                    "the guest agent channel failed while waiting for a "
                    f"reply: {failed}",
                    rule_id="guest-agent.connection-lost") from failed
            if not chunk:
                raise RunFailure(
                    "the guest agent channel closed before answering",
                    rule_id="guest-agent.connection-lost")
            self._buffer += chunk.decode("utf-8", errors="strict")

    def sync(self, timeout=None):
        """Resynchronize the channel — QGA's own recommended handshake.

        The leading 0xFF byte is QGA's resync marker: it tells the
        agent to discard whatever partial or stale bytes it may
        already be holding, from a previous aborted connection or from
        the guest itself, before this request. Any reply that does not
        carry the matching id is stale and is discarded rather than
        mistaken for this request's answer.
        """
        deadline = time.monotonic() + (timeout or self._timeout)
        marker = random.randint(1, 2 ** 31 - 1)
        self._sock.sendall(b"\xff")
        self._send({"execute": "guest-sync-delimited",
                    "arguments": {"id": marker}})
        while True:
            reply = self._read_value(deadline)
            if reply.get("return") == marker:
                return

    def ping(self, timeout=None):
        """Confirm the agent is alive and answering."""
        deadline = time.monotonic() + (timeout or self._timeout)
        self._send({"execute": "guest-ping"})
        reply = self._read_value(deadline)
        if "return" not in reply:
            raise RunFailure(
                f"guest-ping did not return cleanly: {reply}",
                rule_id="guest-agent.protocol-error")

    def run(self, path, args=(), timeout=None):
        """Run one guest executable to completion and return its result.

        `path` is the executable's path inside the guest, run
        directly — QGA has no shell of its own, so a shell command
        line needs to be handed to the guest's own shell explicitly
        (for example ``path="/bin/sh", args=["-c", "..."]``).
        """
        deadline = time.monotonic() + (timeout or self._timeout)
        self._send({"execute": "guest-exec",
                    "arguments": {"path": path, "arg": list(args),
                                  "capture-output": True}})
        reply = self._read_value(deadline)
        if "return" not in reply:
            raise RunFailure(
                f"guest-exec did not return cleanly: {reply}",
                rule_id="guest-agent.protocol-error")
        pid = reply["return"]["pid"]
        while True:
            self._send({"execute": "guest-exec-status",
                        "arguments": {"pid": pid}})
            reply = self._read_value(deadline)
            status = reply.get("return")
            if status is None:
                raise RunFailure(
                    f"guest-exec-status did not return cleanly: {reply}",
                    rule_id="guest-agent.protocol-error")
            if status.get("exited"):
                return GuestAgentResult(
                    exit_code=status.get("exitcode"),
                    signal=status.get("signal"),
                    stdout=base64.b64decode(
                        status.get("out-data", "")).decode(
                            "utf-8", errors="replace"),
                    stderr=base64.b64decode(
                        status.get("err-data", "")).decode(
                            "utf-8", errors="replace"))
            if time.monotonic() >= deadline:
                raise RunFailure(
                    f"guest command {path!r} (pid {pid}) did not finish "
                    "in time", rule_id="guest-agent.timeout")
            time.sleep(0.2)
