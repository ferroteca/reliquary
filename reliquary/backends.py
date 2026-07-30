# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The backend adapter seam: one API, four adapters.

The *provider* contract behind Reliquary's semantic surface
(planning/pledged/design/backend-adapter.md). It is deliberately not
one of the world-facing interfaces: no adapter operation appears on
the CLI or in the embedding API, and consumers touch backends only
through blueprint vocabulary (``backend``, ``backend-settings`` —
whose keys each adapter defines and validates — ``control-planes``,
``devices``, drives and controllers) and through the capability
failures preflight reports.

The constraint that governs here is honesty: **capabilities are
reported, never emulated**. A backend that cannot provide a declared
drive, controller, materialization mode, control plane or device fails
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
    control planes, drive media kinds, controller types, media
    materialization modes, and the curated ``devices``. ``vvfat``
    reports the host-directory drive QEMU alone provides — a
    directory-source media's realized shape, which is only knowable
    after resolution, so it is judged where the drive is rendered
    rather than at assignment. **A device is not like that**: it is a
    declared fact from the moment the blueprint is read, so it is
    judged at assignment with the rest of the demand, and an adapter
    that reports one must render it.
    """

    backend: str
    control_planes: Tuple[str, ...] = ()
    media: Tuple[str, ...] = ()
    controllers: Tuple[str, ...] = ()
    materialize: Tuple[str, ...] = ()
    devices: Tuple[str, ...] = ()
    vvfat: bool = False
    #: Whether the adapter can present a drive image as an addressable
    #: device, which is what at-rest reading of a stopped machine's
    #: disk needs. Reported rather than assumed: an adapter whose
    #: format nothing can open says so, and the file verbs refuse by
    #: name instead of guessing at the drive's contents (P11).
    at_rest: bool = False
    #: Whether that access can also be writable, with a commit point
    #: behind it. Split from ``at_rest`` because reading and writing a
    #: disk are different promises: an adapter may be able to open its
    #: own format and have nowhere to stand an undo.
    at_rest_write: bool = False


@dataclasses.dataclass(frozen=True)
class Evaluation:
    """One backend judged against one blueprint's demand.

    Availability and capability are **two answers because they are
    two questions**: whether this host has the backend, and whether
    the backend could build this machine at all. Assignment needs
    both. Asking whether a blueprint would work on a host one is not
    standing on needs the second alone, which is what
    ``create-machine --dry-run --backend`` asks — so the two are
    reported separately rather than collapsed into one verdict.
    """

    backend: str
    available: bool
    detail: str = ""
    unmet: Tuple[str, ...] = ()


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
    devices: Tuple[str, ...] = ()


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

    #: The keys this backend's ``backend-settings`` section may carry.
    #: The adapter owns this vocabulary because the section is written
    #: in the backend's own configuration language and nothing above
    #: the seam can judge it. **Empty is the honest default**: an
    #: adapter that reads no settings refuses every key rather than
    #: carrying configuration nothing will honor (P11).
    settings_keys = ()

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
        for device in requirements.devices:
            if device not in report.devices:
                missing.append(f"device {device!r}")
        return tuple(missing)

    def validate_settings(self, settings):
        """Refuse a ``backend-settings`` section this backend cannot honor.

        Called with **this backend's own section** — the one the
        machine's assigned backend matches, other sections being inert
        — at materialization, and again when a changed blueprint is
        applied. A section that validates is one the launch will
        render: an adapter whose validation and rendering could
        disagree would promise configuration at create time and drop
        it at start.

        The shared rule is the key set: anything outside
        :attr:`settings_keys` is refused, naming the backend. An
        adapter whose settings reach its backend as arguments extends
        this with its own overlap rule, since what Reliquary owns
        through first-class fields (memory, drives, boot order, CPU
        count, identity) is only expressible in that backend's own
        vocabulary.
        """
        unknown = sorted(key for key in (settings or ())
                         if key not in self.settings_keys)
        if not unknown:
            return
        if self.settings_keys:
            known = ", ".join(self.settings_keys)
            detail = f"the {self.name} keys are {known}"
        else:
            detail = (f"the {self.name} adapter reads no settings, so it "
                      "defines no keys")
        raise StaticError(
            f"backend-settings.{self.name} does not define "
            f"{unknown[0]!r}; {detail}",
            rule_id="machine.settings-unknown-key")

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

    def open_drive(self, path, *, writable=False):
        """The drive image at ``path`` as an at-rest **access**.

        The native format is the adapter's choice (P12's twin at this
        seam), so presenting it as addressable bytes is the adapter's
        job and the portable FAT reader above never learns what qcow2
        is. What comes back answers:

        ``device``
            The byte device :mod:`reliquary.at_rest` reads and writes
            through -- ``size`` / ``read_at`` / ``write_at`` /
            ``flush`` / ``close``.
        ``commit()``
            Make the writes permanent. **Atomic from the caller's
            side**: the image is the old one or the new one, never a
            half-written third thing. An adapter whose format carries
            a backing relationship keeps it -- a differencing image is
            still a difference over the same base afterwards.
        ``close()``
            Release everything. A writable access closed **without**
            ``commit()`` puts the image back as it was, so a refused,
            interrupted or crashed write costs nothing.

        **The image is locked for the length of the access**, so
        nothing else writes the disk part-way through. An image
        another process holds is refused by name rather than waited
        for.

        Only called for a **stopped** machine: a running backend holds
        its own lock on the image, and this would be refused by it.
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


