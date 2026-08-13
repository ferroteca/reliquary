# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The command surfaces against the command manifest.

The manifest — ``src/reliquary/schemas/command-manifest.toml``,
shipped in the package — is the normative inventory of the command
surfaces (P6): each capability declared once, the dash-separated
CLI word and the underscored Session twin both derived from the
one name, so the twin rule is the artifact's shape rather than a
checked convention. These tests hold the code to it in all four
directions: everything declared ships both faces, every registered
command is declared, every public name is classified, and nothing
declared or classified is absent.

**Every declared capability is a collected node named for itself**,
so a twin that stops shipping fails as `[create-machine]` rather than
as one method reporting for all thirty-seven (F60).

The classification is what makes the reverse half of P6 — "no
capability is unreachable from the CLI" — mechanical for the first
time. The judgment (is ``resolve_machine`` legitimately not a
command?) happened once, in the governed edit that classified it;
here it is only membership. A new export or session method cannot
arrive unclassified, and an exception whose gap has since closed
fails as stale rather than lingering as a quiet carve-out.

The manifest is the norm. When these tests fail, the fix is a
surface decision, never a test edit: either the code diverged from
the declared inventory — a bug (P24) — or the inventory itself is
being changed, which is a surface change vetted under
planning/SURFACES.md before it lands (P23).
"""

import tomllib
from importlib import resources

import pytest

import reliquary
from reliquary import Session, cli


def _manifest():
    text = (resources.files("reliquary") / "schemas"
            / "command-manifest.toml").read_text(encoding="utf-8")
    return tomllib.loads(text)


def _twin(command):
    return command.replace("-", "_")


def _family_members(manifest):
    """Every (command, api-face) pair across all families."""
    return [(command, face)
            for family in manifest["families"].values()
            for command, face in family.items()]


MANIFEST = _manifest()
TWINS = sorted(MANIFEST["twins"])
FAMILY = sorted(_family_members(MANIFEST))
EXCEPTIONS = MANIFEST["exceptions"]
EXCEPTION_IDS = [entry["name"] for entry in EXCEPTIONS]


# The artifact's own soundness: one declaration per name.

def test_each_command_is_declared_exactly_once():
    declared = (list(MANIFEST["twins"])
                + [c for c, _ in FAMILY]
                + [e["name"] for e in EXCEPTIONS])
    duplicated = sorted({name for name in declared
                         if declared.count(name) > 1})
    assert duplicated == [], (
        f"{duplicated} are declared more than once; a capability "
        "has one declaration — twin, family member, or exception, "
        "never several.")


def test_each_public_name_is_classified_exactly_once():
    classified = [name
                  for names in MANIFEST["embedding-surface"].values()
                  for name in names]
    duplicated = sorted({name for name in classified
                         if classified.count(name) > 1})
    assert duplicated == [], (
        f"{duplicated} appear in more than one embedding-surface "
        "class; the classification is a partition.")


@pytest.mark.parametrize("entry", EXCEPTIONS, ids=EXCEPTION_IDS)
def test_every_exception_is_complete(entry):
    assert entry["missing"] in {"cli", "api"}, (
        "an exception names which face is missing, and there are "
        "only two.")
    assert entry.get("reason", "").strip(), (
        "an exception without a reason is a bare parity break; the "
        "reason is what makes it a decision.")


# Declared but absent — the class the specs could not catch
# mechanically: a capability the inventory promises and the code
# never grew, or stopped shipping.

@pytest.mark.parametrize("command", TWINS)
def test_every_twin_ships_both_faces(command):
    assert command in cli._COMMANDS, (
        f"the manifest declares `{command}` and the CLI does not "
        "register it; the manifest is normative, so the missing "
        "command is the bug (P6, P24).")
    assert hasattr(Session, _twin(command)), (
        f"the manifest declares `{command}` and Session has no "
        f"`{_twin(command)}`; the manifest is normative, so the "
        "missing twin is the bug (P6, P24).")


@pytest.mark.parametrize("command,face", FAMILY,
                         ids=[command for command, _ in FAMILY])
def test_every_family_member_ships_both_faces(command, face):
    assert command in cli._COMMANDS, (
        f"the manifest maps `{command}` to `{face}` and the CLI does "
        "not register the command.")
    assert face in reliquary.__all__, (
        f"the manifest maps `{command}` to `{face}` and the package "
        "does not export that face.")


@pytest.mark.parametrize("entry", EXCEPTIONS, ids=EXCEPTION_IDS)
def test_every_exception_ships_its_present_face_only(entry):
    name, missing = entry["name"], entry["missing"]
    if missing == "api":
        assert name in cli._COMMANDS, (
            f"`{name}` is an exception missing its API face, so its "
            "CLI face must ship — it does not, which makes this "
            "entry a declaration of nothing.")
        twin = _twin(name)
        assert not (hasattr(Session, twin) or twin in reliquary.__all__), (
            f"`{name}` is declared API-less, but `{twin}` ships — the "
            "gap this exception records has closed, so the entry is "
            "stale: promote the capability to a twin or family "
            "member.")
    else:
        assert hasattr(Session, name) or name in reliquary.__all__, (
            f"`{name}` is an exception missing its CLI face, so its "
            "API face must ship — it does not.")
        assert name.replace("_", "-") not in cli._COMMANDS, (
            f"`{name}` is declared CLI-less, but the command ships — "
            "the exception is stale.")


# Shipped but undeclared — the `fetch_media` class: surface arriving
# without the inventory hearing about it.

def test_every_registered_command_is_declared():
    declared = (set(MANIFEST["twins"])
                | {c for c, _ in FAMILY}
                | {e["name"] for e in EXCEPTIONS
                   if e["missing"] == "api"})
    undeclared = sorted(set(cli._COMMANDS) - declared)
    assert undeclared == [], (
        f"{undeclared} are registered commands the manifest does "
        "not declare. Declaring a capability is a surface change: "
        "add it to command-manifest.toml under the vetting the "
        "surface rule requires (P23).")


def test_every_public_name_is_classified():
    faces = {face for _, face in FAMILY}
    classified = set().union(*MANIFEST["embedding-surface"].values())
    public = set(reliquary.__all__)
    unclassified = sorted(public - classified - faces)
    assert unclassified == [], (
        f"{unclassified} are public names the manifest neither "
        "classifies nor maps as a family face. Every export is "
        "classified — that classification is P6's reverse "
        "direction, judged once in the manifest.")
    phantom = sorted((classified | faces) - public)
    assert phantom == [], (
        f"{phantom} are classified or mapped in the manifest and no "
        "longer exported; the manifest is normative, so either the "
        "export is the bug or the entry must leave by a surface "
        "change.")


def test_every_session_method_is_accounted():
    methods = {name for name in dir(Session) if not name.startswith("_")}
    twin_methods = {_twin(c) for c in MANIFEST["twins"]}
    lifecycle = set(MANIFEST["session-lifecycle"])
    unaccounted = sorted(methods - twin_methods - lifecycle)
    assert unaccounted == [], (
        f"{unaccounted} are Session methods that are neither a "
        "declared twin nor classified session-lifecycle. A new "
        "method is a surface change: declare it in "
        "command-manifest.toml first (P6, P23).")
    phantom = sorted(lifecycle - methods)
    assert phantom == [], (
        f"{phantom} are classified session-lifecycle and Session "
        "does not have them; the manifest is normative, so the "
        "missing method is the bug — or the entry leaves by a "
        "surface change.")
