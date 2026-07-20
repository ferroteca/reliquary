<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The user property registry

> **Status:** this documents the planned property-registry format and
> scripting integration. Neither is implemented yet; details may still
> change before first release.

The user property registry keeps machine-independent values that recur
across installations: a registered owner, a preferred login name, product
installation keys, organization names, and initial passwords. Scripts bind
their inputs to named properties instead of embedding personal values or
requiring the same answers on every run.

Each reliquary home has one registry:

```text
<reliquary_home>/properties.json
```

It belongs to the user, not to a machine or script. Changing homes selects a
different registry. Reliquary never copies registry values into a machine
blueprint, script, media definition, or response file.

An absent file means an empty registry. The first successful `property set`
creates it; reading or running an unrelated script does not.

## Property names and values

The registry is a flat JSON object. Dotted names provide human-chosen
namespaces without giving dots traversal or inheritance semantics:

```json
{
  "identity.full-name": "Paul Galbraith",
  "identity.preferred-username": "paul",
  "products.windows-98.install-key": {"secret": true},
  "accounts.default-password": {"secret": true}
}
```

A property name consists of dot-separated script identifiers. Segments use
ASCII letters, digits, `_`, and `-`, must start with a letter, and are
case-sensitive. Lowercase names are recommended. Names such as
`identity.full-name`, `products.<product>.install-key`, and
`accounts.<purpose>.password` make ownership clear, but reliquary reserves no
top-level namespace.

There are two value kinds:

- An ordinary property is a JSON string stored directly in the file.
- A secret property is exactly `{"secret": true}` in the file. Its value is
  stored separately in the host credential store.

Numbers, booleans, null, arrays, other object shapes, duplicate keys, and
invalid property names fail validation. The initial registry deliberately
stores only strings: input declarations provide the useful type, and
future value kinds can be introduced deliberately instead of through JSON
coercion.

The file is UTF-8 JSON. Reliquary accepts user formatting but writes a stable,
canonical format when a property command changes it. Writes are atomic; an
invalid file is reported with its path and location and is never partly
rewritten.

## Maintaining properties

Ordinary values may be edited directly or maintained through the CLI:

```text
reliquary property list [<prefix>]
reliquary property get <key>
reliquary property set <key> <value>
reliquary property set <key> --secret
reliquary property unset <key>
```

`list` sorts keys and shows whether each is ordinary, a present secret, or a
secret whose credential is missing. A prefix such as `products.windows-98`
limits the listing to that key and its dotted descendants; it is not a raw
string-prefix search. `get` prints an ordinary value; for a secret it reports
only whether the credential exists and never reveals it.

`set <key> <value>` creates or replaces an ordinary property. `set <key>
--secret` reads a value using a no-echo terminal prompt, writes it to the host
credential store, and records only the secret marker in `properties.json`.
There is no secret-value command-line argument because process listings and
shell history are not credential stores. Secret setting without an
interactive terminal fails with guidance to use the embedding API or the
host's credential-management facility.

Replacing a property with another value of the same kind is allowed.
Changing between ordinary and secret requires `unset` first, preventing an
accidental secret downgrade. Unsetting a secret removes both its marker and
its credential.

The JSON file and a host credential service cannot provide one atomic
transaction. Reliquary therefore orders updates fail-safely: it stores a new
credential before publishing its marker, and removes a marker before deleting
its credential. An interrupted operation may leave an inaccessible orphaned
credential, but never a plaintext fallback or a marker that reliquary reported
as successfully bound. A later property command reports any orphan it can
identify and gives explicit cleanup guidance; read-only commands never remove
credentials.

## Secret storage

Secret properties occupy the same logical registry and use the same names as
ordinary properties, but their values never appear in `properties.json`.
Reliquary stores them in the host's protected credential service, scoped by
the absolute reliquary home and property name. Windows Credential Manager,
macOS Keychain, and a Secret Service provider on Linux are examples of
suitable backends; the public contract is the protected credential-store
capability, not a particular library.

There is no plaintext fallback. If a required secret marker has no credential
or the host has no usable credential store, binding fails before machine
creation or startup. Copying `properties.json` to another home copies names
and ordinary values but intentionally does not copy credentials.

Product keys are not necessarily passwords, but treating them as secret
properties is the safe default. A user may store a non-sensitive product key
as an ordinary property when disclosure is acceptable.

## Binding script inputs

An input opts into the registry with the `property:` modifier:

```rqs
input text owner, property: "identity.full-name", prompt: "Registered owner"
input text login, property: "identity.preferred-username", prompt: "Login name"
input secret product-key, property: "products.windows-98.install-key"
input secret password, property: "accounts.default-password"
```

The modifier names one literal property key. It does not accept input
expansion or compute a key at runtime. Several inputs may intentionally
bind to the same property.

Binding uses this precedence for each input:

1. A value explicitly supplied in the invocation's response file.
2. The property named by the declaration's `property:` modifier.
3. Interactive prompting using `prompt:` or the input name.

An explicit response therefore overrides a personal default for one run.
When neither a response nor a usable property is present, an interactive run
prompts and a noninteractive run fails before the machine starts. Prompted
values are invocation-local; reliquary never changes the registry unless the
user runs a property command or calls the corresponding embedding API.

Input and property kinds must agree:

- `text` consumes an ordinary string.
- `media` consumes an ordinary string, then resolves it as a media item name.
- `secret` consumes a secret property and otherwise behaves like protected
  text input.

Binding `text` or `media` to a secret property is an error, as is binding
`secret` to an ordinary property. This prevents an accidental downgrade from
protected handling. A response file may directly supply a string for a
`secret` input, but that file then contains plaintext sensitive data and
must be protected accordingly.

## Secret inputs at runtime

A `secret` input may be expanded only in `enter` and `type` arguments. It
cannot influence observations, menu selection, state names, paths, media
names, screenshot names, or control flow. Reliquary treats the entire expanded
input argument as sensitive:

- transcripts record the input reference and its source kind, never its
  value or expanded argument;
- diagnostics redact exact secret values from scraped text and exceptions;
- automatic failure screenshots are suppressed for the rest of a run after
  secret input, with the suppression recorded in the transcript; and
- secret values are retained in memory only for the run that binds them.

These rules protect reliquary's host-side records. They cannot prevent a guest
installer from displaying a value, storing it in its own logs or command
history, or exposing it in an explicitly requested screenshot. Script authors
must still use the guest's password or product-key entry fields correctly.

## Checking and diagnostics

`check-script` validates property-key syntax and input/property kind
compatibility without changing the registry or credential store. It reports
which inputs resolve from responses, properties, or an interactive prompt
but never reports values. A missing property is reported as an unresolved
source rather than being created implicitly.

Binding failures identify the script input and property key, then state
whether the property is absent, has the wrong kind, lacks its secret
credential, or cannot be accessed through a secure host store. All such
failures occur during preflight, before a media definition is installed or a
machine is created or started.

## Sharing

`properties.json` is personal configuration, not part of a shareable recipe.
A recipe shares input declarations and recommended property names; each
recipient supplies their own registry, response file, or interactive answers.
Example response files contain only non-sensitive illustrative values. Secret
markers and credentials are never installed from scripts.
