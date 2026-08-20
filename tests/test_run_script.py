# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for labeled script wiring: the returned output and the CLI."""

import contextlib
import hashlib
import io
import json
import os
from unittest import mock

import pytest

from reliquary import cli
from reliquary.errors import PreflightError, RunFailure, StaticError
from reliquary.machines import create_machine, set_machine_var
from reliquary.events import RUN_END, RUN_START
from reliquary.script_parser import parse_script
from reliquary.transcript import _TranscriptWriter
from reliquary.script_runner import (
    ScriptRun, _ScriptEngine,
    _existing_machine, _resolve_script_stem, execute_script, run_script,
)
from tests import fake_backend


@pytest.fixture
def home(tmp_path):
    """A home directory with the fake backend installed."""
    with fake_backend.installed():
        yield str(tmp_path)


def _write_plain_blueprint(blueprints, scripts_map=None):
    if scripts_map is None:
        scripts_map = {"install": "install-script"}
    with open(os.path.join(blueprints, "plain.rlqb"), "w",
              encoding="utf-8") as handle:
        json.dump([
            {"type": "machine", "name": "plain", "platform": "dos",
             "drives": {"hdd0": "blank-20m"},
             "scripts": scripts_map},
            {"type": "media", "name": "blank-20m",
             "materialize": "new", "size": "20M"},
        ], handle)


def _write_script(scripts, stem, text='wait "ready" timeout=1s\n'):
    with open(os.path.join(scripts, f"{stem}.rlqs"), "w",
              encoding="utf-8", newline="\n") as handle:
        handle.write("platform dos\n")
        handle.write(text)


# The label is a bare stem, resolved through the blueprint's map.

def test_label_maps_through_scripts_map():
    assert _resolve_script_stem(
        "install", {"install": "freedos-install"}) == "freedos-install"


def test_unknown_label_is_bare_stem():
    assert _resolve_script_stem("my-script", {"install": "x"}) == "my-script"


def test_rejects_path_components():
    with pytest.raises(StaticError) as caught:
        _resolve_script_stem("../escape", {})
    assert "bare name" in str(caught.value)


def test_rejects_rlqs_suffix():
    with pytest.raises(StaticError) as caught:
        _resolve_script_stem("install.rlqs", {})
    assert ".rlqs" in str(caught.value)


# The label map is the blueprint's, read at invocation.
#
# A script label names *which instructions to run*, not what the
# machine is, so it belongs with `parameters` on the live-read side of
# the instance model rather than in the machine's shape baseline —
# cli.md resolves a label against "the blueprint's `scripts` map", and
# the U5 record has parameters read at invocation "like the scripts
# map".

@pytest.fixture
def label_home(home):
    blueprints = os.path.join(home, "blueprints")
    scripts = os.path.join(home, "scripts")
    os.makedirs(blueprints)
    os.makedirs(scripts)
    _write_plain_blueprint(blueprints)
    for stem in ("install-script", "ready-script"):
        _write_script(scripts, stem)
    return home


def _run_label(home, label):
    def execute(script, *, machine_id, **rest):
        del script, machine_id, rest
        return ("-", "ready")

    with mock.patch("reliquary.script_runner.execute_script",
                    side_effect=execute):
        return run_script(label, blueprint="plain", context=home,
                          progress="plain")


def test_a_label_added_after_the_machine_exists_resolves(label_home):
    # the machine was created when the blueprint named one label;
    # adding a second must not require `apply` to become runnable,
    # because a label map is not machine shape
    _run_label(label_home, "install")

    _write_plain_blueprint(os.path.join(label_home, "blueprints"),
                           {"install": "install-script",
                            "ready": "ready-script"})

    assert _run_label(label_home, "ready").machine_phase == "ready"


