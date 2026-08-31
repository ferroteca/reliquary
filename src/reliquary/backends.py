# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The common interface for all four backend adapters.

This is the contract every backend (QEMU, VirtualBox, VMware, Hyper-V)
implements, described in
planning/pledged/design/backend-adapter.md. Nothing here is exposed
directly on the CLI or the embedding API. Callers only reach a backend
through blueprint fields — ``backend``, ``backend-settings`` (each
adapter defines and validates its own keys there), ``control-planes``,
drives, and controllers — and through the capability failures
preflight reports.

The rule this module enforces: a backend must report its capabilities
honestly, never fake one it doesn't have. If a backend can't provide a
drive, controller, materialization mode, or control plane the
blueprint asks for, preflight fails and names exactly what's missing,
rather than approximating it.

This module holds three things that don't belong to any single
backend: the adapter interface (:class:`BackendAdapter`), the
capability vocabulary shared between the report and the requirements,
and **assignment** — the priority walk in :func:`assign` that picks
which backend builds a given machine.
"""

import dataclasses
from typing import Optional, Tuple

from .errors import PreflightError, StaticError


#: The default order backends are tried in (D66, owner 2026-07-28).
#: QEMU and VirtualBox come first because they support agentless
#: display — every guest gets that, since assignment happens at
#: materialization time, before any guest exists, and the install
#: that follows is always agentless at that point (P3's arc). This
#: order only breaks ties among backends that are already available
#: *and* capable of the blueprint; it never substitutes for the
#: capability check itself (P11).
PRIORITY = ("qemu", "virtualbox", "vmware", "hyperv")

#: Where each adapter's class lives. Imported lazily, so naming a
#: backend costs nothing until something actually asks for it.
_ADAPTERS = {
    "qemu": (".backend_qemu", "QemuAdapter"),
    "virtualbox": (".backend_virtualbox", "VirtualBoxAdapter"),
    "vmware": (".backend_stubs", "VMwareAdapter"),
    "hyperv": (".backend_stubs", "HyperVAdapter"),
}

_INSTANCES = {}


@dataclasses.dataclass(frozen=True)
class Availability:
    """What probing the host found for one backend.

    This only reports whether a backend could be used; it never
    picks one and never changes a machine's recorded backend.
    ``executable`` is what the probe found (a binary path, a service
    name); ``home`` is its install directory, when known; ``detail``
    says where it was found, or why it wasn't.
    """

    backend: str
    available: bool
    version: Optional[str] = None
    executable: Optional[str] = None
    home: Optional[str] = None
    detail: str = ""


@dataclasses.dataclass(frozen=True)
class Capabilities:
    """What one backend can do, using the blueprint's own vocabulary.

    The fields use the same terms the blueprint uses
    (docs/spec/blueprint-model.md): control planes, drive media kinds,
    controller types, and media materialization modes.

    Whether a drive or share actually resolves to a directory is only
    known after resolution runs, so that check happens where the
    device is materialized, not at assignment time.
    """

    backend: str
    control_planes: Tuple[str, ...] = ()
    media: Tuple[str, ...] = ()
    controllers: Tuple[str, ...] = ()
    materialize: Tuple[str, ...] = ()
    #: The pointing devices this backend can attach (F66): ``tablet``
    #: or ``mouse``, the blueprint's own terms. Defaults to empty, so
    #: an adapter that hasn't set this claims no pointing devices.
    pointing_devices: Tuple[str, ...] = ()
    #: The NIC models this backend can attach (D120): ``pcnet`` or
    #: ``ne2k``, the blueprint's own terms. Defaults to empty, the
    #: same way ``controllers`` does — an adapter that hasn't set
    #: this claims no network devices.
    network_models: Tuple[str, ...] = ()
    #: The network attachments this backend can provide (D120): ``nat``
    #: or ``bridged``, the blueprint's own terms. Defaults to empty.
    network_attachments: Tuple[str, ...] = ()
    #: The share models this backend can render when a share names one
    #: explicitly (F68): ``vvfat``, ``9pfs``, or ``virtio-fs``. Defaults
    #: to empty, the same way ``controllers`` does.
    #:
    #: These two fields are the first here whose value can depend on
    #: the *installation* rather than on the adapter's own code (F69):
    #: QEMU's live transports are build options, so its adapter probes
    #: the selected binary and reports what it found. One consequence
    #: is worth stating, since it breaks a pattern the rest of this
    #: class keeps: a backend that isn't installed on this host can no
    #: longer answer the share half of "could you build this
    #: blueprint?", because there is no binary to ask. It reports no
    #: live model, which is the honest answer and not a claim that the
    #: backend could never serve one.
    share_models: Tuple[str, ...] = ()
    #: The model an *unstated*-model share resolves to on this backend
    #: (F68) — never ``vvfat``, which only arrives by name (design:
    #: planning/pledged/design/share-devices.md). ``None`` means this
    #: backend cannot serve an unstated-model share: on QEMU, a binary
    #: built without fsdev support, and on VirtualBox, every install
    #: until F71 builds its own mechanism.
    share_default: Optional[str] = None
    #: The RNG models this backend can attach (D125): ``virtio-rng``,
    #: the blueprint's own portable name — never the backend-internal
    #: spelling D91 was overruled for admitting. Defaults to empty, the
    #: same way ``network_models`` does — an adapter that hasn't set
    #: this claims no RNG devices.
    rng_models: Tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Evaluation:
    """The result of checking one backend against one blueprint.

    ``available`` and ``unmet`` answer two separate questions: whether
    this host has the backend installed, and whether the backend
    could build this machine at all. Assignment needs both answers.
    But ``create-machine --dry-run --backend`` only needs the second
    one — it asks whether a blueprint would work on a backend without
    caring if this particular host has it installed — which is why
    the two are kept as separate fields instead of being combined
    into a single pass/fail verdict.
    """

    backend: str
    available: bool
    detail: str = ""
    unmet: Tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Requirements:
    """What a blueprint needs a backend to provide, as a whole.

    Checked against a candidate backend's :class:`Capabilities` at
    assignment time. The check covers the whole blueprint at once,
    never one drive at a time, because a backend is chosen for the
    whole machine, not per drive.
    """

    control_planes: Tuple[str, ...] = ()
    media: Tuple[str, ...] = ()
    controllers: Tuple[str, ...] = ()
    materialize: Tuple[str, ...] = ()
    #: The guest platform this machine declared, or ``None`` when the
    #: caller is asking about a blueprint rather than a machine (F69).
    #: This isn't a requirement the way the fields around it are —
    #: nothing is checked against it. It's here because a backend
    #: whose host tooling differs by guest architecture has to be
    #: asked about the right tool: QEMU installs one system binary per
    #: architecture, and its live share transports are build options,
    #: so which of them exist is a fact about one binary. Passed
    #: straight through to :meth:`BackendAdapter.capabilities`, the
    #: same way :meth:`BackendAdapter.discover` already takes it.
    platform: Optional[str] = None
    #: The machine's pointer device, with the default already filled
    #: in (F66, D124) — never ``None``. Unlike the tuple fields above,
    #: this is a single value, since a machine can declare at most
    #: one pointing device.
    pointing_device: Optional[str] = None
    #: The distinct NIC models this machine's ``network`` slots need
    #: (D120): the platform-resolved chipset, never authored directly
    #: — the same shape ``controllers`` already uses.
    network_models: Tuple[str, ...] = ()
    #: The distinct attachments this machine's ``network`` slots
    #: declare (D120): ``nat`` and/or ``bridged``.
    network_attachments: Tuple[str, ...] = ()
    #: The distinct share models this machine's enabled shares name
    #: explicitly (F68) — never includes an unstated one; see
    #: ``share_unstated`` for that.
    share_models: Tuple[str, ...] = ()
    #: Whether any enabled share left ``model`` unstated (F68). An
    #: unstated share needs the assigned backend's own live default,
    #: so this is checked against ``share_default``, not
    #: ``share_models`` — the two ask different questions.
    share_unstated: bool = False
    #: The distinct RNG models this machine's ``devices`` declare
    #: (D125) — never includes an absent one, the same way
    #: ``network_models`` never speaks for a machine with no NIC.
    rng_models: Tuple[str, ...] = ()


class BackendAdapter:
    """The operations every backend must provide, or explicitly refuse.

    Subclasses implement the methods below that raise
    ``NotImplementedError``. :meth:`unmet` is shared by all of them,
    since comparing a requirement against a capability report is the
    same math for every backend, not something each one computes on
    its own.

    The methods are grouped into: discovery, capability report,
    materialize and dispose, start / stop / liveness, and the
    carriers a session exposes. Converting a drive to or from a raw
    image file belongs to this same list of operations but isn't
    implemented here — it will live with the exporter feature that
    needs it, which hasn't been built yet.
    """

    #: The blueprint's spelling of this backend.
    name = ""

    #: The keys this backend's ``backend-settings`` section may carry.
    #: Each adapter defines its own keys, because that section is
    #: written in the backend's own configuration language and no
    #: shared code can judge it. Defaults to empty: an adapter that
    #: reads no settings rejects every key, rather than silently
    #: accepting configuration it will never act on (P11).
    settings_keys = ()

    # -- discovery and capability ---------------------------------

    def discover(self, platform=None):
        """Probe the host: is this backend usable, and with which tool?

        ``platform`` is the guest platform of the machine about to
        start, or ``None`` for a plain availability check. If a
        backend's host tooling differs by guest architecture — QEMU
        ships one system binary per architecture — this checks for
        the specific binary that machine will actually use, so
        preflight can never pass by checking one binary and then
        launch a different one. A backend with only one host tool
        ignores ``platform``.
        """
        raise NotImplementedError

    def capabilities(self, platform=None):
        """What this backend can do, using the blueprint's vocabulary.

        ``platform`` is the guest platform of the machine being
        judged, or ``None`` when the question isn't about one
        particular machine. It exists for the same reason
        :meth:`discover` takes it: a backend whose host tooling
        differs by guest architecture reports what *that* tool can do,
        not what some other one can (F69 — QEMU's live share
        transports are build options, so the answer differs between
        two binaries of the same install). A backend with one tool
        ignores it.
        """
        raise NotImplementedError

    def capture_format(self, plane):
        """The pixel format this plane's screen carrier captures, or None.

        Returns ``None`` by default, meaning this plane doesn't read a
        framebuffer at all, so preflight refuses any landmark
        condition run against it, naming the reason (F65). QEMU's
        agentless-display plane returns ``None`` because it reads
        characters the guest has already resolved out of VGA text
        memory — there are no pixels to compare there. The VNC plane
        and VirtualBox's display plane both return a format, because
        both read an actual captured framebuffer that a matcher can
        compare pixel-by-pixel.

        This reports a format rather than a plain yes/no because
        ``docs/spec/landmarks.md`` normalizes the reference image
        through that same format before comparing, so an asset
        captured on one plane still matches correctly on another
        plane whose capture uses fewer bits per pixel (a 16-bit
        thumbnail, for example). Every plane built so far reports
        ``"rgb"``, so today that normalization is a no-op.

        A session whose plane reports a format offers
        ``framebuffer()``, the method that returns that capture as a
        Pillow image.
        """
        return None

    def pointer_capable(self, plane):
        """Whether this plane can deliver a pointer event at all (F66).

        Returns ``False`` by default. When it's ``False``, a `click`
        against a machine on this plane is refused at preflight,
        naming the reason. This is a different question from
        :meth:`capture_format`: whether the management interface can
        send a pointer event, versus whether `click` has a
        framebuffer to search for its target's position. A plane can
        have one without the other.
        """
        return False

    def unmet(self, requirements):
        """List, by name, which requirements this backend can't meet.

        This is what a preflight failure message quotes, so a refusal
        always names the specific requirement that failed rather than
        just saying something failed.
        """
        report = self.capabilities(requirements.platform)
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
        if (requirements.pointing_device and
                requirements.pointing_device not in report.pointing_devices):
            missing.append(f"pointing device {requirements.pointing_device!r}")
        for model in requirements.network_models:
            if model not in report.network_models:
                missing.append(f"network device {model!r}")
        for attachment in requirements.network_attachments:
            if attachment not in report.network_attachments:
                missing.append(f"network attachment {attachment!r}")
        for model in requirements.share_models:
            if model not in report.share_models:
                missing.append(f"share model {model!r}")
        for model in requirements.rng_models:
            if model not in report.rng_models:
                missing.append(f"rng device {model!r}")
        if requirements.share_unstated and report.share_default is None:
            # No "yet": as of F69 this is as often a fact about the
            # install as about what's built — a QEMU compiled without
            # fsdev support has no live default and never will,
            # whereas VirtualBox's is genuinely unbuilt (F71). The
            # message states the finding, not a guess at the reason.
            missing.append("a share with no stated model (this backend "
                           "has no live default)")
        return tuple(missing)

    def validate_settings(self, settings):
        """Reject a ``backend-settings`` section this backend can't handle.

        Called with the section that matches this machine's assigned
        backend — sections for other backends are ignored — both at
        materialization time and again whenever a changed blueprint
        is applied. If a section passes validation here, start()
        must be able to render it: an adapter whose validation and
        rendering disagreed would accept configuration at create time
        and then silently drop it at start.

        The rule shared by every adapter: any key outside
        :attr:`settings_keys` is rejected, naming the backend. An
        adapter that turns its settings into command-line arguments
        adds its own extra rule on top of that, refusing settings that
        overlap fields Reliquary already owns directly — memory,
        drives, boot order, CPU count, VM identity — since those are
        only expressible through that backend's own configuration
        syntax when they show up in this section.
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
        """The full path, including extension, for a per-machine image.

        Each adapter uses its own native image format — qcow2 for
        QEMU, VDI/VMDK/VHDX for the others — so the machine model
        itself never has to know which extension to use.
        """
        raise NotImplementedError

    def create_image(self, path, *, mode, size=None, base=None):
        """Create one per-machine drive image.

        ``mode`` is the drive's ``materialize`` setting: ``new`` uses
        ``size``, while ``difference`` and ``copy`` use ``base``.
        Returns the path of the image created.
        """
        raise NotImplementedError

    def dispose(self, machine_dir):
        """Remove this backend's own machine object, if it keeps one.

        ``destroy`` deletes the machine's whole directory afterwards,
        so an adapter whose machine object *is* that directory (QEMU)
        has nothing extra to do here.
        """

    # -- start, stop, liveness ------------------------------------

    def start(self, state, *, machine_dir, backend_dir, display=False,
              current=None):
        """Launch the machine and return its verified VM identity.

        ``state`` is the machine's resolved state document. It takes
        in Reliquary's own drive vocabulary and produces backend
        configuration; callers never pass raw backend arguments
        through here. ``current`` is the machine's previously
        recorded identity, or ``None``. If ``current`` is still
        reachable, the launch is refused, so a live VM is never
        orphaned. The record this returns matches what
        :func:`identity` builds, and the machine model saves it as-is,
        together with the phase, in one atomic write.
        """
        raise NotImplementedError

    def stop(self, vm):
        """Power off the identified VM; refuse if identity doesn't match."""
        raise NotImplementedError

    def session(self, vm, cache=None):
        """Yield an identity-verified session over the running VM.

        A context manager. Every carrier (keyboard, screen, and so on)
        is reached through the session, and the session checks the
        recorded identity before it sends any command.

        ``cache`` is the resolved cache root — a plain directory, not
        a :class:`~home.Context` — where an adapter may save things it
        extracts from its own installation on this host
        (``cache/support/<backend>/``, see
        `text_recognize.cached_banks`). It's optional because caching
        only affects speed, never correctness: an adapter given
        ``None`` does the same work, it just doesn't save the result
        for next time.
        """
        raise NotImplementedError


