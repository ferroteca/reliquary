# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Where a machine lives, what serializes it, and how one is named.

This module is the foundation the rest of the machine code is built
on: the ids and directories a machine is addressed by, the locks
that serialize work against it, its ``machine.json`` file, and the
selector resolution that turns ``--blueprint`` / ``--machine`` into
one machine id.

This stayed a separate module even after one of its two callers went
away. ``drives.py`` used to be the other caller — it held the drive
report and the "in-band file" family of features — and D108 deleted
it, so ``machines.py`` is now the only caller of most of what is
here. The reason to keep the split is ``machine_handle.py``, which
needs the ``read_vm_state`` function; without this split,
``machine_handle.py`` would be back in an import cycle with
``machines.py``. Phase-transition code has only one caller and stays
in ``machines.py`` instead of moving here: this module holds the
shared foundation, not just anything that happens to have no other
home.

Nothing here knows what a machine *is*. No backend, no adapter, no
drive, no media — just a machine id, a directory, a lock, and a JSON
document.
"""

import contextlib
import json
import os

from .errors import InternalError, PreflightError, StaticError
from .home import machines_dir
from .library import locate_blueprint


def machine_dir_path(machine_id, context=None):
    """Return the machine's cache directory path."""
    return os.path.join(machines_dir(context), machine_id)


def machine_disks_dir(machine_id, context=None):
    """Per-machine directory for materialized images, keyed by media
    item.

    Images are named after the media (``<media-name>.<ext>``), not
    the slot, so different media passing through one removable slot
    each keep their own image, and re-inserting a medium reuses the
    image already built for it.
    """
    return os.path.join(machine_dir_path(machine_id, context), "disks")


def backend_dir(machine_id, backend, context=None):
    """The backend's own subdirectory for its files (``<backend>/``).

    Reliquary keeps each backend's own files in a subdirectory named
    after that backend, so the machine's root directory holds only
    ``machine.json`` plus the ``disks/`` and ``screenshots/``
    directories. For QEMU, this subdirectory holds just the captured
    ``qemu-stderr.log``.
    """
    return os.path.join(machine_dir_path(machine_id, context),
                        backend or "qemu")


def _state_path(machine_id, context=None):
    return os.path.join(machine_dir_path(machine_id, context),
                        "machine.json")


def machine_id_for(blueprint_name, number):
    """Return the canonical machine id for a blueprint and number."""
    return f"{blueprint_name}-{number}"


def split_machine_id(machine_id):
    """Return ``(blueprint_name, number)`` for a well-formed id.

    The number is the trailing decimal after the final ``-``.  Returns
    ``None`` when the id is not ``<blueprint>-<n>``.
    """
    if not isinstance(machine_id, str) or "-" not in machine_id:
        return None
    blueprint, sep, number = machine_id.rpartition("-")
    if not sep or not blueprint or not number.isdigit():
        return None
    if len(number) > 1 and number.startswith("0"):
        return None
    return blueprint, int(number)


def _locks_dir(context=None):
    return os.path.join(machines_dir(context), ".locks")


def _lock_file(handle):
    if os.name == "nt":
        import msvcrt
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                return
            except OSError:
                # LK_LOCK retries ~10s then raises; keep waiting.
                continue
    import fcntl
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_file(handle):
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl
    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def blueprint_alloc_lock(blueprint_name, context=None):
    """Serialize machine-number allocation for one blueprint."""
    lock_root = _locks_dir(context)
    os.makedirs(lock_root, exist_ok=True)
    lock_path = os.path.join(lock_root, f"{blueprint_name}.lock")
    with open(lock_path, "a+b") as handle:
        _lock_file(handle)
        try:
            yield
        finally:
            _unlock_file(handle)


@contextlib.contextmanager
def machine_lock(machine_id, context=None):
    """Hold the exclusive per-machine operation lock.

    Every mutating operation on one machine (create materialization,
    start, stop, destroy, media/boot changes) takes this before
    inspecting or changing backend state, so operations on one
    machine never interleave. The lock file lives beside the
    allocation locks; its ``.op.lock`` suffix keeps it distinct from
    any blueprint's allocation lock.
    """
    lock_root = _locks_dir(context)
    os.makedirs(lock_root, exist_ok=True)
    lock_path = os.path.join(lock_root, f"{machine_id}.op.lock")
    with open(lock_path, "a+b") as handle:
        _lock_file(handle)
        try:
            yield
        finally:
            _unlock_file(handle)


def allocate_machine_id(blueprint_name, context=None):
    """Return the lowest free ``<blueprint>-<n>`` id (directories count)."""
    number = 0
    while True:
        machine_id = machine_id_for(blueprint_name, number)
        if not os.path.exists(machine_dir_path(machine_id, context)):
            return machine_id
        number += 1