def test_a_relabelled_script_takes_effect_without_apply(label_home):
    _run_label(label_home, "install")

    _write_plain_blueprint(os.path.join(label_home, "blueprints"),
                           {"install": "ready-script"})

    with mock.patch("reliquary.script_runner.load_script") as loaded:
        loaded.side_effect = AssertionError("stop here")
        with pytest.raises(AssertionError):
            _run_label(label_home, "install")
    assert "ready-script" in str(loaded.call_args[0][0])


# Resolving the machine a run works on, or creating one.

@pytest.fixture
def plain_home(home):
    blueprints = os.path.join(home, "blueprints")
    os.makedirs(blueprints)
    _write_plain_blueprint(blueprints)
    return home


def test_no_machine_yet_is_reported_as_none(plain_home):
    # _existing_machine never creates; None means "would create".
    assert _existing_machine(blueprint="plain", context=plain_home) is None


def test_reuses_sole_machine(plain_home):
    first = create_machine("plain", context=plain_home)
    second = _existing_machine(blueprint="plain", context=plain_home)
    assert first == second


def test_machine_id_resolves_to_itself(plain_home):
    machine_id = create_machine("plain", context=plain_home)
    resolved = _existing_machine(machine=machine_id, context=plain_home)
    assert resolved == machine_id


def test_a_specific_machine_id_selects_among_several(plain_home):
    first = create_machine("plain", context=plain_home)
    second = create_machine("plain", context=plain_home)
    resolved = _existing_machine(machine="plain-1", context=plain_home)
    assert first == "plain-0"
    assert resolved == second
    assert resolved == "plain-1"


# A noninteractive unbound property fails before any machine.

def test_unbound_property_fails_without_creating_a_machine(home):
    from reliquary.binding import PropertyBindingError

    os.makedirs(os.path.join(home, "blueprints"))
    os.makedirs(os.path.join(home, "scripts"))
    with open(os.path.join(home, "blueprints", "plain.rlqb"),
              "w", encoding="utf-8") as handle:
        json.dump({"type": "machine", "name": "plain", "platform": "dos"},
                  handle)
    with open(os.path.join(home, "scripts", "needs.rlqs"),
              "w", encoding="utf-8") as handle:
        handle.write('property owner\nenter "${owner}"\n')

    with mock.patch("reliquary.script_runner.console_asker",
                    return_value=None), \
            mock.patch("reliquary.machines.create_machine") as create:
        with pytest.raises(PropertyBindingError):
            run_script("needs", blueprint="plain", context=home)
    create.assert_not_called()
    machines_root = os.path.join(home, "cache", "machines")
    created = (os.path.isdir(machines_root)
               and [name for name in os.listdir(machines_root)
                    if not name.startswith(".")])
    assert not created


# The run returns its output and writes nothing (D36).

def _run_engine(home):
    machine_id = "abcd" * 8
    machine_home = os.path.join(home, "cache", "machines", machine_id)
    os.makedirs(machine_home)
    script = parse_script('platform dos\nentry only\n'
                          'phase only {\n    wait "Hello"\n'
                          "    finish\n}\n")
    engine = _ScriptEngine(
        script, machine_id, home, machine_home,
        script_path="/tmp/demo.rlqs")
    engine._port = 5555

    class _Console:
        def screen_text(self):
            return ["Hello"]

        def screen(self, font_banks=()):
            rows = self.screen_text()
            return rows, [[0x07] * 80 for _ in range(len(rows))]

    @contextlib.contextmanager
    def console():
        yield _Console()

    engine._console = console

    with mock.patch("reliquary.script_runner._machines") as machines:
        machines.load_machine_state.return_value = {"phase": "running"}
        machines.machine_dir_path.return_value = machine_home
        machines.read_vm_state.return_value = {
            "backend": "qemu", "backend-id": "reliquary-plain-0",
            "token": "0" * 32, "endpoint": {"port": 5555}}
        engine.run()
    return engine, machine_home


