<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The conformance corpus

The shared valid/invalid corpus for the **composed blueprint model** —
[docs/spec/blueprint-model.md](../../../../docs/spec/blueprint-model.md),
which is normative for every fixture here.

Written at milestone 7's **S2**, before the parser, so that S3 had an
executable acceptance test from its first line rather than after it.
That ordering paid immediately: run against the first parser written to
the spec, the corpus found the spec **contradicting itself** about
whether a containment path lives inside the braces or after them —
D22/D24 said after, D26/D27 said inside, and blueprint-model.md had
inherited both. Settled inside by D32. A corpus written from a spec and
run against an implementation of the same spec is a differential test
*of the spec*.

## The buckets

| directory | the assertion |
|---|---|
| `valid/` | parses, and validates against the schema |
| `invalid/` | rejected **at parse**, by parser and schema alike |
| `invalid-at-resolution/` | parses clean; rejected when resolved |

The third bucket exists because two-phase validation is real: shape at
parse, value at resolution. A fixture whose rule needs a resolved
value — or a binding to a spec that may live in another file — would
fail a parse-time assertion for the wrong reason, so it is separated
rather than quietly weakened. It needs the resolve harness, not the
parse harness, and the published schema cannot judge it at all.

## Fixture headers

Every fixture opens with comment lines naming what it exercises and
where the rule lives:

```jsonc
// invalid: P14's acceptance test: this passes the character class and
//          is refused by the production - mem is not a qualifier
// spec: The closure
// id: ref.qualifier-unknown
```

A `// warns:` line marks a fixture that is **valid but must emit a
warning** — currently the one name-repair case. There is no warning
assertion yet; adding one is part of S3, and the header is the record
of what it must say.

**The headers are assertions now.** They were documentation, and this
README said so, because an invalid fixture failing for the *wrong*
reason is a false pass and only a reviewer could catch it. Blueprint
diagnostics carry stable ids since 2026-07-27, so a `// id:` line
names the diagnostic that must reject each fixture and the harness
compares it against the raised `rule_id`. All 47 carry one; none reads
`none`. That marker is asserted in both directions, so a fixture
claiming `none` whose diagnostic has since gained an id fails until
its header catches up — the marker cannot outlive the gap it records.

This is the assertion the script corpus was built with and called the
stronger pattern, naming this corpus's inability to make it as the
cost. That cost is paid off; what remains different is that corpus's
`# rule:` line, which it can have because the script rules are
S-numbered and these are not — so an id here cannot be checked against
the rule it is *meant* to serve, only against the one that fired.

`// spec:` stays what it was: the section a reader goes to, not
something the harness checks.

One id is deliberately coarse. `ref.not-allowed-here` rejects nine
fixtures — a reference in `backend`, `control-planes`, `controller`,
`materialize`, `platform`, `type`, a name, a drive key and a children
path — from three raise sites, because those are one rule (D26/D27:
references are refused in identity and graph positions and in closed
vocabularies) and the message names the field. A consumer switching on
the id learns the rule; a person reading the message learns the place.
Three more ids cover two fixtures each and `name.machine-charter`
covers three, for the same reason.

## What this corpus deliberately does not cover

Single-document parse fixtures cannot reach these. They need unit tests
at S3, and their absence here is not coverage:

- **Cross-file identity** — dedup of canonically identical specs,
  collision of differing ones, and the origin-naming in both messages.
  Every fixture is one document; `duplicate-in-file` and
  `case-collision` cover only the in-file half.
- **Resolution-time checks** — the `sha256`-required-once-remote rule
  (a `${key}` rung may resolve to a URL, so parse cannot know) and
  coercion at non-string positions.
- **The container-format roster** — zip accepted, anything else failing
  closed by name, which needs a real container.
- **Medium compatibility** — a directory on a cdrom, an ISO into an
  `hdd` slot, a `new` size onto a cdrom.
- **Property binding**, which lands at milestone 8. Until then a
  `${key}` reference must parse and then fail closed naming
  *properties* — never naming a milestone number. `name-no-stem` and
  `location-object-forms` carry property references for the parse half
  only.
