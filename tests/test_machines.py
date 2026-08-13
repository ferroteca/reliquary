# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for machine materialization and cached-state management.

The composed model: a machine's drive names a media, and the media owns
materialization (new/use/difference/copy). Tests write a composed
``.rlqb`` into the home and drive ``create_machine``; ``use`` media point
at a real local ISO (attached in place, no fetch), and blank/differencing
image creation is mocked.

**The `rig` fixture is the shared construction** — a temp home, the
adapter double, and the writers every family needs — so a test says
what it is about rather than how its home was built (F59).
"""

import contextlib
import json
import os
from unittest import mock

import pytest

from reliquary import backends
from reliquary import platform_dos
from reliquary import machines as machines_module
from reliquary import machines
from reliquary.errors import (PreflightError, RunFailure, StaticError,
                              WaitExpired, exit_code)
from reliquary.interaction_agentless import (AgentlessGuestExec,
                                             _command_output)
from reliquary.machines import exec as machines_exec
from reliquary.machines import (apply_blueprint, create_machine,
                                describe_drives,
                                destroy_machine, eject_media, get_file,
                                get_files, get_machine_dir, get_machine_var,
                                insert_media, list_files, list_machines,
                                load_machine_state, machine_dir_path,
                                mark_stopped, put_file, put_files,
                                recreate_machine, refresh_drives,
                                restart_machine,
                                resolve_machine,
                                set_boot_order, set_machine_var,
                                start_machine, stop_machine,
                                wait_machine_var)
from reliquary.backends import Capabilities
from tests import fake_backend, fat_image

_BLANK = {"name": "blank", "materialize": "new", "size": "20M"}


class _Rig:
    """One machine-layer case: a home, an adapter double, and writers."""

    def __init__(self, home, backend):
        self.home = home
        self.backend = backend
        self.iso_path = os.path.join(home, "live.iso")
        with open(self.iso_path, "wb") as handle:
            handle.write(b"ISO-CONTENT")

    def images(self):
        """(image name, mode, size) for every image materialized."""
        return sorted((os.path.basename(path), mode, size)
                      for path, mode, size, _base in self.backend.images)

    def livecd(self):
        return {"name": "freedos-livecd", "materialize": "use",
                "read-only": True, "location": {"local": self.iso_path}}

    def write(self, name, machine, media=None):
        specs = [dict(machine, type="machine", name=name)]
        specs.extend(dict(spec, type="media") for spec in (media or ()))
        bpdir = os.path.join(self.home, "blueprints")
        os.makedirs(bpdir, exist_ok=True)
        with open(os.path.join(bpdir, f"{name}.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump(specs, handle)

    def create(self, name, machine, media=None):
        self.write(name, machine, media)
        return create_machine(name, context=self.home)

    def state(self, machine_id):
        return load_machine_state(machine_id, self.home)

    def identity(self, machine_id):
        return backends.identity(
            "qemu", f"reliquary-{machine_id}", "1" * 32,
            {"port": 54321}, pid=1234)

    def force(self, machine_id, phase, *, vm=False):
        state = self.state(machine_id)
        state["phase"] = phase
        if vm:
            # The live-VM identity is folded into machine.json now.
            state["vm"] = self.identity(machine_id)
        path = os.path.join(machine_dir_path(machine_id, self.home),
                            "machine.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)

    def path(self, *parts):
        return os.path.join(self.home, *parts)


@pytest.fixture
def rig(tmp_path):
    # The machine model is driven against an adapter double: no
    # hypervisor is probed, no image is written, and nothing is
    # launched. What QEMU's own adapter does with the same calls
    # is test_backend_qemu.py's.
    with fake_backend.installed() as backend:
        yield _Rig(str(tmp_path), backend)


# --- materialization -------------------------------------------------

def test_create_populates_the_machine_cache_directory(rig):
    machine_id = rig.create(
        "freedos", {"platform": "dos", "drives": {"hdd0": "blank"}},
        media=[_BLANK])
    root = machine_dir_path(machine_id, rig.home)
    assert os.path.isfile(os.path.join(root, "machine.json"))
    assert os.path.isdir(os.path.join(root, "disks"))
    assert not os.path.exists(os.path.join(root, "media"))


def test_state_records_bookkeeping_and_defaults(rig):
    machine_id = rig.create(
        "freedos", {"platform": "dos", "drives": {"hdd0": "blank"},
                    "description": "A description.",
                    "scripts": {"install": "install-script"}},
        media=[_BLANK])
    state = rig.state(machine_id)
    assert state["id"] == machine_id
    assert state["blueprint"] == "freedos"
    assert state["phase"] == "ready"
    assert state["backend"] == "qemu"
    assert state["memory"] == 16
    assert state["cpus"] == 1
    assert state["control-planes"] == ["agentless-display"]
    # The blueprint declares a scripts map and the state does not
    # record it (D101): a label names which instructions to run,
    # not what the machine is, so it stays outside the shape
    # baseline and is read live at each invocation.
    assert "scripts" not in state
    assert state["boot"] == ["hdd0"]
    assert state["backend-id"] == f"reliquary-{machine_id}"
    assert state["blueprint-digest"].startswith("sha256:")


def test_optional_fields_absent(rig):
    machine_id = rig.create("minimal", {"platform": "dos"})
    state = rig.state(machine_id)
    assert state["memory"] == 16
    assert state["description"] is None
    assert "scripts" not in state
    assert state["drives"] == {}
    assert state["boot"] == []


def test_new_media_creates_qcow2_image(rig):
    rig.write("sized", {"platform": "dos",
                        "drives": {"hdd0": "blank", "floppy1": "boot"}},
              media=[_BLANK,
                     {"name": "boot", "materialize": "new",
                      "size": "720K"}])
    machine_id = create_machine("sized", context=rig.home)
    # Per-machine images are named for the media, not the slot,
    # and the adapter names the file — the extension is its
    # native format's, never the machine model's.
    assert rig.images() == [("blank.qcow2", "new", "20M"),
                            ("boot.qcow2", "new", "720K")]
    state = rig.state(machine_id)
    assert state["drives"]["hdd0"]["size"] == "20M"
    assert state["drives"]["hdd0"]["materialize"] == "new"


def test_use_media_attaches_the_payload_path(rig):
    machine_id = rig.create(
        "with-media", {"platform": "dos",
                       "drives": {"hdd0": "blank",
                                  "cdrom0": "freedos-livecd"},
                       "boot": ["cdrom0", "hdd0"]},
        media=[_BLANK, rig.livecd()])
    cdrom = rig.state(machine_id)["drives"]["cdrom0"]
    assert cdrom["media"] == "freedos-livecd"
    assert cdrom["materialize"] == "use"
    assert os.path.normpath(cdrom["path"]) == os.path.normpath(rig.iso_path)


def test_difference_media_materializes_an_overlay(rig):
    rig.write("based", {"platform": "dos", "drives": {"hdd0": "base"}},
              media=[{"name": "base", "materialize": "difference",
                      "location": {"local": rig.iso_path}}])
    machine_id = create_machine("based", context=rig.home)
    path, mode, _size, base = rig.backend.images[0]
    assert os.path.basename(path) == "base.qcow2"
    assert mode == "difference"
    assert base == rig.iso_path
    assert rig.state(machine_id)["drives"]["hdd0"]["materialize"] == (
        "difference")


def test_copy_media_materializes_a_duplicate(rig):
    rig.write("dup", {"platform": "dos", "drives": {"hdd0": "base"}},
              media=[{"name": "base", "materialize": "copy",
                      "location": {"local": rig.iso_path}}])
    machine_id = create_machine("dup", context=rig.home)
    assert [mode for _p, mode, _s, _b in rig.backend.images] == ["copy"]
    assert rig.state(machine_id)["drives"]["hdd0"]["materialize"] == "copy"


def test_directory_source_media_attaches_the_directory(rig):
    work = rig.path("work")
    os.makedirs(work)
    machine_id = rig.create(
        "hd", {"platform": "dos", "drives": {"hdd0": "shared"}},
        media=[{"name": "shared", "materialize": "use",
                "location": {"local": work}}])
    drive = rig.state(machine_id)["drives"]["hdd0"]
    # The state records the host directory itself; rendering it as
    # a vvfat drive is the adapter's (test_backend_qemu.py).
    assert os.path.normpath(drive["path"]) == os.path.normpath(work)


def test_cdrom_rejects_a_new_media(rig):
    rig.write("bad", {"platform": "dos", "drives": {"cdrom0": "blank"}},
              media=[_BLANK])
    with pytest.raises(StaticError) as caught:
        create_machine("bad", context=rig.home)
    assert "cdrom" in str(caught.value)


def test_a_controller_no_backend_wires_fails_closed(rig):
    # Capabilities are reported, never emulated: no available
    # backend claims a scsi controller, so assignment refuses the
    # machine naming the requirement rather than quietly wiring it
    # to ide.
    rig.write("scsi", {"platform": "dos",
                       "drives": {"hdd0": {"media": "blank",
                                           "controller": "scsi"}}},
              media=[_BLANK])
    with pytest.raises(PreflightError) as caught:
        create_machine("scsi", context=rig.home)
    assert "controller 'scsi'" in str(caught.value)
    assert rig.backend.images == []


@pytest.mark.parametrize("backend", ["vmware", "hyperv"])
def test_a_pinned_incapable_backend_fails_closed(rig, backend):
    """A pinned stub backend that cannot honor the blueprint is refused.

    VMware and Hyper-V still claim nothing. VirtualBox (F52) now
    claims agentless-display, so it is no longer one of these.
    """
    rig.write(backend, {"platform": "dos",
                        "backend": backend,
                        "drives": {"hdd0": "blank"}},
              media=[_BLANK])
    with pytest.raises(PreflightError) as caught:
        create_machine(backend, context=rig.home)
    assert repr(backend) in str(caught.value)
    assert rig.backend.images == []
    assert not os.path.exists(machine_dir_path(f"{backend}-0", rig.home))


@pytest.mark.parametrize("declared", ["qemu", None],
                         ids=["declared", "default"])
def test_the_default_backend_is_qemu_and_is_recorded(rig, declared):
    # The gate must not refuse what it is meant to allow, whether
    # the blueprint names qemu or leaves it out.
    spec = {"platform": "dos", "drives": {"hdd0": "blank"}}
    if declared is not None:
        spec["backend"] = declared
    name = f"be-{declared or 'default'}"
    rig.write(name, spec, media=[_BLANK])
    machine_id = create_machine(name, context=rig.home)
    assert load_machine_state(machine_id, rig.home)["backend"] == "qemu"


def test_unimplemented_control_plane_fails_closed(rig):
    # A wired plane in the list excuses nothing: the policy is
    # every plane Reliquary may use, so each has to exist.
    rig.write("vnc", {"platform": "dos",
                      "drives": {"hdd0": "blank"},
                      "control-planes": ["agentless-display", "vnc",
                                         "guest-agent"]},
              media=[_BLANK])
    with pytest.raises(PreflightError) as caught:
        create_machine("vnc", context=rig.home)
    assert "'vnc'" in str(caught.value)
    assert "'guest-agent'" in str(caught.value)
    # Refused before any image work, and no machine left behind.
    assert rig.backend.images == []
    assert not os.path.exists(machine_dir_path("vnc-0", rig.home))


def test_declared_agentless_display_is_recorded(rig):
    machine_id = rig.create(
        "cp", {"platform": "dos", "drives": {"hdd0": "blank"},
               "control-planes": ["agentless-display"]},
        media=[_BLANK])
    assert rig.state(machine_id)["control-planes"] == ["agentless-display"]


def test_a_settings_section_is_validated_against_the_assigned_backend(rig):
    # The seam is called with this backend's own section, and a key
    # it does not define is refused before any image work.
    with fake_backend.installed(settings_keys=("machine",)) as adapter:
        rig.write("hatch", {"platform": "dos",
                            "drives": {"hdd0": "blank"},
                            "backend-settings": {"qemu": {"machine": "pc"}}},
                  media=[_BLANK])
        machine_id = create_machine("hatch", context=rig.home)
        assert adapter.validated == [{"machine": "pc"}]
        assert rig.state(machine_id)["backend-settings"] == {
            "qemu": {"machine": "pc"}}

        rig.write("bad", {"platform": "dos",
                          "drives": {"hdd0": "blank"},
                          "backend-settings": {"qemu": {"cpus": 2}}},
                  media=[_BLANK])
        adapter.images.clear()
        with pytest.raises(StaticError) as caught:
            create_machine("bad", context=rig.home)
        assert caught.value.rule_id == "machine.settings-unknown-key"
        assert adapter.images == []
        assert not os.path.exists(machine_dir_path("bad-0", rig.home))


def test_another_backends_section_is_inert_and_never_judged(rig):
    # Preserved verbatim and not validated: no adapter can speak
    # for another's vocabulary, so judging an inert section would
    # refuse a machine over configuration nothing will read.
    with fake_backend.installed(settings_keys=()) as adapter:
        machine_id = rig.create(
            "inert", {"platform": "dos", "backend": "qemu",
                      "drives": {"hdd0": "blank"},
                      "backend-settings": {"vmware": {"nonsense": True}}},
            media=[_BLANK])
        assert adapter.validated == [None]
    assert rig.state(machine_id)["backend-settings"] == {
        "vmware": {"nonsense": True}}


def test_a_lone_settings_section_narrows_assignment_to_its_backend(rig):
    # No `backend` declared, one section: the blueprint has already
    # said which backend it is written for.
    with fake_backend.installed(name="vmware",
                                settings_keys=("machine",)) as vmware:
        rig.write("narrow", {"platform": "dos",
                             "drives": {"hdd0": "blank"},
                             "backend-settings": {"vmware": {"machine": "x"}}},
                  media=[_BLANK])
        machine_id = create_machine("narrow", context=rig.home)
        assert vmware.validated == [{"machine": "x"}]
    state = rig.state(machine_id)
    assert state["backend"] == "vmware"
    # And qemu — first in the priority order, available, capable —
    # was passed over rather than winning the walk.
    assert rig.backend.images == []


def test_two_sections_narrow_nothing_and_the_walk_decides(rig):
    machine_id = rig.create(
        "both", {"platform": "dos", "drives": {"hdd0": "blank"},
                 "backend-settings": {"vmware": {}, "hyperv": {}}},
        media=[_BLANK])
    assert rig.state(machine_id)["backend"] == "qemu"


def test_a_declared_backend_outranks_a_narrowing_section(rig):
    machine_id = rig.create(
        "pinned", {"platform": "dos", "backend": "qemu",
                   "drives": {"hdd0": "blank"},
                   "backend-settings": {"vmware": {}}},
        media=[_BLANK])
    assert rig.state(machine_id)["backend"] == "qemu"


def test_disabled_drive_excluded_from_state(rig):
    machine_id = rig.create(
        "disabled", {"platform": "dos",
                     "drives": {"hdd0": "blank",
                                "hdd1": {"media": "big", "enabled": False}}},
        media=[_BLANK, {"name": "big", "materialize": "new",
                        "size": "50M"}])
    state = rig.state(machine_id)
    assert "hdd0" in state["drives"]
    assert "hdd1" not in state["drives"]


def test_blueprint_source_recorded_and_digest_stable(rig):
    rig.write("twin", {"platform": "dos", "drives": {"hdd0": "blank"}},
              media=[_BLANK])
    first = create_machine("twin", context=rig.home)
    second = create_machine("twin", context=rig.home)
    s1, s2 = rig.state(first), rig.state(second)
    assert s1["blueprint-source"].endswith("twin.rlqb")
    assert s1["blueprint-digest"] == s2["blueprint-digest"]
    assert first != second


def test_location_property_binds_at_create_and_records_the_path(rig):
    # A media located by ${live.iso}, supplied by a blueprint
    # parameter, materializes -- and the resolved path lands in
    # state, so start never re-resolves the reference.
    rig.write("param", {"platform": "dos",
                        "drives": {"cdrom0": "livecd"},
                        "parameters": {"live.iso": rig.iso_path}},
              media=[{"name": "livecd", "materialize": "use",
                      "read-only": True, "location": "${live.iso}"}])
    machine_id = create_machine("param", context=rig.home)
    entry = rig.state(machine_id)["drives"]["cdrom0"]
    assert entry["path"] == rig.iso_path
    # The recorded location is concrete: no ${...} survives.
    assert "${" not in json.dumps(entry)


def test_location_property_from_an_explicit_value(rig):
    rig.write("explicit", {"platform": "dos",
                           "drives": {"cdrom0": "livecd"}},
              media=[{"name": "livecd", "materialize": "use",
                      "read-only": True, "location": "${live.iso}"}])
    machine_id = create_machine(
        "explicit", context=rig.home,
        properties={"live.iso": rig.iso_path})
    entry = rig.state(machine_id)["drives"]["cdrom0"]
    assert entry["path"] == rig.iso_path


def test_an_unbound_location_property_is_asked(rig):
    rig.write("needy", {"platform": "dos", "drives": {"cdrom0": "livecd"}},
              media=[{"name": "livecd", "materialize": "use",
                      "read-only": True, "location": "${live.iso}"}])
    asker = mock.Mock(return_value=rig.iso_path)
    with mock.patch("reliquary.binding.console_asker", return_value=asker):
        create_machine("needy", context=rig.home)
    asker.assert_called_once_with("live.iso", "live.iso", False)
    entry = rig.state("needy-0")["drives"]["cdrom0"]
    assert entry["path"] == rig.iso_path


def test_missing_state_raises_filenotfound(rig):
    with pytest.raises(PreflightError):
        load_machine_state("nonexistent", context=rig.home)


def test_machine_id_numbered_and_reused(rig):
    rig.write("plain", {"platform": "dos"})
    rig.write("other", {"platform": "dos"})
    first = create_machine("plain", context=rig.home)
    second = create_machine("plain", context=rig.home)
    other = create_machine("other", context=rig.home)
    assert (first, second, other) == ("plain-0", "plain-1", "other-0")
    destroy_machine(second, context=rig.home)
    assert create_machine("plain", context=rig.home) == "plain-1"


def test_create_machine_unknown_name_errors(rig):
    with pytest.raises(PreflightError):
        create_machine("no-such", context=rig.home)


# --- lifecycle -------------------------------------------------------

def _ready(rig, name="test-bp", **machine):
    # A per-blueprint blank so several blueprints can coexist in one
    # home without a media (name, type) collision.
    machine.setdefault("platform", "dos")
    blank = f"{name}-blank"
    machine.setdefault("drives", {"hdd0": blank})
    return rig.create(name, machine,
                      media=[{"name": blank, "materialize": "new",
                              "size": "20M"}])


def test_list_and_filter_machines(rig):
    first = _ready(rig, "alpha")
    second = _ready(rig, "beta")
    ids = {s["id"] for s in list_machines(context=rig.home)}
    assert ids == {first, second}
    assert [s["id"] for s in
            list_machines(context=rig.home, blueprint="alpha")] == [first]


def test_list_orders_by_number(rig):
    _ready(rig, "plain")
    _ready(rig, "plain")
    _ready(rig, "plain")
    destroy_machine("plain-1", context=rig.home)
    assert [s["id"] for s in
            list_machines(context=rig.home, blueprint="plain")] == [
        "plain-0", "plain-2"]


def test_resolve_by_blueprint_sole(rig):
    machine_id = _ready(rig, "freedos")
    assert resolve_machine(blueprint="freedos",
                           context=rig.home) == machine_id


def test_resolve_by_blueprint_none_suggests_create(rig):
    with pytest.raises(PreflightError) as caught:
        resolve_machine(blueprint="missing", context=rig.home)
    assert "no machine exists" in str(caught.value)


def test_resolve_by_blueprint_ambiguous(rig):
    _ready(rig, "freedos")
    _ready(rig, "freedos")
    with pytest.raises(PreflightError) as caught:
        resolve_machine(blueprint="freedos", context=rig.home)
    assert "has 2 machines" in str(caught.value)


def test_resolve_by_full_id_and_rejections(rig):
    machine_id = _ready(rig, "freedos")
    assert resolve_machine(machine=machine_id,
                           context=rig.home) == machine_id
    with pytest.raises(StaticError):
        resolve_machine(blueprint="freedos", machine=machine_id,
                        context=rig.home)
    with pytest.raises(StaticError):
        resolve_machine(machine="0", context=rig.home)
    with pytest.raises(PreflightError):
        resolve_machine(machine="freedos-", context=rig.home)


def test_start_hands_the_state_to_the_adapter_and_sets_running(rig):
    machine_id = rig.create(
        "bootable", {"platform": "dos",
                     "drives": {"hdd0": "blank",
                                "cdrom0": "freedos-livecd"},
                     "boot": ["cdrom0", "hdd0"]},
        media=[_BLANK, rig.livecd()])
    started = start_machine(machine_id, context=rig.home)
    assert started == machine_id
    # Reliquary vocabulary crosses the seam, never backend
    # arguments: the adapter is handed the resolved state and the
    # directories that are its to write in.
    launch = rig.backend.starts[-1]
    assert launch["state"]["boot"] == ["cdrom0", "hdd0"]
    assert set(launch["state"]["drives"]) == {"hdd0", "cdrom0"}
    assert launch["machine_dir"] == machine_dir_path(machine_id, rig.home)
    assert launch["backend_dir"] == os.path.join(
        machine_dir_path(machine_id, rig.home), "qemu")
    state = rig.state(machine_id)
    assert state["phase"] == "running"
    # The live-VM identity is folded into the state, atomic with
    # phase, and it names the backend that owns it.
    assert state["vm"]["backend"] == "qemu"
    assert state["vm"]["backend-id"] == f"reliquary-{machine_id}"


def test_start_refuses_when_the_recorded_backend_is_absent(rig):
    # A machine carries its backend for life; a host that no
    # longer has it is told so, and nothing is launched.
    machine_id = _ready(rig)
    rig.backend.available = False
    with pytest.raises(PreflightError) as caught:
        start_machine(machine_id, context=rig.home)
    assert "not available on this host" in str(caught.value)
    assert rig.backend.starts == []
    assert rig.state(machine_id)["phase"] == "ready"


def test_start_rejects_already_running(rig):
    machine_id = _ready(rig)
    rig.force(machine_id, "running")
    with pytest.raises(PreflightError) as caught:
        start_machine(machine_id, context=rig.home)
    assert "already running" in str(caught.value)


def test_stop_returns_phase_to_ready(rig):
    machine_id = _ready(rig)
    rig.force(machine_id, "running", vm=True)
    stop_machine(machine_id, context=rig.home)
    # The adapter is handed the recorded VM identity, not a home
    # dir — the endpoint behind it is the adapter's own business.
    assert len(rig.backend.stops) == 1
    assert rig.backend.stops[0]["backend-id"] == f"reliquary-{machine_id}"
    state = rig.state(machine_id)
    assert state["phase"] == "ready"
    assert "vm" not in state


def test_restart_stops_then_starts_a_running_machine(rig):
    machine_id = _ready(rig)
    rig.force(machine_id, "running", vm=True)
    restart_machine(machine_id, context=rig.home)
    assert len(rig.backend.stops) == 1
    assert len(rig.backend.starts) == 1
    assert rig.state(machine_id)["phase"] == "running"


def test_restart_starts_a_machine_that_is_already_stopped(rig):
    """The end state asked for is *running*, not "the other one".

    Refusing would make the command's answer depend on a phase
    the caller usually neither knows nor cares about — and stop
    is already satisfied by a machine that is off.
    """
    machine_id = _ready(rig)
    restart_machine(machine_id, context=rig.home)
    assert rig.backend.stops == []
    assert len(rig.backend.starts) == 1
    assert rig.state(machine_id)["phase"] == "running"


def test_restart_completes_an_interrupted_stop_first(rig):
    """A machine caught mid-`stopping` is reconciled, as either
    command alone would reconcile it."""
    machine_id = _ready(rig)
    rig.force(machine_id, "stopping", vm=True)
    restart_machine(machine_id, context=rig.home)
    assert len(rig.backend.stops) == 1
    assert rig.state(machine_id)["phase"] == "running"


def test_restart_never_lets_go_of_the_machine_lock(rig):
    """The whole difference from typing the two commands.

    A restart that released the lock could come back to a machine
    someone else had started and fail as `already-running` — a
    race the caller never asked to run. The lock is a file lock
    and not re-entrant, so holding it across both halves is also
    why the two bodies had to be split from their wrappers.
    """
    machine_id = _ready(rig)
    rig.force(machine_id, "running", vm=True)
    taken = []
    real_lock = machines.machine_lock

    @contextlib.contextmanager
    def counting_lock(*args, **kwargs):
        taken.append(args[0])
        with real_lock(*args, **kwargs):
            yield

    with mock.patch.object(machines, "machine_lock", counting_lock):
        restart_machine(machine_id, context=rig.home)
    assert taken == [machine_id]


def test_stop_keeps_running_on_identity_mismatch(rig):
    machine_id = _ready(rig)
    rig.force(machine_id, "running", vm=True)
    rig.backend.stop_error = PreflightError("QMP identity mismatch")
    with pytest.raises(PreflightError, match="identity mismatch"):
        stop_machine(machine_id, context=rig.home)
    state = rig.state(machine_id)
    assert state["phase"] == "running"
    assert "vm" in state


def test_stop_reconciles_when_vm_gone(rig):
    machine_id = _ready(rig)
    rig.force(machine_id, "running")
    rig.backend.stop_error = PreflightError("no longer reachable")
    with pytest.raises(PreflightError, match="no longer reachable"):
        stop_machine(machine_id, context=rig.home)
    assert rig.state(machine_id)["phase"] == "ready"


def test_stop_is_satisfied_by_an_unreachable_vm(rig):
    """A VM that is already gone is the state stop was asked for.

    The machine keeps its recorded ``vm`` section — a guest that
    halted itself between runs leaves one behind — so the phase
    can only be reconciled by reading the rule id (T19).
    """
    machine_id = _ready(rig)
    rig.force(machine_id, "running", vm=True)
    rig.backend.stop_error = PreflightError(
        "the recorded reliquary VM is no longer reachable",
        rule_id="machine.vm-unreachable")
    stop_machine(machine_id, context=rig.home)
    state = rig.state(machine_id)
    assert state["phase"] == "ready"
    assert "vm" not in state


def test_a_machine_whose_vm_died_can_still_be_destroyed(rig):
    """The whole T19 cascade: stop was the door destroy needed."""
    machine_id = _ready(rig)
    rig.force(machine_id, "running", vm=True)
    rig.backend.stop_error = PreflightError(
        "the recorded reliquary VM is no longer reachable",
        rule_id="machine.vm-unreachable")
    root = machine_dir_path(machine_id, rig.home)
    stop_machine(machine_id, context=rig.home)
    destroy_machine(machine_id, context=rig.home)
    assert not os.path.exists(root)


def test_stop_still_fails_closed_on_an_unrelated_refusal(rig):
    """The rule id is the whole test; a wrong port is not a stop."""
    machine_id = _ready(rig)
    rig.force(machine_id, "running", vm=True)
    rig.backend.stop_error = PreflightError(
        "QMP identity mismatch", rule_id="machine.vm-identity-mismatch")
    with pytest.raises(PreflightError):
        stop_machine(machine_id, context=rig.home)
    state = rig.state(machine_id)
    assert state["phase"] == "running"
    assert "vm" in state


def test_destroy_removes_directory(rig):
    machine_id = _ready(rig)
    root = machine_dir_path(machine_id, rig.home)
    destroy_machine(machine_id, context=rig.home)
    assert not os.path.exists(root)
    assert list_machines(context=rig.home) == []


def test_destroy_disposes_of_the_backend_object_first(rig):
    # The directory is the whole materialization only for QEMU;
    # another backend has its own object to remove, and it goes
    # before the directory that would otherwise strand it.
    machine_id = _ready(rig)
    root = machine_dir_path(machine_id, rig.home)
    destroy_machine(machine_id, context=rig.home)
    assert rig.backend.disposed == [root]


def test_destroy_retries_after_failure(rig):
    machine_id = _ready(rig)
    with mock.patch("reliquary.machines.shutil.rmtree",
                    side_effect=PermissionError("locked")):
        with pytest.raises(PermissionError):
            destroy_machine(machine_id, context=rig.home)
    assert rig.state(machine_id)["phase"] == "ready"
    destroy_machine(machine_id, context=rig.home)
    assert not os.path.exists(machine_dir_path(machine_id, rig.home))


def test_destroy_completes_a_stranded_destroy(rig):
    machine_id = _ready(rig)
    rig.force(machine_id, "destroying")
    destroy_machine(machine_id, context=rig.home)
    assert not os.path.exists(machine_dir_path(machine_id, rig.home))


def test_destroy_rejects_running(rig):
    machine_id = _ready(rig)
    rig.force(machine_id, "running")
    with pytest.raises(PreflightError) as caught:
        destroy_machine(machine_id, context=rig.home)
    assert "stop it before destroying" in str(caught.value)


def test_generation_advances(rig):
    machine_id = _ready(rig)
    assert rig.state(machine_id)["generation"] == 0
    start_machine(machine_id, context=rig.home)
    gen1 = rig.state(machine_id)["generation"]
    assert gen1 > 0
    stop_machine(machine_id, context=rig.home)
    assert rig.state(machine_id)["generation"] > gen1


def test_operation_takes_a_lock(rig):
    machine_id = _ready(rig)
    start_machine(machine_id, context=rig.home)
    assert os.path.exists(rig.path("cache", "machines", ".locks",
                                   f"{machine_id}.op.lock"))


def test_interrupted_stop_completed(rig):
    machine_id = _ready(rig)
    rig.force(machine_id, "stopping")
    stop_machine(machine_id, context=rig.home)
    assert len(rig.backend.stops) == 1
    assert rig.state(machine_id)["phase"] == "ready"


def test_interrupted_create_rolled_back(rig):
    machine_id = _ready(rig)
    rig.force(machine_id, "creating")
    with pytest.raises(PreflightError) as caught:
        start_machine(machine_id, context=rig.home)
    assert "rolled back" in str(caught.value)
    assert not os.path.exists(machine_dir_path(machine_id, rig.home))


def test_interrupted_destroy_completes(rig):
    machine_id = _ready(rig)
    rig.force(machine_id, "destroying")
    with pytest.raises(PreflightError) as caught:
        start_machine(machine_id, context=rig.home)
    assert "removed" in str(caught.value)


def test_failed_materialization_rolls_back(rig):
    rig.write("doomed", {"platform": "dos", "drives": {"hdd0": "blank"}},
              media=[_BLANK])
    with mock.patch.object(rig.backend, "create_image",
                           side_effect=RunFailure("disk full")):
        with pytest.raises(RunFailure):
            create_machine("doomed", context=rig.home)
    assert list_machines(context=rig.home, blueprint="doomed") == []


def test_get_machine_dir(rig):
    machine_id = _ready(rig)
    result = get_machine_dir(machine=machine_id, context=rig.home)
    assert os.path.isabs(result)
    assert os.path.normpath(result) == os.path.normpath(
        machine_dir_path(machine_id, rig.home))


def test_recreate_reuses_id(rig):
    machine_id = _ready(rig, "rc")
    again = recreate_machine(machine=machine_id, context=rig.home)
    assert again == machine_id


def test_recreate_keeps_id_at_gap(rig):
    rig.write("g", {"platform": "dos", "drives": {"hdd0": "blank"}},
              media=[_BLANK])
    create_machine("g", context=rig.home)
    create_machine("g", context=rig.home)
    two = create_machine("g", context=rig.home)
    destroy_machine("g-0", context=rig.home)
    again = recreate_machine(machine=two, context=rig.home)
    assert again == "g-2"


def test_apply_absorbs_memory_and_boot(rig):
    machine_id = rig.create(
        "ap", {"platform": "dos", "memory": "16M",
               "drives": {"hdd0": "blank", "cdrom0": None},
               "boot": ["hdd0", "cdrom0"]}, media=[_BLANK])
    digest0 = rig.state(machine_id)["blueprint-digest"]
    rig.write("ap", {"platform": "dos", "memory": "32M",
                     "drives": {"hdd0": "blank", "cdrom0": None},
                     "boot": ["cdrom0", "hdd0"]}, media=[_BLANK])
    apply_blueprint(machine=machine_id, context=rig.home)
    state = rig.state(machine_id)
    assert state["memory"] == 32
    assert state["boot"] == ["cdrom0", "hdd0"]
    assert state["blueprint-digest"] != digest0


def test_apply_fails_closed_on_size_change(rig):
    machine_id = rig.create(
        "sz", {"platform": "dos", "drives": {"hdd0": "blank"}},
        media=[_BLANK])
    rig.write("sz", {"platform": "dos", "drives": {"hdd0": "blank"}},
              media=[{"name": "blank", "materialize": "new",
                      "size": "50M"}])
    with pytest.raises(PreflightError) as caught:
        apply_blueprint(machine=machine_id, context=rig.home)
    assert "recreate" in str(caught.value)


def test_apply_reconciles_diverged_media(rig):
    machine_id = rig.create(
        "dv", {"platform": "dos",
               "drives": {"hdd0": "blank", "cdrom0": None},
               "boot": ["hdd0", "cdrom0"]},
        media=[_BLANK, rig.livecd()])
    insert_media(machine_id, "cdrom0", "freedos-livecd", context=rig.home)
    assert rig.state(machine_id)["drives"]["cdrom0"]["media"] is not None
    apply_blueprint(machine=machine_id, context=rig.home)
    assert rig.state(machine_id)["drives"]["cdrom0"]["media"] is None


def test_apply_adds_and_removes_drives(rig):
    machine_id = rig.create(
        "ar", {"platform": "dos",
               "drives": {"hdd0": "blank", "hdd1": "big"}},
        media=[_BLANK, {"name": "big", "materialize": "new",
                        "size": "30M"}])
    disks_root = os.path.join(machine_dir_path(machine_id, rig.home),
                              "disks")
    # The dropped drive's per-machine image is named for its media.
    open(os.path.join(disks_root, "big.qcow2"), "w").close()
    rig.write("ar", {"platform": "dos",
                     "drives": {"hdd0": "blank", "cdrom0": None}},
              media=[_BLANK])
    apply_blueprint(machine=machine_id, context=rig.home)
    state = rig.state(machine_id)
    assert "hdd1" not in state["drives"]
    assert "cdrom0" in state["drives"]
    assert not os.path.exists(os.path.join(disks_root, "big.qcow2"))


def test_apply_refuses_an_unimplemented_control_plane(rig):
    machine_id = rig.create(
        "cpa", {"platform": "dos",
                "drives": {"hdd0": "blank", "hdd1": "big"}},
        media=[_BLANK, {"name": "big", "materialize": "new",
                        "size": "30M"}])
    rig.write("cpa", {"platform": "dos",
                      "drives": {"hdd0": "blank"},
                      "control-planes": ["serial-console"]},
              media=[_BLANK])
    with pytest.raises(PreflightError) as caught:
        apply_blueprint(machine=machine_id, context=rig.home)
    assert "'serial-console'" in str(caught.value)
    # Refused before the drives are reconciled, so the dropped
    # drive is still there and the machine is as it was.
    state = rig.state(machine_id)
    assert "hdd1" in state["drives"]
    assert state["control-planes"] == ["agentless-display"]


def test_apply_absorbs_a_settings_change_and_refuses_a_bad_one(rig):
    with fake_backend.installed(settings_keys=("machine",)):
        machine_id = rig.create(
            "sa", {"platform": "dos",
                   "drives": {"hdd0": "blank", "hdd1": "big"}},
            media=[_BLANK, {"name": "big", "materialize": "new",
                            "size": "30M"}])
        rig.write("sa", {"platform": "dos", "backend": "qemu",
                         "drives": {"hdd0": "blank", "hdd1": "big"},
                         "backend-settings": {"qemu": {"machine": "pc"}}},
                  media=[_BLANK, {"name": "big", "materialize": "new",
                                  "size": "30M"}])
        apply_blueprint(machine=machine_id, context=rig.home)
        assert rig.state(machine_id)["backend-settings"] == {
            "qemu": {"machine": "pc"}}

        # An edited section this backend cannot honor is refused
        # with the capability gate, before a drive is touched.
        rig.write("sa", {"platform": "dos", "backend": "qemu",
                         "drives": {"hdd0": "blank"},
                         "backend-settings": {"qemu": {"cpus": 2}}},
                  media=[_BLANK])
        with pytest.raises(StaticError) as caught:
            apply_blueprint(machine=machine_id, context=rig.home)
    assert caught.value.rule_id == "machine.settings-unknown-key"
    state = rig.state(machine_id)
    assert "hdd1" in state["drives"]
    assert state["backend-settings"] == {"qemu": {"machine": "pc"}}


def test_apply_requires_stopped(rig):
    machine_id = _ready(rig)
    rig.force(machine_id, "running")
    with pytest.raises(PreflightError) as caught:
        apply_blueprint(machine=machine_id, context=rig.home)
    assert "must be stopped" in str(caught.value)


# --- media insertion -------------------------------------------------

def _installer(rig):
    return rig.create(
        "installer", {"platform": "dos",
                      "drives": {"hdd0": "blank", "cdrom0": None},
                      "boot": ["hdd0", "cdrom0"]},
        media=[_BLANK, rig.livecd()])


def test_create_records_empty_removable_drive(rig):
    cdrom = rig.state(_installer(rig))["drives"]["cdrom0"]
    assert cdrom["medium"] == "cdrom"
    assert cdrom["media"] is None
    assert cdrom["path"] is None


def test_insert_persists_media(rig):
    machine_id = _installer(rig)
    insert_media(machine_id, "cdrom0", "freedos-livecd", context=rig.home)
    cdrom = rig.state(machine_id)["drives"]["cdrom0"]
    assert cdrom["media"] == "freedos-livecd"
    assert os.path.normpath(cdrom["path"]) == os.path.normpath(rig.iso_path)


def test_eject_returns_slot_to_empty(rig):
    machine_id = _installer(rig)
    insert_media(machine_id, "cdrom0", "freedos-livecd", context=rig.home)
    eject_media(machine_id, "cdrom0", context=rig.home)
    cdrom = rig.state(machine_id)["drives"]["cdrom0"]
    assert cdrom["media"] is None
    assert cdrom["path"] is None


def test_set_boot_order_persists(rig):
    machine_id = _installer(rig)
    set_boot_order(machine_id, ["cdrom0", "hdd0"], context=rig.home)
    assert rig.state(machine_id)["boot"] == ["cdrom0", "hdd0"]


def test_set_boot_order_rejects_running(rig):
    machine_id = _installer(rig)
    rig.force(machine_id, "running")
    with pytest.raises(PreflightError):
        set_boot_order(machine_id, ["cdrom0"], context=rig.home)


def test_set_boot_order_rejects_undeclared(rig):
    machine_id = _installer(rig)
    with pytest.raises(PreflightError) as caught:
        set_boot_order(machine_id, ["floppy0"], context=rig.home)
    assert "undeclared drive floppy0" in str(caught.value)


def test_boot_order_reaches_the_adapter_as_drive_keys(rig):
    machine_id = _installer(rig)
    start_machine(machine_id, context=rig.home)
    # Drive keys cross the seam; turning them into a firmware
    # boot order is the adapter's (test_backend_qemu.py).
    assert rig.backend.starts[-1]["state"]["boot"] == ["hdd0", "cdrom0"]


def test_inserted_media_survives_start(rig):
    machine_id = _installer(rig)
    insert_media(machine_id, "cdrom0", "freedos-livecd", context=rig.home)
    start_machine(machine_id, context=rig.home)
    cdrom = rig.backend.starts[-1]["state"]["drives"]["cdrom0"]
    assert os.path.normpath(cdrom["path"]) == os.path.normpath(rig.iso_path)


def test_insert_rejects_undeclared_slot(rig):
    with pytest.raises(PreflightError) as caught:
        insert_media(_installer(rig), "floppy0", "freedos-livecd",
                     context=rig.home)
    assert "declares no drive floppy0" in str(caught.value)


def test_insert_rejects_non_removable(rig):
    with pytest.raises(PreflightError) as caught:
        insert_media(_installer(rig), "hdd0", "freedos-livecd",
                     context=rig.home)
    assert "not a removable drive slot" in str(caught.value)


def test_insert_on_running_changes_live(rig):
    machine_id = _installer(rig)
    rig.force(machine_id, "running", vm=True)
    with mock.patch("reliquary.machines._change_media_live") as live:
        insert_media(machine_id, "cdrom0", "freedos-livecd",
                     context=rig.home)
    live.assert_called_once()
    assert live.call_args.args[1] == "cdrom0"
    assert rig.state(machine_id)["drives"]["cdrom0"]["media"] == (
        "freedos-livecd")


def test_eject_on_running_ejects_live(rig):
    machine_id = _installer(rig)
    insert_media(machine_id, "cdrom0", "freedos-livecd", context=rig.home)
    rig.force(machine_id, "running", vm=True)
    with mock.patch("reliquary.machines._change_media_live") as live:
        eject_media(machine_id, "cdrom0", context=rig.home)
    live.assert_called_once()
    assert live.call_args.args[2] is None


def test_a_live_change_goes_through_the_adapter_session(rig):
    # The swap the guest sees is one operation with the state
    # change, and it reaches the backend by drive key — never by
    # a monitor command this module composes itself.
    machine_id = _installer(rig)
    rig.force(machine_id, "running", vm=True)
    machines_module._change_media_live(
        machine_id, "cdrom0", rig.iso_path, rig.home)
    machines_module._change_media_live(
        machine_id, "cdrom0", None, rig.home)
    changes = [change for session in rig.backend.sessions
               for change in session.media_changes]
    assert changes == [("cdrom0", rig.iso_path), ("cdrom0", None)]


def test_insert_on_stopped_is_state_only(rig):
    machine_id = _installer(rig)
    with mock.patch("reliquary.machines._change_media_live") as live:
        insert_media(machine_id, "cdrom0", "freedos-livecd",
                     context=rig.home)
    live.assert_not_called()
    assert rig.state(machine_id)["drives"]["cdrom0"]["media"] == (
        "freedos-livecd")


def test_mark_stopped_reconciles(rig):
    machine_id = _installer(rig)
    rig.force(machine_id, "running", vm=True)
    mark_stopped(machine_id, context=rig.home)
    state = rig.state(machine_id)
    assert state["phase"] == "ready"
    assert "vm" not in state


def test_mark_stopped_leaves_ready_alone(rig):
    machine_id = _installer(rig)
    mark_stopped(machine_id, context=rig.home)
    assert rig.state(machine_id)["phase"] == "ready"


# --- `insert-media --file`: the caller's own image, mounted as-is ----

def _anonymous_rig(rig):
    machine_id = rig.create(
        "rig", {"platform": "dos",
                "drives": {"hdd0": "blank", "floppy0": None}},
        media=[_BLANK])
    image = rig.path("round-1.img")
    with open(image, "wb") as handle:
        handle.write(b"BINARY")
    return machine_id, image


def test_a_file_mounts_in_place_with_no_catalog_identity(rig):
    machine_id, image = _anonymous_rig(rig)
    insert_media(machine_id, "floppy0", file=image, context=rig.home)
    floppy = rig.state(machine_id)["drives"]["floppy0"]
    # Anonymous: no media name, attached ("use") in place.
    assert floppy["media"] is None
    assert floppy["materialize"] == "use"
    assert os.path.normpath(floppy["path"]) == os.path.normpath(image)


def test_the_image_is_never_copied_into_the_cache(rig):
    machine_id, image = _anonymous_rig(rig)
    insert_media(machine_id, "floppy0", file=image, context=rig.home)
    cache = rig.path("cache", "media")
    assert not (os.path.isdir(cache) and os.listdir(cache))


def test_a_rebuilt_image_is_picked_up_at_the_next_start(rig):
    machine_id, image = _anonymous_rig(rig)
    insert_media(machine_id, "floppy0", file=image, context=rig.home)
    with open(image, "wb") as handle:
        handle.write(b"ROUND-2")
    start_machine(machine_id, context=rig.home)
    # Mutable and unverified: no hash is re-checked, and the path
    # the consumer just rewrote is what the adapter is handed.
    floppy = rig.backend.starts[-1]["state"]["drives"]["floppy0"]
    assert os.path.normpath(floppy["path"]) == os.path.normpath(image)


def test_naming_both_a_media_and_a_file_is_refused(rig):
    machine_id, image = _anonymous_rig(rig)
    with pytest.raises(StaticError) as caught:
        insert_media(machine_id, "floppy0", "blank", file=image,
                     context=rig.home)
    assert "not both and not neither" in str(caught.value)


def test_naming_neither_is_refused(rig):
    machine_id, _image = _anonymous_rig(rig)
    with pytest.raises(StaticError):
        insert_media(machine_id, "floppy0", context=rig.home)


def test_a_missing_image_fails_closed(rig):
    machine_id, _image = _anonymous_rig(rig)
    with pytest.raises(PreflightError):
        insert_media(machine_id, "floppy0", file=rig.path("absent.img"),
                     context=rig.home)


def test_a_directory_names_the_gap(rig):
    machine_id, _image = _anonymous_rig(rig)
    with pytest.raises(StaticError) as caught:
        insert_media(machine_id, "floppy0", file=rig.home,
                     context=rig.home)
    assert "location is that directory" in str(caught.value)


# --- a live floppy swap keeps the geometry it launched with ----------
#
# The transport spike (milestone 9, T1) proved live media-change and
# eject-flush on QEMU/DOS, and found this one condition: the drive's
# geometry is fixed at attach, so a differently sized medium reaches
# the guest as read and write errors. Reliquary did not choose that
# geometry, so it fails closed rather than build a broken drive.

def _sized_image(rig, name, size):
    path = rig.path(name)
    with open(path, "wb") as handle:
        handle.write(b"\0" * size)
    return path


def _running_rig(rig, launched=None):
    machine_id = rig.create(
        "rig", {"platform": "dos",
                "drives": {"hdd0": "blank", "floppy0": None}},
        media=[_BLANK])
    if launched is not None:
        insert_media(machine_id, "floppy0", file=launched, context=rig.home)
    start_machine(machine_id, context=rig.home)
    return machine_id


def test_a_same_sized_swap_is_allowed(rig):
    first = _sized_image(rig, "round-1.img", 1474560)
    machine_id = _running_rig(rig, launched=first)
    second = _sized_image(rig, "round-2.img", 1474560)
    with mock.patch("reliquary.machines._change_media_live") as change:
        insert_media(machine_id, "floppy0", file=second, context=rig.home)
    change.assert_called_once()
    assert os.path.normpath(
        rig.state(machine_id)["drives"]["floppy0"]["path"]) == (
        os.path.normpath(second))


def test_a_differently_sized_swap_fails_closed(rig):
    first = _sized_image(rig, "round-1.img", 1474560)
    machine_id = _running_rig(rig, launched=first)
    bigger = _sized_image(rig, "round-2.img", 2949120)
    with pytest.raises(PreflightError) as caught:
        insert_media(machine_id, "floppy0", file=bigger, context=rig.home)
    message = str(caught.value)
    assert "1474560-byte medium" in message
    assert "2949120 bytes" in message


def test_a_slot_launched_empty_names_the_fix(rig):
    machine_id = _running_rig(rig)
    image = _sized_image(rig, "round-1.img", 1474560)
    with pytest.raises(PreflightError) as caught:
        insert_media(machine_id, "floppy0", file=image, context=rig.home)
    assert "was empty when machine" in str(caught.value)
    assert "start again" in str(caught.value)


def test_a_stopped_insert_is_never_geometry_checked(rig):
    # Stopped, the drive has not been attached yet, so any size is
    # legitimate — it becomes the geometry at the next start.
    machine_id = _running_rig(rig)
    rig.force(machine_id, "ready")
    image = _sized_image(rig, "round-1.img", 1474560)
    insert_media(machine_id, "floppy0", file=image, context=rig.home)
    assert os.path.normpath(
        rig.state(machine_id)["drives"]["floppy0"]["path"]) == (
        os.path.normpath(image))


def test_a_cdrom_swap_is_not_constrained(rig):
    machine_id = rig.create(
        "rig", {"platform": "dos",
                "drives": {"hdd0": "blank", "cdrom0": None}},
        media=[_BLANK, rig.livecd()])
    start_machine(machine_id, context=rig.home)
    with mock.patch("reliquary.machines._change_media_live"):
        insert_media(machine_id, "cdrom0", "freedos-livecd",
                     context=rig.home)
    assert rig.state(machine_id)["drives"]["cdrom0"]["media"] == (
        "freedos-livecd")


# --- the script -> host scalar channel -------------------------------

def _plain_rig(rig):
    return rig.create(
        "rig", {"platform": "dos", "drives": {"hdd0": "blank"}},
        media=[_BLANK])


def test_a_set_variable_reads_back_from_any_process(rig):
    machine_id = _plain_rig(rig)
    set_machine_var(machine_id, "result", "42", context=rig.home)
    assert get_machine_var("result", machine=machine_id,
                           context=rig.home) == "42"


def test_an_unset_variable_reads_as_none(rig):
    machine_id = _plain_rig(rig)
    assert get_machine_var("ready", machine=machine_id,
                           context=rig.home) is None


def test_start_clears_the_variables_of_the_previous_boot(rig):
    machine_id = _plain_rig(rig)
    set_machine_var(machine_id, "ready", "yes", context=rig.home)
    start_machine(machine_id, context=rig.home)
    assert get_machine_var("ready", machine=machine_id,
                           context=rig.home) is None


@pytest.mark.parametrize("key", ["rlq.ready", "reliquary", "9lives", ""],
                         ids=["rlq", "reliquary", "digit", "empty"])
def test_the_reserved_namespaces_are_refused(rig, key):
    machine_id = _plain_rig(rig)
    with pytest.raises(StaticError):
        set_machine_var(machine_id, key, "x", context=rig.home)


def test_a_variable_holds_text(rig):
    machine_id = _plain_rig(rig)
    with pytest.raises(StaticError):
        set_machine_var(machine_id, "count", 3, context=rig.home)


# --- the polling half, for a variable another actor sets (F30) -------
#
# Every case here uses a tiny interval and a tiny timeout: what is
# under test is the loop's logic and its refusals, not how long a real
# wait takes.

def test_a_value_already_there_returns_at_once(rig):
    machine_id = _plain_rig(rig)
    set_machine_var(machine_id, "ready", "yes", context=rig.home)
    assert wait_machine_var("ready", machine=machine_id, timeout=0.2,
                            interval=0.01, context=rig.home) == "yes"


def test_without_a_value_any_value_will_do(rig):
    """What the readiness idiom actually wants: presence."""
    machine_id = _plain_rig(rig)
    set_machine_var(machine_id, "ready", "whatever", context=rig.home)
    assert wait_machine_var("ready", machine=machine_id, timeout=0.2,
                            interval=0.01, context=rig.home) == "whatever"


def test_a_different_value_is_not_the_one_waited_for(rig):
    machine_id = _plain_rig(rig)
    set_machine_var(machine_id, "ready", "no", context=rig.home)
    with pytest.raises(WaitExpired) as caught:
        wait_machine_var("ready", "yes", machine=machine_id, timeout=0.05,
                         interval=0.01, context=rig.home)
    # The diagnostic says what it found, not just what it wanted:
    # "still 'no'" and "never arrived" are different situations.
    assert "'no'" in str(caught.value)


def test_a_variable_arriving_mid_wait_is_returned(rig):
    machine_id = _plain_rig(rig)
    state = {"reads": 0}
    real = machines_module.get_machine_var

    def arrive_on_third_read(key, **keywords):
        state["reads"] += 1
        if state["reads"] >= 3:
            set_machine_var(machine_id, key, "yes", context=rig.home)
        return real(key, **keywords)

    with mock.patch.object(machines_module, "get_machine_var",
                           side_effect=arrive_on_third_read):
        value = wait_machine_var("ready", "yes", machine=machine_id,
                                 timeout=2, interval=0.01,
                                 context=rig.home)
    assert value == "yes"
    assert state["reads"] >= 3


def test_an_expired_wait_is_a_failure_and_a_timeout_at_once(rig):
    """Both readings are true, which is why it has both bases.

    A caller holding the loop catches `TimeoutError` and asks
    again; the CLI's taxonomy arm sees a `RunFailure` and exits 4.
    A bare builtin would have exited 1 and blamed reliquary.
    """
    machine_id = _plain_rig(rig)
    with pytest.raises(RunFailure):
        wait_machine_var("ready", machine=machine_id, timeout=0.05,
                         interval=0.01, context=rig.home)
    with pytest.raises(TimeoutError):
        wait_machine_var("ready", machine=machine_id, timeout=0.05,
                         interval=0.01, context=rig.home)
    assert exit_code(WaitExpired("x")) == 4


@pytest.mark.parametrize("timeout,interval", [(0, 1), (1, 0), (-1, 1)],
                         ids=["no-timeout", "no-interval",
                              "negative-timeout"])
def test_a_nonpositive_bound_is_refused_before_any_read(rig, timeout,
                                                        interval):
    machine_id = _plain_rig(rig)
    with pytest.raises(StaticError):
        wait_machine_var("ready", machine=machine_id, timeout=timeout,
                         interval=interval, context=rig.home)


def test_the_reserved_namespaces_are_refused_here_too(rig):
    machine_id = _plain_rig(rig)
    with pytest.raises(StaticError):
        wait_machine_var("rlq.ready", machine=machine_id, timeout=0.05,
                         interval=0.01, context=rig.home)


# --- the run family's one-shot member returns its output -------------

def test_a_stopped_machine_is_refused(rig):
    machine_id = _plain_rig(rig)
    with pytest.raises(PreflightError) as caught:
        machines_exec("DIR", machine=machine_id, context=rig.home)
    assert "is not running" in str(caught.value)


def test_the_command_output_is_returned(rig):
    machine_id = _plain_rig(rig)
    rig.force(machine_id, "running", vm=True)
    with mock.patch(
            "reliquary.interaction_agentless.AgentlessGuestExec.execute",
            return_value=("VOL SERIAL", "2 FILES")) as run:
        rows = machines_exec("DIR", machine=machine_id, timeout=30,
                             context=rig.home)
    assert rows == ("VOL SERIAL", "2 FILES")
    # The outcome check is opt-in, so the twin passes it through
    # explicitly rather than leaving the adapter to assume.
    run.assert_called_once_with("DIR", 30, check=False)


# --- agentless capture: the rows between the echo and the prompt -----

def test_the_rows_between_echo_and_prompt_are_the_output():
    rows = _command_output(
        ["C:\\>DIR", "VOL SERIAL IS 1234", "2 FILE(S)", "C:\\>"],
        "DIR", echoed=True)
    assert rows == ("VOL SERIAL IS 1234", "2 FILE(S)")


def test_a_command_with_no_output_returns_nothing():
    assert _command_output(["C:\\>CLS", "C:\\>"], "CLS", echoed=True) == ()


def test_a_scrolled_echo_yields_what_is_still_visible():
    # The honest limit of screen scraping: the echo scrolled off,
    # so what remains on screen is what the caller gets. `echoed`
    # is what says it scrolled rather than never arrived.
    rows = _command_output(["LINE 1", "LINE 2", "C:\\>"],
                           "TYPE BIG.TXT", echoed=True)
    assert rows == ("LINE 1", "LINE 2")


def test_an_echo_never_seen_is_a_failure_not_a_tuple():
    # The same screen, and the opposite answer: with no echo ever
    # observed, the rows above the prompt belong to something else
    # and returning them would pass one command's text off as
    # another's (P11).
    with pytest.raises(RunFailure) as caught:
        _command_output(["LINE 1", "LINE 2", "C:\\>"],
                        "TYPE BIG.TXT", echoed=False)
    assert caught.value.rule_id == "screen.no-echo"
    assert "never echoed" in str(caught.value)


class _ScriptedConsole:
    """A console playing fixed screens, one segment per console opened.

    `execute` opens a console, and `--check`'s probe opens another, so
    a script is grouped the same way rather than as one flat run of
    reads. Within a segment the **last frame repeats**: a screen that
    has settled stays settled however often a wait looks at it, which
    is what a real guest does and what keeps these scripts independent
    of how many reads any one wait happens to take.
    """

    def __init__(self, segments):
        self.segments = [list(frames) for frames in segments]
        self.opened = -1
        self.sent = []

    def open(self):
        self.opened += 1

    @property
    def _frames(self):
        return self.segments[min(self.opened, len(self.segments) - 1)]

    def send_text(self, text, enter=True):
        del enter
        self.sent.append(text)

    def screen_text(self):
        frames = self._frames
        return list(frames[0] if len(frames) == 1 else frames.pop(0))

    def screen(self):
        """The same sequence, as the seam's (rows, attributes) pair.

        These scripts say what the guest displayed, so the attribute
        half is supplied uniformly: nothing here turns on a highlight.
        """
        rows = self.screen_text()
        return rows, [[0x07] * 80 for _ in range(len(rows))]


class _ScriptedMachine:
    """A machine whose console replays a script.

    A flat list of frames is the single-segment case, which is every
    script but the checked command's.
    """

    def __init__(self, frames, segments=None):
        self.console_double = _ScriptedConsole(
            segments if segments is not None else [frames])

    @contextlib.contextmanager
    def console(self):
        self.console_double.open()
        yield self.console_double


class _ScriptedClock:
    """A deterministic clock advanced only by sleeping.

    The command wait now holds a candidate prompt until the screen
    under it settles, so these scripts would otherwise sleep for real
    while the settle window passes — slow, and margin against a
    one-second timeout that a loaded machine could eat.
    """

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture
def scripted_clock():
    """Drive the agentless module's clock for one test."""
    clock = _ScriptedClock()
    with mock.patch("reliquary.interaction_agentless.time.sleep",
                    clock.sleep), \
            mock.patch("reliquary.interaction_agentless.time.monotonic",
                       clock.monotonic):
        yield clock


