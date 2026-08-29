# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the run event stream and its live renderings."""

import io
import json
import os
import re

import pytest

import reliquary
from reliquary import events, progress
from reliquary.errors import StaticError

_PACKAGE = os.path.dirname(os.path.abspath(reliquary.__file__))
# Every consumer spells the module `_events` (`from . import events
# as _events`); the optional underscore keeps the plain spelling
# working too, and the uppercase tail keeps `.events.emit` out.
_KIND_REFERENCE = re.compile(r"\b_?events\.([A-Z][A-Z_]*)\b")


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class _Recorder:
    def __init__(self):
        self.events = []
        self.ticks = []
        self.cleared = 0
        self.closed = 0

    def event(self, event):
        self.events.append(event)

    def tick(self, **fields):
        self.ticks.append(fields)

    def clear(self):
        self.cleared += 1

    def close(self):
        self.closed += 1


# Every declared event kind is actually emitted somewhere.
#
# This is P24's inventory check, applied to the event stream. The
# script spec lists the stream's minimum set of event kinds in
# prose, not as a table of names, so there is no list of names to
# directly diff the code's constants against. What can be checked
# instead is the claim underneath that list — that the stream
# actually carries each of these kinds. A constant that nothing ever
# emits is a kind the docs advertise but the code never produces,
# and a consumer written to expect it would wait for it forever.
#
# This check found `screen.read` on 2026-07-27: it was declared, had
# a renderer for it, but nothing ever emitted it. The spec described
# it in present tense as "emitted by the `screen` command" — but the
# `screen` command has no stream to emit into; only `run-script` and
# `fetch-media` carry `--progress` at all. It is now spec-reserved
# instead, with no constant, which is the rule the spec states now
# and that `KINDS` embodies.
#
# **How emission is measured, and its limit**: a kind counts as
# emitted when a module other than `events` or `progress` references
# its constant. Referencing a kind outside the renderer is only ever
# done to emit it, but this measures reachability rather than a
# literal call — `script_runner` emits through one `emit(kind,
# **fields)` helper, so no call-site analysis could see the kinds its
# callers pass in.
#
# The converse — "renderers may omit what the stream carries; they
# may never add to it" — gets no test here because it needs none:
# `describe` dispatches on the constants themselves, so a kind it
# could invent would have to be declared first, and
# `test_kinds_lists_every_declared_constant` is where that fails. A
# test that cannot fail is worse than an absent one.

def _referenced_outside(*exclude):
    found = set()
    for name in sorted(os.listdir(_PACKAGE)):
        if not name.endswith(".py") or name[:-3] in exclude:
            continue
        with open(os.path.join(_PACKAGE, name), encoding="utf-8") as handle:
            found.update(_KIND_REFERENCE.findall(handle.read()))
    return {getattr(events, name) for name in found
            if isinstance(getattr(events, name, None), str)}


def test_kinds_lists_every_declared_constant():
    declared = {value for name, value in vars(events).items()
                if name.isupper() and not name.startswith("_")
                and isinstance(value, str)}
    assert declared == set(events.KINDS), (
        "KINDS is the stream's declared vocabulary and the set the "
        "checks below compare against; a kind constant outside it "
        "is invisible to them.")


def test_every_declared_kind_is_emitted():
    unemitted = sorted(set(events.KINDS)
                       - _referenced_outside("events", "progress"))
    assert unemitted == [], (
        f"{unemitted} are declared and emitted by nothing. The "
        "stream is the one place every surface reports through, so "
        "a kind it never carries is a promise to consumers that "
        "cannot come true; a designed-but-unbuilt kind is reserved "
        "in docs/spec/script-spec.md and gets no constant.")


# The event envelope.

def test_every_event_carries_the_envelope():
    clock = _Clock()
    stream = events.EventStream(clock=clock)
    clock.now = 2.5
    stream.emit(events.RUN_START, script="demo.rlqs")
    document = stream.events[0]
    assert document["seq"] == 1
    assert document["kind"] == events.RUN_START
    assert document["elapsed"] == 2.5
    assert document["script"] == "demo.rlqs"
    assert re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$", document["time"])


def test_sequence_numbers_are_dense_and_ordered():
    stream = events.EventStream()
    for index in range(4):
        stream.emit(events.ACTION_START, verb="press", detail=index)
    assert [event["seq"] for event in stream.events] == [1, 2, 3, 4]


def test_absent_fields_are_dropped():
    stream = events.EventStream()
    stream.emit(events.ACTION_START, verb="start", detail=None)
    assert "detail" not in stream.events[0]


def test_every_event_serializes_as_one_json_line():
    stream = events.EventStream()
    event = stream.emit(events.RUN_END, outcome="ok")
    line = event.as_json()
    assert "\n" not in line
    assert json.loads(line)["outcome"] == "ok"


def test_redaction_reaches_nested_values():
    stream = events.EventStream(
        redact=lambda text: text.replace("swordfish", "X"))
    stream.emit(events.ACTION_START, verb="type",
                detail="swordfish", rows=["a swordfish b"],
                nested={"k": "swordfish"})
    document = stream.events[0]
    assert document["detail"] == "X"
    assert document["rows"] == ["a X b"]
    assert document["nested"] == {"k": "X"}


