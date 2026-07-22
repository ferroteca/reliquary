<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Script-language residual problems, by example

Design-review artifacts for the July 2026 script surface
([planning/design/script-spec.md](../script-spec.md)). Each file
isolates one **remaining** soft spot — mushiness, inconsistency,
or ambiguity that survived the redesign — and shows it through
contrasting examples with commentary. These are not runnable
scripts: some lines are deliberately illegal (always commented and
marked), and the themes matter more than end-to-end coherence. The
surface's *reference* script is a shipped builtin,
`reliquary/codex/scripts/freedos-1.4-plain-install.rlqs` — the
`design-install.rlqs` that used to sit here retired into it when
the implementation caught up (ROADMAP milestone 4).

| file | residual problem |
|---|---|
| [01-enter-three-roles.rlqs](01-enter-three-roles.rlqs) | **RESOLVED** by deleting `<key>` tokens — keys live only after `press`; kept as a regression note |
| [02-stop-stopped-family.rlqs](02-stop-stopped-family.rlqs) | **RESOLVED** by named observation channels (`machine=stopped`; a bare string/regex is the screen's only spelling) — kept as a regression note |
| [03-timing-spellings-and-scope.rlqs](03-timing-spellings-and-scope.rlqs) | `timeout 30s` vs `timeout=5m`; non-local defaults; the stable split; reset asymmetry |
| [04-on-two-lifecycles.rlqs](04-on-two-lifecycles.rlqs) | **RESOLVED** by the `on`/`always` keyword split — lifetime in the first word; fall-through and hidden terminals stay documented — regression note |
| [05-strings-two-worlds.rlqs](05-strings-two-worlds.rlqs) | **RESOLVED** by dropping the file-exchange verbs with the run-collection model — no verb takes a host path; strings are guest text only — regression note |
| [06-media-label-vs-item.rlqs](06-media-label-vs-item.rlqs) | the media label named a file while `@` referenced an item — resolved 2026-07-22 by deleting embedded media blocks; the `@` vs `$` definiteness half stands |
| [07-regex-escaping-regimes.rlqs](07-regex-escaping-regimes.rlqs) | the same screen text escapes differently in `"..."` and `/.../` |
| [08-bare-word-namespaces.rlqs](08-bare-word-namespaces.rlqs) | bare words span six namespaces; asymmetric reservations |
| [09-boot-verb-tense.rlqs](09-boot-verb-tense.rlqs) | **RESOLVED** by renaming to `set-boot` — the prefix names the persistence; kept as a regression note |

Each file ends with an open question. Resolving one should update
the spec first, then delete the example (or rewrite it as a
regression note).