# --- a prompt alone does not mean *this* command finished ------------
#
# `wait_ready` returns because a prompt is on screen, so a completion
# test that asks only for a prompt is satisfied by the one already
# there — and hands back the boot's output as though it were the
# command's. These are the cases that tell the two apart.

PROMPT = "C:\\>"
BOOT = ["UDVD2 CD driver, success",
        "Modules using memory below 1 MB:", PROMPT]


def _execute(frames, command="VER", timeout=1):
    guest = AgentlessGuestExec(_ScriptedMachine(frames))
    return guest.execute(command, timeout)


def test_the_prompt_wait_ready_left_is_not_completion(scripted_clock):
    # The reported failure: the guest is still finishing its boot
    # script, the echo has not landed, and the screen is exactly
    # what wait_ready saw. Nothing here is this command's.
    with pytest.raises(RunFailure) as caught:
        _execute([BOOT, BOOT])
    assert "timed out" in str(caught.value)


def test_output_is_returned_once_the_echo_lands(scripted_clock):
    rows = _execute([
        BOOT, BOOT,
        ["C:\\>VER"],
        ["C:\\>VER", "FreeCom version 0.86", PROMPT]])
    assert rows == ("FreeCom version 0.86",)


def test_a_scrolled_echo_still_completes_with_the_tail(scripted_clock):
    # Seen once, gone later: that is scrolling, and the tail is
    # the documented answer rather than an error.
    rows = _execute([
        [PROMPT],
        ["C:\\>TYPE BIG.TXT"],
        ["LINE 24", "LINE 25", PROMPT]], "TYPE BIG.TXT")
    assert rows == ("LINE 24", "LINE 25")


