<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Python API reference

This document describes Reliquary's actual, implemented Python API —
the first language binding of the embedding API. Everything below is
importable from the `reliquary` package, and it mirrors the CLI: the
same operations are available both ways. The authoritative definition
of the API is [docs/spec/api.md](spec/api.md) — this Python binding
implements that spec, it doesn't define it, so if this reference ever
disagrees with the spec, this reference is the one that's wrong.

Reliquary doesn't interpret what a guest command outputs — figuring
out what the output means is up to your own code.

## The session

**Everything goes through the session** (P26). Any call that resolves
a working directory, touches machine or media state, or reads
configuration from the environment is a method on one `Session`
object:

```python
import reliquary

session = reliquary.Session(r"D:\my-project-home")
machine_id = session.create_machine("freedos")
```

- `Session(context)` - Open a session by passing a home path
  directly, or a `Context` object that sets any of the working
  directories and the properties file. If no home directory is
  given, construction fails immediately with `StaticError`
  (`dir.unassigned`) — there's no fallback. Once a session is
  created, all its directories are fixed for good: the home
  directory determines every other directory, so a session can
  never end up with an undefined one. You can safely open more than
  one `Session` in the same process.
- `Context(home_dir=None, blueprints_dir=None, scripts_dir=None,
  cache_dir=None, media_dir=None, machines_dir=None,
  properties_file=None)` - The value you pass to create a session: a
  plain record holding the six directory settings (matching the six
  `--*-dir` command-line flags) and the properties file setting
  (matching `--properties`). That's all it holds — there's no other
  way to configure where things live. Any directory you leave unset
  is derived from the others: `blueprints`, `scripts`, and `cache`
  default to subdirectories of the home directory; `media` and
  `machines` default to subdirectories of the cache directory.
- `default_home_dir()` - The home directory the CLI uses when
  nothing else specifies one: `Documents/reliquary`, or
  `~/reliquary` if that's not available. This is computed by the
  CLI, not assigned automatically by the library.

**The Python API never picks a default for you.** If you create a
`Session` without a home directory, it fails immediately instead of
falling back to your user directory or the current working
directory. It also never resolves anything from the built-in
blueprint library on its own, so nothing can silently feed into an
automated run. Environment variables (`RELIQUARY_HOME` and related
ones, plus `RELIQUARY_PROPERTIES`) are read by the CLI when it
builds its own `Context` — the library itself never reads them.

Every method listed below is a `Session` method, written without the
`session.` prefix for brevity. The exceptions are marked as they come
up: the standalone parsers and value helpers (plain functions that
just take data in and return data out), the guest-interaction
functions (module-level functions that take a machine's directory
directly), and the read-only backend vocabulary described later.

## Cached machines (the blueprint lifecycle)

- `create_machine(name, *, properties=None, dry_run=False,
  backend=None)` - Create a new machine from a blueprint name and
  return the machine id (`<blueprint>-<n>`, the lowest free number).
  The blueprints directory is the only place a blueprint can come
  from: nothing is seeded automatically, and a name that only exists
  in the built-in library is refused, with the seed command named in
  the error. `properties` — together with the session's properties
  file — resolves any `${key}` referenced in a media location.
  CLI twin: `create-machine`.
- `create_machine(name, dry_run=True)` returns a `DryRun` object
  instead of a machine id — so if calling code mistakenly treats the
  return value as an id, it fails right away with a `TypeError`
  instead of breaking somewhere else later. A dry run doesn't create
  anything: no machine, no seeding, no fetching, no locking, and no
  prompts. It reports the machine id that would be allocated, the
  backend it would run on, the resolved plan for each drive, and
  where each media file would come from. Any error a real
  `create_machine` call would raise, the dry run raises at the same
  point. Pass `backend=` to check whether the blueprint would work on
  a specific backend — this only checks capability, the backend
  doesn't need to be installed — and `backend=` is only valid
  together with `dry_run=True`. See
  [cli.md](spec/cli.md#the-dry-run) for the full rules.
- `DryRun` has three fields: `operation` (the name of the action
  being described), `report` (text meant for printing), and `plan`
  (a structured record of the operation — this is what `--json`
  serializes).
- `list_machines(blueprint=None)` - List machines.
  CLI twin: `list-machines`.
- `resolve_machine(*, machine=None, blueprint=None)` -
  Turn a CLI-style selector into exactly one machine id. Pass one or
  the other, not both: `machine=` takes the full id
  (`<blueprint>-<n>`) exactly as written, or `blueprint=` selects
  that blueprint's only machine (this fails if the blueprint has
  more than one). There's no prefix matching, and you can't pass
  just the number.
