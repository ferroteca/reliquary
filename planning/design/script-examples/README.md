<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Script-language residual problems, by example

Design-review artifacts for the July 2026 script surface
([script-spec.md](../../../docs/spec/script-spec.md)). Each file isolates one
**unresolved** soft spot — mushiness, inconsistency, or ambiguity
that survived the redesign — and shows it through contrasting
examples with commentary. These are not runnable scripts: some
lines are deliberately illegal (always commented and marked), and
the themes matter more than end-to-end coherence. The surface's
*reference* script is a shipped builtin,
`reliquary/codex/scripts/freedos-install.rlqs` — the
`design-install.rlqs` that used to sit here retired into it when
the implementation caught up (milestone 4).

| file | residual problem |
|---|---|
| [03-timing-spellings-and-scope.rlqs](03-timing-spellings-and-scope.rlqs) | `timeout 30s` vs `timeout=5m`; non-local defaults; the stable split; reset asymmetry |
| [06-media-label-vs-item.rlqs](06-media-label-vs-item.rlqs) | the media label named a file while `@` referenced an item — resolved 2026-07-22 by deleting embedded media blocks; the `@` vs `$` definiteness half stands |
| [07-regex-escaping-regimes.rlqs](07-regex-escaping-regimes.rlqs) | the same screen text escapes differently in `"..."` and `/.../` |
| [08-bare-word-namespaces.rlqs](08-bare-word-namespaces.rlqs) | bare words span six namespaces; asymmetric reservations |

Each file ends with an open question. Resolving one should update
the spec first, then **delete the example** — numbers are not
reused, and the argument survives in the D-number that settled it.

## Why resolved examples are not kept here

Examples 01, 02, 04, 05 and 09 were resolved and kept as
"regression notes" until 2026-07-26, when the claim was tested and
did not hold. **Nothing executed them** — no test in the tree
referenced this directory — so they guarded nothing, and 04 had
itself drifted into syntax the language no longer accepts (its `on`
handler bodies did not end in a terminal, which
[script-spec.md](../../../docs/spec/script-spec.md) requires) with no one noticing.
A note that cannot fail is not a guard.

Deleting them lost nothing, because their resolutions were already
recorded where resolutions belong — in
[DECISIONS.md](../../DECISIONS.md): `<key>` tokens deleted (01),
named observation channels (02), the `on`/`always` keyword split
(04), the file-exchange verbs dropped with the run-collection model
(05, D5), and the rename to `set-boot` (09).

The rule this leaves: **this directory holds open problems only.**
Should a resolved example ever be worth keeping, it earns a test
that executes it first.
