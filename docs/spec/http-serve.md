<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Local HTTP server for installer answer files

> **Status:** implemented - milestone 5 completed on
> 2026-07-22. Packer parity is the settled shape, and the
> milestone's decide-first round is recorded here: scripts declare
> named run-scoped served content, inline or from a script-relative
> file,
> `$rlq.http.ip` / `$rlq.http.port` / `$rlq.http.url` bind the live
> address, and QEMU reaches
> the host through user-mode networking's host gateway. Distinct
> from the deleted property-binding "response file" concept
> (planning/DECISIONS.md).

## Purpose

Guests whose installers already accept a declarative answer file
- Kickstart, preseed, AutoYaST, Windows `unattend.xml`, and kin -
should consume that path rather than a keystroke script that
reinvents it. Packer's builders solve delivery with an ephemeral
local HTTP server the guest fetches from during the build.
Reliquary adopts the same pattern.

This does not compete with those formats, and it does not weaken
agentless keystroke scripting for guests that lack them
(docs/spec/script-spec.md "The procedural–declarative seam"; language goal
G1 is about the control plane, not a ban on the installer's own
answer-file mechanism).

## Contract

The feature is a run-scoped answer-file server:

- It is declared by the script that needs it. A blueprint may
  parameterize the script's paths and values, but does not own an
  HTTP server of its own: serving answer files is a run behavior,
  not machine shape.
- It serves generated path-to-body content declared inline in the
  script. Packer's `http_content` is the model; Packer's
  `http_directory` becomes a later asset-distribution item because
  milestone 5 has no mechanism for bundling arbitrary support files
  with a seeded codex script.
- It listens on a randomly chosen free port in the configured
  inclusive range, defaulting to 8000-9000. Setting the minimum and
  maximum to the same port pins that single port.
- It exposes its live address as bound run properties available to
  `type` and `enter`, so the script can tell the installer where
  to fetch.
- Its content and port range bind during preflight, but the server
  starts only when execution reaches `http start`. `http stop`
  stops it if running and succeeds as a no-op if it is already
  stopped. A final `http stop` is implied on every terminal path:
  success, run failure, cancellation, or process exit.
- The guest reaches the server over the VM network. Reliquary does
  not push answer files into the guest.

This is strong alignment with U1, U4, and U5: installer-native
answer files make unattended installs easier, keep shareable
automation as authored assets beside blueprints and media
definitions, and give customized installs a clear data seam without
turning `.rlqs` into a general computation language.

## Script Surface

A script may declare at most one `http` block in its declarative
zone, after `property` declarations and before the script body:

```rlqs
http port-min=8000 port-max=9000 {
    content install "/ks.cfg" """
        install
        url --url=https://mirror.example/os/
        rootpw ${accounts.root-password}
    """
}
```

The block contains one or more named `content` entries. A content
entry's first argument is its script-local name, and its second is
the guest-visible absolute HTTP path. The content source is either
an inline triple-quoted text body or a file named with `from=`:

```rlqs
content install "/ks.cfg" from="answers/ks.cfg"
```

`from=` paths are relative to the script file's directory. Absolute
paths and `.` / `..` segments are rejected, and the path must be an
uninterpolated string. File-backed content uses the same `${key}`
property-template handling as inline content, but does not use
indentation cleanup: the external file is already its own authored
document. Its served body is still normalized to end with exactly
one final LF unless the file is empty, which is rejected.

An inline body is a triple-quoted text body, not a statement list.
By default,
Reliquary applies Java-text-block-style indentation cleanup before
serving: it finds the common leading whitespace of all non-blank
body lines and removes exactly that prefix from every body line
that has it. This lets authors indent the response inside the
script without indentation leaking into the answer file. Blank
lines do not participate in computing the margin and remain blank.
The served body ends with exactly one final LF unless the body is
empty, which is rejected.

When indentation is meaningful and must be preserved exactly, the
content entry opts out with `indent=literal`:

```rlqs
content verbatim "/verbatim.txt" indent=literal """
    leading spaces are served
"""
```

This is closer to Java text blocks than to Python: Java's `"""`
syntax strips incidental indentation by default, while Python
triple-quoted strings preserve indentation exactly unless the
caller separately applies `textwrap.dedent()` or
`inspect.cleandoc()`. Reliquary makes the common installer-answer
case the default and uses an explicit modifier for the
non-adjusted form.