- `start_machine(machine_id, *, display=False)` -
  Start a machine through its assigned backend and return its id.
  The VM's verified identity is recorded in the machine's
  `machine.json` file, in a `vm` section, written atomically along
  with the `phase` field. CLI twin: `start-machine`.
- `stop_machine(machine_id)` - Stop a running machine. If the running
  VM's identity doesn't match what was recorded, the call refuses to
  proceed rather than risk stopping the wrong VM.
  CLI twin: `stop-machine`.
- `restart_machine(machine_id, *, display=False, events=None,
  cancelled=None)` - Stop the machine if it's running, then start
  it, and return its id. This happens as one operation, not two
  separate calls: the per-machine lock stays held the whole time, so
  nothing else can start the machine or change its media in between.
  If the machine is already stopped, this just starts it.
  CLI twin: `restart-machine`.
- `destroy_machine(machine_id)` - Stop the machine first if it's
  running, then delete it entirely, freeing its number for reuse. As
  with `restart_machine`, the per-machine lock stays held across
  both steps. CLI twin: `destroy-machine`.
- `recreate_machine(*, machine=None, blueprint=None,
  properties=None)` -
  Destroy the selected machine and recreate it under the same id,
  resolving the blueprint fresh. Returns the reused id. CLI
  twin: `recreate-machine`.
- `apply_blueprint(*, machine=None, blueprint=None,
  properties=None)` -
  Update a stopped machine to match the current blueprint: memory,
  CPU count, boot order, control-planes, backend-settings, metadata,
  and any drive changes that can be applied in place are all
  applied, and the baseline digest is re-recorded. If the blueprint
  changed a media image's `size` or `materialize` setting in a way
  that would require rebuilding an already-created image, the call
  refuses rather than proceed (use `recreate_machine` instead).
  Returns the id. CLI twin: `apply-blueprint`.
- `get_machine_dir(*, machine=None, blueprint=None)` -
  Return the selected machine's cache directory as an absolute path.
  Works regardless of the machine's phase (running, stopped, etc.).
  CLI twin: `get-machine-dir`.
- `mark_stopped(machine_id)` - Update a machine's recorded phase to
  `stopped` after its QEMU process has already exited.
- `load_machine_state(machine_id)` - Read the
  machine's `machine.json`.
- `machine_dir_path(machine_id)` - The machine's cache
  directory.

These three calls change a machine's persistent state and survive a
stop/start cycle. `insert_media` and `eject_media` work on floppy and
cdrom slots, and work whether the machine is running or stopped — if
it's running, the change is applied live over QMP. `set_boot_order`
only works when the machine is stopped:

- `insert_media(machine_id, slot, media=None, *, file=None)`
  (`insert-media`) - Pass exactly one of `media` or `file`. `media`
  is a media declared in a blueprint — it gets fetched and
  hash-verified. `file` is your own image file, mounted in place as
  is: it isn't copied, isn't hash-verified, and isn't tracked by
  name. This is the option to use when you're iterating on a disk
  image directly.
- `eject_media(machine_id, slot)` (`eject-media`)
- `set_boot_order(machine_id, boot_keys)` (`set-boot-order`)

## Driving a machine from a program

This section covers the mechanics of automating a guest: send input,
run it, read the result back, and repeat. Reliquary moves the data
back and forth but doesn't interpret what it means — that's up to
your code.