def test_the_stream_carries_the_run_and_ends_with_its_outcome(tmp_path):
    engine, _machine_home = _run_engine(str(tmp_path))
    events = engine.events.events
    assert events[0]["kind"] == RUN_START
    assert events[0]["script"] == "/tmp/demo.rlqs"
    assert events[-1]["kind"] == RUN_END
    assert events[-1]["outcome"] == "ok"
    assert events[-1]["exit-code"] == 0
    # Sequence numbers are dense and ordered.
    assert [event["seq"] for event in events] == list(
        range(1, len(events) + 1))
    kinds = [event["kind"] for event in events]
    assert "observation.arm" in kinds
    assert "observation.match" in kinds


def test_the_run_writes_nothing_to_disk(tmp_path):
    _engine, machine_home = _run_engine(str(tmp_path))
    assert sorted(os.listdir(machine_home)) == []


# `run-script` end to end, through the session and the CLI.

@pytest.fixture
def wiring_home(home):
    blueprints = os.path.join(home, "blueprints")
    scripts = os.path.join(home, "scripts")
    os.makedirs(blueprints)
    os.makedirs(scripts)
    _write_plain_blueprint(blueprints)
    _write_script(scripts, "install-script")
    return home


def _run_setting(home, variable, value, **keywords):
    """Run the script, having it `set` a variable as scripts do."""
    def execute(script, *, machine_id, **rest):
        del script, rest
        if variable is not None:
            set_machine_var(machine_id, variable, value, context=home)
        return ("-", "ready")

    with mock.patch("reliquary.script_runner.execute_script",
                    side_effect=execute):
        return run_script("install", blueprint="plain", context=home,
                          progress="plain", **keywords)


def test_expect_passes_when_the_run_left_the_value(wiring_home):
    result = _run_setting(wiring_home, "ready", "yes",
                          expect={"ready": "yes"})
    assert result.machine_phase == "ready"


def test_expect_fails_when_the_value_differs(wiring_home):
    with pytest.raises(RunFailure) as caught:
        _run_setting(wiring_home, "ready", "no", expect={"ready": "yes"})
    message = str(caught.value)
    assert "'yes'" in message
    assert "'no'" in message


def test_expect_fails_when_the_script_never_set_it(wiring_home):
    """The silence this exists to break.

    An unset variable and a machine that never ran read alike, so
    without a contract a script that failed to reach its `set` is
    indistinguishable from one that never had one.
    """
    with pytest.raises(RunFailure) as caught:
        _run_setting(wiring_home, None, None, expect={"ready": "yes"})
    assert "unset" in str(caught.value)


def test_expect_is_refused_on_a_dry_run(wiring_home):
    # A plan runs nothing, so there is no variable to contract.
    with pytest.raises(StaticError) as caught:
        run_script("install", blueprint="plain", context=wiring_home,
                   dry_run=True, expect={"ready": "yes"})
    assert caught.value.rule_id == "progress.expect-on-a-dry-run"


def test_no_expect_reads_no_variable(wiring_home):
    """The default path pays nothing: no contract, no read."""
    with mock.patch("reliquary.machines.get_machine_var") as read:
        _run_setting(wiring_home, "ready", "yes")
    read.assert_not_called()


def test_run_script_resolves_label_and_returns_its_output(wiring_home):
    with mock.patch("reliquary.script_runner.execute_script",
                    return_value=("-", "ready")) as execute:
        result = run_script("install", blueprint="plain",
                            context=wiring_home, progress="plain")
    assert isinstance(result, ScriptRun)
    assert result.created_machine
    assert result.script_path.endswith("install-script.rlqs")
    assert result.final_phase == "-"
    assert result.machine_phase == "ready"
    assert isinstance(result.events, tuple)
    execute.assert_called_once()
    kwargs = execute.call_args.kwargs
    assert kwargs["machine_id"] == result.machine_id
    assert kwargs["script_path"] == result.script_path
    assert kwargs["context"] == wiring_home
    assert not kwargs["display"]
    assert kwargs["events"] is not None


