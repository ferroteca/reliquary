# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The replay harness: the interpretation layer driven off a transcript.

F43's first work item. This file is shared across test modules on
purpose, for the same reason `fake_backend.py` is: the corpus module,
the harness's own round-trip test, and any future regression pinned
to a capture all drive the same code path, and none of them should
need a real hypervisor.

Replay stands up the real interpretation layer. The transcript
records calls at the carrier level — `text_screen`, `send_keys`,
`screenshot`, `change_medium` — so putting `ReplaySession` in place of
the real carrier leaves `control_display`, `interaction_agentless`,
and the runner's dispatch running unmodified above it. That is why
the fixtures are worth having: a regression in prompt detection or
echo scanning changes what the layer asks the carrier for, and the
transcript is the record of what it asked for last time.

The transcript itself is the expected result, so no separate expected
result needs to be written down. `ReplaySession` already raises if a
call was not in the capture (P11), so a run that diverges raises
`TranscriptError` naming the carrier method and the point in the
transcript, instead of quietly passing. A fixture passes by *being
replayable* — nothing about what should happen has to be restated
somewhere else, where it could drift out of sync with the capture.

Two more things are faked here, because the capture never recorded
them either. One is the machine's lifecycle: a replay creates no
machine and starts no process, so `MachineLayer` answers whatever a
script asks of it, from memory. The other is time: every layer under
the runner reads the wall clock, so replaying against the real clock
would make a five-minute install take five minutes again; `Clock`
gives it a virtual clock instead.
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

    The reader carries the transcript's header, including its pace. A
    replayed run must poll at the pace the capture was taken at — a
    different cadence reads the same screens at moments the recorded
    run never had, and the stability measure judges screens over
    wall-clock windows, so a different cadence gives a different
    verdict.
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
    """Virtual time: replays instantly, but keeps the capture's own timing.

    A capture takes several minutes because the guest is slow, not
    because the interpretation layer is: the poll ramp-up, the
    stability windows, and the menu-handling code all call
    `time.sleep` and check `time.monotonic`. Replaying against the
    real clock would take as long as the original install did — and
    F43's fixtures run in the default test suite, so they cannot
    afford that.

    Only the waiting is skipped. The capture's own recorded
    timestamps still drive this clock, so every frame is read at the
    same virtual moment the guest drew it. That timing matters: a
    clock that just advanced by however long each `sleep` call asked
    for would place two frames 100ms apart when the recorded run
    actually took a third of a second between them (each QEMU sample
    is a 4000-byte memory dump). `screen_stability` measures how long
    a screen holds steady over wall-clock time, so a denser poll rate
    gives a different, wrong verdict. This is not hypothetical:
    without jumping to the recorded timestamps, a replayed install
    capture judged a screen as "never settled enough to compare
    against" on a boot where it plainly had.
    """

    def __init__(self, start=0.0):
        self._now = float(start)

    def monotonic(self):
        return self._now

    def sleep(self, seconds):
        """A sleep passes, and the read that follows it lands at the
        right moment.

        In the recorded run, the gap between two samples is the
        layer's own sleep plus however long the read itself took —
        the two are not the same thing, because the layer reads the
        clock *before* it reads the screen. If only reads moved the
        clock forward, a replay would hand the caller a moment that
        is one read late. Advancing the clock here on `sleep`, and
        jumping to the exact recorded moment when the read happens
        (`advance_to`), reproduces both parts of that gap. The jump
        only ever moves forward, so a `sleep` call can never push the
        clock past what the guest's own recorded timeline says.
        """
        self._now += max(0.0, float(seconds))

    def advance_to(self, elapsed):
        """Move to a recorded moment, but never backwards.

        A transcript is read forwards, and a clock that moved
        backwards could make an already-expired deadline look
        unexpired again. The recorded moment is a floor: the clock
        only ever advances to it or stays put.
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

    The capture is taken at the carrier level and, by design, records
    nothing above that (`screen-transcripts.md`), so the machine
    lifecycle is left for this harness to fake: a replay creates no
    machine, starts no process, and touches no disk, but a script
    under replay still asks for the phase it starts in, the boot
    order a scope saves and restores, and the drive slot an insert
    fills.

    It refuses in the same cases the real machine layer refuses:
    setting the boot order is a launch-time firmware setting, so it
    is allowed only while stopped. That is the same rule D104
    accepted a cost for — a scope's restore-on-exit can fail — and if
    this fake allowed it anyway, a replay could succeed on a run the
    real layer would have stopped.
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
            "devices": {key: {} for key in drives},
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
        self.state["devices"].setdefault(slot, {})
        self.state["devices"][slot] = (
            {"media": media} if media else {"path": file})

    def eject_media(self, machine_id, slot, context=None):
        self.calls.append(("eject", (slot,)))
        self.state["devices"][slot] = {}

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
    """A `Machine` over the replayed session, with the same two entry points.

    The runner reaches the carrier through `_machine()` — using
    `console()` for every read and input verb, and `screenshot()` for
    the screenshot verb and for automatic failure capture. Replacing
    the handle with this class covers both, without the harness
    having to patch either one separately.
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
    """Stand the whole run on a transcript: the carrier, the lifecycle,
    and the clock.

    Yields the `(session, machines, clock)` a replayed run works
    against, with the pace the capture recorded already applied by
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

    This is the other kind of fixture, and a narrower stand-up than a
    script's: the adapter reaches the carrier through a machine
    handle and asks nothing of the lifecycle, so the carrier and the
    clock are the whole of what the harness supplies here. Yields the
    adapter and the session the capture is being read through, along
    with the header — the command it was taken of and the limit it
    was given, both of which the replay has to use unchanged.
    """
    entries, reader = read(path)
    clock = Clock()
    session = ReplaySession(entries, advance=clock.advance_to)
    with virtual_time(clock):
        yield AgentlessGuestExec(machine_handle(session)), session, reader


def engine_for(script, home, machine_home, clock, reader, **rest):
    """The engine a replay runs, on the capture's own pace and clock.

    `record_pace` is not about recording here — it is what set the
    minimum poll interval when the capture was taken. A replay that
    leaves it out reads the same screens two seconds apart where the
    recorded run read them a tenth of a second apart, and the
    stability gate measures how long a screen holds steady over
    wall-clock time, so that difference changes the verdict.
    """
    return _ScriptEngine(script, "freedos-0", home, machine_home,
                         clock=clock.monotonic, sleep=clock.sleep,
                         record_pace=reader.pace, **rest)