- `wait_machine_var(key, value=None, *, machine=None, blueprint=None,
  timeout=120, interval=1)` - Poll for a machine variable until it
  appears (or matches `value`), and return it. Use this when
  something else is setting the variable — a script running on
  another thread, or a run you're watching rather than driving
  directly. A `run_script` call that runs to completion has already
  finished setting its variables by the time it returns, so check
  those with `expect=` instead of waiting for them here. Leave
  `value` unset to wait for the variable to be set to anything at
  all — useful as a readiness check. If the wait times out, it
  raises `WaitExpired`, which is deliberately both a `RunFailure`
  (exit code `4` at the CLI, meaning the work didn't happen) and a
  Python `TimeoutError` (meaning nothing went wrong, just try
  again). CLI twin: `wait-machine-var`.
- `wait_ready(*, machine=None, blueprint=None, timeout=90,
  prompt=None)` - Wait until a running guest is ready to accept
  commands. `start_machine` returns as soon as the backend is up,
  not once the guest OS has finished booting, so this call waits out
  the boot by watching for the platform's own sign of readiness — on
  DOS, a prompt on the bottom row of the screen. That's either the
  standard DOS prompt shape, or the exact text you pass as `prompt`,
  for a guest whose `AUTOEXEC.BAT` sets a custom prompt (D113). This
  is the one call to make between `start_machine` and your first
  `exec` call (D114) — you don't need to describe what the screen
  should look like yourself. A prompt only counts once the screen
  underneath it has stopped changing (D115) — the same rule `exec`
  uses to decide a command has finished. `wait_ready` returns
  nothing. If it times out, it raises `WaitExpired` — both a
  `RunFailure` (exit code `4`) and a `TimeoutError`, same as
  `wait_machine_var` — naming what it was waiting for. If the
  machine isn't running, or the blueprint isn't for a DOS platform,
  it raises `PreflightError` immediately, before reading the screen
  at all. CLI twin: `wait-ready`.
- `exec(command, *, machine=None, blueprint=None, timeout=120,
  check=False)` - Run one command in a running guest and return what
  it printed, as a tuple of screen rows. This is the one-shot member
  of the run family: it sends the command, waits, and returns the
  output — it doesn't store anything. Because there's no agent
  running inside the guest, the output is just whatever is visible
  on screen — if the command's output scrolled past the visible
  area, you only get the tail. Retrieve a file, or read a machine
  variable, when you need more than that. Completion here means
  *this specific command* finished, not just that some prompt
  reappeared — so if `exec` can't tell that the output belongs to
  the command it ran, it raises `RunFailure` (`screen.no-echo`)
  rather than guess and return the wrong rows. It identifies the
  command's own output by finding the row where the command was
  typed back (the echo) — the rows that were above the prompt when
  you ran the command stay excluded, never mistaken for output — and
  it recognizes the prompt is back either by the standard
  `X:\path>` shape or by matching the exact prompt text the guest
  was already showing, so a custom prompt doesn't need to be
  declared anywhere. The one thing `exec` can't handle: a command
  that changes the prompt to something new. That times out with
  `screen.no-match`, naming what it was waiting for (D111, D112).
  Pass `check=True` to also check whether the command succeeded: if
  it signalled failure, `exec` raises `RunFailure`
  (`command.signalled-failure`) naming it — the returned rows are
  unchanged. This is for a setup command where you don't care about
  its output, only whether it worked. On DOS, `check=True` works by
  having Reliquary run an extra `IF ERRORLEVEL 1` probe after your
  command and read its result — so it costs one extra command at the
  prompt, and it can only see failures signalled by commands that
  actually ran (a mistyped command escapes this check). CLI twin:
  `exec --check`, or just `exec` without it. Non-DOS platforms raise
  `PreflightError` (`platform.verb-not-implemented`). (As a
  `Session` method, this doesn't shadow anything — the CLI-twin
  naming rule settled on `exec` as the name, and Python's own
  `builtins.exec` is unaffected.)
- `get_machine_var(key, *, machine=None, blueprint=None)` -
  Read one machine variable, returning `None` if it isn't set. This
  is a read-only query and works regardless of the machine's phase.
  CLI twin: `get-machine-var`.
- `parse_document(value)` / `load_document(path)` - Parse and
  validate a `.rlqb` document. A document is an array of specs,
  though a single spec object is accepted as shorthand for an array
  of one. Both return a `Document`, whose `machines` and `media`
  fields are dicts keyed by name. `type` defaults to `media`, so a
  machine entry has to say `"type": "machine"` explicitly. Errors
  raise `BlueprintError` (a subclass of `StaticError`, so exit code
  `2` and any `except StaticError` still work as expected).
  `load_document` has an actual file to point into, so its errors
  carry a `line` and `column`, shown with the source line and a
  caret under the problem. `parse_document` is handed a value with
  no file behind it, so its errors have no line or column — just the
  path to the offending field.
- `load_namespace()` - Build the combined `(name, type)` catalog
  from every `.rlqb` file in the active blueprint source.
  `create_machine` and media resolution both read from this catalog.
  Two files can declare the exact same spec under the same name
  without conflict; if they declare different specs under the same
  name, that's an error. (The catalog-level
  `resolve_media(name, namespace)` function lives in
  `reliquary.resolve`.)
