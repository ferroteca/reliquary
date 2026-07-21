<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Script-language residual problems, by example

Design-review artifacts for the July 2026 script surface
([docs/script-spec.md](../docs/script-spec.md)). Each file
isolates one **remaining** soft spot — mushiness, inconsistency,
or ambiguity that survived the redesign — and shows it through
contrasting examples with commentary. These are not runnable
scripts: some lines are deliberately illegal (always commented and
marked), and the themes matter more than end-to-end coherence.

| file | residual problem |
|---|---|
| [01-enter-three-roles.rlqs](01-enter-three-roles.rlqs) | the word "enter" is a verb, a key name, and a key token |
| [02-stop-stopped-family.rlqs](02-stop-stopped-family.rlqs) | **RESOLVED** by named observation channels (`machine=stopped`, `screen=` shorthand) — kept as a regression note |
| [03-timing-spellings-and-scope.rlqs](03-timing-spellings-and-scope.rlqs) | `timeout 30s` vs `timeout=5m`; non-local defaults; the stable split; reset asymmetry |
| [04-on-two-lifecycles.rlqs](04-on-two-lifecycles.rlqs) | one `on` syntax, two lifecycles; invisible fall-through; hidden terminals |
| [05-strings-two-worlds.rlqs](05-strings-two-worlds.rlqs) | quoted strings are guest text in one verb, host paths in the next |
| [06-media-label-vs-item.rlqs](06-media-label-vs-item.rlqs) | the media label names a file, `@` references an item; `@` vs `$` definiteness |
| [07-regex-escaping-regimes.rlqs](07-regex-escaping-regimes.rlqs) | the same screen text escapes differently in `"..."` and `/.../` |
| [08-bare-word-namespaces.rlqs](08-bare-word-namespaces.rlqs) | bare words span six namespaces; asymmetric reservations |
| [09-boot-verb-tense.rlqs](09-boot-verb-tense.rlqs) | `boot` reads immediate but is persistent configuration |

Each file ends with an open question. Resolving one should update
the spec first, then delete the example (or rewrite it as a
regression note).