def test_ticks_render_but_are_never_recorded():
    sink = _Recorder()
    stream = events.EventStream(sink)
    stream.tick(description="wait", elapsed=1.0, limit=10.0)
    stream.emit(events.RUN_END, outcome="ok")
    assert len(sink.ticks) == 1
    assert [e["kind"] for e in stream.events] == [events.RUN_END]


# Media-transfer notifications work whether a stream exists or not.

def test_a_note_becomes_an_event_when_a_stream_exists():
    stream = events.EventStream()
    events.note(stream, events.TRANSFER_START, "downloading x",
                name="x", source="http://example/x")
    document = stream.events[0]
    assert document["kind"] == events.TRANSFER_START
    assert document["message"] == "downloading x"
    assert document["name"] == "x"


# Resolving the rendering mode.

def test_auto_resolves_by_the_rendering_stream():
    class _Tty(io.StringIO):
        def isatty(self):
            return True

    assert progress.resolve_mode("auto", stream=_Tty()) == "pretty"
    assert progress.resolve_mode("auto", stream=io.StringIO()) == "plain"


def test_an_unknown_mode_is_refused():
    with pytest.raises(StaticError) as caught:
        progress.resolve_mode("fancy")
    assert "auto, pretty, plain, jsonl" in str(caught.value)


def test_plain_and_jsonl_never_prompt():
    assert not progress.interactive("plain")
    assert not progress.interactive("jsonl")
    assert progress.interactive("pretty")


# stdout carries the event stream and nothing else.

def test_stdout_is_one_json_line_per_event():
    out, err = io.StringIO(), io.StringIO()
    stream = progress.stream_for("jsonl", out=out, err=err)
    stream.emit(events.RUN_START, script="demo.rlqs")
    stream.tick(description="wait", elapsed=1.0, limit=5.0)
    stream.emit(events.RUN_END, outcome="ok")
    stream.close()
    lines = out.getvalue().splitlines()
    assert len(lines) == 2
    documents = [json.loads(line) for line in lines]
    assert documents[0]["kind"] == events.RUN_START
    # The terminal event is last: it is the machine-readable
    # result, and there is no separate result mode.
    assert documents[-1]["kind"] == events.RUN_END
    assert err.getvalue() == ""


# The human modes render everything to stderr.

def test_plain_writes_lines_to_stderr_and_leaves_stdout_empty():
    out, err = io.StringIO(), io.StringIO()
    stream = progress.stream_for("plain", out=out, err=err)
    stream.emit(events.RUN_START, script="demo.rlqs", machine="plain-0")
    stream.emit(events.OBSERVATION_ARM, description="'Welcome'",
                timeout=30.0, line=4)
    stream.emit(events.RUN_END, outcome="ok")
    stream.close()
    assert out.getvalue() == ""
    text = err.getvalue()
    assert "run demo.rlqs on machine plain-0" in text
    assert "line 4: wait 'Welcome'" in text
    assert "run complete" in text


def test_plain_heartbeats_rather_than_flooding():
    err = io.StringIO()
    renderer = progress.PlainRenderer(err, interval=5.0)
    for elapsed in (0.0, 1.0, 2.0, 6.0):
        renderer.tick(description="wait", elapsed=elapsed, limit=30.0,
                      phase="install", step=2)
    lines = err.getvalue().splitlines()
    assert len(lines) == 2
    # Elapsed against its limit -- never an invented progress bar.
    assert "[install] step 2 wait  0s / 30s" in lines[0]
    assert "#" not in err.getvalue()


def test_plain_emits_no_ansi():
    err = io.StringIO()
    renderer = progress.PlainRenderer(err)
    renderer.event(events.Event(1, "t", 0.0, events.FAILURE,
                                {"error": "boom"}))
    assert "\033" not in err.getvalue()


def test_a_failure_report_names_what_the_run_knew():
    err = io.StringIO()
    renderer = progress.PlainRenderer(err)
    renderer.event(events.Event(
        1, "t", 0.0, events.FAILURE,
        {"error": "timed out", "pending": "'Welcome'",
         "clock": "the observation timeout of 30s",
         "scope": "header (line 2)",
         "route": ("boot", "install", "boot"),
         "revisits": {"boot": 2},
         "nearest-miss": "Welcom",
         "screenshot": "/tmp/failure.png",
         "next-command": "rlq screen --machine plain-0"}))
    text = err.getvalue()
    for expected in ("timed out", "pending: 'Welcome'",
                     "the observation timeout of 30s",
                     "scope: header (line 2)",
                     "boot -> install -> boot", "boot x2",
                     "nearest miss: Welcom", "/tmp/failure.png",
                     "rlq screen --machine plain-0"):
        assert expected in text


def test_a_transfer_shows_a_total_only_when_one_is_named():
    with_total = progress.describe(events.Event(
        1, "t", 0.0, events.TRANSFER_PROGRESS,
        {"name": "iso", "transferred": 1024, "total": 4096}))
    without = progress.describe(events.Event(
        2, "t", 0.0, events.TRANSFER_PROGRESS,
        {"name": "iso", "transferred": 1024}))
    assert "/" in with_total
    assert "/" not in without
