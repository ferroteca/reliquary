# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The session: ambient state carried once, behind one door.

P26 pledges that all consumer API interaction passes through a
``Session`` opened on — at the minimum — a home directory. The
session pins the ambient state every call is otherwise handed per
call — the six placeable working directories and the selected
properties file, one :class:`~reliquary.home.Context` record — at
construction, from the record it was opened on alone, and every
method is a veneer: one thin method per ambient-state verb,
forwarding to the engine function of the same name with the
stored record and carrying no logic of its own. Behavior lives in
the engine modules, and a veneer's contract is its engine
function's.

The boundary is ambient state, and it is named (P26): whatever
resolves a working directory, touches machine or media state, or
reads ambient configuration takes a veneer; pure data-in/data-out
work — parsing and validating a document or script handed to it —
stays a free function, so tooling never invents a home to parse a
string. The codex verbs take no veneer either: reaching the
shipped library is a human act, CLI-only under P6's named
exception (D87).

``Session`` is deliberately **unexported** while the module-level
surface stands: the package root exports none of this today, and
the public surface will move once, coherently, when the door
closes. Two sessions in one process are unremarkable —
construction reads and writes no module-global state, and the
pinned record means no later call reads any either.
"""

from . import (authoring, binding, library, machines, media,
               properties, resolve, script_runner)
from .errors import StaticError
from .home import as_context, pinned


class Session:
    """Ambient state carried once: the six working directories and
    the selected properties file, pinned at construction, with one
    thin method per ambient-state verb forwarding to its engine
    function.

    Opened on what ``context=`` accepts today — a bare home string
    or a ``Context`` — and refusing construction without a home:
    the same fail-closed safety as ``dir.unassigned``, moved to the
    door. An assigned home reaches all six directories by
    derivation, so nothing a session does can find a directory
    unassigned.
    """

    __slots__ = ("_context",)

    def __init__(self, context):
        record = as_context(context)
        if record.home_dir is None:
            # The same condition first-use ``dir.unassigned`` names,
            # noticed at the door: one rule, one id (the tier is
            # never the subject — docs/spec/script-spec.md).
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

        One act rather than two: the per-machine lock is held across
        both halves, so nothing can start the machine or change its
        media in between. A machine that is already stopped is simply
        started.
        """
        return machines.restart_machine(
            machine_id, display=display, context=self._context,
            events=events, cancelled=cancelled)

    def destroy_machine(self, machine_id):
        """Remove a machine's materialization directory."""
        return machines.destroy_machine(machine_id, self._context)

    def apply_blueprint(self, *, machine=None, blueprint=None,
                        properties=None, events=None):
        """Adopt blueprint edits into a stopped machine."""
        return machines.apply_blueprint(
            machine=machine, blueprint=blueprint, context=self._context,
            properties=properties, events=events)

    def get_machine_dir(self, *, machine=None, blueprint=None):
        """Return the selected machine's directory; the out-of-band
        door."""
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
        """Return a machine whose VM is gone to the ready phase."""
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

    # The machine-variable family. Read-only by design: the script
    # `set` verb is the channel's only writer (docs/spec/cli.md,
    # "the host side only reads"), so the session carries no
    # setter.

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