def evaluate(name, requirements):
    """Probe one backend and judge it, choosing nothing.

    The judgment :func:`assign` is built from, exposed on its own
    because a dry run asks the capability half without the
    availability half — a backend nothing installed here can still
    answer whether it could build this machine.
    """
    found = adapter(name)
    probe = found.discover()
    return Evaluation(backend=name, available=probe.available,
                      detail=probe.detail,
                      unmet=found.unmet(requirements))


def assign(requirements, *, declared=None, narrowed=None):
    """Pick the backend a machine materializes on.

    A declared ``backend`` pins the choice and skips the walk: that
    backend alone is probed, and assignment fails closed if it is
    unavailable or incapable. A ``narrowed`` one is the same
    walk-of-one reached differently — the blueprint declares no
    backend and carries ``backend-settings`` for exactly one, so the
    sections themselves say where this machine belongs — and it fails
    closed the same way, naming what narrowed it. Otherwise Reliquary
    walks :data:`PRIORITY` one by one, probing each for availability,
    and takes the first that is available **and** capable of the whole
    blueprint. The result is recorded in the machine state, so the
    machine stays on that backend thereafter.
    """
    only = declared if declared is not None else narrowed
    if only is not None:
        subject = (f"the blueprint pins backend {only!r}"
                   if declared is not None else
                   "the blueprint's only backend-settings section "
                   f"narrows assignment to backend {only!r}")
        verdict = evaluate(only, requirements)
        if not verdict.available:
            raise PreflightError(
                f"{subject}, which is not "
                f"available on this host: {verdict.detail}",
                rule_id="machine.backend-unavailable")
        if verdict.unmet:
            raise PreflightError(
                f"{subject}, which cannot "
                f"provide: {', '.join(verdict.unmet)}",
                rule_id="machine.backend-incapable")
        return only
    refusals = []
    for name in PRIORITY:
        verdict = evaluate(name, requirements)
        if not verdict.available:
            refusals.append(f"  {name}: {verdict.detail}")
            continue
        if verdict.unmet:
            refusals.append(f"  {name}: cannot provide "
                            f"{', '.join(verdict.unmet)}")
            continue
        return name
    raise PreflightError(
        "no available backend can materialize this machine:\n"
        + "\n".join(refusals),
        rule_id="machine.no-capable-backend")