def identity(backend, backend_id, token, endpoint, pid=None):
    """Build the ``vm`` record every adapter uses to identify its VM.

    Every adapter records a VM the same way: the backend name, the
    backend's own machine identifier (``backend-id`` — QEMU's
    readable ``-name``, a VirtualBox machine UUID, a ``.vmx`` path, or
    a Hyper-V VM Id), a per-start ``token`` for cases where the
    connection is an addressable endpoint that can outlive the
    process that created it, and the ``endpoint`` itself, whose shape
    is up to the adapter. Every adapter operation checks this record
    before sending a command; if it doesn't match, the operation
    fails rather than risk touching an unrelated VM.
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
    """The adapter for a backend name, or raise an error naming it."""
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
    """Install an adapter for one backend; returns the one it replaced.

    Used only by tests: it's how the test suite runs the machine model
    against a fake adapter instead of a real hypervisor, the same way
    it runs the credential store against a fake instead of a real
    keyring. Nothing outside a test calls this — assignment and every
    other operation always go through :func:`adapter`.
    """
    previous = _INSTANCES.get(name)
    if instance is None:
        _INSTANCES.pop(name, None)
    else:
        _INSTANCES[name] = instance
    return previous


def discover(backends=None):
    """Probe each backend in priority order and report availability.

    This only reports availability; it never picks a backend or
    changes a machine's recorded one.
    """
    return tuple(adapter(name).discover()
                 for name in (backends or PRIORITY))


def evaluate(name, requirements):
    """Probe one backend and judge it against requirements, without picking it.

    This is the same check :func:`assign` uses internally, exposed on
    its own because a dry run wants only the capability half of the
    answer, not the availability half — even a backend that isn't
    installed on this host can still answer whether it's capable of
    building this machine.
    """
    found = adapter(name)
    probe = found.discover()
    return Evaluation(backend=name, available=probe.available,
                      detail=probe.detail,
                      unmet=found.unmet(requirements))


def assign(requirements, *, declared=None, narrowed=None):
    """Pick the backend a machine materializes on.

    If the blueprint declares a ``backend``, that pins the choice and
    skips the priority walk: only that backend is probed, and
    assignment fails if it's unavailable or can't meet the
    requirements. A ``narrowed`` backend reaches the same single-
    backend check a different way — the blueprint declared no backend,
    but its ``backend-settings`` only has a section for one backend,
    so that's the one this machine is narrowed to — and it fails the
    same way, naming what narrowed it. Otherwise, this walks
    :data:`PRIORITY` in order, probing each backend for availability,
    and picks the first one that's both available **and** capable of
    the whole blueprint. The chosen backend is then recorded in the
    machine state, so the machine stays on it from then on.
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
