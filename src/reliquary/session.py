# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Session: reliquary's working-directory and properties-file config,
resolved once and reused by every call made through it.

P26 requires that every API call that touches reliquary's state goes
through a ``Session``, opened on at least a home directory. When a
``Session`` is constructed, it resolves and stores the six placeable
working directories plus the selected properties file — one
:class:`~reliquary.home.Context` record — from whatever it was opened
on. Every method on ``Session`` is a thin wrapper: it forwards to the
matching function of the same name in one of the engine modules,
passing along the stored ``Context``, and adds no logic of its own.
The actual behavior lives in the engine modules; a ``Session``
method's contract is whatever its underlying engine function's
contract is.

Only functions that touch reliquary's state — resolving a working
directory, reading or writing machine or media state, or reading
config — get a ``Session`` method (P26). Functions that only take
input and produce output, like parsing and validating a document or
script that's handed to them, stay standalone functions instead, so a
tool calling them never needs a home directory just to parse a
string. The codex functions (for the built-in blueprint library)
don't get a ``Session`` method either — using the shipped library is
something only a human does directly from the CLI, which is a named
exception in P6 (D87).

``Session`` is not currently exported from the package root, even
though it's meant to be the primary interface: the root currently
exports the older, function-based surface, and the public surface
will switch over to ``Session`` all at once, later. Using two
separate ``Session`` objects in the same process is fine: constructing
one reads and writes no shared global state, and because each one
stores its own resolved ``Context``, later calls on one don't read
anything from the other.
"""

from . import (authoring, binding, library, machines, media,
               properties, resolve, script_runner)
from .errors import StaticError
from .home import as_context, pinned


class Session:
    """Holds the six working directories and the selected properties
    file, resolved once when constructed, with one thin method per
    state-touching call, each forwarding to its matching engine
    function.

    Can be constructed from either a bare home-directory string or a
    ``Context``, and refuses to construct at all without a home
    directory — the same "dir.unassigned" check that would otherwise
    happen later, moved up to construction time instead. Because an
    assigned home directory lets all six working directories be
    derived, no ``Session`` method can ever find a directory
    unassigned.
    """

    __slots__ = ("_context",)

    def __init__(self, context):
        record = as_context(context)
        if record.home_dir is None:
            # This is the same "no home directory assigned" condition
            # that would otherwise be caught later, on first use;
            # catching it here means it's checked in exactly one
            # place, under one rule_id, regardless of which error
            # class would apply to the eventual use
            # (docs/spec/script-spec.md).
            raise StaticError(
                "a session requires a home\n"
                "  open it on a home directory path, or a Context "
                "assigning home_dir=<path>; every other slot can "
                "derive from it",
                rule_id="dir.unassigned")
        self._context = pinned(record)

    def __repr__(self):
        return "Session(%r)" % (self._context,)

    # The machines lifecycle.

    def create_machine(self, name, *, number=None, properties=None,
                       events=None, dry_run=False, backend=None):
        """Materialize a machine from blueprint ``name``."""
        return machines.create_machine(
            name, context=self._context, number=number,
            properties=properties, events=events, dry_run=dry_run,
            backend=backend)

    def recreate_machine(self, *, machine=None, blueprint=None,
                         properties=None, events=None):
        """Destroy and re-create the selected machine under its id."""
        return machines.recreate_machine(
            machine=machine, blueprint=blueprint, context=self._context,
            properties=properties, events=events)

    def start_machine(self, machine_id, *, display=False, events=None,
                      cancelled=None):
        """Start a created machine and wait for guest readiness."""
        return machines.start_machine(
            machine_id, display=display, context=self._context,
            events=events, cancelled=cancelled)

    def stop_machine(self, machine_id):
        """Stop a running machine."""
        return machines.stop_machine(machine_id, self._context)

    def restart_machine(self, machine_id, *, display=False, events=None,
                        cancelled=None):
        """Stop a machine if it is running, then start it.

        This happens as one operation, not two separate calls: the
        per-machine lock is held across both the stop and the start,
        so nothing else can start the machine or change its media in
        between. If the machine is already stopped, it's simply
        started.
        """
        return machines.restart_machine(
            machine_id, display=display, context=self._context,
            events=events, cancelled=cancelled)

    def destroy_machine(self, machine_id):
        """Stop a machine if it is running, then remove its
        materialization directory."""
        return machines.destroy_machine(machine_id, self._context)

    def apply_blueprint(self, *, machine=None, blueprint=None,
                        properties=None, events=None):
        """Adopt blueprint edits into a stopped machine."""
        return machines.apply_blueprint(
            machine=machine, blueprint=blueprint, context=self._context,
            properties=properties, events=events)

    def get_machine_dir(self, *, machine=None, blueprint=None):
        """Return the selected machine's directory.

        For inspecting a machine's files directly, outside the normal
        API.
        """
        return machines.get_machine_dir(
            machine=machine, blueprint=blueprint, context=self._context)

    def list_machines(self, blueprint=None):
        """Return state dicts for machines under the cache."""
        return machines.list_machines(self._context, blueprint)

    def resolve_machine(self, *, machine=None, blueprint=None):
        """Resolve the selectors to an existing machine id."""
        return machines.resolve_machine(
            machine=machine, blueprint=blueprint, context=self._context)

    def load_machine_state(self, machine_id):
        """Return the machine's recorded state (``machine.json``)."""
        return machines.load_machine_state(machine_id, self._context)

    def machine_dir_path(self, machine_id):
        """Return where ``machine_id`` materializes."""
        return machines.machine_dir_path(machine_id, self._context)

    def mark_stopped(self, machine_id):
        """Move a machine whose VM process is gone back to the ready phase."""
        return machines.mark_stopped(machine_id, self._context)

    def insert_media(self, machine_id, slot, media=None, *, file=None,
                     events=None, cancelled=None):
        """Insert a declared media or an anonymous ``file`` image."""
        return machines.insert_media(
            machine_id, slot, media, file=file, context=self._context,
            events=events, cancelled=cancelled)

    def eject_media(self, machine_id, slot):
        """Empty a removable drive."""
        return machines.eject_media(machine_id, slot,
                                    context=self._context)

    def set_boot_order(self, machine_id, boot_keys):
        """Persist a stopped machine's launch-time boot order."""
        return machines.set_boot_order(machine_id, boot_keys,
                                       context=self._context)

    # The exec family.

    def exec(self, command, *, machine=None, blueprint=None, timeout=120,
             check=False):
        """Run one guest command and return its output."""
        return machines.exec(
            command, machine=machine, blueprint=blueprint,
            timeout=timeout, check=check, context=self._context)

    def wait_ready(self, *, machine=None, blueprint=None, timeout=90,
                   prompt=None):
        """Wait until a running guest is ready for commands."""
        return machines.wait_ready(
            machine=machine, blueprint=blueprint, timeout=timeout,
            prompt=prompt, context=self._context)

    # Machine variables: reading only, by design. A script's `set`
    # statement is the only thing that ever writes a machine variable
    # (docs/spec/cli.md, "the host side only reads"), so Session has
    # no method for setting one.

    def get_machine_var(self, key, *, machine=None, blueprint=None):
        """Read a machine variable a script ``set``."""
        return machines.get_machine_var(
            key, machine=machine, blueprint=blueprint,
            context=self._context)

    def wait_machine_var(self, key, value=None, *, machine=None,
                         blueprint=None, timeout=machines._VAR_TIMEOUT,
                         interval=machines._VAR_POLL):
        """Wait until a machine variable arrives, and return it."""
        return machines.wait_machine_var(
            key, value, machine=machine, blueprint=blueprint,
            timeout=timeout, interval=interval, context=self._context)

    # The media family.

    def fetch_media(self, name, on_mismatch="fail", progress="auto"):
        """Return the named media's verified payload, fetching on
        demand."""
        return media.fetch_media(name, self._context,
                                 on_mismatch=on_mismatch,
                                 progress=progress)

    def list_media(self):
        """Return sorted media names from the catalog."""
        return media.list_media(self._context)

    def clean_media(self, name=None):
        """Reclaim cached payloads; returns the names reclaimed."""
        return media.clean_media(name, context=self._context)

    def prune_media(self, *, dry_run=False):
        """Drop cached payloads outside the attachment closure."""
        return media.prune_media(context=self._context, dry_run=dry_run)

    # Blueprint authoring.

    def new_blueprint(self, name, *, platform="dos"):
        """Scaffold a minimal composed blueprint; returns its path."""
        return authoring.new_blueprint(name, platform=platform,
                                       context=self._context)

    def add_media(self, name, path):
        """Author a media declaration for a file already on disk."""
        return authoring.add_media(name, path, context=self._context)

    def delete_blueprint(self, name):
        """Remove a home blueprint file; fails closed while its
        machines exist."""
        return authoring.delete_blueprint(name, context=self._context)

    # Script management

    def delete_script(self, name):
        """Remove the home script file for ``name``. Returns the removed path.

        Fails closed while any blueprint refers to the script.
        Never deletes package codex files — only a file under
        ``scripts/``.
        """
        return authoring.delete_script(name, context=self._context)

    # Asset resolution.

    def load_namespace(self):
        """Build the merged resolution namespace from the source."""
        return resolve.load_namespace(self._context)

    def list_blueprints(self):
        """Return sorted ``[{name, path, description, platform}]``
        for the blueprints directory."""
        return library.list_blueprints(self._context)

    def list_scripts(self):
        """Return sorted ``[{name, path}]`` for the scripts
        directory."""
        return library.list_scripts(self._context)

    # Properties and their credentials.

    def get_property(self, key):
        """Return the named property's value, or None if it has
        none."""
        return properties.get_property(key, self._context)

    def has_credential(self, key):
        """Return True when this key's secret credential is
        present."""
        return properties.has_credential(key, self._context)

    def set_property(self, key, value, secret=False):
        """Create or replace a property, preserving the rest of the
        file."""
        return properties.set_property(key, value, secret,
                                       self._context)

    def unset_property(self, key):
        """Remove a property, marker and credential alike."""
        return properties.unset_property(key, self._context)

    def list_properties(self, prefix=None):
        """Return the properties projection: key to value or
        marker."""
        return properties.list_properties(prefix, self._context)

    # Property binding.

    def bind_properties(self, script, *, parameters=None, explicit=None,
                        asker=None):
        """Bind every declared property, or fail closed naming the
        key."""
        return binding.bind_properties(
            script, parameters=parameters, explicit=explicit,
            context=self._context, asker=asker)

    def describe_sources(self, script, *, parameters=None,
                         explicit=None):
        """Name each declared property's supplying source, without a
        run."""
        return binding.describe_sources(
            script, parameters=parameters, explicit=explicit,
            context=self._context)

    # The script family.

    def run_script(self, label, *, blueprint=None, machine=None,
                   display=False, properties=None, progress="auto",
                   dry_run=False, expect=None, record=None):
        """Resolve ``label``, ensure a machine, run it, and return
        its output."""
        return script_runner.run_script(
            label, blueprint=blueprint, machine=machine,
            context=self._context, display=display,
            properties=properties, progress=progress, dry_run=dry_run,
            expect=expect, record=record)