- `new_blueprint(name, *, platform="dos")` - Scaffold a
  home ``blueprints/<name>.rlqb``. CLI twin: `new-blueprint`.
- `add_media(name, path)` - Write a new `blueprints\<name>.rlqb`
  file in your home directory that declares a media entry pointing
  at `path`, pinned to that file's computed SHA-256 hash. The file
  at `path` stays where it is — nothing gets copied into the cache.
  Returns the path to the new blueprint file. If a blueprint of that
  name already exists, this raises `FileExistsError` rather than
  overwriting it. CLI twin: `add-media`.
- `delete_blueprint(name)` - Delete a blueprint file from your home
  directory. This refuses to run while any machine created from that
  blueprint still exists. It never touches the built-in blueprints
  that ship with the package. CLI twin: `delete-blueprint`.
- The spec types themselves live in `reliquary.document`: `Machine`,
  `Media`, `MachineDrive`, `Location`, `Reference`, and `Deferred`.
  `Deferred` holds a value that still contains unresolved `${...}`
  references — it's only fully resolved later, not at parse time.

## Media

- `fetch_media(name, on_mismatch="fail")` - Look up a media by name
  in the catalog and return the path to its verified,
  already-fetched file, fetching it if it isn't cached yet. It
  checks, in order: whether a verified cached copy already exists,
  whether a cached container file just needs re-extracting, and
  finally tries each configured mirror in turn. Every file is
  verified against its SHA-256 hash before use. `on_mismatch`
  controls what happens when a cached file's hash doesn't match:
  `"fail"` (the default) stops with an error, `"prompt"` asks
  interactively whether to delete and refetch, and `"refetch"`
  deletes and refetches without asking. A mismatched file that isn't
  declared as any media's source is left alone either way. CLI twin:
  `fetch-media`.
- `list_media()` - List media names from your namespace, sorted
  alphabetically. This only includes media you've declared yourself
  — there's no way to list the built-in library's media separately,
  since media aren't standalone seedable things, they're components
  inside a `.rlqb` blueprint (D88). CLI twin: `list-media`.
- `clean_media(name=None)` - Delete cached media payloads and return
  the names deleted. With no argument, this deletes everything in
  the cache except payloads a currently running machine has open —
  since anything in the cache can be fetched or derived again,
  nothing is protected just because of where it came from. Pass a
  name to delete only that one payload. CLI twin: `clean-media`.
- `prune_media(*, dry_run=False)` - Delete cached payloads that no
  existing machine is using and no declared media in your namespace
  currently needs, returning the names deleted (or, with
  `dry_run=True`, the names that would be deleted). This only
  considers your own project's media and machines — it won't touch
  anything belonging to another project. CLI twin: `prune-media`.

(`add_media` writes a blueprint declaration and never touches the
cache — that's why it's listed with the blueprint-authoring calls
above, not here.)

## User properties