def test_run_script_creates_no_run_directory(wiring_home):
    with mock.patch("reliquary.script_runner.execute_script",
                    return_value=("-", "ready")):
        result = run_script("install", blueprint="plain",
                            context=wiring_home, progress="plain")
    machine_dir = os.path.join(wiring_home, "cache", "machines",
                               result.machine_id)
    assert not os.path.exists(os.path.join(machine_dir, "runs"))


def test_run_script_bare_stem_when_label_absent(wiring_home):
    _write_script(os.path.join(wiring_home, "scripts"), "extra", text="")
    with mock.patch("reliquary.script_runner.execute_script",
                    return_value=("-", "ready")):
        result = run_script("extra", blueprint="plain",
                            context=wiring_home)
    assert result.script_path.endswith("extra.rlqs")


def test_run_script_missing_script_fails(wiring_home):
    os.remove(os.path.join(wiring_home, "scripts", "install-script.rlqs"))
    with pytest.raises(PreflightError) as caught:
        run_script("install", blueprint="plain", context=wiring_home)
    assert "install-script.rlqs" in str(caught.value)


def test_run_script_forwards_display(wiring_home):
    with mock.patch("reliquary.script_runner.execute_script",
                    return_value=("-", "ready")) as execute:
        run_script("install", blueprint="plain", context=wiring_home,
                   display=True)
    assert execute.call_args.kwargs["display"]


def test_cli_run_script_invokes_runtime_end_to_end(wiring_home):
    """rlq run-script install --blueprint … wires through."""
    stdout = io.StringIO()
    with mock.patch(
                "reliquary.session.Session.run_script",
                return_value=ScriptRun(
                    machine_id="abcd" * 8,
                    script_path=os.path.join(
                        wiring_home, "scripts", "install-script.rlqs"),
                    created_machine=True,
                )) as run, \
            contextlib.redirect_stdout(stdout):
        result = cli.main([
            "--home-dir", wiring_home,
            "--blueprint", "plain",
            "run-script", "install",
        ])
    assert result == 0
    run.assert_called_once_with(
        "install",
        blueprint="plain",
        machine=None,
        display=False,
        properties=None,
        # No properties_file: the selection rides in the record
        # the session was opened on (P26's cargo), not per call.
        progress="auto",
        dry_run=False,
        # No --expect given, so no contract: the CLI passes the
        # absence through rather than inventing an empty mapping,
        # which would make "expected nothing" and "expected
        # nothing in particular" the same value.
        expect=None,
        record=None,
    )
    # A stream-bearing command's human modes leave stdout empty:
    # the outcome travels by exit code.
    assert stdout.getvalue() == ""


def test_jsonl_puts_the_stream_on_stdout_and_nothing_else(wiring_home):
    def emit(script, **kwargs):
        stream = kwargs["events"]
        stream.emit("action.start", verb="enter", detail="'DIR'")
        stream.emit("run.end", outcome="ok",
                    **{"exit-code": 0, "final-phase": "-",
                       "machine-phase": "ready"})
        return "-", "ready"

    out, err = io.StringIO(), io.StringIO()
    with mock.patch("reliquary.script_runner.execute_script",
                    side_effect=emit), \
            contextlib.redirect_stdout(out), \
            contextlib.redirect_stderr(err):
        code = cli.main([
            "--home-dir", wiring_home, "--blueprint", "plain",
            "run-script", "install", "--progress", "jsonl",
        ])
    assert code == 0
    lines = out.getvalue().splitlines()
    documents = [json.loads(line) for line in lines]
    assert documents[0]["kind"] == "action.start"
    # The last line is the terminal event: the machine-readable
    # result, with no separate result mode.
    assert documents[-1]["kind"] == RUN_END
    assert documents[-1]["outcome"] == "ok"