def test_a_changed_screen_without_an_echo_still_refuses_to_guess(
        scripted_clock):
    # The screen moved, so something happened and the wait ends —
    # but nothing ties it to this command, so it fails rather than
    # returning rows it cannot place.
    with pytest.raises(RunFailure) as caught:
        _execute([[PROMPT], ["SOMETHING ELSE ENTIRELY", PROMPT]])
    assert caught.value.rule_id == "screen.no-echo"


def test_the_command_is_sent_exactly_once(scripted_clock):
    guest = AgentlessGuestExec(_ScriptedMachine([
        [PROMPT], ["C:\\>VER", "FreeCom version", PROMPT]]))
    guest.execute("VER", 1)
    assert guest._machine.console_double.sent == ["VER"]


# --- `check=True`: whether the command signalled failure (F26) -------
#
# The rows a command leaves cannot answer "did it work?" — a setup
# command's output is nothing and its success is everything — so the
# verdict comes from a probe reliquary composes and reads back, which
# is why this reads no meaning into the guest's own output (G2, P18):
# the sentinel is a word reliquary said, not one the command did.

PROBE = "IF ERRORLEVEL 1 ECHO RLQ-EXEC-FAILED"


def _checked_guest(segments):
    return AgentlessGuestExec(_ScriptedMachine(None, segments=segments))


