# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the run event stream and its live renderings."""

import io
import json
import os
import re
import unittest

from reliquary import events, progress
from reliquary.errors import StaticError

_PACKAGE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "reliquary")
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


class KindVocabularyTests(unittest.TestCase):
    """The declared vocabulary is the emitted vocabulary.

    P24's inventory pass over the recorded outputs. The script spec
    lists the stream's minimum vocabulary in prose rather than as a
    table of names, so there is no set to diff the constants
    against; what *is* checkable is the claim underneath the list —
    that the stream carries these kinds. A constant nothing emits
    is vocabulary the surface advertises and never produces, which
    a consumer written against it would wait for forever.

    It found `screen.read` on 2026-07-27: declared, given a
    rendering arm, emitted by nothing, and specified in present
    tense as "emitted by the `screen` command" — which has no
    stream to emit into, only `run-script` and `fetch-media`
    carrying `--progress` at all. It is now spec-reserved and
    carries no constant, which is the rule the spec now states and
    `KINDS` embodies.

    **How emission is measured, and its limit**: a kind counts as
    emitted when a module other than `events` or `progress`
    references its constant. Referencing a kind outside the
    renderer is only ever done to emit it, but this measures
    reachability rather than a literal call — `script_runner`
    emits through one `emit(kind, **fields)` helper, so no
    call-site analysis could see the kinds its callers pass in.

    The converse — "renderers may omit what the stream carries;
    they may never add to it" — gets no test here because it needs
    none: `describe` dispatches on the constants themselves, so a
    kind it could invent would have to be declared first, and
    `test_kinds_lists_every_declared_constant` is where that
    fails. A test that cannot fail is worse than an absent one.
    """

    def _referenced_outside(self, *exclude):
        found = set()
        for name in sorted(os.listdir(_PACKAGE)):
            if not name.endswith(".py") or name[:-3] in exclude:
                continue
            with open(os.path.join(_PACKAGE, name),
                      encoding="utf-8") as handle:
                found.update(_KIND_REFERENCE.findall(handle.read()))
        return {getattr(events, name) for name in found
                if isinstance(getattr(events, name, None), str)}

    def test_kinds_lists_every_declared_constant(self):
        declared = {value for name, value in vars(events).items()
                    if name.isupper() and not name.startswith("_")
                    and isinstance(value, str)}
        self.assertEqual(
            declared, set(events.KINDS),
            "KINDS is the stream's declared vocabulary and the set the "
            "checks below compare against; a kind constant outside it "
            "is invisible to them.")

    def test_every_declared_kind_is_emitted(self):
        unemitted = sorted(set(events.KINDS)
                           - self._referenced_outside("events", "progress"))
        self.assertEqual(
            unemitted, [],
            f"{unemitted} are declared and emitted by nothing. The "
            "stream is the one place every surface reports through, so "
            "a kind it never carries is a promise to consumers that "
            "cannot come true; a designed-but-unbuilt kind is reserved "
            "in docs/spec/script-spec.md and gets no constant.")