def write_state(machine_id, state, context=None):
    path = _state_path(machine_id, context)
    part = path + ".part"
    with open(part, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(part, path)


def read_vm_state(machine_dir):
    """Return a machine's recorded live-VM identity, or ``None``.

    The identity lives in the ``vm`` section of the machine's own
    ``machine.json``, written atomically together with the ``phase``
    field. The fields every VM identity has are: which backend it
    runs on, that backend's own id for the machine, a token generated
    at each start, and an endpoint; what the endpoint actually
    contains is up to that backend's adapter, which checks it is
    valid when it opens a session. A state file with no ``vm``
    section means the machine is stopped and this returns ``None``; a
    ``vm`` section that is malformed raises an error instead of
    returning something invalid.
    """
    path = os.path.join(machine_dir, "machine.json")
    try:
        with open(path, encoding="utf-8") as state_file:
            document = json.load(state_file)
    except FileNotFoundError:
        return None
    except (ValueError, json.JSONDecodeError) as error:
        raise InternalError(
            f"invalid reliquary machine state file: {path}: {error}"
        ) from error
    vm = document.get("vm") if isinstance(document, dict) else None
    if vm is None:
        return None
    fields = (vm.get("backend"), vm.get("backend-id"), vm.get("token"))
    if (not isinstance(vm, dict)
            or not all(isinstance(value, str) and value
                       for value in fields)
            or not isinstance(vm.get("endpoint"), dict)):
        raise InternalError(
            f"invalid reliquary VM state in {path}: a recorded VM names "
            "its backend, that backend's machine id, a per-start token "
            "and an endpoint")
    return vm


def load_machine_state(machine_id, context=None):
    """Read and return the machine's ``machine.json``."""
    path = _state_path(machine_id, context)
    if not os.path.exists(path):
        raise PreflightError(
            f"machine state not found: {path}",
            rule_id="machine.state-missing")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _machine_sort_key(state):
    """Sort by blueprint name, then machine number, then id."""
    machine_id = state.get("id") or ""
    parsed = split_machine_id(machine_id)
    if parsed is not None:
        return (parsed[0], parsed[1], machine_id)
    return (state.get("blueprint") or "", -1, machine_id)


def list_machines(context=None, blueprint=None):
    """Return state dicts for machines under the cache.

    Ordered by blueprint name, then ascending machine number.  When
    ``blueprint`` is set, only machines of that blueprint are returned.
    """
    root = machines_dir(context)
    if not os.path.isdir(root):
        return []
    machines = []
    for entry in os.listdir(root):
        path = os.path.join(root, entry, "machine.json")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
        if state.get("id") != entry:
            raise InternalError(
                f"machine id mismatch: directory {entry!r} "
                f"contains id {state.get('id')!r}")
        if blueprint is not None and state.get("blueprint") != blueprint:
            continue
        machines.append(state)
    machines.sort(key=_machine_sort_key)
    return machines


def resolve_machine(*, machine=None, blueprint=None, context=None):
    """Resolve a ``--machine`` / ``--blueprint`` selector to one id.

    Selectors are mutually exclusive:

    - ``--blueprint NAME``: the sole machine of that blueprint
    - ``--machine NAME-N``: the full machine id, exactly
    """
    if machine is None and blueprint is None:
        raise StaticError(
            "select a machine with --blueprint or --machine",
            rule_id="machine.no-selector")
    if machine is not None and blueprint is not None:
        raise StaticError(
            "--blueprint and --machine are mutually exclusive; "
            "pass --machine <id> or --blueprint <name>",
            rule_id="machine.selectors-conflict")
    if machine is not None:
        return _resolve_by_id(machine, context)
    return _resolve_by_blueprint(blueprint, context)


def _resolve_by_id(selector, context):
    """Resolve a full machine id — exact match only."""
    if not isinstance(selector, str) or not selector:
        raise StaticError(
            f"machine id must be a non-empty string, got: {selector!r}",
            rule_id="machine.id-malformed")
    if selector.isdigit():
        raise StaticError(
            f"machine id must be the full <blueprint>-<n> form, "
            f"got: {selector!r}", rule_id="machine.id-malformed")
    for state in list_machines(context):
        if state["id"] == selector:
            return selector
    raise PreflightError(f"no machine {selector!r}", rule_id="machine.unknown")


def machines_for_blueprint(name, context=None):
    """Machines of blueprint ``name`` scoped to this invocation's source.

    Under the instance model, a machine matches only when its
    recorded ``blueprint-source`` equals what this invocation itself
    resolves ``name`` to, so identically-named blueprints in
    different projects never select each other's machines, and
    ``apply`` never adopts one of them by mistake. A machine with no
    recorded source matches by name alone, since there is nothing to
    compare it against; when ``name`` does not resolve at all in this
    invocation, only such sourceless machines can match. Ordered the
    same way as :func:`list_machines`.
    """
    matches = list_machines(context, blueprint=name)
    try:
        resolved = os.path.abspath(locate_blueprint(name, context=context))
    except PreflightError:
        resolved = None
    scoped = []
    for state in matches:
        source = state.get("blueprint-source")
        if source is None:
            scoped.append(state)
        elif resolved is not None and os.path.abspath(source) == resolved:
            scoped.append(state)
    return scoped


def _resolve_by_blueprint(name, context):
    matches = machines_for_blueprint(name, context)
    if not matches:
        raise PreflightError(
            f"no machine exists for blueprint {name!r}\n"
            f"create one: rlq create-machine --blueprint {name}",
            rule_id="machine.none-for-blueprint")
    if len(matches) > 1:
        lines = [
            f"blueprint {name!r} has {len(matches)} machines; "
            "pick one with --machine <id>:",
        ]
        for state in matches:
            lines.append(f"  {state['id']}  ({state.get('phase', '?')})")
        raise PreflightError("\n".join(lines),
            rule_id="machine.ambiguous-selector")
    return matches[0]["id"]