def _probe_frames(*, failed):
    """The screens for one command plus its probe, one segment each.

    Each `execute` opens its own console, so the probe's screens
    are their own segment rather than following the command's in
    one run — the command's wait settles against its own last
    frame instead of consuming the probe's first.
    """
    probe_output = (["RLQ-EXEC-FAILED"] if failed else [])
    return [
        [[PROMPT], ["C:\\>DRIVER.EXE", "loading", PROMPT]],
        [[PROMPT], [f"C:\\>{PROBE}"] + probe_output + [PROMPT]],
    ]


def test_a_failing_command_raises_naming_it(scripted_clock):
    with pytest.raises(RunFailure) as caught:
        _checked_guest(_probe_frames(failed=True)).execute(
            "DRIVER.EXE", 1, check=True)
    assert caught.value.rule_id == "command.signalled-failure"
    assert "DRIVER.EXE" in str(caught.value)


def test_a_succeeding_command_returns_its_rows_unchanged(scripted_clock):
    rows = _checked_guest(_probe_frames(failed=False)).execute(
        "DRIVER.EXE", 1, check=True)
    assert rows == ("loading",)


def test_the_probe_is_asked_after_the_command_and_only_when_checked(
        scripted_clock):
    guest = _checked_guest(_probe_frames(failed=False))
    guest.execute("DRIVER.EXE", 1, check=True)
    assert guest._machine.console_double.sent == ["DRIVER.EXE", PROBE]

    unchecked = _checked_guest(_probe_frames(failed=True))
    unchecked.execute("DRIVER.EXE", 1)
    assert unchecked._machine.console_double.sent == ["DRIVER.EXE"], (
        "an unchecked exec must cost no extra command")


