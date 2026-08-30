<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# `reliquary.properties`: a settings file for CLI/context defaults

> **Status:** design from an owner design round, 2026-08-29. **Nothing
> here is pledged, and this document adds no vocabulary by itself**:
> `reliquary.properties` becomes real only when a feature entry citing
> this document goes through the surface-change rule
> ([SURFACES.md](../../SURFACES.md)).

## The need

Five of the six working directories, the properties file, and the
QEMU install location can each be pinned two ways today: a CLI flag
for one invocation, or an environment variable for a whole shell
session. Neither one is a good fit for "this Reliquary home always
uses these paths." A flag has to be retyped every time. An
environment variable has to be set in every shell profile, every CI
job, and every terminal a person opens — and it applies process-wide,
not to one particular home directory, so it's easy for it to leak
into a run where it wasn't intended, or to be missing in a fresh
terminal where it was.

A settings file fixes that by attaching the preference to the home
directory itself, the same way `user.properties` already attaches
personal script-property values to it. Open that folder, and the
choices that apply to it are sitting right there in a file, not
scattered across shell configuration the folder itself says nothing
about.

This serves U1 directly: U1 wants a sandbox install to be easy and to
take short commands, and repeating `--cache-dir D:\ci-cache` on every
invocation, or requiring an environment variable set up before
Reliquary is even run once, works against that. It's also consistent
with P6 — "different defaults don't break this rule" already
established that the CLI is allowed to pick up settings the API
requires explicitly — and with P12, since a value read from this file
is exactly as explicit an assignment as a flag or an environment
variable: every directory stays either explicitly assigned or derived
from one that was.

## What the file is

`reliquary.properties` lives at `<home>/reliquary.properties`. It is
read only after `home` itself has already been resolved by a flag, an
environment variable, or the built-in default — the file lives inside
`home`, so it cannot also set `home`; that would have no directory to
be found in. An absent file means no settings, exactly like an absent
`user.properties` means no properties: nothing creates it
automatically, and Reliquary never writes to it.

The format is the same line-based grammar `user.properties` already
uses (D4): one `key = value` per line, `#` full-line comments, blank
lines, whitespace trimmed around `=`, no quoting, no escapes, no line
continuations. `user.properties` picked this format specifically
because every layer of the property system already speaks it, and
because a structured format like JSON or TOML would need either an
external dependency or its own surgical-rewrite logic to keep hand
edits intact — neither buys anything for a small, hand-edited file
like this one, so the same reasoning applies again (P21).

This is a separate file from `user.properties`, not a second section
inside it. `user.properties` holds personal script-property values,
including secrets, under a dotted, `rlq`-reserved namespace with
`@`-prefixed value kinds; `reliquary.properties` holds CLI/context
defaults for one specific home, under plain hyphenated keys, with
nothing secret in it. Mixing the two would mean teaching one file two
unrelated grammars for no real gain.

### Keys

Each key is the CLI flag's own name, without its leading `--`:

| Key | Mirrors |
|---|---|
| `blueprints-dir` | `--blueprints-dir` / `RELIQUARY_BLUEPRINTS_DIR` |
| `scripts-dir` | `--scripts-dir` / `RELIQUARY_SCRIPTS_DIR` |
| `cache-dir` | `--cache-dir` / `RELIQUARY_CACHE_DIR` |
| `media-dir` | `--media-dir` / `RELIQUARY_MEDIA_DIR` |
| `machines-dir` | `--machines-dir` / `RELIQUARY_MACHINES_DIR` |
| `properties` | `--properties` / `RELIQUARY_PROPERTIES` |
| `qemu-home` | `RELIQUARY_QEMU_HOME` / `QEMU_HOME` |
| `virtualbox-home` | `RELIQUARY_VIRTUALBOX_HOME` / `VIRTUALBOX_HOME` (new — see below) |

