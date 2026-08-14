# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The replay harness: the interpretation layer driven off a transcript.

F43's first work item. Cross-cutting on purpose, the neutral home the
tdd rules allow and for the same reason `fake_backend.py` sits here:
the corpus module, the harness's own round-trip test, and any future
regression pinned to a capture all drive the same path, and none of
them should need a hypervisor.

**What replay stands up is the real interpretation layer.** The
transcript was captured at the carrier seam — `text_screen`,
`send_keys`, `screenshot`, `change_medium` — so standing
`ReplaySession` back at that seam leaves `control_display`,
`interaction_agentless` and the runner's dispatch running unmodified
above it. That is the whole reason the fixtures are worth having: a
regression in prompt detection or echo scanning changes what the layer
asks the carrier for, and the transcript is the record of what it
asked last time.

**The transcript is the expectation, and it needs no separate one.**
`ReplaySession` already refuses a call the capture does not cover
(P11), so a run that diverges raises `TranscriptError` naming the
carrier and the moment rather than quietly passing. That is the
assertion vocabulary: a fixture asserts by *being replayable*, and
nothing has to be restated in a sidecar that could drift from it.
"""

import contextlib

from reliquary.control_display import DisplayConsole
from reliquary.transcript import ReplaySession, _TranscriptReader


def entries_of(path):
    """Every entry in a transcript, digests checked as it reads."""
    return _TranscriptReader(path).read()


def console_over(session):
    """A `_ScriptEngine._console` standing the real console on `session`.

    The engine opens a fresh console per sample and per input verb —
    QEMU admits one QMP client at a time — so this yields a new
    `DisplayConsole` each time over the one session, which is what
    keeps the replay's read cursor advancing across the whole run
    rather than restarting with every statement.
    """
    @contextlib.contextmanager
    def console():
        yield DisplayConsole(session)
    return console


def replay_console(path):
    """The console factory for one transcript, and its session."""
    session = ReplaySession(entries_of(path))
    return console_over(session), session
