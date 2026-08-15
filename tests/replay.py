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

**Two things stand beside the seam, because the capture deliberately
holds neither.** The lifecycle is one — a replay creates no machine
and starts no process, so `MachineLayer` answers what a script asks of
it. Time is the other: every layer under the runner reads the wall
clock, so a five-minute install would take five minutes to replay
against the real one, and `Clock` gives it a virtual one instead.
"""

import contextlib
import copy
import os
from unittest import mock

from reliquary import control_display, interaction_agentless, screen_stability
from reliquary import script_runner
from reliquary.control_display import DisplayConsole
from reliquary.errors import PreflightError
from reliquary.interaction_agentless import AgentlessGuestExec
from reliquary.script_runner import _ScriptEngine
from reliquary.transcript import ReplaySession, _TranscriptReader

#: The modules that read the clock directly rather than through an
#: injected one. The runner takes `clock=` / `sleep=` at construction;
#: everything below it calls `time` where it stands.
_TIMED_MODULES = (control_display, interaction_agentless,
                  screen_stability)


def entries_of(path):
    """Every entry in a transcript, digests checked as it reads."""
    return _TranscriptReader(path).read()


def read(path):
    """A transcript's entries and the reader that validated them.

    The reader carries the header, and the pace in it is not
    decoration: a replayed run must poll at the pace the capture was
    taken at, or it reads the same screens on a cadence the recorded
    one never had — and the stability measure judges over wall-clock
    windows, so a different cadence is a different verdict.
    """
    reader = _TranscriptReader(path)
    return reader.read(), reader


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


class Clock:
    """Virtual time: the capture's own, and no waiting at all.

    A capture is minutes long because a guest is slow, not because the
    interpretation layer is: the run's own poll ramps, the stability
    windows and the menu machinery are all `time.sleep` against
    `time.monotonic`. Replaying against the real clock would take as
    long as the install did, which is the one thing F43's fixtures
    must not do — they run in the **default** suite.

    Only the waiting is gone: **the capture's own timestamps drive
    this clock**, so every frame is read where the guest drew it. That
    is not a refinement. A reader ticking by its own sleeps puts two
    frames 100ms apart that the recorded run took a third of a second
    over — each QEMU sample is a 4000-byte memory dump — and
    `screen_stability` measures over wall-clock windows precisely so a
    denser poll cannot reach a different verdict. Left to its sleeps,
    the install capture replayed to a screen that "never settled
    enough to compare against" on a boot where it plainly had.
    """

    def __init__(self, start=0.0):
        self._now = float(start)

    def monotonic(self):
        return self._now

    def sleep(self, seconds):
        """A sleep passes, and the reading that follows it lands.

        The recorded gap between two samples is the layer's own sleep
        plus what the read cost, and the two are not
        interchangeable: the layer samples the clock **before** it
        reads, so a replay where only reads moved time would hand the
        caller a moment one read stale. Sleeping here and jumping to
        the recorded moment at the read reproduces both halves — and
        the jump is monotone, so a sleep can never carry the clock
        past the guest's own timeline.
        """
        self._now += max(0.0, float(seconds))

    def advance_to(self, elapsed):
        """Move to a recorded moment, never backwards.

        Monotone because a transcript is read forwards and a clock
        that went back would make a deadline unexpire; the recording
        is the floor.
        """
        self._now = max(self._now, float(elapsed))


class _TimeShim:
    """`time` as the interpretation layer uses it: two functions."""

    def __init__(self, clock):
        self.monotonic = clock.monotonic
        self.sleep = clock.sleep


@contextlib.contextmanager
def virtual_time(clock):
    """Run the interpretation layer against `clock` instead of the wall."""
    shim = _TimeShim(clock)
    with contextlib.ExitStack() as stack:
        for module in _TIMED_MODULES:
            stack.enter_context(mock.patch.object(module, "time", shim))
        yield clock


class MachineLayer:
    """The lifecycle a replayed run drives, answered from memory.

    The capture sits at the carrier seam and holds nothing above it by
    design (`screen-transcripts.md`), so the machine layer is the
    harness's to stand up: a replay materializes nothing, starts no
    process and touches no disk, while a script still asks for the
    phase it begins in, the boot order a scope captures and puts back,
    and the slot an insert fills.

    It **refuses where the machine layer refuses**: a boot order is a
    launch-time firmware order and so stopped-only, which is exactly
    the rule D104 accepted a cost for — a scope's restore can fail —
    and a double that said yes to it would replay a run the real layer
    would have stopped.
    """

    def __init__(self, machine_id="freedos-0", machine_home=None,
                 boot=("hdd0", "cdrom0"), drives=("hdd0", "cdrom0"),
                 phase="ready"):
        self.machine_id = machine_id
        self.machine_home = machine_home
        self.state = {
            "id": machine_id,
            "phase": phase,
            "boot": list(boot),
            "drives": {key: {} for key in drives},
        }
        #: Every lifecycle call the run made, in order, for a test that
        #: wants to assert on the shape of a run rather than only that
        #: it finished.
        self.calls = []
        self.variables = {}

    # -- what the engine reads -----------------------------------

    def load_machine_state(self, machine_id, context=None):
        return copy.deepcopy(self.state)

    def machine_dir_path(self, machine_id, context=None):
        return self.machine_home

    def read_vm_state(self, machine_dir):
        if self.state["phase"] != "running":
            return None
        return {"backend": "transcript", "backend-id": self.machine_id,
                "token": "0" * 32, "endpoint": {"port": 0}}

    # -- what the engine changes ---------------------------------

    def start_machine(self, machine_id, display=False, context=None,
                      events=None, cancelled=None):
        self.calls.append(("start", ()))
        self.state["phase"] = "running"

    def stop_machine(self, machine_id, context=None):
        self.calls.append(("stop", ()))
        self.state["phase"] = "ready"

    def mark_stopped(self, machine_id, context=None):
        if self.state["phase"] != "running":
            return
        self.calls.append(("mark-stopped", ()))
        self.state["phase"] = "ready"

    def insert_media(self, machine_id, slot, media=None, file=None,
                     context=None, events=None, cancelled=None):
        self.calls.append(("insert", (slot, media or file)))
        self.state["drives"].setdefault(slot, {})
        self.state["drives"][slot] = (
            {"media": media} if media else {"path": file})

    def eject_media(self, machine_id, slot, context=None):
        self.calls.append(("eject", (slot,)))
        self.state["drives"][slot] = {}

    def set_boot_order(self, machine_id, boot_keys, context=None):
        if self.state["phase"] != "ready":
            raise PreflightError(
                f"machine {machine_id} must be stopped to change boot "
                f"order (phase: {self.state['phase']})",
                rule_id="machine.must-be-stopped")
        self.calls.append(("set-boot", tuple(boot_keys)))
        self.state["boot"] = list(boot_keys)

    def set_machine_var(self, machine_id, key, value, context=None):
        self.calls.append(("set", (key, value)))
        self.variables[key] = value


class _MachineHandle:
    """A `Machine` over the replayed session, at the same two doors.

    The runner reaches the carrier through `_machine()` — the console
    for every read and input verb, `screenshot` for the verb and the
    automatic failure capture — so replacing the handle covers both
    without the harness reaching into either.
    """

    def __init__(self, session, home=None, cache=None,
                 _session_wrapper=None):
        self._session = session
        self.home = home

    @contextlib.contextmanager
    def console(self):
        yield DisplayConsole(self._session)

    def screenshot(self, name="screen", directory=None):
        target = directory or os.path.join(self.home or "", "screenshots")
        path = os.path.join(target, f"{name}.png")
        return self._session.screenshot(path)


def machine_handle(session):
    """A `Machine` standing on one session — replayed or recorded.

    The exec adapter takes a machine and reaches the carrier through
    it, so this is what a capture is taken *through* as well as what a
    replay is stood on.
    """
    return _MachineHandle(session)


def machine_handles(session):
    """A `Machine` replacement bound to one replayed session."""
    def handle(home=None, deadline=None, cache=None, _session_wrapper=None):
        return _MachineHandle(session, home=home)
    return handle


@contextlib.contextmanager
def replaying(path, machines=None):
    """Stand the whole run on a transcript: seam, lifecycle and clock.

    Yields the `(session, machines, clock)` a replayed run works
    against, with the pace the capture states already applied by
    `engine_for` below.
    """
    entries, reader = read(path)
    clock = Clock()
    session = ReplaySession(entries, advance=clock.advance_to)
    layer = machines if machines is not None else MachineLayer()
    with mock.patch.object(script_runner, "_machines", layer), \
            mock.patch.object(script_runner, "Machine",
                              machine_handles(session)), \
            virtual_time(clock):
        yield session, layer, clock, reader


@contextlib.contextmanager
def replaying_exec(path):
    """Stand the agentless exec adapter on a capture of one command.

    The other kind of fixture, and a narrower stand-up than a script's:
    the adapter reaches the carrier through a machine handle and asks
    nothing of the lifecycle, so the seam and the clock are the whole
    of what the harness supplies. Yields the adapter and the session
    the capture is being read through, with the header beside them —
    the command it was taken of and the limit it was given, both of
    which the replay has to use unchanged.
    """
    entries, reader = read(path)
    clock = Clock()
    session = ReplaySession(entries, advance=clock.advance_to)
    with virtual_time(clock):
        yield AgentlessGuestExec(machine_handle(session)), session, reader


def engine_for(script, home, machine_home, clock, reader, **rest):
    """The engine a replay runs, on the capture's own pace and clock.

    `record_pace` is not about recording here: it is what floored the
    poll intervals when the capture was taken, so a replay that leaves
    it out reads the same screens two seconds apart where the recorded
    run read them a tenth of a second apart — and the stability gate
    measures over wall-clock windows.
    """
    return _ScriptEngine(script, "freedos-0", home, machine_home,
                         clock=clock.monotonic, sleep=clock.sleep,
                         record_pace=reader.pace, **rest)