`home` cannot appear here, for the reason above. A file containing a
`home` key, or any key outside this table, is a load error naming the
file and the line — the same fail-closed treatment
`PropertiesError` already gives a malformed `user.properties`, and
the same instinct behind P11: a setting nobody recognizes is refused
by name, never silently ignored.

This list is closed the same way the property-source order is closed
(D19): a new key is added by a design decision that names it, not by
convention or by whoever happens to be editing the parser. It does
not cover `RELIQUARY_PROPERTY_<KEY>` — that family answers to its own
source order, already ruled fixed and closed (D19, script-spec.md),
and nothing here argues for reopening it.

### Precedence

For the five directories and `properties`: **CLI flag, then
environment variable, then this file, then the existing default** —
inserted as one new rung below the environment variable and above
`home.py`'s derivation (`<home>/blueprints`, `<cache>/media`, and so
on) or, for `properties`, above the `<home>/user.properties` default.
Nothing about how those defaults derive changes; the file just gives
one more explicit source to check first.

For `qemu-home` and `virtualbox-home`, there's no CLI flag to rank
above the environment variable — that stays true after this change —
so the order is: **environment variable, then this file, then the
existing PATH / well-known-install-directory search.**

### Where the read happens

This is a CLI-only construction detail, added to `cli.py`'s
`_invocation_context` right alongside the environment-variable checks
already there, for exactly the same reason environment variables are
read only by the CLI and never by `home.py` or the embedding API:
P6/D87 already settled that "the CLI picks up settings ... where the
API requires you to set those explicitly" is a legitimate difference
in defaults, not a break in CLI/API parity. This proposal doesn't
touch `home.py`, `Context`, `Session`, or the API surface (S2) at
all — an API caller keeps assigning every directory it wants
explicitly, exactly as it does today.