These calls edit the `<home>/user.properties` file. Edits are
precise: comments, blank lines, and the ordering of other keys are
all preserved. If the file is malformed, these calls raise
`PropertiesError` (a `ValueError`) naming the path and line — and
they never write a partial, half-edited file.

Which file gets edited is set on the session itself: the `Context`'s
`properties_file` setting (matching the CLI's `--properties` flag
and the `RELIQUARY_PROPERTIES` environment variable — both read when
the CLI builds its `Context`) replaces the home directory's
`user.properties` entirely, rather than being merged with it.

- `get_property(key)` - Return the property's value, or `None` if it
  isn't set. For a secret property, this returns the marker
  `{"secret": True}` rather than the actual value — the same thing
  `--json` serializes. CLI twin: `get-property`.
- `set_property(key, value, secret=False)` - Create or replace a
  property, rewriting or adding only that one key's line in the
  file. With `secret=True`, the actual value is stored in the host's
  credential store, and only the marker goes into the file. You
  can't change an existing property between ordinary and secret
  directly — unset it first, then set it again with the new `secret`
  value. CLI twin: `set-property`.
  **One deliberate difference from the CLI:** here, a secret's
  value is just the ordinary `value` argument. The CLI instead
  prompts for secret values or reads them from stdin, because a
  value passed as a command-line argument would be visible in
  process listings and shell history — a Python value passed
  in-process never has that exposure, and a library function
  shouldn't prompt interactively anyway.
- `unset_property(key)` - Remove a property. For a secret property,
  this also removes its stored credential. It also clears up any
  orphaned credential left behind for that key. CLI twin:
  `unset-property`.
- `list_properties(prefix=None)` -
  Return all properties as a sorted mapping from key to value (or,
  for secrets, the marker). Pass `prefix` to limit the results to
  that key and its dotted descendants (e.g. `prefix="db"` also
  matches `db.host`). CLI twin: `list-properties`.
- `has_credential(key)` - Check whether a secret's credential is
  actually present in this host's credential store. This is a
  separate call from `get_property` so that reading a property never
  depends on reaching the credential store. The CLI reports a
  missing credential as a warning on stderr rather than mixing it
  into the result.
- `is_secret(value)` / `secret_marker()` - Recognize and build the
  secret marker.

Secrets are stored in the host's credential service, scoped by the
absolute path of the properties file and the property name. There's
no plaintext fallback: if the host has no usable credential store,
this raises `CredentialError`. Setting a secret writes its credential
before writing the marker line, and unsetting a secret deletes the
marker line before deleting the credential — so if either operation
gets interrupted partway, the only thing that can be left behind is
an orphaned credential, never a marker pointing at nothing. An
ordinary `set_property` call on that key refuses to overwrite an
orphaned credential; use `unset_property` first to clear it.

## Scripts and runs

- `parse_script(source, path="<script>")` / `load_script(path)` -
  Parse a `.rlqs` script into an immutable `Script` object; errors
  raise `ScriptParseError` with source locations.