def test_the_run_returns_the_stream_it_rendered(wiring_home):
    def emit(script, **kwargs):
        kwargs["events"].emit(RUN_START, script="demo.rlqs")
        return "-", "ready"

    with mock.patch("reliquary.script_runner.execute_script",
                    side_effect=emit), \
            contextlib.redirect_stderr(io.StringIO()):
        result = run_script("install", blueprint="plain",
                            context=wiring_home, progress="plain")
    assert [event["kind"] for event in result.events] == [RUN_START]


def test_cli_script_requires_selector(wiring_home):
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        result = cli.main([
            "--home-dir", wiring_home, "run-script", "install",
        ])
    assert result == 2
    assert "--blueprint or --machine" in stderr.getvalue()


def test_cli_script_rejects_json(wiring_home):
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        result = cli.main([
            "--home-dir", wiring_home, "--blueprint", "plain",
            "run-script", "install", "--json",
        ])
    assert result == 2
    assert "--progress jsonl" in stderr.getvalue()


def test_cli_script_forwards_display_and_progress(wiring_home):
    with mock.patch(
            "reliquary.session.Session.run_script",
            return_value=ScriptRun(
                machine_id="abcd" * 8,
                script_path="/tmp/x.rlqs",
            )) as run, \
            contextlib.redirect_stdout(io.StringIO()):
        result = cli.main([
            "--home-dir", wiring_home,
            "--blueprint", "plain",
            "run-script", "install",
            "--display", "--progress", "jsonl",
        ])
    assert result == 0
    assert run.call_args.kwargs["display"]
    assert run.call_args.kwargs["progress"] == "jsonl"


# --record installs the recorder on a frozen Machine.

def test_the_runner_installs_the_recorder_through_construction(tmp_path):
    """`--record` must survive `Machine` being frozen (regression).

    The engine used to assign `machine._session_wrapper` after
    construction, and `Machine` is a frozen dataclass, so **every**
    recorded run died at its first screen read with "cannot assign to
    field '_session_wrapper'". The flag had never worked on a real
    run: F42's own tests build `RecordingSession` directly and the
    replay harness replaces `_console`, so nothing drove the wiring
    this covers.
    """
    home = str(tmp_path)
    machine_home = os.path.join(home, "machine")
    os.makedirs(machine_home)
    with open(os.path.join(machine_home, "machine.json"), "w",
              encoding="utf-8") as handle:
        json.dump({"id": "freedos-0", "phase": "running",
                   "vm": {"backend": "qemu",
                          "backend-id": "reliquary-freedos-0",
                          "token": "0" * 32,
                          "endpoint": {"port": 5555}}}, handle)
    target = os.path.join(home, "run.rlqt")
    writer = _TranscriptWriter(target, pace=0.05)
    writer.open()
    engine = _ScriptEngine(
        parse_script('platform dos\nentry only\nphase only {\n'
                     '    finish\n}\n'),
        "freedos-0", home, machine_home, script_path="/tmp/demo.rlqs",
        record_pace=0.05, recording_writer=writer)
    with fake_backend.installed():
        with engine._console() as console:
            console.screen_text()
    writer.close()
    with open(target, encoding="utf-8") as handle:
        kinds = [json.loads(line)["type"] for line in handle
                 if line.strip() and "type" in json.loads(line)]
    assert "frame" in kinds, (
        "the console read a screen and the transcript holds no frame, "
        "so the recorder was never installed on the session.")


