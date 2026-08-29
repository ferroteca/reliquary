<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The conformance corpus

The shared valid/invalid corpus for the **composed blueprint model**,
specified in
[docs/spec/blueprint-model.md](../../../../docs/spec/blueprint-model.md).
Every fixture here follows that spec.

This corpus was written during milestone 7's **second stage**, before
the parser existed. That way the parser, built in the third stage, had
a working acceptance test from its first line instead of getting one
added afterward.

That order paid off immediately. Run against the first parser written
to the spec, the corpus found that the spec **contradicted itself**: it
was unclear whether a containment path belongs inside the braces or
after them. D22 and D24 said after; D26 and D27 said inside;
blueprint-model.md still had both versions in it. D32 settled it:
inside. A corpus written from a spec, then run against code that
implements the same spec, ends up testing the spec itself, not just the
code.

## The buckets

| directory | the assertion |
|---|---|
| `valid/` | parses, and validates against the schema |
| `invalid/` | rejected **at parse**, by parser and schema alike |
| `invalid-at-resolution/` | parses clean; rejected when resolved |

The third bucket exists because validation genuinely happens in two
phases: shape is checked at parse time, values are checked at
resolution time. A fixture whose rule needs a resolved value — or a
binding to a spec that might live in a different file — would fail a
parse-time check for the wrong reason if it were mixed into the
`invalid/` bucket. So it gets its own bucket instead of being tested
with a weaker check. It needs the resolve harness, not the parse
harness, and the published schema can't judge it at all.

## One fixture, one node

Every fixture is its own pytest node, named after its file, in every
check that runs against it — for example
`test_a_valid_fixture_parses[children-batch.rlqb]` or
`test_the_schema_rejects_exactly_what_the_fixture_declares[ref-in-platform.rlqb]`.
That means you can run one fixture on its own, in every check at once,
while you're fixing it:

```powershell
uv run pytest tests/test_conformance_corpus.py -k children-batch
```

This naming choice isn't just for readability — it once caught a real
bug. This corpus used to run only against the parser, not the schema,
while claiming the two could not drift apart. Nobody noticed, because a
loop of fixtures inside one `subTest` test reports a single pass
whether it checked all of the fixtures or only half of them
([D106](../../../../planning/DECISIONS.md)). Giving each fixture its
own node in each check means the node *count* is itself part of what
gets checked — a check that silently covers fewer fixtures now shows up
as fewer nodes, not as a still-green run.

The count for each bucket is pinned in `tests/corpus.py` — the helper
both this corpus and the script corpus use to gather their fixtures —
at 25, 48, and 2. If a bucket stops loading fixtures, that pin makes
the run fail with a collection error, instead of quietly passing with
nothing left to check. When you add or retire a fixture, update both
the pin and the counts in this README.

## Fixture headers

Every fixture opens with comment lines naming what it tests and which
spec section the rule comes from:

```json5
// invalid: P14's acceptance test: this passes the character class and
//          is refused by the production - mem is not a qualifier
// spec: The closure
// id: ref.qualifier-unknown
```

A `// warns:` line marks a fixture that is **valid but must produce a
warning** — currently there is one such fixture, for name repair. One
check covers the whole `valid/` bucket in both directions: a fixture
that declares `// warns:` must actually warn, and every other valid
fixture must parse silently. What the warning message *says* is still
just recorded in the header, not checked.

**The headers used to be documentation only; this README used to say
so. Now they are assertions.** The reason for the change: an invalid
fixture that fails for the *wrong* reason is a false pass, and only a
human reviewer could catch that. Blueprint diagnostics have carried
stable ids since 2026-07-27, so a `// id:` line now names the
diagnostic that must reject the fixture, and the harness checks it
against the `rule_id` the parser actually raised. All 47 fixtures in
`invalid/` carry an id; none of them says `none`. The `none` marker is
checked in both directions: if a fixture still says `none` after its
diagnostic gains a real id, the check fails until the header is
updated. The marker can't go stale without the test suite catching it.

This is the same assertion the script corpus was built with. When the
script corpus's README called this the stronger pattern, it named this
corpus's inability to make the same assertion as the cost of not having
it. That cost is gone now. What's still different is the script
corpus's `# rule:` line: script rules are numbered (`V7`, `V8`, and so
on), so the script corpus can check that an id serves the specific rule
it's meant to. This corpus's rules aren't numbered, so an id here can
only be checked against the diagnostic that actually fired — not
against which rule it was written to test.

`// spec:` is unchanged: it still just points a reader to the right
section of the spec, and the harness does not check it.

One id is deliberately shared across many fixtures.
`ref.not-allowed-here` rejects nine fixtures — a reference used in
`backend`, `control-planes`, `controller`, `materialize`, `platform`,
`type`, a name, a drive key, and a children path — raised from three
different places in the code. They share one id because they are all
the same rule (D26/D27: references are refused in identity and graph
positions, and in closed vocabularies), and the error message itself
names which field is the problem. Code that switches on the id learns
the rule; a person reading the message learns the exact spot. Three
more ids each cover two fixtures, and `name.machine-charter` covers
three fixtures, for the same reason.

## What this corpus deliberately does not cover

A fixture that is a single parsed document can't test any of these.
They need unit tests instead, and their absence from this corpus is not
a coverage gap:

- **Cross-file identity** — deduplicating specs that are identical once
  canonicalized, flagging a collision between specs that differ, and
  naming the origin of each in the error message. Every fixture here is
  one document; `duplicate-in-file` and `case-collision` cover only the
  in-file half of this.
- **Resolution-time checks** — the rule that `sha256` is required
  exactly once a spec is remote (a `${key}` reference might resolve to
  a URL, which parsing can't know yet), and coercion at non-string
  positions.
- **The list of accepted container formats** — zip is accepted,
  anything else is rejected by name, which needs a real container file
  to test.
- **Medium compatibility** — a directory used on a cdrom, an ISO
  inserted into an `hdd` slot, a `new` size specified for a cdrom.
- **Property binding**, which lands at milestone 8. Until then, a
  `${key}` reference must parse and then fail closed, naming
  *properties* as the reason — never citing a milestone number.
  `name-no-stem` and `location-object-forms` carry property references
  only for the parse half of this; they don't test binding.
