<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The revised-format conformance corpus (staged)

The shared valid/invalid corpus for the **composed blueprint model** —
[planning/design/blueprint-model.md](../../../../planning/design/blueprint-model.md),
which is normative for every fixture here. Written at milestone 7's
**S2**, before the parser, so that S3 has an executable acceptance test
from its first line rather than after it.

**Staged, not live.** `test_conformance_corpus.py` walks
`../blueprint/`, which holds the *pre-composition* fixtures the shipped
parser still validates. Nothing here is asserted against the parser yet,
because the parser it describes does not exist. What *is* checked today
is that every fixture is well-formed JSONC and carries its header —
enough to keep a typo from surviving until S3.

## Wiring it in at S3

1. Delete `../blueprint/` and move this directory to `blueprint/`.
2. Point `test_conformance_corpus.py` at the three buckets below,
   dropping `StagedRevisedCorpusTests`.
3. Replace the two milestone-6 schemas with the one two-variant
   blueprint schema, which the same fixtures must agree with — the
   schema cannot lag the parser, since every fixture runs against both.

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
```

A `// warns:` line marks a fixture that is **valid but must emit a
warning** — currently the one name-repair case. There is no warning
assertion yet; adding one is part of S3, and the header is the record
of what it must say.

The headers are documentation, not assertions. They are there because
an invalid fixture that fails for the *wrong* reason is a false pass,
and the header is what lets a reviewer catch that.

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
