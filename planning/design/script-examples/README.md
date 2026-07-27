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
| [07-regex-escaping-regimes.rlqs](07-regex-escaping-regimes.rlqs) | the same screen text escapes differently in `"..."` and `/.../` |
| [08-bare-word-namespaces.rlqs](08-bare-word-namespaces.rlqs) | `screenshot installed` creates, `goto finished` must exist — identical shape, opposite failure. The reservation half was settled 2026-07-27 (D53) and the file narrowed to this |

Each file ends with an open question. Resolving one should update
the spec first, then **delete the example** — numbers are not
reused, and the argument survives in the D-number that settled it.

**Not every open question is a problem to fix.** [03] and [07]
document *tradeoffs* — the boundary tax on guest-text escaping,
and the consequences of placement-equals-scope — where a fix
mostly relocates the mush rather than removing it. Several are the
procedural–declarative seam showing through the syntax. Read
"Primary language goals" (G1–G7) and "The procedural–declarative
seam" in [script-spec.md](../../../docs/spec/script-spec.md)
before proposing a fix, and judge it against the goals it costs
rather than in isolation. Two of these questions have already
resolved as *no change*: [08]'s reservation half (D53) and 06's
`@`-versus-`$` half (D54).

**These files parse, and a test says so**
(`test_documented_examples.ScriptExampleTests`, added 2026-07-27
with 03's repair). Deliberately illegal lines are commented, so an
example that will not parse is drift rather than intent — which is
exactly what had happened to 03: empty handler bodies, one-line
blocks, and `on` where a reactive phase requires `always`. The
guard is the conclusion below applied forward.

## Why resolved examples are not kept here

06 left 2026-07-27 (D54), the last of its three questions closed:
the label/item split died with embedded media blocks, the unknown
`@`-reference became a preflight rejection, and the `@`-versus-`$`
definiteness point resolved as inherent-but-observable — properties
exist to defer a choice, and the stream names the media an `insert`
actually mounted.

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
