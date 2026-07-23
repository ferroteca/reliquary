<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Script properties

> **Status:** this documents the planned script-properties
> mechanism — its sources and the user properties file. None of it
> is implemented yet; details may still
> change before first release.

Script properties carry the values scripts consume without
embedding them:
machine-independent values that recur
across installations — a registered owner, a preferred login
name, product
installation keys, organization names, initial passwords — and
run-specific answers. A script [declares its
properties](script-spec.md#properties); every source that can
answer speaks the same keys: the caller's explicit `--property`
values, the blueprint's designed parameters, the environment, the
user properties file, and finally an interactive ask (the
flattened order is
normative in the [script
spec](script-spec.md#the-property-sources)). This document owns
the operator-side mechanics of those sources, and among them the
*person's* source — the durable **user properties file** — while
the ephemeral
sources let
automation inject the values it may not check in without
touching a personal file.

Each Reliquary home has one user properties file:

```text
<reliquary_home>/user.properties
```

It belongs to the user, not to a machine or script. Changing homes selects
different properties. Reliquary never copies property values into a machine
blueprint or script.

An absent file means no properties. The first successful `set-property`
creates it; reading or running an unrelated script does not.

## Property names and values

The file is line-based (owner, 2026-07-21 — the format round):
one `key = value` per line, `#` full-line comments, and blank
lines. Dotted names provide human-chosen
namespaces without giving dots traversal or inheritance semantics:

```properties
# reliquary user properties
identity.full-name = Paul Galbraith
identity.preferred-username = paul

# the Win98 key lives in the credential store
products.windows-98.install-key = @secret
accounts.default-password = @secret
```

A property name consists of dot-separated script identifiers. Segments use
ASCII letters, digits, `_`, and `-`, must start with a letter, and are
case-sensitive. Lowercase names are recommended. Names such as
`identity.full-name`, `products.<product>.install-key`, and
`accounts.<purpose>.password` make ownership clear. The top-level
`rlq` and `reliquary` namespaces are reserved for Reliquary-owned
run facts and future system properties; user-authored properties,
blueprint parameters, environment bindings, and property-file
entries may not use `rlq`, `rlq.*`, `reliquary`, or any
`reliquary.*` key.

Whitespace around `=` is trimmed; the value is the trimmed
remainder of the line, verbatim — no quoting, no escapes, no line
continuations. Despite the familiar extension, the format is
deliberately *not* Java properties: none of its unicode escapes
or continuation rules apply — the named caveat of the
editor-friendly name (owner, 2026-07-21).

There are two value kinds:

- An ordinary property's value is the line's text.
- A secret property is exactly `@secret`. Its value is stored
  separately in the host credential store.

A value starting with `@` is reserved for value-kind tokens:
`@secret` is the first, and the reserved prefix is the seam
through which future value kinds are introduced deliberately; a
literal leading `@` is spelled `@@`. Every ordinary value is
text — input declarations provide the useful type. Duplicate
keys, invalid property names, and unparseable lines fail
validation naming the file and line.

The file is UTF-8. Property commands edit it surgically:
`set-property` rewrites or appends the one line it names (written
canonically as `key = value`), `unset-property` deletes it, and
every comment, blank line, and ordering choice elsewhere in the
file is preserved — the reason the format is line-based, and what
the earlier strict-JSON shape (whose canonical rewrites had to
ban comments) could not offer. Writes are atomic; an invalid file
is reported with its path and line and is never partly rewritten.
In the API and the `--json` rendering a secret still serializes
as the JSON marker `{"secret": true}` — returns stay JSON-shaped
under the value-union rule; `@secret` is file syntax only.

## Property sources

Everything that can answer for a property key is a source, in one
flattened order — an explicit `--property` value, the target
blueprint's parameters, the environment, this file, then an
interactive ask (owner, 2026-07-21; the order is normative in the
[script spec](script-spec.md#the-property-sources)). The blueprint
side belongs to the [blueprint
reference](machine-blueprint-reference.md#parameters); this
document owns the operator-side mechanics:

- **Command line** — a repeatable `--property <key>=<value>`
  supplies one explicit value for one invocation (API: the
  `properties=` mapping under parity). It is the caller's answer
  and beats every other source, the blueprint included; a key
  given twice is an error, and each explicit key must be declared
  by the running script. It never satisfies a secret-typed key:
  argv enters process listings and shell history — the
  `set-property` rule.
- **Environment** — `RELIQUARY_PROPERTY_<KEY>` supplies a
  standing value for the process: the injection path for CI
  harnesses and other automation (U3, U4), sitting below the
  blueprint — an ambient variable never overrides a designed
  value. The spelling uppercases the key
  and maps `.`, `-`, and `_` all to `_`:
  `products.windows-98.install-key` is read from
  `RELIQUARY_PROPERTY_PRODUCTS_WINDOWS_98_INSTALL_KEY`. That
  mapping can collide; when two keys a run actually consults
  mangle to the same variable, preflight fails naming both
  keys. An environment value may satisfy a secret-typed key —
  the CI secret-injection path — but it is plaintext in the
  process environment, a warned protection class; the credential
  store remains the durable home
  for secrets.
- **The properties file** — `user.properties` in the Reliquary
  home, or the file named by `--properties <path>` (environment
  `RELIQUARY_PROPERTIES`; API `properties_file=`), which
  *replaces* the home file for that invocation rather than
  layering over it. Pointing it at a project-controlled file
  makes a run hermetic: nothing from the operator's personal
  file can reach it. Ordinary values, secret markers, and the
  kind rules live at this source — the ephemeral sources above
  hold direct values only.
- **Asking** — in an interactive context (a terminal under the
  `auto`/`pretty` progress renderings) the last source asks the
  user (owner, 2026-07-21): one ask per unresolved key per run,
  presented with the declaration's `prompt=` text, its answer
  serving every reference to the key. The answer is
  invocation-local and never
  written back. Noninteractively this source does not exist: the
  order exhausts and binding fails during preflight, before the
  machine starts.

A blueprint [redirect](machine-blueprint-reference.md#parameters)
resolves its target key through the non-blueprint sources here: a
CI run may satisfy a redirect to
`products.windows-98.install-key` from its own
secret store via the environment, without pre-provisioning
a Reliquary home.

## Maintaining properties

Ordinary values may be edited directly or maintained through the CLI:

```text
rlq list-properties [<prefix>]
rlq get-property <key>
rlq set-property <key> <value>
rlq set-property <key> --secret
rlq unset-property <key>
```

Every property command operates on the selected properties file —
the home file, or the file named by `--properties` — so a
project-controlled file's secret markers can be provisioned with
`set-property --secret` like any other.

`list-properties` sorts keys and shows whether each is ordinary, a present secret, or a
secret whose credential is missing. A prefix such as `products.windows-98`
limits the listing to that key and its dotted descendants; it is not a raw
string-prefix search. `get-property` prints an ordinary value; for a secret it reports
only whether the credential exists and never reveals it.

`set-property <key> <value>` creates or replaces an ordinary property.
`set-property <key> --secret` reads the value from the entry channel the
context provides (owner, 2026-07-21 — the house tty-detection pattern): on
an interactive terminal, a no-echo prompt; otherwise it reads stdin to EOF,
strips one trailing newline, and rejects an empty value — so
`echo $key | rlq set-property product-key --secret` is the programmatic
path and the CLI stays a complete binding for unbound languages. Either
way the value is written to the host credential store and only the secret
marker is recorded in the properties file. There is no secret-value
command-line argument because process listings and shell history are not
credential stores.

Replacing a property with another value of the same kind is allowed.
Changing between ordinary and secret requires `unset-property` first, preventing an
accidental secret downgrade. Unsetting a secret removes both its marker and
its credential.

The embedding-API twins are `list_properties(prefix=None)`,
`get_property(key)`, `set_property(key, value, secret=False)`, and
`unset_property(key)` (planning/design/api.md). One named divergence
(owner, 2026-07-21): `set_property` takes a secret's value as its
ordinary in-memory `value` parameter — the CLI's entry channels exist
because argv leaks into process listings and shell history, which an
in-process value never touches, and a library function never prompts
or reads stdin. Reading stays the CLI's rule: `get_property` returns
an ordinary value but only the secret marker for a secret, never the
value (exactly the `--json` serialization); `list_properties` returns
the properties projection — key to value-or-marker — of which the
pretty listing is a rendering; and the kind-change rule
applies unchanged — `set_property` over a property of the other kind
fails; `unset_property` first.

The JSON file and a host credential service cannot provide one atomic
transaction. Reliquary therefore orders updates fail-safely: it stores a new
credential before publishing its marker, and removes a marker before deleting
its credential. An interrupted operation may leave an inaccessible orphaned
credential, but never a plaintext fallback or a marker that Reliquary reported
as successfully bound. A later property command reports any orphan it can
identify and gives explicit cleanup guidance; read-only commands never remove
credentials.

## Secret storage

Secret properties occupy the same logical property set and use the same names
as ordinary properties, but their values never appear in the properties file.
Reliquary stores them in the host's protected credential service, scoped by
the absolute path of the properties file holding the marker and the
property name (for a home's file, that path is
`<reliquary_home>/user.properties` — the original home scoping,
generalized to selected files). Windows Credential Manager,
macOS Keychain, and a Secret Service provider on Linux are examples of
suitable backends; the public contract is the protected credential-store
capability, not a particular library.

There is no plaintext fallback. If a required secret marker has no credential
or the host has no usable credential store, binding fails before machine
creation or startup. Copying a properties file to another home copies names
and ordinary values but intentionally does not copy credentials.

Product keys are not necessarily passwords, but treating them as secret
properties is the safe default. A user may store a non-sensitive product key
as an ordinary property when disclosure is acceptable.

## Binding script properties

A script declares each property it consumes; the declared name *is*
the key here — there is no separate script-side namespace:

```rlqs
property identity.full-name prompt="Registered owner"
property identity.preferred-username prompt="Login name"
property secret products.windows-98.install-key
property secret accounts.default-password
```

The key is literal — never computed at runtime — and declared once
per script; `${key}` references reuse the one bound value. The
[script spec](script-spec.md#properties) owns the declaration
grammar and the [source order](script-spec.md#the-property-sources);
this document owns the sources' operator-side mechanics and the
stored values. The short form: the blueprint's designed values
override this file's standing defaults, an explicit `--property`
overrides even the blueprint for one run, and when no source
answers, an interactive run asks and a
noninteractive run fails before the machine starts. Asked
values are invocation-local; Reliquary never changes the user's properties
unless the user runs a property command or calls the corresponding
embedding API.

Declaration types and stored kinds must agree:

- `text` consumes an ordinary string.
- `media` consumes an ordinary string, then resolves it as a media item name.
- `secret` consumes a secret property and otherwise behaves like protected
  text.

A `text` or `media` declaration finding a secret property is an error, as is
`secret` finding an ordinary stored value. This prevents an accidental
downgrade from
protected handling. The ephemeral sources carry their own secret
rules — never argv, the environment as a warned plaintext class —
under [Property sources](#property-sources).

## Secret properties at runtime

A `secret` property may be expanded only in `enter` and `type` arguments. It
cannot influence observations, menu selection, state names, paths, media
names, screenshot names, or control flow. Reliquary treats the entire expanded
argument as sensitive:

- transcripts record the property key and its supplying source, never its
  value or expanded argument;
- diagnostics redact exact secret values from scraped text and exceptions;
- automatic failure screenshots are suppressed for the rest of a run after
  secret entry, with the suppression recorded in the transcript; and
- secret values are retained in memory only for the run that binds them.

These rules protect Reliquary's host-side records. They cannot prevent a guest
installer from displaying a value, storing it in its own logs or command
history, or exposing it in an explicitly requested screenshot. Script authors
must still use the guest's password or product-key entry fields correctly.

## Checking and diagnostics

`check-script` validates property-key syntax and declaration/kind
compatibility without changing the properties file or credential store. It reports
each declared property's supplying source — flag, blueprint
parameter (direct or redirect), environment, file, or ask —
but never reports values. A missing property is reported as an unresolved
key rather than being created implicitly, and an environment-name
collision among consulted keys is reported naming both keys.

Binding failures identify the declared property key, then state
whether it is unanswered, has the wrong kind, lacks its secret
credential, or cannot be accessed through a secure host store. All such
failures occur during preflight, before a media is materialized or a
machine is created or started.

## Sharing

`user.properties` is personal configuration, not part of a shareable
blueprint/script bundle. A bundle shares property declarations and
their recommended keys; each recipient supplies their own properties,
explicit values, or interactive answers.
An example properties file in a bundle contains only non-sensitive
illustrative values. Secret
markers and credentials are never installed from scripts.

A project *may* commit a properties file of its own for
`--properties` runs — ordinary values and secret markers only,
since a marker is not a secret. Each user still provisions the
marker's credential in their own host store
(`set-property --secret --properties <path>`), which is exactly
U4's model: the repository defines everything except what it must
not contain.