def test_the_sentinel_in_the_probes_own_echo_is_not_the_answer(
        scripted_clock):
    # The probe's echo contains the sentinel because the command
    # text does. Reading the echo as output would make every
    # checked command fail, so the answer is the rows *after* it.
    rows = _checked_guest(_probe_frames(failed=False)).execute(
        "DRIVER.EXE", 1, check=True)
    assert rows == ("loading",)


def test_an_unreadable_probe_refuses_rather_than_passing(scripted_clock):
    # The probe never echoed, so its verdict cannot be read. An
    # unknown outcome is not a success (P11).
    segments = [
        [[PROMPT], ["C:\\>DRIVER.EXE", "loading", PROMPT]],
        [[PROMPT], ["SOMETHING ELSE ENTIRELY", PROMPT]],
    ]
    with pytest.raises(RunFailure) as caught:
        _checked_guest(segments).execute("DRIVER.EXE", 1, check=True)
    assert caught.value.rule_id == "command.outcome-unreadable"
    assert "DRIVER.EXE" in str(caught.value)


# --- guest-terms addressing over a vvfat drive (U14) -----------------

#: What an installed C: holds, for the at-rest tests.
INSTALLED = {"AUTOEXEC.BAT": b"@ECHO OFF\r\n",
             "OUT": {"RESULT.LOG": b"pass\r\n"}}


