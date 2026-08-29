# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for dry runs: what a create or run-script would do, without doing any of it.

Two things must always hold, and are tested directly first: a dry
run leaves no state on disk, and it returns a DryRun object, not a
machine id or an actual run result. Everything else in this module
checks that what a dry run predicts matches what a real create or
run then actually does — the only thing that makes a plan worth
reading.
"""

import contextlib
import dataclasses
import hashlib
import io
import json
import os
from unittest import mock

import pytest

import reliquary
from reliquary import backends, cli
from reliquary.backends import Capabilities
from reliquary.errors import PreflightError, StaticError
from reliquary.home import Context
from reliquary.library import seed_blueprint
from reliquary.machines import DryRun, create_machine, load_machine_state
from reliquary.script_nodes import RULE_OF, ScriptParseError
from reliquary.script_parser import load_script, parse_script
from reliquary.script_runner import run_script
from reliquary.script_timing import format_plan, resolve as resolve_timing
from reliquary.script_validation import reach
from tests import fake_backend

#: The payload the remote media's sha256 field pins, and its hash. A
#: real create finds this payload already in the cache, so it's a
#: cache hit rather than a download; a dry run with an empty cache
#: still reports `would-download`, which is the state this module
#: tests.
TOOLS = b"TOOLS-PAYLOAD"
TOOLS_SHA = hashlib.sha256(TOOLS).hexdigest()


def _no_network():
    """A real create in these tests must never reach the network.

    Every fixture with a remote media pairs it with a cached payload
    or is not created for real; this makes a slip loud rather than
    slow.
    """
    return mock.patch("reliquary.acquire._download",
                      side_effect=AssertionError(
                          "a test create tried to download"))


class _Dry:
    """One dry-run case: its home, its blueprints, and its backends."""

    def __init__(self, home, backend, stack):
        self.home = home
        self.backend = backend
        self.stack = stack
        self.iso_path = os.path.join(home, "live.iso")
        with open(self.iso_path, "wb") as handle:
            handle.write(b"ISO-CONTENT")

    def write(self, name, machine, media=None):
        specs = [dict(machine, type="machine", name=name)]
        specs.extend(dict(spec, type="media") for spec in (media or ()))
        bpdir = os.path.join(self.home, "blueprints")
        os.makedirs(bpdir, exist_ok=True)
        with open(os.path.join(bpdir, f"{name}.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump(specs, handle)

    def livecd(self):
        return {"name": "livecd", "materialize": "use",
                "read-only": True, "location": {"local": self.iso_path}}

    def remote(self):
        return {"name": "tools", "materialize": "use",
                "sha256": TOOLS_SHA,
                "location": "https://example.invalid/tools.img"}

    def cache_tools(self):
        """Put the pinned payload in the cache, so a create hits it."""
        cache = os.path.join(self.home, "cache", "media")
        os.makedirs(cache, exist_ok=True)
        with open(os.path.join(cache, "tools.img"), "wb") as handle:
            handle.write(TOOLS)

    def mixed(self):
        """A machine touching every materialization path at once."""
        return {
            "platform": "dos",
            "drives": {
                "hdd0": {"type": "media", "size": "20M"},
                "cdrom0": "livecd",
                "floppy0": "tools",
                "floppy1": None,
            },
        }

    def write_mixed(self, name="demo"):
        self.write(name, self.mixed(), [self.livecd(), self.remote()])

    def tree(self):
        """Every path under the home, relative and sorted."""
        found = []
        for root, dirs, files in os.walk(self.home):
            for name in list(dirs) + list(files):
                found.append(os.path.relpath(
                    os.path.join(root, name), self.home))
        return sorted(found)

    def media(self, result, name):
        for entry in result.plan["media"]:
            if entry["name"] == name:
                return entry
        raise AssertionError(f"no media entry for {name!r} in "
                             f"{result.plan['media']}")

    def install(self, name, *, available, capabilities=None):
        return self.stack.enter_context(fake_backend.installed(
            name=name, available=available, capabilities=capabilities))

    def run(self, name="demo", **kwargs):
        return create_machine(name, context=self.home, dry_run=True,
                              **kwargs)


@pytest.fixture
def dry(tmp_path):
    with contextlib.ExitStack() as stack:
        backend = stack.enter_context(fake_backend.installed())
        yield _Dry(str(tmp_path), backend, stack)


# The first invariant, asserted against the disk itself.

def test_a_dry_run_writes_nothing_at_all(dry):
    dry.write_mixed()
    before = dry.tree()
    result = dry.run()
    assert before == dry.tree()
    # Named individually too: the tree comparison would pass if
    # the walk itself were broken, and these are the four things
    # a create writes.
    for leftover in ("cache", os.path.join("cache", "machines"),
                     os.path.join("cache", "media"),
                     os.path.join("cache", "machines", ".locks")):
        assert not os.path.exists(os.path.join(dry.home, leftover)), (
            f"a dry run created {leftover}")
    assert result.plan["machine"] == "demo-0"


def test_it_materializes_no_image(dry):
    dry.write_mixed()
    dry.run()
    assert dry.backend.images == []


def test_a_codex_blueprint_is_refused_rather_than_read(dry):
    # This test used to check the opposite: create_machine seeded a
    # codex blueprint the first time it was referenced, and a dry
    # run read the codex blueprint directly instead of seeding it.
    # Neither happens now (D88) — the blueprints directory is the
    # only source of blueprints — so a dry run still writes nothing,
    # but it now refuses more cases than it used to.
    context = Context(home_dir=dry.home)
    with pytest.raises(PreflightError) as caught:
        create_machine("freedos", context=context, dry_run=True)
    assert "rlq seed-blueprint freedos" in str(caught.value)
    assert not os.path.exists(os.path.join(dry.home, "blueprints")), (
        "a refused dry run wrote a blueprints directory")


def test_nothing_is_hashed(dry):
    # `cached` means the file is present, not that it's the right
    # file — checking that is a separate, later --dry-run=verify
    # step, because hashing a LiveCD takes real time.
    dry.write_mixed()
    cache = os.path.join(dry.home, "cache", "media")
    os.makedirs(cache)
    with open(os.path.join(cache, "tools.img"), "wb") as handle:
        handle.write(b"NOT-THE-PINNED-PAYLOAD")
    entry = dry.media(dry.run(), "tools")
    assert entry["state"] == "cached"


# The second invariant: no caller can mistake one for the other.

def test_a_dry_create_returns_a_dry_run_not_a_machine_id(dry):
    dry.write_mixed()
    result = dry.run()
    assert isinstance(result, DryRun)
    assert not isinstance(result, str)
    assert result.operation == "create-machine"


def test_a_real_create_still_returns_the_id(dry):
    dry.write_mixed()
    dry.cache_tools()
    with _no_network():
        machine_id = create_machine("demo", context=dry.home)
    assert machine_id == "demo-0"


def test_the_document_serializes_whole(dry):
    # --json prints exactly what dry.run() returns, so that result
    # has to survive json.dumps with nothing dropped.
    dry.write_mixed()
    document = dataclasses.asdict(dry.run())
    round_tripped = json.loads(json.dumps(document))
    assert document["plan"]["machine"] == round_tripped["plan"]["machine"]
    assert "nothing was created." in round_tripped["report"]


# A plan is worth reading only if the create then matches it.

def test_the_plan_is_what_the_create_writes(dry):
    dry.write_mixed()
    plan = dry.run().plan
    dry.cache_tools()
    with _no_network():
        machine_id = create_machine("demo", context=dry.home)
    state = load_machine_state(machine_id, dry.home)

    assert plan["machine"] == machine_id
    assert plan["backend"] == state["backend"]
    assert plan["platform"] == state["platform"]
    assert plan["memory"] == state["memory"]
    assert plan["cpus"] == state["cpus"]
    assert plan["boot"] == state["boot"]
    assert plan["control-planes"] == state["control-planes"]

    predicted = {drive["key"]: drive for drive in plan["drives"]}
    assert sorted(predicted) == sorted(state["drives"])
    for key, built in state["drives"].items():
        for field in ("medium", "slot", "controller", "media",
                      "materialize", "size", "path"):
            if field not in built:
                continue
            assert built[field] == predicted[key].get(field), (
                f"drive {key} field {field} was mispredicted")


def test_the_predicted_number_is_the_lowest_free(dry):
    dry.write_mixed()
    dry.cache_tools()
    with _no_network():
        create_machine("demo", context=dry.home)
    plan = dry.run().plan
    assert plan["machine"] == "demo-1"
    assert plan["machine-number"] == "lowest free"


def test_a_pinned_number_that_exists_is_refused(dry):
    dry.write_mixed()
    dry.cache_tools()
    with _no_network():
        create_machine("demo", context=dry.home)
    with pytest.raises(PreflightError) as caught:
        dry.run(number=0)
    assert caught.value.rule_id == "machine.already-exists"


# Media: resolved, never fetched — and each state named honestly.

def test_a_local_payload_is_present_where_it_lies(dry):
    dry.write_mixed()
    entry = dry.media(dry.run(), "livecd")
    assert entry["state"] == "local-present"
    assert entry["path"] == dry.iso_path
    assert entry["size"] == len(b"ISO-CONTENT")


def test_an_uncached_remote_would_download(dry):
    dry.write_mixed()
    entry = dry.media(dry.run(), "tools")
    assert entry["state"] == "would-download"
    assert entry["source"] == "https://example.invalid/tools.img"
    assert entry["sha256"] == TOOLS_SHA
    # No "size" field: nothing on this host knows the size of an
    # unfetched remote payload. "size" appears only where something
    # does know it.
    assert "size" not in entry


def test_a_missing_local_payload_refuses_naming_every_one(dry):
    gone = os.path.join(dry.home, "gone.img")
    away = os.path.join(dry.home, "away.img")
    dry.write("demo", {
        "platform": "dos",
        "drives": {"hdd0": "one", "floppy0": "two"},
    }, [
        {"name": "one", "materialize": "use",
         "location": {"local": gone}},
        {"name": "two", "materialize": "use",
         "location": {"local": away}},
    ])
    with pytest.raises(PreflightError) as caught:
        dry.run()
    message = str(caught.value)
    assert caught.value.rule_id == "media.file-missing"
    # Both at once: a validator that stops at the first fault
    # costs a fix-and-rerun for each of them.
    assert "'one'" in message
    assert "'two'" in message


def test_a_container_child_names_the_download_behind_it(dry):
    dry.write("demo", {
        "platform": "dos",
        "drives": {"cdrom0": "inner"},
    }, [
        {"name": "outer", "sha256": "1" * 64,
         "location": "https://example.invalid/bundle.zip",
         "children": [{"type": "media", "name": "inner",
                       "path": "DISC.iso", "read-only": True,
                       "sha256": "2" * 64}]},
    ])
    plan = dry.run().plan
    states = {entry["name"]: entry["state"] for entry in plan["media"]}
    assert states["inner"] == "would-extract"
    assert states["outer"] == "would-download"


def test_a_cached_container_hides_the_download_behind_it(dry):
    # This mirrors how `prune-media` decides what it can reclaim: a
    # container is only fetched while its child is still missing, so
    # once the child is cached, the plan reports no download for the
    # container either.
    dry.write("demo", {
        "platform": "dos",
        "drives": {"cdrom0": "inner"},
    }, [
        {"name": "outer", "sha256": "1" * 64,
         "location": "https://example.invalid/bundle.zip",
         "children": [{"type": "media", "name": "inner",
                       "path": "DISC.iso", "read-only": True,
                       "sha256": "2" * 64}]},
    ])
    cache = os.path.join(dry.home, "cache", "media")
    os.makedirs(cache)
    with open(os.path.join(cache, "inner.iso"), "wb") as handle:
        handle.write(b"DISC")
    names = [entry["name"] for entry in dry.run().plan["media"]]
    assert names == ["inner"]


# A location nothing answers is reported, never asked for.

_VENDOR_MACHINE = {"platform": "dos", "drives": {"cdrom0": "vendor"}}
_VENDOR_MEDIA = [{"name": "vendor", "materialize": "use",
                  "read-only": True, "location": "${license-iso}"}]


def test_an_unbound_location_is_reported_unevaluated(dry):
    dry.write("demo", _VENDOR_MACHINE, _VENDOR_MEDIA)
    plan = dry.run().plan
    entry, = plan["media"]
    assert entry["state"] == "unbound"
    assert entry["needs"] == ["license-iso"]
    assert entry["path"] is None
    # And the report says what a real create would have done
    # about it, which is ask.
    assert plan["properties"]["license-iso"] == "interactive ask"


def test_a_bound_location_resolves_all_the_way(dry):
    dry.write("demo", _VENDOR_MACHINE, _VENDOR_MEDIA)
    plan = dry.run(properties={"license-iso": dry.iso_path}).plan
    entry, = plan["media"]
    assert entry["state"] == "local-present"
    assert entry["path"] == dry.iso_path
    assert plan["properties"]["license-iso"] == "--property"


# --backend can name a backend not installed on this host, so what
# decides whether the dry run accepts it is capability, not
# availability.

def test_an_absent_but_capable_backend_answers_yes(dry):
    dry.write_mixed()
    dry.install("vmware", available=False)
    plan = dry.run(backend="vmware").plan
    assert plan["backend"] == "vmware"
    assert plan["backend-source"] == "--backend"
    assert not plan["backend-available"]
    assert "no vmware on this host" in plan["backend-detail"]


def test_an_incapable_backend_is_refused_by_name(dry):
    dry.write_mixed()
    dry.install("vmware", available=True,
                capabilities=Capabilities(backend="vmware"))
    with pytest.raises(PreflightError) as caught:
        dry.run(backend="vmware")
    assert caught.value.rule_id == "machine.backend-incapable"
    assert "cdrom drives" in str(caught.value)


def test_an_unknown_backend_is_refused(dry):
    dry.write_mixed()
    with pytest.raises(StaticError) as caught:
        dry.run(backend="parallels")
    assert caught.value.rule_id == "machine.backend-unknown"


def test_backend_overrides_the_blueprint_field(dry):
    machine = dict(dry.mixed(), backend="qemu")
    dry.write("demo", machine, [dry.livecd(), dry.remote()])
    # Without --backend, the blueprint's declared backend wins.
    assert dry.run().plan["backend-source"] == "declared"
    assert dry.run().plan["backend"] == "qemu"
    # --backend overrides that, pinning which backend gets assigned.
    dry.install("vmware", available=True,
                capabilities=Capabilities(
                    backend="vmware",
                    control_planes=("agentless-display",),
                    media=("floppy", "hdd", "cdrom"),
                    controllers=("ide",),
                    materialize=("new", "use"),
                    pointing_devices=("tablet", "mouse")))
    plan = dry.run(backend="vmware").plan
    assert plan["backend"] == "vmware"
    assert plan["backend-source"] == "--backend"


def test_without_the_flag_assignment_still_needs_availability(dry):
    # --backend changes the question being asked; without it, an
    # ordinary dry run just reports what this host would do.
    dry.write_mixed()
    dry.backend.available = False
    # VirtualBox is a real capable candidate on hosts that have
    # it (F52); pin it absent so there's no backend left to pick.
    dry.install("virtualbox", available=False)
    with pytest.raises(PreflightError) as caught:
        dry.run()
    assert caught.value.rule_id == "machine.no-capable-backend"


def test_a_narrowing_section_is_named_as_the_source(dry):
    machine = dict(dry.mixed(),
                   **{"backend-settings": {"qemu": {"machine": "pc"}}})
    dry.write("demo", machine, [dry.livecd(), dry.remote()])
    dry.backend.settings_keys = ("machine",)
    plan = dry.run().plan
    assert plan["backend"] == "qemu"
    assert plan["backend-source"] == "backend-settings"
    assert "backend: qemu (backend-settings)" in dry.run().report


def test_a_section_the_backend_cannot_honor_is_refused_dry(dry):
    # A dry run refuses what a create would refuse, and settings
    # are authored input — judged the same on any host.
    machine = dict(dry.mixed(),
                   **{"backend-settings": {"qemu": {"cpus": 2}}})
    dry.write("demo", machine, [dry.livecd(), dry.remote()])
    with pytest.raises(StaticError) as caught:
        dry.run()
    assert caught.value.rule_id == "machine.settings-unknown-key"


def test_a_declared_backend_is_named_as_the_source(dry):
    machine = dict(dry.mixed(), backend="qemu")
    dry.write("demo", machine, [dry.livecd(), dry.remote()])
    assert dry.run().plan["backend-source"] == "declared"


# backends.evaluate() is the underlying judgment that backend
# assignment relies on; tested here on its own.

def test_it_reports_both_answers_separately():
    requirements = backends.Requirements(media=("cdrom",))
    with fake_backend.installed(name="vmware", available=False):
        verdict = backends.evaluate("vmware", requirements)
    assert not verdict.available
    assert verdict.unmet == ()


def test_an_available_backend_can_still_be_unmet():
    requirements = backends.Requirements(controllers=("scsi",))
    with fake_backend.installed(name="vmware", available=True):
        verdict = backends.evaluate("vmware", requirements)
    assert verdict.available
    assert verdict.unmet == ("controller 'scsi'",)


# --- the script half ------------------------------------------------

_HEAD = "platform dos\n"


# The plan report names every observation's timeout and source.

def test_the_report_lists_defaults_budgets_and_observations():
    script = parse_script(
        _HEAD + "entry a\ntimeout 30s\ndeadline 45m\n"
        "phase a timeout=5m deadline=20m {\n"
        '    wait "x"\n'
        '    wait "y" timeout=90s\n'
        "    finish\n}\n")
    report = format_plan(resolve_timing(script), name="sample.rlqs")
    assert "timing plan for sample.rlqs" in report
    assert "default timeout: 30s from the header" in report
    assert "run deadline: 45m from the header" in report
    assert "phase a: 20m from the phase a" in report
    assert "wait: 5m from the phase a" in report
    assert "wait: 90s from the statement" in report


def test_a_built_in_default_is_named():
    report = format_plan(resolve_timing(parse_script(_HEAD + 'wait "x"\n')))
    assert "default timeout: 60s from the built-in" in report


# What a static pass can and cannot promise will run.

def test_a_linear_script_is_wholly_reachable():
    script = parse_script(_HEAD + 'start\nwait "x"\n')
    assert reach(script) == (2, 2)


def test_a_handler_body_is_the_guests_decision():
    script = parse_script(
        _HEAD + "entry a\nphase a {\n"
        '    wait {\n        on "x" {\n            press enter\n'
        "            finish\n        }\n"
        '        on "y" {\n            finish\n        }\n'
        "    }\n}\n")
    reachable, total = reach(script)
    # The wait is reached; what its handlers do is not.
    assert reachable == 1
    assert total == 4


def test_a_phase_only_a_handler_can_reach_is_not_reachable():
    script = parse_script(
        _HEAD + "entry a\nphase a {\n"
        '    wait {\n        on "x" {\n            goto b\n'
        "        }\n"
        '        on "y" {\n            finish\n        }\n'
        "    }\n}\n"
        "phase b {\n    press enter\n    finish\n}\n")
    reachable, _total = reach(script)
    assert reachable == 1


def test_an_unconditional_goto_carries_reachability_along():
    script = parse_script(
        _HEAD + "entry a\nphase a {\n    start\n    goto b\n}\n"
        'phase b {\n    wait "x"\n    finish\n}\n')
    assert reach(script) == (4, 4)


def test_the_shipped_install_script_is_mostly_the_guests():
    # This is the real-world case the reachability check exists for:
    # a branching wait means most of a real installer script can
    # only run depending on what the guest does, so static analysis
    # can't confirm it will run.
    path = os.path.join(
        os.path.dirname(os.path.abspath(reliquary.__file__)),
        "codex", "scripts", "freedos-install.rlqs")
    reachable, total = reach(load_script(path))
    assert reachable < total
    assert reachable > 0


# run_script(dry_run=True) replaces the separate check-script
# command; this section tests it as the one way to check a script.

def _codex_context(home):
    """A home the codex blueprint has been seeded into.

    A blueprint's scripts no longer resolve straight from the
    library (D88), so a test that wants the shipped script has to
    seed it by name first, the same as a user would — `seed-blueprint`
    brings along the scripts the blueprint names.
    """
    context = Context(home_dir=home)
    seed_blueprint("freedos", context=context)
    return context


def _dry_script(label, **kwargs):
    return run_script(label, dry_run=True, **kwargs)


def _write_script(home, stem, text):
    scripts = os.path.join(home, "scripts")
    os.makedirs(scripts, exist_ok=True)
    path = os.path.join(scripts, f"{stem}.rlqs")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def test_it_returns_a_dry_run_and_not_a_script_run(tmp_path):
    result = _dry_script("freedos-install",
                         context=_codex_context(str(tmp_path)))
    assert isinstance(result, DryRun)
    assert result.operation == "run-script"
    assert "nothing was run." in result.report


def test_a_seeded_name_plans_without_writing(tmp_path):
    result = _dry_script("freedos-install",
                         context=_codex_context(str(tmp_path)))
    assert result.plan["timing"]["run_deadline"]["spelling"] == "45m"
    assert "timing plan for" in result.report
    assert "45m" in result.report


def test_an_unseeded_name_is_refused_naming_the_fix(tmp_path):
    """A dry run refuses in the same case a live run refuses, and says how to fix it.

    This used to fall back to reading a codex script directly,
    without the user seeding it first. That fallback is gone (D88),
    so now there's nothing to read, and the honest response is a
    refusal plus the command that fixes it (P11).
    """
    home = str(tmp_path)
    with pytest.raises(PreflightError) as caught:
        _dry_script("freedos-install", context=Context(home_dir=home))
    assert "rlq seed-script freedos-install" in str(caught.value)
    assert not os.path.isdir(os.path.join(home, "scripts"))


def test_without_a_selector_the_tier_is_static(tmp_path):
    plan = _dry_script("freedos-install",
                       context=_codex_context(str(tmp_path))).plan
    assert plan["tier"] == "static"
    assert plan["machine"] is None


def test_a_home_script_wins_over_the_builtin(tmp_path):
    home = str(tmp_path)
    path = _write_script(home, "mine", _HEAD + 'timeout 12s\nwait "x"\n')
    plan = _dry_script("mine", context=home).plan
    assert plan["script"] == path
    assert plan["timing"]["default"]["spelling"] == "12s"


def test_a_blueprint_label_resolves_without_creating_a_machine(tmp_path):
    home = str(tmp_path)
    result = _dry_script("install", blueprint="freedos",
                         context=_codex_context(home))
    assert "freedos-install" in result.plan["script"]
    assert not os.path.isdir(os.path.join(home, "cache"))
    assert result.plan["timing"]["run_deadline"]["spelling"] == "45m"


def test_a_blueprint_with_a_machine_reaches_the_preflight_tier(tmp_path):
    # The selector determines which tier a dry run reaches, so
    # --blueprint has to resolve to a machine exactly as a live run
    # does. The retired check-script command only did that for
    # --machine.
    with fake_backend.installed():
        context = _codex_context(str(tmp_path))
        create_machine("freedos", context=context)
        plan = _dry_script("install", blueprint="freedos",
                           context=context).plan
    assert plan["machine"] == "freedos-0"
    assert plan["tier"] == "preflight"


def test_a_blueprint_with_no_machine_says_which_tier_it_reached(tmp_path):
    result = _dry_script("install", blueprint="freedos",
                         context=_codex_context(str(tmp_path)))
    assert result.plan["machine"] is None
    assert result.plan["tier"] == "static"
    assert result.plan["selector"] == "blueprint"
    assert "has no machine yet" in result.report


def test_a_static_error_propagates(tmp_path):
    home = str(tmp_path)
    _write_script(home, "bad",
                  _HEAD + "entry a\nphase a {\n    goto a\n}\n")
    with pytest.raises(ScriptParseError) as caught:
        _dry_script("bad", context=home)
    assert RULE_OF[caught.value.rule_id] == "V12"


def test_with_a_machine_media_slots_are_preflighted(tmp_path):
    home = str(tmp_path)
    _write_script(home, "use-cd",
                  _HEAD + 'insert cdrom0 @freedos-livecd\nwait "x"\n')
    with mock.patch("reliquary.script_runner._machines") as machines:
        machines.resolve_machine.return_value = "plain-0"
        machines.load_machine_state.return_value = {
            "scripts": {},
            "drives": {"hdd0": {"medium": "hdd"}},
        }
        with pytest.raises(PreflightError) as caught:
            _dry_script("use-cd", machine="plain-0", context=home)
    assert "no drive cdrom0" in str(caught.value)


def test_the_report_counts_what_it_could_not_reach(tmp_path):
    result = _dry_script("freedos-install",
                         context=_codex_context(str(tmp_path)))
    counts = result.plan["statements"]
    assert counts["statically-reachable"] < counts["total"]
    assert "statically reachable" in result.report
    assert "depend on what the guest does" in result.report


def test_a_wholly_reachable_script_claims_no_gap(tmp_path):
    home = str(tmp_path)
    _write_script(home, "flat", _HEAD + 'start\nwait "x"\n')
    result = _dry_script("flat", context=home)
    assert "statements: 2 of 2 statically reachable" in result.report
    assert "depend on what the guest does" not in result.report


def test_display_and_progress_are_refused(tmp_path):
    context = _codex_context(str(tmp_path))
    with pytest.raises(StaticError) as caught:
        _dry_script("freedos-install", context=context, display=True)
    assert caught.value.rule_id == "progress.display-on-a-dry-run"
    with pytest.raises(StaticError) as caught:
        _dry_script("freedos-install", context=context, progress="jsonl")
    assert caught.value.rule_id == "progress.stream-on-a-document"


def test_record_is_refused(tmp_path):
    """The fourth refusal, for the same reason as the other three.

    A dry run doesn't read the guest's screen, so `--record` would
    just create an empty file. Accepting a flag that has no effect
    would be exactly the kind of dishonesty P11 exists to refuse.
    """
    home = str(tmp_path)
    context = _codex_context(home)
    target = os.path.join(home, "run.rlqt")
    with pytest.raises(StaticError) as caught:
        _dry_script("freedos-install", context=context, record=target)
    assert caught.value.rule_id == "progress.record-on-a-dry-run"
    assert not os.path.exists(target), (
        "the refusal wrote a transcript anyway")


# CLI conflicts that had to be resolved when check-script was
# folded into run_script --dry-run.

@pytest.fixture
def flat_home(tmp_path):
    home = str(tmp_path)
    _write_script(home, "flat", _HEAD + 'start\nwait "x"\n')
    return home


def _cli_run(home, *args):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), \
            contextlib.redirect_stderr(stderr):
        code = cli.main(["--home-dir", home] + list(args))
    return code, stdout.getvalue(), stderr.getvalue()


def test_the_selector_is_optional_under_dry_run(flat_home):
    code, out, _err = _cli_run(flat_home, "run-script", "flat", "--dry-run")
    assert code == 0
    assert "nothing was run." in out


def test_a_live_run_still_requires_one(flat_home):
    code, _out, err = _cli_run(flat_home, "run-script", "flat")
    assert code == 2
    assert "--blueprint or --machine" in err


def test_json_is_legal_on_a_dry_run(flat_home):
    code, out, _err = _cli_run(
        flat_home, "run-script", "flat", "--dry-run", "--json")
    assert code == 0
    document = json.loads(out)
    assert document["operation"] == "run-script"
    assert document["plan"]["tier"] == "static"


def test_json_is_still_refused_on_a_live_run(flat_home):
    # This split is the whole point: a plan is a document, so --json
    # fits; a run is a stream, so --json is refused there and
    # --progress jsonl exists instead.
    code, _out, err = _cli_run(
        flat_home, "run-script", "flat", "--blueprint", "nope", "--json")
    assert code == 2
    assert "--progress jsonl" in err


def test_check_script_is_gone(flat_home):
    with pytest.raises(SystemExit):
        _cli_run(flat_home, "check-script", "flat")