class EventEnvelopeTests(unittest.TestCase):
    def test_every_event_carries_the_envelope(self):
        clock = _Clock()
        stream = events.EventStream(clock=clock)
        clock.now = 2.5
        stream.emit(events.RUN_START, script="demo.rlqs")
        document = stream.events[0]
        self.assertEqual(document["seq"], 1)
        self.assertEqual(document["kind"], events.RUN_START)
        self.assertEqual(document["elapsed"], 2.5)
        self.assertEqual(document["script"], "demo.rlqs")
        self.assertRegex(
            document["time"],
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

    def test_sequence_numbers_are_dense_and_ordered(self):
        stream = events.EventStream()
        for index in range(4):
            stream.emit(events.ACTION_START, verb="press", detail=index)
        self.assertEqual([event["seq"] for event in stream.events],
                         [1, 2, 3, 4])

    def test_absent_fields_are_dropped(self):
        stream = events.EventStream()
        stream.emit(events.ACTION_START, verb="start", detail=None)
        self.assertNotIn("detail", stream.events[0])

    def test_every_event_serializes_as_one_json_line(self):
        stream = events.EventStream()
        event = stream.emit(events.RUN_END, outcome="ok")
        line = event.as_json()
        self.assertNotIn("\n", line)
        self.assertEqual(json.loads(line)["outcome"], "ok")

    def test_redaction_reaches_nested_values(self):
        stream = events.EventStream(
            redact=lambda text: text.replace("swordfish", "X"))
        stream.emit(events.ACTION_START, verb="type",
                    detail="swordfish", rows=["a swordfish b"],
                    nested={"k": "swordfish"})
        document = stream.events[0]
        self.assertEqual(document["detail"], "X")
        self.assertEqual(document["rows"], ["a X b"])
        self.assertEqual(document["nested"], {"k": "X"})

    def test_ticks_render_but_are_never_recorded(self):
        sink = _Recorder()
        stream = events.EventStream(sink)
        stream.tick(description="wait", elapsed=1.0, limit=10.0)
        stream.emit(events.RUN_END, outcome="ok")
        self.assertEqual(len(sink.ticks), 1)
        self.assertEqual([e["kind"] for e in stream.events],
                         [events.RUN_END])


class NoteTests(unittest.TestCase):
    """Media movement is honest with a stream and without one."""

    def test_a_note_becomes_an_event_when_a_stream_exists(self):
        stream = events.EventStream()
        events.note(stream, events.TRANSFER_START, "downloading x",
                    name="x", source="http://example/x")
        document = stream.events[0]
        self.assertEqual(document["kind"], events.TRANSFER_START)
        self.assertEqual(document["message"], "downloading x")
        self.assertEqual(document["name"], "x")


class ResolveModeTests(unittest.TestCase):
    def test_auto_resolves_by_the_rendering_stream(self):
        class _Tty(io.StringIO):
            def isatty(self):
                return True

        self.assertEqual(
            progress.resolve_mode("auto", stream=_Tty()), "pretty")
        self.assertEqual(
            progress.resolve_mode("auto", stream=io.StringIO()), "plain")

    def test_an_unknown_mode_is_refused(self):
        with self.assertRaises(StaticError) as caught:
            progress.resolve_mode("fancy")
        self.assertIn("auto, pretty, plain, jsonl", str(caught.exception))

    def test_plain_and_jsonl_never_prompt(self):
        self.assertFalse(progress.interactive("plain"))
        self.assertFalse(progress.interactive("jsonl"))
        self.assertTrue(progress.interactive("pretty"))


class JsonlRendererTests(unittest.TestCase):
    """stdout carries the event stream and nothing else."""

    def test_stdout_is_one_json_line_per_event(self):
        out, err = io.StringIO(), io.StringIO()
        stream = progress.stream_for("jsonl", out=out, err=err)
        stream.emit(events.RUN_START, script="demo.rlqs")
        stream.tick(description="wait", elapsed=1.0, limit=5.0)
        stream.emit(events.RUN_END, outcome="ok")
        stream.close()
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        documents = [json.loads(line) for line in lines]
        self.assertEqual(documents[0]["kind"], events.RUN_START)
        # The terminal event is last: it is the machine-readable
        # result, and there is no separate result mode.
        self.assertEqual(documents[-1]["kind"], events.RUN_END)
        self.assertEqual(err.getvalue(), "")


class HumanRendererTests(unittest.TestCase):
    """The human modes render everything to stderr."""

    def test_plain_writes_lines_to_stderr_and_leaves_stdout_empty(self):
        out, err = io.StringIO(), io.StringIO()
        stream = progress.stream_for("plain", out=out, err=err)
        stream.emit(events.RUN_START, script="demo.rlqs",
                    machine="plain-0")
        stream.emit(events.OBSERVATION_ARM, description="'Welcome'",
                    timeout=30.0, line=4)
        stream.emit(events.RUN_END, outcome="ok")
        stream.close()
        self.assertEqual(out.getvalue(), "")
        text = err.getvalue()
        self.assertIn("run demo.rlqs on machine plain-0", text)
        self.assertIn("line 4: wait 'Welcome'", text)
        self.assertIn("run complete", text)

    def test_plain_heartbeats_rather_than_flooding(self):
        err = io.StringIO()
        renderer = progress.PlainRenderer(err, interval=5.0)
        for elapsed in (0.0, 1.0, 2.0, 6.0):
            renderer.tick(description="wait", elapsed=elapsed, limit=30.0,
                          phase="install", step=2)
        lines = err.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        # Elapsed against its limit -- never an invented progress bar.
        self.assertIn("[install] step 2 wait  0s / 30s", lines[0])
        self.assertNotIn("#", err.getvalue())

    def test_plain_emits_no_ansi(self):
        err = io.StringIO()
        renderer = progress.PlainRenderer(err)
        renderer.event(events.Event(1, "t", 0.0, events.FAILURE,
                                    {"error": "boom"}))
        self.assertNotIn("\033", err.getvalue())

    def test_a_failure_report_names_what_the_run_knew(self):
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
            self.assertIn(expected, text)

    def test_a_transfer_shows_a_total_only_when_one_is_named(self):
        with_total = progress.describe(events.Event(
            1, "t", 0.0, events.TRANSFER_PROGRESS,
            {"name": "iso", "transferred": 1024, "total": 4096}))
        without = progress.describe(events.Event(
            2, "t", 0.0, events.TRANSFER_PROGRESS,
            {"name": "iso", "transferred": 1024}))
        self.assertIn("/", with_total)
        self.assertNotIn("/", without)


if __name__ == "__main__":
    unittest.main()