def _exchange_rig(rig):
    exchange = rig.path("exchange")
    os.makedirs(exchange)
    machine_id = rig.create(
        "rig", {"platform": "dos",
                "drives": {"hdd0": "blank", "floppy0": "exchange-dir"}},
        media=[_BLANK,
               {"name": "exchange-dir", "materialize": "use",
                "location": {"local": exchange}}])
    return machine_id, exchange


def _image_rig(rig):
    """The same rig, with a real filesystem on the hard disk."""
    rig.backend.image_payload = fat_image.volume(INSTALLED)
    return _exchange_rig(rig)


def _problems(rig, machine_id):
    """Structural problems in the machine's disk, read independently."""
    path = rig.state(machine_id)["drives"]["hdd0"]["path"]
    with open(path, "rb") as handle:
        return fat_image.consistency(handle.read())


def _place(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="ascii") as handle:
        handle.write(text)


def test_an_exchange_disk_behind_an_installed_c_is_addressable(rig):
    # The shape P16 was failing on: results live on an installed
    # C: and the exchange drive is the second disk. Its letter is
    # D: because the installed disk really does hold one volume —
    # read, now, rather than assumed.
    rig.backend.image_payload = fat_image.volume(INSTALLED)
    exchange = rig.path("exchange2")
    os.makedirs(exchange)
    machine_id = rig.create(
        "two-disks", {"platform": "dos",
                      "drives": {"hdd0": "blank", "hdd1": "exchange-dir"}},
        media=[_BLANK,
               {"name": "exchange-dir", "materialize": "use",
                "location": {"local": exchange}}])
    source = rig.path("X.TXT")
    with open(source, "w", encoding="ascii") as handle:
        handle.write("x")
    assert put_file(source, r"D:\X.TXT", machine=machine_id,
                    context=rig.home) == r"D:\X.TXT"
    with open(os.path.join(exchange, "X.TXT"), encoding="ascii") as h:
        assert h.read() == "x"


def test_a_put_lands_where_the_guest_will_read_it(rig):
    machine_id, exchange = _exchange_rig(rig)
    source = rig.path("TEST.EXE")
    with open(source, "wb") as handle:
        handle.write(b"MZ")
    address = put_file(source, r"A:\TEST.EXE", machine=machine_id,
                       context=rig.home)
    assert address == r"A:\TEST.EXE"
    with open(os.path.join(exchange, "TEST.EXE"), "rb") as handle:
        assert handle.read() == b"MZ"


def test_a_get_retrieves_by_guest_address(rig):
    machine_id, exchange = _exchange_rig(rig)
    os.makedirs(os.path.join(exchange, "OUT"))
    with open(os.path.join(exchange, "OUT", "RESULT.TXT"), "w",
              encoding="ascii") as handle:
        handle.write("PASS")
    target = rig.path("result.txt")
    written = get_file(r"A:\OUT\RESULT.TXT", target, machine=machine_id,
                       context=rig.home)
    assert written == os.path.abspath(target)
    with open(target, encoding="ascii") as handle:
        assert handle.read() == "PASS"


def test_a_running_machine_is_refused_by_a_file_verb(rig):
    machine_id, _exchange = _exchange_rig(rig)
    rig.force(machine_id, "running", vm=True)
    with pytest.raises(PreflightError) as caught:
        get_file(r"A:\X.TXT", rig.path("x"), machine=machine_id,
                 context=rig.home)
    assert "must be stopped" in str(caught.value)


def test_an_empty_removable_slot_says_it_is_empty(rig):
    # Now reachable, because the letter map places a cdrom behind
    # a disk. It is neither an image nor a directory, and calling
    # it an image would be the lie the old message told. The disk
    # carries a real volume, which is what puts the cdrom at D:.
    rig.backend.image_payload = fat_image.volume(INSTALLED)
    exchange = rig.path("exchange3")
    os.makedirs(exchange)
    machine_id = rig.create(
        "with-cdrom", {"platform": "dos",
                       "drives": {"hdd0": "blank", "cdrom0": None,
                                  "floppy0": "exchange-dir"}},
        media=[_BLANK,
               {"name": "exchange-dir", "materialize": "use",
                "location": {"local": exchange}}])
    with pytest.raises(PreflightError) as caught:
        list_files(r"D:\\", machine=machine_id, context=rig.home)
    assert caught.value.rule_id == "drive.slot-empty"
    assert "cdrom0" in str(caught.value)


def test_an_image_drive_is_read_at_rest(rig):
    # P16's residue closing: the results are on the installed C:,
    # the machine is stopped, and the disk is a file the host owns.
    machine_id, _exchange = _image_rig(rig)
    target = rig.path("got.txt")
    assert get_file(r"C:\OUT\RESULT.LOG", target, machine=machine_id,
                    context=rig.home) == target
    with open(target, "rb") as handle:
        assert handle.read() == b"pass\r\n"


def test_a_file_written_into_an_image_lands_in_the_volume(rig):
    # The write half: the guest will read this at next boot, and
    # the volume is left structurally sound — checked by a reader
    # written from the format rather than by the one that wrote it.
    machine_id, _exchange = _image_rig(rig)
    source = rig.path("JOB.BAT")
    with open(source, "wb") as handle:
        handle.write(b"ECHO hello\r\n")
    assert put_file(source, r"C:\JOB.BAT", machine=machine_id,
                    context=rig.home) == r"C:\JOB.BAT"
    back = rig.path("back.bat")
    get_file(r"C:\JOB.BAT", back, machine=machine_id, context=rig.home)
    with open(back, "rb") as handle:
        assert handle.read() == b"ECHO hello\r\n"
    assert _problems(rig, machine_id) == []


def test_a_write_creates_the_directories_its_address_names(rig):
    machine_id, _exchange = _image_rig(rig)
    source = rig.path("R.TXT")
    with open(source, "wb") as handle:
        handle.write(b"deep")
    put_file(source, r"C:\OUT\LOGS\R.TXT", machine=machine_id,
             context=rig.home)
    listed = list_files(r"C:\OUT\LOGS", machine=machine_id,
                        context=rig.home)
    assert [entry["address"] for entry in listed] == [r"C:\OUT\LOGS\R.TXT"]
    assert _problems(rig, machine_id) == []


def test_a_name_the_guest_could_not_type_is_refused(rig):
    # 8.3 or nothing: a silently truncated name would land
    # somewhere the caller never addressed (P11, P17).
    machine_id, _exchange = _image_rig(rig)
    source = rig.path("long.txt")
    with open(source, "wb") as handle:
        handle.write(b"x")
    with pytest.raises(PreflightError) as caught:
        put_file(source, r"C:\RESULTS.TAR.GZ", machine=machine_id,
                 context=rig.home)
    assert caught.value.rule_id == "drive.image-unreadable"
    assert "8.3" in str(caught.value)


def test_a_backend_that_cannot_rebuild_an_image_refuses_the_write(rig):
    with fake_backend.installed(capabilities=Capabilities(
            backend="qemu",
            control_planes=("agentless-display",),
            media=("floppy", "hdd", "cdrom"),
            controllers=("ide",),
            materialize=("new", "difference", "copy", "use"),
            vvfat=True, at_rest=True)) as adapter:
        adapter.image_payload = fat_image.volume({"A.TXT": b"a"})
        machine_id = rig.create(
            "read-only", {"platform": "dos", "drives": {"hdd0": "blank"}},
            media=[_BLANK])
        source = rig.path("X.TXT")
        with open(source, "wb") as handle:
            handle.write(b"x")
        with pytest.raises(PreflightError) as caught:
            put_file(source, r"C:\X.TXT", machine=machine_id,
                     context=rig.home)
    assert caught.value.rule_id == "drive.no-at-rest-write"


def test_the_original_image_is_untouched_when_a_write_fails(rig):
    # The safety property the scratch copy buys: a refusal partway
    # through leaves the machine's disk exactly as it was.
    machine_id, _exchange = _image_rig(rig)
    image = rig.state(machine_id)["drives"]["hdd0"]["path"]
    with open(image, "rb") as handle:
        before = handle.read()
    source = rig.path("X.TXT")
    with open(source, "wb") as handle:
        handle.write(b"x")
    with pytest.raises(PreflightError):
        put_file(source, r"C:\NOT A NAME.TXT", machine=machine_id,
                 context=rig.home)
    with open(image, "rb") as handle:
        assert handle.read() == before


def test_a_backend_that_cannot_flatten_its_images_says_so(rig):
    # Capability honesty at the seam: an adapter reporting no
    # at-rest access is refused before anything is copied, and the
    # message names the backend (P11).
    with fake_backend.installed(capabilities=Capabilities(
            backend="qemu",
            control_planes=("agentless-display",),
            media=("floppy", "hdd", "cdrom"),
            controllers=("ide",),
            materialize=("new", "difference", "copy", "use"),
            vvfat=True)) as adapter:
        adapter.image_payload = fat_image.volume({"A.TXT": b"a"})
        machine_id = rig.create(
            "opaque", {"platform": "dos", "drives": {"hdd0": "blank"}},
            media=[_BLANK])
        with pytest.raises(PreflightError) as caught:
            list_files("C:\\", machine=machine_id, context=rig.home)
    assert caught.value.rule_id == "drive.no-at-rest-access"
    assert "qemu" in str(caught.value)


def _two_volumes():
    return fat_image.partitioned([
        fat_image.volume({"ONE.TXT": b"1"}, bits=16, sectors=20000,
                         per_cluster=4),
        fat_image.volume({"TWO.TXT": b"2"}, bits=16, sectors=20000,
                         per_cluster=4)])


def test_a_disk_holding_two_volumes_gives_each_its_own_letter(rig):
    """D71's defect, closed end to end.

    Two volumes on one disk used to be refused, because the letter
    map assumed one and could not say which letter the second
    took. It reads the count now, so both are addressable and
    each answers for itself.
    """
    rig.backend.image_payload = _two_volumes()
    machine_id = rig.create(
        "two-volumes", {"platform": "dos", "drives": {"hdd0": "blank"}},
        media=[_BLANK])
    assert [entry["name"] for entry in
            list_files("C:\\", machine=machine_id, context=rig.home)] == [
        "ONE.TXT"]
    assert [entry["name"] for entry in
            list_files("D:\\", machine=machine_id, context=rig.home)] == [
        "TWO.TXT"]


def test_a_volume_count_is_recorded_and_cleared_by_a_start(rig):
    """The cache and its invalidation, which is what makes reading
    the disk affordable *and* correct: a guest can only repartition
    while it runs, so a count cannot outlive the boot after it."""
    machine_id, _exchange = _image_rig(rig)
    list_files("C:\\", machine=machine_id, context=rig.home)
    assert rig.state(machine_id)["drives"]["hdd0"]["volumes"] == 1
    start_machine(machine_id=machine_id, context=rig.home)
    assert "volumes" not in rig.state(machine_id)["drives"]["hdd0"]