- `run_script(label, *, blueprint=None, machine=None,
  display=False, properties=None,
  progress="auto", expect=None)` - Look up `label` in the
  blueprint's `scripts` map, create a machine if the blueprint
  doesn't already have one, honor the script's own `machine` header,
  check its insert/eject/set-boot targets ahead of time, bind every
  property the script declares before the machine starts, then run
  it. `properties` is an explicit `{key: value}` mapping (matching
  the CLI's repeated `--property` flag). Which file properties get
  read from is set by the session's `properties_file` (the
  `Context` setting, or the CLI's `--properties`). `progress`
  selects how progress is shown while it runs: `"auto"`, `"pretty"`,
  `"plain"`, or `"jsonl"` (matching the CLI's `--progress`) —
  `"plain"` and `"jsonl"` never prompt interactively.

  **`run_script` returns its results and doesn't save them
  anywhere.** The returned `ScriptRun` object has `machine_id`,
  `script_path`, `created_machine`, `final_phase`, `machine_phase`,
  and `events` (the entire event stream as plain dicts, in the order
  they happened, with the final event last). If you want a record of
  the run, keep this object yourself — Reliquary doesn't keep one.
  Failures raise different error classes depending on what went
  wrong (see below). CLI twin: `run-script`.

  `expect={"ready": "yes"}` (matching the CLI's repeated
  `--expect ready=yes`) **checks the machine variables the script is
  supposed to leave behind.** After the run finishes, each key in
  `expect` is read; if it's unset or holds a different value than
  expected, `run_script` raises `RunFailure` naming the key, what was
  expected, and what it actually found. This turns a script that
  silently never reached its `set` step into a visible failure
  instead. This check happens after the run completes — `run_script`
  blocks until the script is done, so the values are already final
  by the time `expect` checks them. If instead something *else* is
  setting the variable while you watch, use `wait_machine_var`
  instead of `expect`.
- `run_script(label, dry_run=True, ...)` returns a `DryRun` instead
  of a `ScriptRun`. It parses and statically checks the script, and
  reports the timing plan, where each declared property will come
  from, and how many statements can't be statically guaranteed to
  run — all without prompting, starting a machine, running any guest
  step, or reading a secret's actual value. **This is the one mode
  where the machine/blueprint selector is optional** — whether you
  pass it decides which of two levels of checking you get.
  `display=`, a non-default `progress=`, and `expect=` are all
  refused in this mode: there's no window to show, no live stream,
  and no completed run to check variables against. See
  [cli.md](spec/cli.md#the-dry-run) for the details.
- `bind_properties(script, *, parameters=None, explicit=None,
  asker=None)` - Resolve every property a script declares, checking
  each of the possible sources in order, or raise
  `PropertyBindingError` if one can't be resolved. Returns a
  `BoundProperties` object. `describe_sources(script, *,
  parameters=None, explicit=None)` does the same lookup without
  actually binding the values — it just reports which source each
  key would come from, which is what a dry run shows.

`create_machine`, `recreate_machine`, and `apply_blueprint` all
accept `properties=` in addition to reading the session's properties
file. Any `${key}` reference in a media's `location` (or `sha256`)
is resolved through the same source order before the machine is
materialized, and the resolved location is saved in the machine's
state — `start_machine` never re-resolves it later. A bound value
that turns out to itself be a reference is rejected. See the
blueprint guide for the `location` grammar.

## Guest interaction

`Machine(home=None, deadline=None)` is a handle for interacting with
a running, Reliquary-owned machine, and it works the same way
regardless of which backend the machine runs on. `home` is the
machine's own cache directory — a plain, already-resolved path, not a
`Context`. That directory is the whole address: the machine's
recorded VM identity lives there, and the backend adapter named in
that record supplies the connection endpoint and verifies the
identity before sending anything. There's no port number to pass in.

- `Machine.session()` - A context manager that yields the backend
  session, after verifying the machine's identity. (This gives you
  the adapter's own communication channels.)
- `Machine.console()` - A context manager that yields the display
  console for reading and controlling the guest's screen, without
  needing any agent running inside the guest.
- `Machine.qmp()` - A context manager that yields an
  identity-verified QMP session, with its `cmd()` and `hmp()`
  methods available. This is the escape hatch to QEMU's own native
  monitor, and it only works for QEMU: a machine running on another
  backend refuses this call rather than fake a monitor it doesn't
  have.
- `Machine.screen_text()` /
  `Machine.wait_text(pattern, timeout=60)` - Read the guest's text
  screen, or wait for a pattern to appear on it. `wait_text` is what
  the `.rlqs` script language's `wait` statement calls at the API
  level (D116). `pattern` is a regular expression, searched against
  each visible row after normalizing it (trailing padding trimmed,
  whitespace collapsed — but never joining separate rows together).
  A match only counts once the screen underneath it has stopped
  changing (D115), and the matching screen is returned as one string
  with rows joined by newlines. If it times out, it raises
  `WaitExpired`. The CLI equivalent is `rlq wait`; when you give it
  plain text instead of a regular expression, that text is escaped
  with `re.escape` after the same normalization.
- `Machine.wait_stopped(timeout=60)` - This backs the
  `machine=stopped` form of the `wait` statement: it returns once
  the backend reports the VM is gone (either the session refuses the
  recorded identity, or the connection fails outright). It only
  observes — it doesn't update the machine's recorded phase itself.
  That's `Session.mark_stopped`, which `rlq wait machine=stopped`
  calls right after this returns. There's no module-level version of
  this one; that's planned alongside the control-plane design.
- `Machine.send_keys(combos, delay=0.06)` /
  `Machine.send_text(text, enter=True)` - Keyboard input.
- `Machine.cursor_menu_select(item, timeout=30, exclude=())` -
  Select an item from a cursor-driven menu, watching the screen to
  confirm each step.
- `Machine.screenshot(name="screen", directory=None)` - Capture the
  guest's screen as a PNG image file, and return its path.

There are also module-level versions of these functions that take
`home=` directly instead of a `Machine` object: `send_keys`,
`send_text`, `screen_text`, `wait_text`, `cursor_menu_select`, and
`screenshot(name="screen", home=None, directory=None)`.

`GuestExec` defines the interface that any platform adapter for
running guest commands must implement: `wait_ready(timeout=90, *,
prompt=None)` and `execute(command, timeout=120, *, check=False)`.
`AgentlessGuestExec` is the actual DOS implementation of it, built
on top of a `Machine`. Its `wait_ready` considers the guest ready
once it sees the standard DOS prompt, or exactly the bottom-row text
given as `prompt` — for example, a guest whose `AUTOEXEC.BAT` sets
`PROMPT [$P]$G` is reported ready with
`wait_ready(prompt="[C:\\]>")`. You have to declare the prompt
explicitly here because, unlike `execute`, there's no earlier screen
to read a customized prompt off of (D112, D113). A prompt containing
the time (`$T`) can't be matched as exact text — that's the one thing
this can't handle, and it's also true for `execute`. A prompt only
counts as ready once the screen underneath it has stopped changing,
the same rule `execute` uses to decide a command has finished (D115).
If it times out, it raises `WaitExpired` (D90). The same capability,
reached through the session, is `Session.wait_ready` (CLI:
`wait-ready`, D114), which also resolves the machine and checks that
it's running first. How `check` is implemented is left up to each
platform: DOS checks ERRORLEVEL, while an agent-based platform would
read a process exit status — but every adapter has to give the same
answer either way.

## Backends

The backend-adapter API is an internal contract between Reliquary
and each backend (QEMU, VirtualBox, and so on) — it isn't something
you're meant to call directly, and none of it has a CLI command or
API twin. As a user, you reach backends through blueprint fields
(`backend`, `backend-settings`, `control-planes`, drives and
controllers) and through the capability errors that preflight checks
report. What the `reliquary` package exposes about backends is only
for reading information about them, not for driving them directly:

- `adapter(name)` / `discover()` - `adapter(name)` returns the
  adapter object for a named backend. `discover()` checks every
  backend's availability, in priority order. `discover()` only
  reports what's available — it never picks a backend for you, and
  it never changes which backend a machine is recorded as using.
- `BACKEND_PRIORITY` - The default order backends are tried in
  (QEMU, VirtualBox, VMware Workstation, Hyper-V), used to pick one
  among backends that are both available and capable of running the
  blueprint.
- `Availability` / `Capabilities` / `BackendAdapter` - `Availability`
  is the result of a discovery probe. `Capabilities` is a report of
  what a backend supports, in the same vocabulary blueprints use.
  `BackendAdapter` is the contract every adapter implements. Each
  adapter also defines which `backend-settings` keys its section
  accepts (`settings_keys`) and rejects any others
  (`validate_settings`), since that section of a blueprint is
  written in whatever configuration language the backend itself
  uses.

QEMU's own helper functions (`find_qemu`, `create_hdd_image`, `Qmp`,
and the drive-rendering code) are internal to the adapter, living in
`reliquary.backend_qemu` — they aren't part of the public Python API.

`main(argv=None)` is the CLI entry point.

For the command-line equivalents of everything above, see the
[CLI reference](cli-reference.md).
