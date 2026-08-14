# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The third conformance corpus: the one nobody can author.

The blueprint and script corpora are written — a fixture states a
document and what must happen to it. This one is **captured**: the
interpretation layer is heuristic over real-world text, and a
fabricated screen encodes the same belief the heuristic does, so the
only honest input is a screen a guest actually drew
(`planning/pledged/design/screen-transcripts.md`).

**A fixture asserts by being replayable.** The transcript records both
directions at the carrier seam, and `ReplaySession` refuses a call the
capture never covered (P11), so a regression in prompt detection, echo
scanning or the menu machinery changes what the layer asks for and the
replay names it. Nothing is restated in a sidecar that could drift.

Two things this asks of every fixture beyond "it finished". The
capture's **calls must all be made** — a run that stops early replays
without error, because it simply stops asking — and the **script it
was taken against must not have moved**, which the header's digest
answers before a divergence can be reported as anything vaguer.

The fixtures are taken by the integration tier against real QEMU and
promoted by hand; `fixtures/conformance/transcript/README.md` is where
that recipe and this corpus's findings live. They reconstruct with no
hypervisor present, so they run **here**, in the default suite: a
failing capture is a defect to fix, never a skip to tolerate.
"""

import os

from reliquary.library import _builtins_root
from reliquary.script_parser import parse_script
from reliquary.transcript import script_identity
from tests import corpus, replay

ROOT = os.path.join(os.path.dirname(__file__), "fixtures", "conformance")

#: Pinned where the fixtures are gathered, so a bucket that stops
#: loading is a collection error rather than a green run over nothing.
CAPTURES = corpus.fixtures(ROOT, "transcript", ".rlqt", 2)


def _script_path(reader, fixture):
    """The script a capture was taken of, wherever that script lives.

    A codex label resolves to the shipped file rather than to a copy —
    the codex is the live, tested one and a second copy would be one
    more thing to keep in step — and anything else resolves beside the
    fixture, which is how a capture of a script written to provoke one
    misbehaviour carries it.
    """
    stem = reader.script
    assert stem, (
        f"{os.path.basename(fixture)} does not say which script it "
        "captured; a transcript recorded by `--record` carries the "
        "name in its header, so this one predates that and needs "
        "re-recording.")
    packaged = _builtins_root() / "scripts" / f"{stem}.rlqs"
    if packaged.is_file():
        return str(packaged)
    beside = os.path.join(os.path.dirname(fixture), f"{stem}.rlqs")
    assert os.path.exists(beside), (
        f"{os.path.basename(fixture)} was captured against {stem}.rlqs, "
        "which is neither in the codex nor beside the fixture.")
    return beside


@corpus.parametrize(CAPTURES)
def test_a_capture_replays_through_the_interpretation_layer(fixture,
                                                            tmp_path):
    """Stand the real layer back on a screen a real guest drew.

    `control_display`, `interaction_agentless` and the runner's
    dispatch are the shipped ones; only the carrier, the lifecycle and
    the clock are the harness's.
    """
    entries, reader = replay.read(fixture)
    script_path = _script_path(reader, fixture)
    identity = script_identity(script_path)
    assert identity.get("script_digest") == reader.script_digest, (
        f"{os.path.basename(fixture)} was captured against a different "
        f"{reader.script}.rlqs than the one in the tree today. Replaying "
        "it would report a divergence in the interpretation layer for "
        "what is really an edited script: re-record the capture.")
    with open(script_path, encoding="utf-8") as handle:
        script = parse_script(handle.read())

    home = str(tmp_path)
    machine_home = os.path.join(home, "machine")
    os.makedirs(machine_home)
    with replay.replaying(fixture) as (session, _machines, clock, header):
        engine = replay.engine_for(script, home, machine_home, clock,
                                   header)
        engine.run()

    assert engine.events.events[-1]["outcome"] == "ok", (
        "the capture is of a run that succeeded, so its replay must "
        "reach the same end")
    assert session.remaining_calls() == 0, (
        f"{session.remaining_calls()} carrier calls the capture "
        "recorded were never made: the replayed run ended early, which "
        "no error reports on its own — a run that stops asking simply "
        "stops reading.")


@corpus.parametrize(CAPTURES)
def test_a_capture_reconstructs_every_screen_it_holds(fixture):
    """Every frame rebuilds to the screen whose digest it carries.

    Cheap, and it is the format's own claim rather than the layer's:
    the reader checks each digest as it goes, so a delta chain that
    lost its footing or a hand-edited fixture fails here rather than
    surfacing as a mysterious divergence in the replay above.
    """
    entries, _reader = replay.read(fixture)
    frames = [entry for entry in entries if entry.kind == "frame"]
    assert frames, "a capture with no screens in it is not a capture"