def test_an_undeclared_letter_names_the_ones_that_exist(rig):
    # The disk is readable here on purpose: a letter nothing could
    # ever take is a different failure from one reliquary cannot
    # place, and this asserts the first.
    machine_id, _exchange = _image_rig(rig)
    with pytest.raises(PreflightError) as caught:
        get_file(r"Z:\X.TXT", rig.path("x"), machine=machine_id,
                 context=rig.home)
    assert "no drive at Z:" in str(caught.value)
    assert "A:" in str(caught.value)


def test_an_address_may_not_escape_its_drive(rig):
    machine_id, _exchange = _exchange_rig(rig)
    with pytest.raises(StaticError):
        get_file(r"A:\..\..\secret.txt", rig.path("x"),
                 machine=machine_id, context=rig.home)


def test_a_host_path_is_not_a_guest_address(rig):
    machine_id, _exchange = _exchange_rig(rig)
    with pytest.raises(StaticError) as caught:
        get_file("/etc/passwd", rig.path("x"), machine=machine_id,
                 context=rig.home)
    assert "is not a DOS path" in str(caught.value)


def test_a_missing_guest_file_fails_closed(rig):
    machine_id, _exchange = _exchange_rig(rig)
    with pytest.raises(PreflightError) as caught:
        get_file(r"A:\ABSENT.TXT", rig.path("x"), machine=machine_id,
                 context=rig.home)
    assert r"A:\ABSENT.TXT" in str(caught.value)


# --- the drive report (D83): the record, its refresh, and the map ----

def _geo(rig, drives=None, media=None):
    return rig.create(
        "geo", {"platform": "dos", "drives": drives or {"hdd0": "blank"}},
        media=media or [_BLANK])


def _entry(report, key):
    return next(drive for drive in report["drives"] if drive["key"] == key)


def test_a_create_records_nothing_and_describe_reads_once(rig):
    """The one automatic read outside a start: no record yet, the
    machine down, and the report user-requested — the window
    between create and first start (D83)."""
    rig.backend.image_payload = _two_volumes()
    machine_id = _geo(rig)
    drive = rig.state(machine_id)["drives"]["hdd0"]
    assert "geometry" not in drive
    assert "volumes" not in drive
    report = describe_drives(machine=machine_id, context=rig.home)
    assert not report["recorded"]
    record = _entry(report, "hdd0")["geometry"]
    assert record["backing"] == "raw"
    assert record["partitioned"]
    assert [volume["filesystem"] for volume in record["volumes"]] == [
        "FAT16", "FAT16"]
    assert [entry["declares"] for entry in record["partitions"]] == [
        "FAT16B", "FAT16B"]
    drive = rig.state(machine_id)["drives"]["hdd0"]
    assert drive["volumes"] == 2
    assert "geometry" in drive


def test_a_start_reads_this_boots_starting_state(rig):
    """The automatic read is the first step of a start (D83), so
    the record a running machine answers from describes what the
    guest actually booted from — not what create materialized."""
    rig.backend.image_payload = fat_image.volume(
        {"A.TXT": b"a"}, bits=16, sectors=20000, per_cluster=4)
    machine_id = _geo(rig)
    path = rig.state(machine_id)["drives"]["hdd0"]["path"]
    with open(path, "wb") as handle:
        handle.write(_two_volumes())
    start_machine(machine_id, context=rig.home)
    record = rig.state(machine_id)["drives"]["hdd0"]["geometry"]
    assert len(record["volumes"]) == 2


def test_an_offline_describe_stands_on_the_record(rig):
    """A recorded disk is not re-read by describe: a layout
    changed behind the record waits for the next start, or for
    an explicit refresh (D83)."""
    rig.backend.image_payload = _two_volumes()
    machine_id = _geo(rig)
    describe_drives(machine=machine_id, context=rig.home)
    path = rig.state(machine_id)["drives"]["hdd0"]["path"]
    with open(path, "wb") as handle:
        handle.write(b"\x01" * 4096)
    report = describe_drives(machine=machine_id, context=rig.home)
    assert report["recorded"]
    record = _entry(report, "hdd0")["geometry"]
    assert len(record["volumes"]) == 2


def test_refresh_rereads_and_is_stopped_only(rig):
    rig.backend.image_payload = _two_volumes()
    machine_id = _geo(rig)
    describe_drives(machine=machine_id, context=rig.home)
    path = rig.state(machine_id)["drives"]["hdd0"]["path"]
    with open(path, "wb") as handle:
        handle.write(b"\x01" * 4096)
    report = refresh_drives(machine=machine_id, context=rig.home)
    assert not report["recorded"]
    unread = _entry(report, "hdd0")["geometry"]["unread"]
    assert unread["id"] == "drive.image-unreadable"
    rig.force(machine_id, "running", vm=True)
    with pytest.raises(PreflightError) as caught:
        refresh_drives(machine=machine_id, context=rig.home)
    assert caught.value.rule_id == "machine.must-be-stopped"


def test_the_report_maps_letters_from_the_records(rig):
    rig.backend.image_payload = _two_volumes()
    machine_id = _geo(rig, drives={"floppy0": None, "hdd0": "blank"})
    report = describe_drives(machine=machine_id, context=rig.home)
    assert not report["recorded"]
    assert report["platform"] == "dos"
    assert report["mapping"]["letters"] == {
        "A": {"drive": "floppy0", "volume": 0},
        "C": {"drive": "hdd0", "volume": 0},
        "D": {"drive": "hdd0", "volume": 1}}
    assert report["mapping"]["undetermined"] == []


def test_the_lazy_read_reports_an_unreadable_disk(rig):
    rig.backend.image_payload = _two_volumes()
    machine_id = _geo(rig)
    path = rig.state(machine_id)["drives"]["hdd0"]["path"]
    with open(path, "wb") as handle:
        handle.write(b"\x01" * 4096)
    report = describe_drives(machine=machine_id, context=rig.home)
    assert not report["recorded"]
    unread = _entry(report, "hdd0")["geometry"]["unread"]
    assert unread["id"] == "drive.image-unreadable"
    assert [entry["drive"]
            for entry in report["mapping"]["undetermined"]] == ["hdd0"]


def test_a_running_machine_answers_from_the_record(rig):
    rig.backend.image_payload = _two_volumes()
    machine_id = _geo(rig)
    start_machine(machine_id, context=rig.home)
    path = rig.state(machine_id)["drives"]["hdd0"]["path"]
    # The disk changes under the record; a running machine's
    # report must answer from the record, not the disk.
    with open(path, "wb") as handle:
        handle.write(b"\x01" * 4096)
    report = describe_drives(machine=machine_id, context=rig.home)
    assert report["recorded"]
    assert report["phase"] == "running"
    record = _entry(report, "hdd0")["geometry"]
    assert len(record["volumes"]) == 2
    assert report["mapping"]["letters"]["C"] == {"drive": "hdd0",
                                                 "volume": 0}


def test_a_start_drops_the_count_and_keeps_the_record(rig):
    rig.backend.image_payload = _two_volumes()
    machine_id = _geo(rig)
    start_machine(machine_id, context=rig.home)
    drive = rig.state(machine_id)["drives"]["hdd0"]
    assert "volumes" not in drive
    assert "geometry" in drive


def test_a_blocking_disk_answers_for_the_drives_behind_it(rig):
    rig.backend.image_payload = fat_image.volume(
        {"A.TXT": b"a"}, bits=16, sectors=20000, per_cluster=4)
    machine_id = _geo(rig, drives={"hdd0": "blank", "hdd1": "blank2"},
                      media=[_BLANK, dict(_BLANK, name="blank2")])
    path = rig.state(machine_id)["drives"]["hdd0"]["path"]
    with open(path, "wb") as handle:
        handle.write(b"\x01" * 4096)
    report = describe_drives(machine=machine_id, context=rig.home)
    undetermined = report["mapping"]["undetermined"]
    assert [entry["drive"] for entry in undetermined] == ["hdd0", "hdd1"]
    assert undetermined[0]["id"] == "drive.image-unreadable"
    # The drive behind the blocker carries the blocker's reason,
    # not its own absence — the specific cause outranks the
    # symptom (P11).
    assert undetermined[1]["id"] == "drive.image-unreadable"
    assert "hdd0" in undetermined[1]["reason"]
    assert report["mapping"]["letters"] == {}


def test_a_directory_disk_reports_its_backing_unread(rig):
    exchange = rig.path("exchange")
    os.makedirs(exchange)
    machine_id = _geo(rig, drives={"hdd0": "exchange-dir"},
                      media=[{"name": "exchange-dir", "materialize": "use",
                              "location": {"local": exchange}}])
    report = describe_drives(machine=machine_id, context=rig.home)
    record = _entry(report, "hdd0")["geometry"]
    assert record["backing"] == "directory"
    assert record["volumes"] == [
        {"index": 0, "filesystem": None, "label": None,
         "size": None, "heads": None, "sectors-per-track": None}]
    assert report["mapping"]["letters"] == {
        "C": {"drive": "hdd0", "volume": 0}}


# --- listing and whole-tree transfer, the two P16 owed (F23) ---------

def test_a_listing_reports_one_level_in_guest_terms(rig):
    machine_id, exchange = _exchange_rig(rig)
    _place(os.path.join(exchange, "JOB.BAT"), "ECHO")
    _place(os.path.join(exchange, "OUT", "RESULT.TXT"), "PASS")
    entries = list_files("A:\\", machine=machine_id, context=rig.home)
    assert entries == [
        {"address": r"A:\JOB.BAT", "name": "JOB.BAT",
         "kind": "file", "size": 4},
        {"address": r"A:\OUT", "name": "OUT",
         "kind": "directory", "size": None}]


def test_a_recursive_listing_walks_the_tree(rig):
    machine_id, exchange = _exchange_rig(rig)
    _place(os.path.join(exchange, "OUT", "RESULT.TXT"), "PASS")
    addresses = [entry["address"] for entry
                 in list_files("A:\\", recursive=True, machine=machine_id,
                               context=rig.home)]
    assert addresses == [r"A:\OUT", r"A:\OUT\RESULT.TXT"]


def test_a_listed_address_is_one_get_file_takes(rig):
    # The point of reporting full addresses: no consumer composes
    # a guest path of its own (P17).
    machine_id, exchange = _exchange_rig(rig)
    _place(os.path.join(exchange, "OUT", "RESULT.TXT"), "PASS")
    entry = list_files(r"A:\OUT", machine=machine_id, context=rig.home)[0]
    target = rig.path("result.txt")
    get_file(entry["address"], target, machine=machine_id,
             context=rig.home)
    with open(target, encoding="ascii") as handle:
        assert handle.read() == "PASS"


def test_listing_a_file_says_it_is_a_file(rig):
    machine_id, exchange = _exchange_rig(rig)
    _place(os.path.join(exchange, "JOB.BAT"))
    with pytest.raises(PreflightError) as caught:
        list_files(r"A:\JOB.BAT", machine=machine_id, context=rig.home)
    assert "is a file, not a directory" in str(caught.value)


def test_a_missing_guest_directory_is_not_an_empty_listing(rig):
    machine_id, _exchange = _exchange_rig(rig)
    with pytest.raises(PreflightError) as caught:
        list_files(r"A:\ABSENT", machine=machine_id, context=rig.home)
    assert r"A:\ABSENT" in str(caught.value)


def test_a_put_places_the_trees_contents_at_the_address(rig):
    machine_id, exchange = _exchange_rig(rig)
    source = rig.path("suite")
    _place(os.path.join(source, "RUN.BAT"), "GO")
    _place(os.path.join(source, "CASES", "ONE.DAT"), "1")
    written = put_files(source, "A:\\", machine=machine_id,
                        context=rig.home)
    assert written == [r"A:\CASES\ONE.DAT", r"A:\RUN.BAT"]
    with open(os.path.join(exchange, "CASES", "ONE.DAT"),
              encoding="ascii") as handle:
        assert handle.read() == "1"


def test_a_put_makes_the_guest_directory_it_names(rig):
    # put_file already creates the directories its address names,
    # so the plural verb refusing to would be arbitrary.
    machine_id, exchange = _exchange_rig(rig)
    source = rig.path("suite")
    _place(os.path.join(source, "RUN.BAT"), "GO")
    written = put_files(source, r"A:\NEW\DEEP", machine=machine_id,
                        context=rig.home)
    assert written == [r"A:\NEW\DEEP\RUN.BAT"]
    assert os.path.isfile(os.path.join(exchange, "NEW", "DEEP", "RUN.BAT"))