Property expansion uses the same `${key}` spelling as script
strings. Inline content expands only after dedent. File-backed
content expands after the file is read. To write a literal `${`,
use the same `\${` escape. No other string escapes are interpreted
in content: backslashes, quotes, XML, shell syntax, `%post`
sections, and installer punctuation pass through as text.

Duplicate guest-visible paths fail static validation. A script with
no `http` block has no server and no reserved port. More than one
`http` block is a static error.

The served URL space is intentionally small:

- paths are normalized URL paths beginning with `/`;
- `.` and `..` segments are rejected;
- only `GET` and `HEAD` are served;
- MIME type is best-effort from the file extension and not part of
  the stable contract;
- no path outside the declared content map is reachable.

The `http` node is declarative: it describes bytes to serve and a
port range. It does not wait, branch, or select control flow. The
triple-quoted inline `content` body is the one deliberate exception
to the language's usual "blocks contain nodes" rule, justified by
the fact that installer answer files are themselves line-oriented
documents.

The executable lifetime controls are ordinary statements:

```rlqs
http start
http start install
http stop
```

`http start` opens the run-scoped listener and binds
`rlq.http.ip`, `rlq.http.port`, and `rlq.http.url` for that run. It
requires declared content or content entries in its own block. With
no names it starts all declared content. With names, it starts only
those declared entries. `http stop` closes the listener if it is
running and does nothing if it is already stopped. Authors may stop
the server as soon as the guest no longer needs the answer file; if
they omit the final stop, the run performs it implicitly.

For odd installers that need a changed response at a later step,
`http start` may carry content entries directly in a block. These
entries are validated like declarations and replace same-named
declared content for that start:

```rlqs
http start {
    content install "/install.conf" """
        System hostname? = second-stage
    """
}
```

## Address Binding

When an `http` block is present, Reliquary binds three reserved
run properties:

```rlqs
$rlq.http.ip
$rlq.http.port
$rlq.http.url
```

`$rlq.http.ip` is the guest-reachable host address,
`$rlq.http.port` is the selected port as text, and
`$rlq.http.url` is `http://${rlq.http.ip}:${rlq.http.port}`. They
are available wherever a text property expansion is already legal,
primarily `type` and `enter`:

```rlqs
enter "linux inst.ks=${rlq.http.url}/ks.cfg"
```

The whole `rlq.*` property namespace is reserved for Reliquary, as
is the long-form `reliquary.*` namespace. User-authored
properties, blueprint parameters, environment bindings, and
property-file entries may not declare or supply any `rlq`,
`rlq.*`, `reliquary`, or `reliquary.*` key. A script that
references an `rlq.http.*` property without an `http` block fails
static validation. The HTTP facts are bound after the listening
socket is opened by `http start`, so a typed URL names a server
that is already reachable.

The reserved properties are run-local facts, not user properties:
they never appear in `user.properties`, blueprint `parameters`, or
transcripts as input values. Run records may report the selected
address and port because they are not secret and are useful
diagnostics.

## Generated Content and Secrets

`content` bodies are templates using the same `${key}` expansion as
script strings. They may reference declared script properties:

```rlqs
property text identity.full-name
property secret products.windows.install-key

http {
    content autounattend "/autounattend.xml" """
        <UserData>
          <FullName>${identity.full-name}</FullName>
          <ProductKey>${products.windows.install-key}</ProductKey>
        </UserData>
    """
}
```

Generated content is rendered during preflight, after property
binding and before execution reaches the first statement. A missing
or kind-mismatched property fails before the machine starts.

Secret properties may be expanded into generated content. This is
the answer-file equivalent of typing a product key into an
installer: Reliquary protects its own host-side records, but cannot
prevent the guest or installer from storing or displaying the
secret. The protection rules are:

- the generated body is never written into the run record,
  transcript, or machine state;
- a served response whose rendered body contains a secret value is
  recorded only as a path, byte count, and redacted property-key
  list;
- diagnostics redact exact secret values from HTTP rendering and
  serving errors;
- automatic failure screenshots are suppressed after any secret
  response has been served, using the same transcript rule as
  secret `enter` / `type`.

