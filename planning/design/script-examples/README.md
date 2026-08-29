<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The script language's unresolved problems, by example

These are design-review files for the July 2026 script surface
([script-spec.md](../../../docs/spec/script-spec.md)). Each file
focuses on one specific problem that survived the redesign
unresolved — something inconsistent, ambiguous, or not fully worked
out — and shows it through contrasting examples with commentary.
These are not runnable scripts: some lines are deliberately illegal
(always commented and marked), and the point of each file is its
theme, not whether it reads end to end as a coherent script. The
reference script for this surface is a shipped builtin,
`src/reliquary/codex/scripts/freedos-install.rlqs`. The file
`design-install.rlqs` used to live in this directory; it was
retired into that builtin once the implementation caught up
(milestone 4).

| file | open problem |
|---|---|
| [03-timing-spellings-and-scope.rlqs](03-timing-spellings-and-scope.rlqs) | `timeout 30s` vs `timeout=5m`; non-local defaults; the stable split; reset asymmetry |
| [07-regex-escaping-regimes.rlqs](07-regex-escaping-regimes.rlqs) | the same screen text escapes differently in `"..."` and `/.../` |
| [08-bare-word-namespaces.rlqs](08-bare-word-namespaces.rlqs) | `screenshot installed` creates, `goto finished` must exist — identical shape, opposite failure. The reservation half was settled 2026-07-27 (D53) and the file narrowed to this |

Each file ends with an open question. Resolving one should update
the spec first, then **delete the example** — numbers are not
reused, and the argument survives in the D-number that settled it.

**Not every open question here is a problem waiting for a fix.**
[03] and [07] document real tradeoffs, where a fix would just move
the awkwardness elsewhere rather than remove it. In [03], where a
setting is written is what determines its scope, so making every
form repeat every setting would trade one kind of awkwardness for
another. In [07], the same screen text needs different escaping
depending on whether it's written as a literal string or as a
regex — a cost that comes from supporting both forms, not from a
bug in either one. Several of these are the procedural–declarative
seam ("The procedural–declarative seam" in
[script-spec.md](../../../docs/spec/script-spec.md)) showing
through in the syntax. Read "Primary language goals" (G1–G7) and
"The procedural–declarative seam" in script-spec.md before
proposing a fix, and weigh a fix against the goals it would cost,
not in isolation. Two of these questions are already settled as *no
change*: [08]'s reservation question (D53) and 06's `@`-versus-`$`
question (D54).

**These files parse, and a test checks it**
(`test_documented_examples.ScriptExampleTests`, added 2026-07-27
with 03's repair). Deliberately illegal lines are commented out, so
a file that fails to parse means something drifted, not that it was
meant to fail — which is exactly what had happened to 03: empty
handler bodies, one-line blocks, and `on` where a reactive phase
requires `always`. This test exists because an example nothing
executes isn't actually guarding anything — see "Why resolved
examples are not kept here" below.

## Why resolved examples are not kept here

File 06 was removed on 2026-07-27 (D54), once the last of its three
open questions was closed: the label/item split was removed along
with embedded media blocks, referencing an unknown `@` name became
a preflight rejection, and the `@`-versus-`$` question was resolved
by recognizing it as inherent rather than fixable — properties
exist specifically to defer a choice, and the event stream records
the actual medium an `insert` mounted, so the choice is still
observable afterward even though it isn't fixed in advance.

Examples 01, 02, 04, 05, and 09 were resolved and kept around as
"regression notes" until 2026-07-26, when that idea was checked and
turned out not to hold up. **Nothing executed them** — no test
anywhere in the tree referenced this directory — so they weren't
guarding anything, and file 04 had itself drifted into syntax the
language no longer accepts (its `on` handler bodies didn't end in a
terminal, which
[script-spec.md](../../../docs/spec/script-spec.md) requires)
without anyone noticing. A note that can't fail isn't a guard.

Deleting them lost nothing, because their resolutions were already
recorded where resolutions belong — in
[DECISIONS.md](../../DECISIONS.md): `<key>` tokens deleted (01),
named observation channels (02), the `on`/`always` keyword split
(04), the file-exchange verbs dropped with the run-collection model
(05, D5), and the rename to `set-boot` (09).

The rule this leaves: **this directory holds open problems only.**
If a resolved example is ever worth keeping, it has to earn a test
that actually executes it first.