def test_a_get_retrieves_the_whole_tree(rig):
    machine_id, exchange = _exchange_rig(rig)
    _place(os.path.join(exchange, "OUT", "RESULT.TXT"), "PASS")
    _place(os.path.join(exchange, "OUT", "LOGS", "RUN.LOG"), "ok")
    target = rig.path("results")
    written = get_files(r"A:\OUT", target, machine=machine_id,
                        context=rig.home)
    assert written == sorted([os.path.join(target, "LOGS", "RUN.LOG"),
                              os.path.join(target, "RESULT.TXT")])
    with open(os.path.join(target, "LOGS", "RUN.LOG"),
              encoding="ascii") as handle:
        assert handle.read() == "ok"


def test_a_get_overwrites_rather_than_mirroring(rig):
    # A copy, never a mirror: what was already at the destination
    # and is not in the guest survives.
    machine_id, exchange = _exchange_rig(rig)
    _place(os.path.join(exchange, "OUT", "RESULT.TXT"), "NEW")
    target = rig.path("results")
    _place(os.path.join(target, "RESULT.TXT"), "OLD")
    _place(os.path.join(target, "MINE.TXT"), "keep")
    get_files(r"A:\OUT", target, machine=machine_id, context=rig.home)
    with open(os.path.join(target, "RESULT.TXT"),
              encoding="ascii") as handle:
        assert handle.read() == "NEW"
    assert os.path.isfile(os.path.join(target, "MINE.TXT"))


def test_a_running_machine_is_refused_by_a_listing(rig):
    machine_id, _exchange = _exchange_rig(rig)
    rig.force(machine_id, "running", vm=True)
    with pytest.raises(PreflightError) as caught:
        list_files("A:\\", machine=machine_id, context=rig.home)
    assert "must be stopped" in str(caught.value)


def test_an_image_drive_lists_and_retrieves_at_rest(rig):
    # The two read verbs over a drive image, in guest terms: the
    # listing's addresses are what get-files takes back.
    rig.backend.image_payload = fat_image.volume(
        {"AUTOEXEC.BAT": b"@ECHO OFF\r\n",
         "OUT": {"RESULT.LOG": b"pass\r\n"}})
    machine_id, _exchange = _exchange_rig(rig)
    listed = list_files("C:\\", machine=machine_id, context=rig.home)
    assert [entry["address"] for entry in listed] == [
        r"C:\AUTOEXEC.BAT", r"C:\OUT"]
    assert listed[0]["size"] == 11
    assert listed[1]["size"] is None
    deep = list_files("C:\\", recursive=True, machine=machine_id,
                      context=rig.home)
    assert r"C:\OUT\RESULT.LOG" in [entry["address"] for entry in deep]
    out = rig.path("retrieved")
    written = get_files("C:\\", out, machine=machine_id, context=rig.home)
    assert sorted(os.path.relpath(path, out) for path in written) == [
        "AUTOEXEC.BAT", os.path.join("OUT", "RESULT.LOG")]


def test_a_whole_tree_is_written_into_an_image(rig):
    rig.backend.image_payload = fat_image.volume({"A.TXT": b"a"})
    machine_id, _exchange = _exchange_rig(rig)
    suite = rig.path("suite")
    os.makedirs(os.path.join(suite, "CASES"))
    for path, text in ((os.path.join(suite, "RUN.BAT"), b"GO\r\n"),
                       (os.path.join(suite, "CASES", "ONE.TXT"), b"1")):
        with open(path, "wb") as handle:
            handle.write(text)
    written = put_files(suite, "C:\\", machine=machine_id,
                        context=rig.home)
    assert written == [r"C:\CASES\ONE.TXT", r"C:\RUN.BAT"]
    listed = [entry["address"] for entry in
              list_files("C:\\", recursive=True, machine=machine_id,
                         context=rig.home)]
    assert listed == [r"C:\A.TXT", r"C:\CASES", r"C:\CASES\ONE.TXT",
                      r"C:\RUN.BAT"]
    path = rig.state(machine_id)["drives"]["hdd0"]["path"]
    with open(path, "rb") as handle:
        assert fat_image.consistency(handle.read()) == []


def test_a_missing_host_directory_fails_closed(rig):
    machine_id, _exchange = _exchange_rig(rig)
    with pytest.raises(PreflightError) as caught:
        put_files(rig.path("absent"), "A:\\", machine=machine_id,
                  context=rig.home)
    assert "no such directory" in str(caught.value)


def test_a_host_destination_that_is_a_file_fails_closed(rig):
    machine_id, exchange = _exchange_rig(rig)
    _place(os.path.join(exchange, "OUT", "RESULT.TXT"))
    target = rig.path("results")
    _place(target)
    with pytest.raises(PreflightError) as caught:
        get_files(r"A:\OUT", target, machine=machine_id, context=rig.home)
    assert "is a file" in str(caught.value)


def test_a_directory_address_may_not_escape_its_drive(rig):
    machine_id, _exchange = _exchange_rig(rig)
    with pytest.raises(StaticError):
        list_files(r"A:\..\..", machine=machine_id, context=rig.home)


# --- the letter map comes from declared facts alone (P10/P17) --------

def test_mixed_controller_types_unfix_every_disk_letter():
    """The second thing that unfixes a letter, after volume count.

    Slot order is authoritative only within a controller type;
    across types the guest's firmware decides how the controllers
    enumerate, so even the *first* disk is not a declared fact.
    Unreachable today — only `ide` is wired — which is exactly why
    it is asserted here rather than left to the capability gate.
    """
    drives = {
        "floppy0": {"medium": "floppy", "slot": 0},
        "hdd0": {"medium": "hdd", "slot": 0, "controller": "ide"},
        "hdd1": {"medium": "hdd", "slot": 1, "controller": "scsi"},
    }
    counts = {"hdd0": 1, "hdd1": 1}
    assert platform_dos.drive_letters(drives, counts) == {
        "A": ("floppy0", 0)}
    # Both disks, named as undetermined rather than absent.
    assert platform_dos.undetermined_letters(drives, counts) == [
        "hdd0", "hdd1"]


def test_one_controller_type_places_every_disk():
    # The guard must not fire on the single-type machines that
    # actually exist, floppies carrying no controller field.
    drives = {
        "floppy0": {"medium": "floppy", "slot": 0},
        "hdd0": {"medium": "hdd", "slot": 0, "controller": "ide"},
        "hdd1": {"medium": "hdd", "slot": 1, "controller": "ide"},
    }
    assert platform_dos.drive_letters(
        drives, {"hdd0": 1, "hdd1": 1}) == {
        "A": ("floppy0", 0), "C": ("hdd0", 0), "D": ("hdd1", 0)}


def test_every_drive_is_placed_from_the_volumes_each_disk_holds():
    # Disks from C: in slot order, then the CD-ROMs after them,
    # which is the order DOS assigns in.
    drives = {
        "floppy0": {"medium": "floppy", "slot": 0},
        "floppy1": {"medium": "floppy", "slot": 1},
        "hdd0": {"medium": "hdd", "slot": 0},
        "hdd1": {"medium": "hdd", "slot": 1},
        "cdrom0": {"medium": "cdrom", "slot": 0},
    }
    counts = {"hdd0": 1, "hdd1": 1}
    assert platform_dos.drive_letters(drives, counts) == {
        "A": ("floppy0", 0), "B": ("floppy1", 0), "C": ("hdd0", 0),
        "D": ("hdd1", 0), "E": ("cdrom0", 0)}
    assert platform_dos.undetermined_letters(drives, counts) == []


def test_a_disk_of_two_volumes_takes_two_letters():
    """D71's defect, closed: the count places the letters.

    Under the assumption this returned C: and D: for the two
    disks, which is what a guest that repartitioned `hdd0` made
    silently wrong. Both volumes of `hdd0` are now addressable and
    `hdd1` is where DOS actually puts it.
    """
    drives = {
        "hdd0": {"medium": "hdd", "slot": 0},
        "hdd1": {"medium": "hdd", "slot": 1},
        "cdrom0": {"medium": "cdrom", "slot": 0},
    }
    assert platform_dos.drive_letters(
        drives, {"hdd0": 2, "hdd1": 1}) == {
        "C": ("hdd0", 0), "D": ("hdd0", 1), "E": ("hdd1", 0),
        "F": ("cdrom0", 0)}


def test_an_unpartitioned_disk_takes_no_letter():
    """DOS gives letters to volumes, not to disks.

    A blank reliquary just materialized holds nothing until a
    guest partitions it, so the drive behind it is C: — which the
    one-volume-per-disk assumption used to call D:.
    """
    drives = {
        "hdd0": {"medium": "hdd", "slot": 0},
        "hdd1": {"medium": "hdd", "slot": 1},
    }
    assert platform_dos.drive_letters(
        drives, {"hdd0": 0, "hdd1": 1}) == {"C": ("hdd1", 0)}


def test_a_disk_whose_volumes_are_unknown_stops_the_walk():
    """An unreadable disk moves everything behind it by an unknown
    amount, so nothing behind it is placed rather than guessed."""
    drives = {
        "hdd0": {"medium": "hdd", "slot": 0},
        "hdd1": {"medium": "hdd", "slot": 1},
        "floppy0": {"medium": "floppy", "slot": 0},
    }
    assert platform_dos.drive_letters(drives, {"hdd1": 1}) == {
        "A": ("floppy0", 0)}
    assert platform_dos.undetermined_letters(drives, {"hdd1": 1}) == [
        "hdd0", "hdd1"]


def test_cdroms_are_determined_when_no_hard_disk_shifts_them():
    # With no disk to carry volumes, nothing can move a cdrom's
    # letter, so they follow the floppies and are knowable.
    drives = {
        "floppy0": {"medium": "floppy", "slot": 0},
        "cdrom0": {"medium": "cdrom", "slot": 0},
        "cdrom1": {"medium": "cdrom", "slot": 1},
    }
    assert platform_dos.drive_letters(drives) == {
        "A": ("floppy0", 0), "C": ("cdrom0", 0), "D": ("cdrom1", 0)}
    assert platform_dos.undetermined_letters(drives) == []


def test_a_cdrom_takes_c_when_there_is_no_hard_disk():
    letters = platform_dos.drive_letters(
        {"cdrom0": {"medium": "cdrom", "slot": 0}})
    assert letters == {"C": ("cdrom0", 0)}


def test_a_cdrom_follows_the_disk_it_sits_behind():
    drives = {
        "hdd0": {"medium": "hdd", "slot": 0},
        "cdrom0": {"medium": "cdrom", "slot": 0},
    }
    counts = {"hdd0": 1}
    assert platform_dos.drive_letters(drives, counts) == {
        "C": ("hdd0", 0), "D": ("cdrom0", 0)}
    assert platform_dos.undetermined_letters(drives, counts) == []


def test_an_address_splits_into_letter_and_segments():
    assert platform_dos.split_address(r"c:\DOS\FOO.TXT") == (
        "C", ["DOS", "FOO.TXT"])
    assert platform_dos.split_address("A:BAR.TXT") == ("A", ["BAR.TXT"])


def test_a_drive_with_no_file_is_not_an_address():
    with pytest.raises(StaticError):
        platform_dos.split_address("A:\\")


def test_a_drive_root_is_a_directory_address():
    # The one thing a directory may say that a file may not: the
    # drive itself, spelled either way.
    assert platform_dos.split_directory_address("A:\\") == ("A", [])
    assert platform_dos.split_directory_address("a:") == ("A", [])


def test_a_trailing_separator_is_the_same_directory():
    assert platform_dos.split_directory_address(r"A:\OUT") == (
        platform_dos.split_directory_address("A:\\OUT\\"))


def test_a_directory_address_refuses_dot_segments():
    with pytest.raises(StaticError):
        platform_dos.split_directory_address(r"A:\..\..")


def test_an_address_renders_back_as_the_guest_writes_it():
    # What a listing reports is what the file verbs accept: one
    # vocabulary, not two spellings of it (P17).
    rendered = platform_dos.join_address("A", ["OUT", "RESULT.TXT"])
    assert rendered == r"A:\OUT\RESULT.TXT"
    assert platform_dos.split_address(rendered) == (
        "A", ["OUT", "RESULT.TXT"])


def test_a_non_dos_platform_fails_closed():
    from reliquary.drives import _addressing
    with pytest.raises(PreflightError) as caught:
        _addressing("openbsd")
    assert "openbsd" in str(caught.value)
