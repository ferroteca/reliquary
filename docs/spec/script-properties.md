<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Script properties

> **Status:** normative and **implemented** (milestone 8, complete).
> This document covers: the **user properties file** — its line
> format, the key-naming rules, the `@` value kinds, how edits
> preserve comments, and the four maintenance verbs with their API
> equivalents; **secret storage** — the credential-store interface
> that different backend providers implement, the ways a secret
> value can be entered, the fail-safe order for updates, and how
> orphaned credentials are handled; **file selection** —
> `--properties` / `RELIQUARY_PROPERTIES` (the CLI's two ways to set
> it, both feeding into the record it builds) and the `Context`
> object's `properties_file` field (the API's one way to set it,
> part of what P26 requires a `Context` to carry), with credentials
> scoped by the selected file's absolute path; **binding into a
> run** — the ordered list of sources (flag, blueprint parameter and
> its redirect, environment with a collision check, file, the
> **declared derivation** with its `rlq.*` host facts, then an
> interactive ask), the rules for matching declared kinds, and the
> runtime rules for secrets (redacted from transcripts and
> diagnostics; a dry run names each key's source but never its
> value); and **`${key}` location references**, which bind at
> `create` / `apply` through that same source order, get recorded in
> state, are never re-resolved at `start`, and cannot be chained.
> Windows is the only host whose credential backend has been
> exercised so far (planning/proposed/FEATURES.md, "Host
> portability"). Details may still change before first release.

Script properties hold values a script consumes without embedding
them directly in the script text: values that stay the same across
installations — a registered owner, a preferred login name, product
installation keys, organization names, initial passwords — and
values specific to one run. A script [declares its
properties](script-spec.md#properties). Several sources can supply
an answer for the same key: an explicit `--property` value on the
command line, the blueprint's designed parameters, the environment,
the user properties file, the script's own declared derivation, and
finally an interactive ask. The order these sources are tried in is
fixed, and normative in the [script
spec](script-spec.md#the-property-sources). This document covers
the operator-facing mechanics of those sources. One of them is the
durable **user properties file**, which belongs to a person; the
other sources are ephemeral — they let automation supply a value for
one run without writing it into that personal file.

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

The file is line-based — decided on 2026-07-21 as part of settling
the file format (owner): one `key = value` per line, `#` full-line
comments, and blank lines. Dotted names give a human-chosen way to
namespace keys; the dots don't imply any traversal or inheritance
behavior:

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
continuations. Despite the familiar `.properties`-style name, this
format is deliberately *not* Java's properties format: none of
Java's Unicode escapes or line-continuation rules apply here. That's
the one trade-off of picking a name editors already recognize
(owner, 2026-07-21).

There are two value kinds:

- An ordinary property's value is the line's text.
- A secret property is exactly `@secret`. Its value is stored
  separately in the host credential store.

A value starting with `@` is reserved for value-kind tokens.
`@secret` is the first one; the reserved prefix is how future value
kinds can be added later without breaking existing files. A literal
leading `@` is written as `@@`. Every ordinary value is
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
In the API and the `--json` rendering, a secret still serializes as
the JSON marker `{"secret": true}` — a returned value is always
either the actual value or that marker object, never the literal
text `@secret`, which is file syntax only.

## Property sources

Anything that can answer for a property key is a source, tried in
one fixed order: an explicit `--property` value, the target
blueprint's parameters, the environment, this file, then an
interactive ask (owner, 2026-07-21; the order is normative in the
[script spec](script-spec.md#the-property-sources)). The blueprint
side is covered in the [blueprint
reference](../blueprint-reference.md#parameters); this document
covers the operator-facing mechanics of the rest:

- **Command line** — a repeatable `--property <key>=<value>`
  supplies one explicit value for one invocation (the API's
  equivalent is the `properties=` mapping, which works the same
  way). It is the caller's answer, and it overrides every other
  source, including the blueprint. Giving the same key twice is an
  error, and each explicit key must be declared by the running
  script. It can never satisfy a secret-typed key, for the same
  reason `set-property --secret` refuses a command-line value:
  command-line arguments show up in process listings and shell
  history.
- **Environment** — `RELIQUARY_PROPERTY_<KEY>` supplies a
  standing value for the process: the injection path for CI
  harnesses and other automation (U14, U4), sitting below the
  blueprint — an ambient variable never overrides a designed
  value. The spelling uppercases the key
  and maps `.`, `-`, and `_` all to `_`:
  `products.windows-98.install-key` is read from
  `RELIQUARY_PROPERTY_PRODUCTS_WINDOWS_98_INSTALL_KEY`. That
  mapping can collide; when two keys a run actually consults
  mangle to the same variable, preflight fails naming both
  keys. An environment value may satisfy a secret-typed key — this
  is the path CI systems use to inject secrets — but it sits as
  plain text in the process environment, which gives it weaker
  protection than the credential store; this document calls that
  out explicitly. The credential store remains the safer, lasting
  place to keep secrets.
- **The properties file** — `user.properties` in the Reliquary
  home, or the file named by `--properties <path>` (environment
  `RELIQUARY_PROPERTIES`; API: the record's `properties_file`
  slot), which
  *replaces* the home file for that invocation rather than
  layering over it. Pointing it at a project-controlled file
  makes a run hermetic: nothing from the operator's personal
  file can reach it. Ordinary values, secret markers, and the
  kind rules live at this source — the ephemeral sources above
  hold direct values only.
- **The declared derivation** — the script's own computed
  answer: a declaration's `default=` candidates, tried in
  declaration order, each resolved in the script language's
  reference grammar over literal text, other declared keys, and
  the `rlq.*` system facts (the catalog below). The first
  candidate whose references all bind answers the key — a
  literal default always answers, so declaring one is opting to
  stop here — and a key no candidate answers falls through to
  the ask. Derivations are recorded like any source:
  a dry run and transcripts name the supplying source, so
  a host-derived value is always auditable, and no hermetic ban
  applies — a project wanting determinism pins the key in its
  committed properties file.
- **Asking** — in an interactive context (a terminal under the
  `auto`/`pretty` progress renderings) the last source asks the
  user (owner, 2026-07-21): one ask per unresolved key per run,
  presented with the declaration's `prompt=` text, its answer
  serving every reference to the key. The answer is
  invocation-local and never
  written back. Noninteractively this source does not exist: the
  order exhausts and binding fails during preflight, before the
  machine starts.

The system facts are what the reserved namespaces were held
for: values Reliquary computes from the host, referenceable in
derivations and unwritable by any user source. The canonical
namespace is the short one — `rlq.*`, the name users already
type — while `reliquary.*` stays reserved and empty, never an
alias. The initial catalog is deliberately small — each fact's
derivation is part of its contract:

- `rlq.host.username` — the host login name, normalized
  to a login-safe form (the per-platform derivation is
  documented with the implementation).
- `rlq.host.full-name` — the host account's descriptive
  name (display name on Windows, the GECOS field on POSIX);
  frequently empty, and an empty fact makes a derivation
  unanswerable by design.
- `rlq.env.<NAME>` — the named host environment variable, read
  verbatim. It exists as a raw fallback beside the curated facts
  above, playing the same role `backend-settings` plays beside the
  portable machine fields: a derivation that reads a raw
  environment variable is host-specific by construction, and the
  reference itself makes that obvious. Lookup follows the
  platform's own case rules. An unset or empty variable makes the
  fact unanswerable. A name outside the property-segment grammar
  cannot be referenced at all. Env facts are always ordinary text —
  routing a secret through one would bypass its protected handling,
  so secrets use their own channels instead. This is different from
  the environment *tier* described above: `RELIQUARY_PROPERTY_*`
  lets a session push a value in for any declared key, while an env
  fact is pulled by name, only where a declaration's derivation
  explicitly asks for it.

Adding to this catalog is a design decision, the same as adding a
new tier — `rlq.host.hostname` and a raw, unnormalized username are
candidates being held for later. Adding transform functions to the
derivation syntax itself is permanently off the table: normalizing
a value belongs in that fact's own definition, and any other
computation belongs in the embedding API's provider interface, not
in the script language.

A blueprint [redirect](../blueprint-reference.md#parameters) looks
up its target key using the sources in this document, other than
the blueprint itself. For example, a CI run can satisfy a redirect
to `products.windows-98.install-key` from its own secret store,
through the environment, without needing to set up a Reliquary home
first.

### Growth: the order is fixed, but three routes let it grow

The order of sources is part of the design, not a setting — each
rank encodes a deliberate decision (an ambient environment variable
never overrides a designed value; the command line never carries
secrets; an interactive answer only applies to that one run) — so
nothing exposed to end users can reorder the tiers or insert a new
one. Even so, the model can still grow, through three routes decided
by design (owner, 2026-07-23; planning/DECISIONS.md):

- **A new tier is added by design decision, at a fixed rank.** A
  new source is added as a one-line change to the normative order,
  and every existing property bundle keeps resolving exactly as it
  did before.
- **Multiple providers can exist inside one tier, behind a shared
  interface.** The credential store is the existing example: Windows
  Credential Manager, macOS Keychain, and a Secret Service provider
  all implement the same interface; a future corporate-secrets
  provider would join the same way, as another implementation of
  that interface, without changing the order at all.
- **Code-driven insertion belongs to the embedding API.** A future
  `register_property_source(name, provider, before=/after=<rank>)`
  call may let *code* insert a source at a named rank. That stays a
  decision made by the developer who writes and versions that code —
  never something a per-machine operator can configure — and it must
  record where the value came from: a dry run and transcripts would
  name the injected source exactly like any built-in tier. The
  provider protocol itself will be defined by Reliquary and kept
  simple enough for any binding language to implement
  (planning/SURFACES.md), rather than adopting an existing settings
  library's own interface.

Other configuration systems converge on the same pattern, which
supports this design: Spring's PropertySource model (a fixed,
documented precedence for file-based users, with programmatic
changes reserved for code, and a chain you can list out with
per-key provenance), Go's Viper (explicit > flag > env > file >
remote store > default), and .NET's configuration providers with
user secrets. Ansible shows what this rule is guarding against: its
precedence order has grown to twenty-two levels. PAM and
nsswitch.conf show the opposite failure: they let an operator
reorder their own config files with no record of why. Reliquary's
own implementation stays simple — the code that resolves a property
through its sources is small — but the design itself (the designed
blueprint tier, the interactive ask, secret kinds bound to the
credential store and the run engine's redaction rules, this file's
surgically editable line format) is specific to Reliquary and not
something any existing settings library provides. Two existing
libraries, pydantic-settings and Dynaconf, were considered and
turned down; the reasons, and the condition for reconsidering them,
are recorded in planning/DECISIONS.md (2026-07-23).

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
`set-property <key> --secret` reads the value from whichever input the
context provides (owner, 2026-07-21 — the same approach Reliquary uses
elsewhere to detect an interactive terminal): on an interactive
terminal, it shows a prompt that doesn't echo what you type;
otherwise, it reads stdin to the end, strips one trailing newline,
and rejects an empty value. So `echo $key | rlq set-property
product-key --secret` is how a script would do this, and the CLI
stays a complete way to set a secret from a language that has no
Reliquary API of its own. Either way, the value is written to the
host credential store, and only the secret marker is recorded in the
properties file. There is no command-line argument for a secret's
value, because process listings and shell history are not credential
stores.

Replacing a property with another value of the same kind is allowed.
Changing between ordinary and secret requires `unset-property` first, preventing an
accidental secret downgrade. Unsetting a secret removes both its marker and
its credential.

The embedding API's equivalents are `list_properties(prefix=None)`,
`get_property(key)`, `set_property(key, value, secret=False)`, and
`unset_property(key)` (docs/spec/api.md). There is one deliberate
difference (owner, 2026-07-21): `set_property` takes a secret's
value as its ordinary in-memory `value` parameter. The CLI needs its
own separate entry methods because command-line arguments leak into
process listings and shell history, which an in-process value never
does — and a library function should never prompt for input or read
from stdin on its own. Reading follows the same rule as the CLI:
`get_property` returns an ordinary value, but for a secret it
returns only the marker, never the value (matching the `--json`
serialization). `list_properties` returns the same projection — each
key mapped to its value or its marker — that the pretty-printed
listing is rendered from. The kind-change rule applies here
unchanged too: `set_property` fails if the property already exists
with the other kind; call `unset_property` first.

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
overrides even the blueprint for one run, and when no outer
source answers, a declared derivation answers when it can, an
interactive run asks, and a
noninteractive run fails before the machine starts. Asked
values are invocation-local; Reliquary never changes the user's properties
unless the user runs a property command or calls the corresponding
embedding API.

Declaration types and stored kinds must agree:

- `text` consumes an ordinary string.
- `media` consumes an ordinary string, then resolves it as a media item name.
- `secret` consumes a secret property and otherwise behaves like protected
  text.

A `text` or `media` declaration that resolves to a secret property is an
error, and so is a `secret` declaration that resolves to an ordinary
stored value — this stops a secret from accidentally losing its
protected handling. The ephemeral sources (command line and
environment) have their own secret rules, described under
[Property sources](#property-sources): a secret can never come from
the command line, and coming from the environment is allowed but
flagged there as weaker protection.

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

`run-script --dry-run` validates property-key syntax and
declaration/kind compatibility without changing the properties file or credential store. It reports
each declared property's supplying source — flag, blueprint
parameter (direct or redirect), environment, file, derivation,
or ask — but never reports values. A missing property is reported as an unresolved
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