def _poll_gaps(tmp_path, **recording):
    """Every interval a run waiting on a screen that never arrives slept."""
    home = str(tmp_path)
    machine_home = os.path.join(home, "machine")
    os.makedirs(machine_home)
    # A clock of its own rather than the replay harness's: there, time
    # is the transcript's and a sleep costs nothing, while what is
    # measured here is a *live* run's cadence, where it is the whole
    # of what passes between two samples.
    now = [0.0]
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        now[0] += seconds

    engine = _ScriptEngine(
        parse_script('platform dos\nentry only\nphase only {\n'
                     '    wait "never drawn" timeout=10s\n'
                     '    finish\n}\n'),
        "freedos-0", home, machine_home, script_path="/tmp/demo.rlqs",
        clock=lambda: now[0], sleep=sleep, **recording)

    @contextlib.contextmanager
    def blank():
        class _Console:
            def screen(self, font_banks=()):
                return [""] * 25, [[0x07] * 80 for _ in range(25)]

            def screen_text(self):
                return [""] * 25
        yield _Console()

    engine._console = blank
    with mock.patch("reliquary.script_runner._machines") as machines:
        machines.load_machine_state.return_value = {"phase": "running"}
        machines.machine_dir_path.return_value = machine_home
        machines.read_vm_state.return_value = {
            "backend": "qemu", "backend-id": "reliquary-freedos-0",
            "token": "0" * 32, "endpoint": {"port": 5555}}
        with pytest.raises(RunFailure):
            engine.run()
    return slept


def test_a_recorded_run_polls_at_the_pace_it_records(tmp_path):
    """The pace has to make the run sample harder, or it does nothing.

    `--record` drives the interpretation layer's own poll clocks
    because QEMU admits one QMP client and an independent sampler
    cannot exist — so the pace is a *ceiling* on the interval, not a
    floor. Taking the larger of the two left the idle poll at its
    production 2.0s, which is the two-second hole through most of an
    install that the whole mechanism exists to close: the first real
    capture held 536 samples across five and a half minutes.
    """
    recorded = _poll_gaps(tmp_path, record_pace=0.25)
    assert max(recorded) <= 0.25, (
        f"a run recording at 0.25s slept {max(recorded)}s between "
        "samples, so the transcript has holes the pace promised to fill")
    assert max(_poll_gaps(tmp_path / "plain")) > 0.25, (
        "and an unrecorded run keeps its cheap production cadence")


def test_a_recorded_run_names_the_script_in_its_header(tmp_path):
    """A capture says what it is a capture of, and against which text.

    The corpus replays a fixture by standing the same script back up
    over it, so the file has to carry which script that was — nothing
    else in the directory knows. The digest is the other half: a
    script edited since the capture was taken diverges partway
    through, and naming the staleness beats a keystroke mismatch
    reported from the middle of a run.
    """
    home = str(tmp_path)
    machine_home = os.path.join(home, "machine")
    os.makedirs(machine_home)
    text = 'platform dos\nentry only\nphase only {\n    finish\n}\n'
    script_path = os.path.join(home, "demo.rlqs")
    # Written as bytes, because the digest is over the file's bytes
    # and a text-mode write on Windows would not be the same ones.
    with open(script_path, "wb") as handle:
        handle.write(text.encode())
    target = os.path.join(home, "run.rlqt")
    with mock.patch("reliquary.script_runner._machines") as machines:
        machines.load_machine_state.return_value = {"phase": "running"}
        machines.machine_dir_path.return_value = machine_home
        machines.read_vm_state.return_value = {
            "backend": "qemu", "backend-id": "reliquary-freedos-0",
            "token": "0" * 32, "endpoint": {"port": 5555}}
        execute_script(parse_script(text), machine_id="freedos-0",
                       context=home, script_path=script_path,
                       record=target)
    header = _entries(target)[0]
    assert header["script"] == "demo"
    assert header["script-sha256"] == hashlib.sha256(
        text.encode()).hexdigest()