File-backed `from=` content is implemented as a single authored
asset reference from a script to a text file. The file is read
during script loading/checking so missing or unreadable content
fails before the machine starts. General asset distribution remains
a backlog item: the built-in codex still needs self-contained
scripts unless a later codex-closure format names additional
support files, and serving arbitrary sibling directories is outside
milestone 5.

## Port Selection

The `http` node accepts:

```rlqs
http port-min=8000 port-max=9000 {
    content answer "/answer.cfg" """
        install
    """
}
```

Both modifiers are optional; the defaults are 8000 and 9000. Values
are decimal integers. The range is inclusive; `port-min` must be
less than or equal to `port-max`; values must be valid TCP port
numbers. Setting both to the same value pins the server to that
port. If no port in the range can be bound when `http start`
executes, the run fails naming the range.

The API exposes the same settings through the parsed script surface,
not through separate `run_script` parameters. A caller that wants a
different range edits or generates the script it owns, preserving
CLI-API parity and keeping the run's behavior inspectable from the
authored asset.

## QEMU Reachability

Milestone 5 targets the QEMU backend only. QEMU uses user-mode
networking when an HTTP server is declared and the machine has no
explicit backend networking settings. The guest-reachable host
address is QEMU user networking's host gateway, `10.0.2.2`, so
`$rlq.http.ip` is `10.0.2.2` on this path.

This is an interim backend default, not a first-class blueprint NIC
model. A later milestone that grows backend adapters and richer
device modeling owns portable network devices. Until then:

- the script's `http` block declares the need for host-reachable
  networking;
- QEMU launch configuration supplies the minimal user-mode network
  needed to satisfy it;
- a blueprint with `backend-settings.qemu.args` that replaces or
  conflicts with that network configuration must also make the
  host reachable, or preflight fails naming the conflict;
- no behavior is inferred from the guest.

The implementation should prefer the least surprising QEMU shape
that works for installer fetches under the DOS-on-QEMU vertical:
user networking with an emulated NIC appropriate for the platform.
If a platform has no supported network path yet, the capability
check fails before the run.

## CLI and API

The main surface is the script declaration. `run-script` and
`run_script()` need no extra server flags: the script says whether
there is a server, and the live address is bound inside that run.
`check-script` reports the HTTP plan, including generated paths,
port range, and whether generated content references secrets,
without rendering or printing secret values.

The run-event stream added later records server lifecycle events:
server started, request served, request failed, and server stopped.
Until run records land, pretty progress may still mention these
events, but the stable record contract waits for milestone 9.

## Example

```rlqs
description "Example Linux install with Kickstart over HTTP"
platform    dos
machine     stopped
timeout     30s
deadline    45m

property text identity.full-name prompt="Registered owner"

http {
    content install "/ks.cfg" """
        install
        url --url=https://mirror.example/os/
        lang en_US.UTF-8
        rootpw ${accounts.root-password}
    """
}

insert cdrom0 @example-linux-installer
start
wait "boot:"
http start install
enter "linux inst.ks=${rlq.http.url}/ks.cfg"
wait "Installation complete"
http stop
stop
eject cdrom0
```

The script controls how the installer learns the URL; Reliquary
only supplies the guest-reachable address and serves the bytes.

## Validation Summary

Static checks:

- at most one `http` block;
- valid `http` modifiers and port range;
- reserved `rlq.*` and `reliquary.*` keys are not declared as user
  properties;
- `rlq.http.*` references appear only when an `http` block exists;
- declared content names are unique;
- `http start` names declared content, or carries content entries
  in its own block;
- `http` statement actions are `start` or `stop`;
- served URL paths are absolute normalized paths;
- `content` has either a non-empty triple-quoted body or a readable
  `from=` source file, never both, and only supported modifiers.

Preflight checks:

- generated-content property references bind with the declared
  kind rules;
- the backend can make the server reachable from the guest;
- backend-specific networking settings do not conflict with the
  host-reachability requirement.

Run-time checks:

- a free port exists in the range when `http start` executes.

## Non-goals

- A Reliquary-owned declarative install language.
- Replacing the FreeDOS (or other answer-file-less) keystroke
  path.
- A long-lived or home-wide HTTP service - the server is
  run-scoped only.
- Serving arbitrary host filesystems or sibling answer files; those
  require a separate asset-distribution design.
