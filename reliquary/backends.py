# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The backend adapter seam: one API, four adapters.

The *provider* contract behind Reliquary's semantic surface
(planning/pledged/design/backend-adapter.md). It is deliberately not
one of the world-facing interfaces: no adapter operation appears on
the CLI or in the embedding API, and consumers touch backends only
through blueprint vocabulary (``backend``, ``backend-settings``,
``control-planes``, drives and controllers) and through the
capability failures preflight reports.

The constraint that governs here is honesty: **capabilities are
reported, never emulated**. A backend that cannot provide a declared
drive, controller, materialization mode or control plane fails
capability preflight by name; nothing is silently approximated.

Three things live in this module because none of them is any one
backend's: the adapter contract (:class:`BackendAdapter`), the
capability vocabulary the report and the requirement share, and
**assignment** — the priority walk that picks the backend a machine is
built on.
"""

import dataclasses
from typing import Optional, Tuple

from .errors import PreflightError, StaticError


#: The default assignment order (D66, owner 2026-07-28), ranking
#: *agentless* scriptability — the capability every guest gets,
#: because assignment happens at materialization, before any guest
#: exists, and the install that follows is agentless by definition
#: (P3's arc). It breaks ties among candidates already available *and*
#: capable, so it never stands in for a capability check (P11).
PRIORITY = ("qemu", "virtualbox", "vmware", "hyperv")

#: Where each adapter lives. Imported on demand so that naming a
#: backend costs nothing until one is actually asked for.
_ADAPTERS = {
    "qemu": (".backend_qemu", "QemuAdapter"),
    "virtualbox": (".backend_stubs", "VirtualBoxAdapter"),
    "vmware": (".backend_stubs", "VMwareAdapter"),
    "hyperv": (".backend_stubs", "HyperVAdapter"),
}

_INSTANCES = {}


@dataclasses.dataclass(frozen=True)
class Availability:
    """What a host probe found: availability only, never a choice.

    Discovery establishes that a backend *could* be used; it never
    selects one and never changes a machine's recorded backend.
    ``executable`` is what the probe found (a binary path, a service
    name); ``detail`` says where it was found, or why it was not.
    """

    backend: str
    available: bool
    version: Optional[str] = None
    executable: Optional[str] = None
    detail: str = ""


@dataclasses.dataclass(frozen=True)
class Capabilities:
    """A backend's named-vocabulary capability report.

    The vocabulary is the blueprint's own (docs/spec/blueprint-model.md):
    control planes, drive media kinds, controller types, and media
    materialization modes. ``vvfat`` reports the host-directory drive
    QEMU alone provides — a directory-source media's realized shape,
    which is only knowable after resolution, so it is judged where the
    drive is rendered rather than at assignment.
    """

    backend: str
    control_planes: Tuple[str, ...] = ()
    media: Tuple[str, ...] = ()
    controllers: Tuple[str, ...] = ()
    materialize: Tuple[str, ...] = ()
    vvfat: bool = False
    #: Whether the adapter can hand back a drive image as raw bytes,
    #: which is what at-rest reading of a stopped machine's disk
    #: needs. Reported rather than assumed: an adapter whose format
    #: nothing can flatten says so, and the file verbs refuse by name
    #: instead of guessing at the drive's contents (P11).
    at_rest: bool = False


@dataclasses.dataclass(frozen=True)
class Requirements:
    """What one whole blueprint asks a backend for.

    Judged against a candidate's :class:`Capabilities` at assignment
    time — the whole blueprint at once, never drive by drive, because
    a backend is picked for the machine and not for a drive.
    """

    control_planes: Tuple[str, ...] = ()
    media: Tuple[str, ...] = ()
    controllers: Tuple[str, ...] = ()
    materialize: Tuple[str, ...] = ()


class BackendAdapter:
    """The operations every backend provides, or honestly refuses.

    Subclasses implement the abstract members below; :meth:`unmet` is
    shared, since judging a requirement against a report is the seam's
    own arithmetic and not any backend's.

    The signatures are grouped as the seam inventory names them:
    discovery, capability report, materialize and dispose, start /
    stop / liveness, and the carriers a session exposes. Raw
    interchange (a drive read out as a raw image, a native drive
    materialized from one) belongs to the same inventory but lands
    with the exporter family that needs it, which is unbuilt.
    """

    #: The blueprint's spelling of this backend.
    name = ""

    # -- discovery and capability ---------------------------------

    def discover(self):
        """Probe the host: is this backend usable here, and which?"""
        raise NotImplementedError

    def capabilities(self):
        """The named-vocabulary report this backend can honor."""
        raise NotImplementedError

    def unmet(self, requirements):
        """Requirements this backend cannot honor, named one by one.

        The whole of "reported, never emulated": what comes back is
        the text a preflight failure quotes, so a refusal always says
        which requirement was refused rather than that something was.
        """
        report = self.capabilities()
        missing = []
        for plane in requirements.control_planes:
            if plane not in report.control_planes:
                missing.append(f"control plane {plane!r}")
        for medium in requirements.media:
            if medium not in report.media:
                missing.append(f"{medium} drives")
        for controller in requirements.controllers:
            if controller not in report.controllers:
                missing.append(f"controller {controller!r}")
        for mode in requirements.materialize:
            if mode not in report.materialize:
                missing.append(f"media materialize {mode!r}")
        return tuple(missing)

    # -- materialize and dispose ----------------------------------

    def image_path(self, root, stem):
        """Where a per-machine image for ``stem`` lands, extension and all.

        The adapter owns its native image format (qcow2 under QEMU;
        VDI/VMDK/VHDX elsewhere), so the machine model never spells
        one.
        """
        raise NotImplementedError

    def create_image(self, path, *, mode, size=None, base=None):
        """Materialize one per-machine drive image.

        ``mode`` is the media's ``materialize``: ``new`` takes
        ``size``, ``difference`` and ``copy`` take ``base``. Returns
        the created path.
        """
        raise NotImplementedError

    def dispose(self, machine_dir):
        """Remove the backend's own machine object, if it keeps one.

        ``destroy`` deletes the materialization directory afterwards,
        so an adapter whose whole machine *is* that directory (QEMU)
        has nothing to do here.
        """

    def raw_image(self, path, workspace):
        """The drive image at ``path`` as raw bytes, for reading at rest.

        Returns a path to a raw image: ``path`` itself when the
        adapter's format already is raw, or a flattened copy inside
        ``workspace``, which the caller owns and removes. The native
        format is the adapter's choice (P12's twin at this seam), so
        undoing it is the adapter's job and the portable FAT reader
        above never learns what qcow2 is.

        Only called for a **stopped** machine: a running backend may
        hold the image open, and a copy taken under it would be a
        torn one.
        """
        raise NotImplementedError

    # -- start, stop, liveness ------------------------------------

    def start(self, state, *, machine_dir, backend_dir, display=False,
              current=None):
        """Launch the machine and return its verified VM identity.

        ``state`` is the machine's resolved state document — Reliquary
        drive vocabulary in, backend configuration out; raw backend
        arguments never cross this seam from callers. ``current`` is
        the machine's previously recorded identity (or ``None``): a
        still-reachable one refuses the launch so a live VM is never
        orphaned. The returned record is what :func:`identity`
        describes, and the machine model persists it verbatim,
        atomically with the phase.
        """
        raise NotImplementedError

    def stop(self, vm):
        """Power off the identified VM, fail-closed on identity."""
        raise NotImplementedError

    def session(self, vm):
        """Yield an identity-verified session over the running VM.

        A context manager. Every carrier hangs off the session, and
        every session verifies the recorded identity before it
        commands anything.
        """
        raise NotImplementedError


def identity(backend, backend_id, token, endpoint, pid=None):
    """Build the ``vm`` record every adapter records its VM by.

    The recorded-VM-identity doctrine, generalized: the backend, the
    backend's own machine identifier (``backend-id`` — QEMU's readable
    ``-name``, a VirtualBox machine UUID, a ``.vmx`` path, a Hyper-V VM
    Id), a per-start ``token`` where the carrier is an addressable
    endpoint that outlives its owner, and the ``endpoint`` itself,
    whose shape is the adapter's. Every adapter operation verifies
    this record before commanding; a mismatch fails closed and never
    reaches a stop path.
    """
    record = {
        "backend": backend,
        "backend-id": backend_id,
        "token": token,
        "endpoint": dict(endpoint),
    }
    if pid is not None:
        record["pid"] = pid
    return record


def adapter(name):
    """The adapter for a backend name, or fail closed naming it."""
    if name not in _ADAPTERS:
        known = ", ".join(PRIORITY)
        raise StaticError(
            f"unknown backend {name!r}; the backends are {known}",
            rule_id="machine.backend-unknown")
    if name not in _INSTANCES:
        import importlib
        module_name, class_name = _ADAPTERS[name]
        module = importlib.import_module(module_name, __package__)
        _INSTANCES[name] = getattr(module, class_name)()
    return _INSTANCES[name]


def _set_adapter(name, instance):
    """Install an adapter for one backend; returns the displaced one.

    The test seam, and the only way an adapter other than the four is
    ever reached: the suite drives the machine model against a double
    rather than a hypervisor, exactly as it drives the credential
    store against one rather than a keyring. Nothing outside a test
    calls this — assignment and every operation resolve through
    :func:`adapter`.
    """
    previous = _INSTANCES.get(name)
    if instance is None:
        _INSTANCES.pop(name, None)
    else:
        _INSTANCES[name] = instance
    return previous


def discover(backends=None):
    """Probe each backend in priority order and report availability.

    Availability only: nothing here selects a backend or touches a
    machine's recorded one.
    """
    return tuple(adapter(name).discover()
                 for name in (backends or PRIORITY))


def assign(requirements, *, declared=None):
    """Pick the backend a machine materializes on.

    A declared ``backend`` pins the choice and skips the walk: that
    backend alone is probed, and assignment fails closed if it is
    unavailable or incapable. Otherwise Reliquary walks :data:`PRIORITY`
    one by one, probing each for availability, and takes the first that
    is available **and** capable of the whole blueprint. The result is
    recorded in the machine state, so the machine stays on that backend
    thereafter.
    """
    if declared is not None:
        found = adapter(declared)
        probe = found.discover()
        if not probe.available:
            raise PreflightError(
                f"blueprint pins backend {declared!r}, which is not "
                f"available on this host: {probe.detail}",
                rule_id="machine.backend-unavailable")
        missing = found.unmet(requirements)
        if missing:
            raise PreflightError(
                f"blueprint pins backend {declared!r}, which cannot "
                f"provide: {', '.join(missing)}",
                rule_id="machine.backend-incapable")
        return declared
    refusals = []
    for name in PRIORITY:
        candidate = adapter(name)
        probe = candidate.discover()
        if not probe.available:
            refusals.append(f"  {name}: {probe.detail}")
            continue
        missing = candidate.unmet(requirements)
        if missing:
            refusals.append(f"  {name}: cannot provide "
                            f"{', '.join(missing)}")
            continue
        return name
    raise PreflightError(
        "no available backend can materialize this machine:\n"
        + "\n".join(refusals),
        rule_id="machine.no-capable-backend")