def test_a_recorded_run_states_what_it_concluded(tmp_path):
    """The half a capture cannot show, said once at the end.

    Two runs over the same screens — one that reached its `finish`,
    one that expired waiting — make the same carrier calls, so the
    file is the same file and only the conclusion differs. A replay
    is asserted against this, which is what makes a capture of a run
    that failed a fixture like any other.
    """
    home = str(tmp_path)
    machine_home = os.path.join(home, "machine")
    os.makedirs(machine_home)
    text = ('platform dos\nentry only\nphase only {\n'
            '    finish\n}\n')
    script_path = os.path.join(home, "demo.rlqs")
    with open(script_path, "wb") as handle:
        handle.write(text.encode())
    target = os.path.join(home, "run.rlqt")
    with mock.patch("reliquary.script_runner._machines") as machines:
        machines.load_machine_state.return_value = {"phase": "running"}
        machines.machine_dir_path.return_value = machine_home
        machines.read_vm_state.return_value = {
            "backend": "qemu", "backend-id": "reliquary-freedos-0",
            "token": "0" * 32, "endpoint": {"port": 5555}}
        execute_script(parse_script(text), machine_id="freedos-0",
                       context=home, script_path=script_path,
                       record=target)
    trailer = _entries(target)[-1]
    assert trailer["type"] == "outcome"
    assert trailer["result"] == "ok"
    assert trailer["phase"] == "only"


def _recording_engine(tmp_path, script_text):
    """An engine over a running machine, recording to its own file.

    Driven a verb at a time rather than through `run()`, following the
    sibling test above: what is under test is which handle a carrier
    call goes through, and the lifecycle around it says nothing about
    that.
    """
    home = str(tmp_path)
    machine_home = os.path.join(home, "machine")
    os.makedirs(machine_home)
    with open(os.path.join(machine_home, "machine.json"), "w",
              encoding="utf-8") as handle:
        json.dump({"id": "freedos-0", "phase": "running",
                   "vm": {"backend": "qemu",
                          "backend-id": "reliquary-freedos-0",
                          "token": "0" * 32,
                          "endpoint": {"port": 5555}}}, handle)
    target = os.path.join(home, "run.rlqt")
    writer = _TranscriptWriter(target, pace=0.05)
    writer.open()
    script = parse_script(script_text)
    engine = _ScriptEngine(script, "freedos-0", home, machine_home,
                           script_path="/tmp/demo.rlqs", record_pace=0.05,
                           recording_writer=writer)
    engine._running = True
    return engine, script, writer, target


def _entries(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_the_screenshot_verb_records_its_carrier_call(tmp_path):
    """A screenshot is a carrier call, so the transcript carries it.

    `screenshot` built its own `Machine` and so never got the
    recording wrapper the console is given, which made it the one
    carrier call a capture silently dropped — and both codex scripts
    take one, so it was every capture. A replay then meets a call the
    transcript cannot answer.
    """
    engine, script, writer, target = _recording_engine(
        tmp_path,
        'platform dos\nentry only\nphase only {\n'
        '    screenshot installed\n'
        '    finish\n}\n')
    with fake_backend.installed():
        engine._screenshot(script.phases[0].statements[0])
    writer.close()
    carriers = [entry.get("carrier") for entry in _entries(target)]
    assert "screenshot" in carriers, (
        "the guest framebuffer was captured and the transcript holds "
        "no screenshot call, so the verb bypassed the recorder.")


def test_a_vanished_vm_is_recorded_as_the_carrier_going_away(tmp_path):
    """The moment the machine stops is the seam's, and it is recorded.

    Identity is verified while the session is being opened, so an
    unreachable VM raises *before* the recording wrapper exists and
    the seam cannot record its own disappearance. Both codex scripts
    end on `wait machine=stopped`, which is answered by exactly this
    failure — a capture that loses it is one no replay can finish.
    """
    engine, _script, writer, target = _recording_engine(
        tmp_path, 'platform dos\nentry only\nphase only {\n'
                  '    finish\n}\n')
    gone = PreflightError("the recorded VM is not reachable",
                          rule_id="machine.vm-unreachable")
    with fake_backend.installed() as adapter:
        adapter.session_error = gone
        with pytest.raises(PreflightError):
            with engine._console():
                pass
    writer.close()
    kinds = [entry.get("type") for entry in _entries(target)]
    assert "vm-gone" in kinds, (
        "the console could not be opened because the machine had "
        "powered itself off, and the transcript says nothing about it.")