`qemu-home` and `virtualbox-home` are read at the same point, once
`home` is resolved, and handled differently: since `find_qemu()` and
the VirtualBox equivalent take no `Context` or home directory
argument today, and read `os.environ` directly, the CLI backfills
the corresponding environment variable — `RELIQUARY_QEMU_HOME` or
`RELIQUARY_VIRTUALBOX_HOME` — from the settings file, but **only if
that variable isn't already set** in the process environment. Nothing
downstream changes: `backend_qemu.py` and the new VirtualBox check
keep reading `os.environ` exactly as they do today, and can't tell a
value a person exported from one the CLI just set from the settings
file. This is a deliberate, narrow exception — mutating one process
environment variable, never overwriting one already present — chosen
because giving the backend-adapter interface a `context` parameter
instead would mean changing `discover()`/`session()` across every
adapter, documented in `planning/design/backend-adapter.md`. That's a
materially bigger change than the rest of this proposal (see "Weighed
and declined" below).

Because of this, an API-only consumer that never runs `cli.py` sees
no change from this feature: it still has no way to steer
`find_qemu()` except a real environment variable, same as today.

### A new environment variable: `RELIQUARY_VIRTUALBOX_HOME`

QEMU already has a Reliquary-defined override for pinning one
install: `RELIQUARY_QEMU_HOME`, then bare `QEMU_HOME`, checked before
anything else — if either is set, `_find_qemu_tool` looks only in
that directory (and its `bin` subdirectory) and fails by name if the
binary isn't there. VirtualBox has no equivalent; `find_vboxmanage`
only ever consults `VBOX_MSI_INSTALL_PATH`, a variable VirtualBox's
own installer sets, as one entry among several well-known
directories, checked after `PATH`.

This proposal gives VirtualBox the same override QEMU already has:
`RELIQUARY_VIRTUALBOX_HOME`, then bare `VIRTUALBOX_HOME`. To match
QEMU's actual guarantee — that an explicit pin is authoritative, not
just one more place to look — `find_vboxmanage` needs reordering, not
just an appended directory: check the override first, and if it's
set, search only there and fail by name if `VBoxManage` isn't found,
before falling through to today's `PATH` / `VBOX_MSI_INSTALL_PATH` /
well-known-directory search. Simply adding the override to the
existing directory list wouldn't give that guarantee, since `PATH` is
checked first in that code today.

This is filling a gap where one backend lags behind another with a
capability that already exists — one of the cases SURFACES.md counts
as easy, needing no use-case or principle amendment.

## Weighed and declined

- **A global, pre-`home` settings file** (for choosing `home` itself,
  or applying across every Reliquary home on a machine) — declined:
  out of scope of what was asked. This file lives inside a `home`
  that's already been chosen; picking which `home` to use is a
  separate question. Could be its own future proposal.
- **Threading `Context`/`home` through the backend-adapter interface**
  instead of backfilling `os.environ` — declined for this round: it's
  the more correct long-term shape, but it changes
  `discover()`/`session()` for every adapter, which is a bigger change
  than the rest of this proposal bundles. Reopens if that interface is
  being revisited for other reasons anyway.
- **Reading the settings file from `home.py`**, so the embedding API
  also honors it automatically, the way `user.properties` already
  is — declined: this keeps the change inside the P6/D87 asymmetry
  already in force (the CLI defaults automatically; the API requires
  explicit values) instead of arguing that the API surface itself
  should change. Reopens if a real API-side need shows up.
- **JSON, TOML, or YAML for the file format** — declined for the same
  reason D4 already gave for `user.properties`: every adjacent layer
  already speaks plain `key = value`, and a structured format would
  need either a new dependency or hand-rolled formatting-preserving
  edit logic that this file, with no maintenance commands, doesn't
  need anyway.
- **Folding these settings into `user.properties`** — declined:
  different owner concern (CLI/context defaults for this home,
  nothing secret) from what `user.properties` already holds (personal
  script-property values, some secret, under a reserved dotted
  namespace).
- **Maintenance CLI commands** (`get-setting` / `set-setting` / ...)
  in v1 — declined on size grounds (P8, D42): the format is plain
  enough to hand-edit directly. Adding commands later costs nothing
  once the file format exists; that's the same one-directional
  argument P6 already relies on elsewhere.
- **Extending this to `RELIQUARY_PROPERTY_<KEY>`** (script property
  values) — declined: that's S5's own property-source order, already
  ruled fixed and closed by D19, with its own reasoning for staying
  custom and unconfigurable. Nothing here argues for reopening D19.

## What delivering this touches (sketch — this document delivers none of it)

- `cli.py`: `_invocation_context` gains the settings-file read for
  the five directories and `properties`, and the `qemu-home` /
  `virtualbox-home` environment-variable backfill; a narration line
  when a value comes from the file, alongside the existing "using
  reliquary home: ..." line for a defaulted home.
- A small parser for the file itself — `key = value`, `#` comments,
  blank lines, fail-closed on `home` or an unrecognized key — plain
  enough that it likely doesn't need `properties.py`'s own machinery,
  which carries secret-kind and reserved-namespace rules this file
  has no use for.
- `backend_virtualbox.py`: `find_vboxmanage` reordered to check
  `RELIQUARY_VIRTUALBOX_HOME` / `VIRTUALBOX_HOME` first and search
  exclusively there when set, mirroring `_find_qemu_tool`'s existing
  shape.
- Docs: `docs/spec/asset-resolution.md`'s "The working directories"
  table and surrounding prose; `docs/spec/cli.md`'s
  environment-variable section; README.md's "Where Reliquary keeps
  things" and QEMU-discovery sections (plus the new VirtualBox
  variable); `docs/cli-reference.md`.
- Tests: precedence coverage (flag beats environment variable beats
  file beats default) for at least one directory, for `properties`,
  and for `qemu-home`; load-error coverage for a `home` key and for
  an unrecognized key; the reordered `find_vboxmanage` against both a
  set and an unset override.
