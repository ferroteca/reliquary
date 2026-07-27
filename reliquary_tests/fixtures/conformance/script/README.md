<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The script conformance corpus

The valid/invalid corpus for the **`.rlqs` scripting language** —
[docs/spec/script-spec.md](../../../../docs/spec/script-spec.md),
which is normative for every fixture here. Harness:
[test_script_corpus.py](../../../test_script_corpus.py).

Written for P24, to answer a question rather than only to add
coverage: **does the [blueprint corpus](../blueprint/README.md)'s
pattern generalize?** The answer is below, because it is the
finding.

## The buckets

| directory | the assertion |
|---|---|
| `valid/` | parses and validates |
| `invalid/` | rejected at parse, **by the diagnostic id the fixture names** |
| `invalid-at-preflight/` | parses clean; rejected with a machine, a namespace or an invocation in scope |

The third bucket is the blueprint corpus's third bucket for
exactly its reason: a rule needing a resolved value would fail a
parse-time assertion for the wrong reason, and separating it is
honester than weakening it.

## What generalized, and what got stronger

The shape transferred without argument — buckets, headers naming
the rule and its spec section, one harness reading them. The
language is a document format like the blueprint, so this was
never the hard half of the question.

What is new is the middle column above. The blueprint corpus can
assert only that a fixture was *rejected*; its README states the
cost plainly — "an invalid fixture that fails for the *wrong*
reason is a false pass, and the header is what lets a reviewer
catch that." Here the header stops being documentation and
becomes an assertion: a fixture declaring `# id: obs.two-channels`
must be rejected by exactly that diagnostic. A reviewer is no
longer the check.

That was worth having immediately. Three fixtures in the first
draft were rejected by the wrong rule — `finish` inside a linear
script trips S10 before the S8 or S9 clause under test — and the
harness named all three. Under the blueprint corpus's assertion
they would have passed, and gone on passing after the rules they
claimed to exercise stopped working.

**So the pattern generalizes, and the ids are what make it worth
generalizing.** That is the reusable conclusion: a corpus is worth
as much as the precision of the failure it can assert, and
identifiers are what buy that precision.

**The corpus came first, and it is why the ids are the shape they
are.** Written against the S-numbers, it worked but blunted: an
S-number names a *rule*, and S7 has six diagnostics under it, so
a fixture asserting `S7` could not tell "no condition" from
"unknown channel". That is the concrete argument for the dotted
scheme being finer than the rules rather than a renaming of
them — the question [D55](../../../../planning/DECISIONS.md)'s
defect left open, answered by trying the coarse version first.

## What the corpus measured on the way

It opened with four fixtures that could not name their rule and
now has none: all 39 name the diagnostic that rejects them. The
corpus was written first and the ids followed, which is the order
that made them right — see below.

One fixture carries `# caught-by:` instead, and it records a
defect the corpus found. `s8-branching-with-a-condition` —
`wait "x" { … }` — exercises S8 and is rejected by the
**grammar**, so its id is `syn.unexpected-token` and the
`wait.branching-condition` arm in `script_validation` is
unreachable. `script_grammar.lark`'s own header says the
S-numbered rules stay above it *"where a diagnostic can cite its
id — encoding them here would trade named errors for 'unexpected
token'"*; this clause is the trade it warns about. Two defensible
fixes (loosen the production so validation sees it, or accept the
parse error and delete the dead arm); the spec calling S8 a rule
"the grammar cannot carry" points at the first. The marker is
asserted in both directions, so it retires itself when either
lands.

What has no id at all is the preflight and runtime tiers — 30
raise sites across `binding`, `resolve`, `script_runner` and
`script_timing` — which no parse fixture can reach, and which the
`invalid-at-preflight/` bucket exists to hold when they do.

## Fixture headers

```rlqs
# invalid: an observation carries exactly one condition
# rule: S7
# id: obs.two-channels
# spec: Syntactic restrictions
```

`# id:` is the assertion — the diagnostic that must reject the
fixture. `# rule:` is what the script violates, and the two must
agree: the id has to serve that rule, checked against the spec's
own list so neither can drift.

Two markers record a gap instead, and both are asserted in the
direction that retires them:

- `# id: none` — the diagnostic has no identifier yet. None
  remain; the marker stays because preflight and runtime fixtures
  will need it.
- `# caught-by: S<n>` — a layer rejects the script before the
  rule's own diagnostic can, so the id serves a *different* rule
  than the fixture exercises. One fixture has it.

## What this corpus deliberately does not cover

Single-file parse fixtures cannot reach these, and their absence
here is not coverage:

- **Runtime semantics** — samples and episodes, handler re-arming,
  clock expiry, the failure report. These need a machine;
  `test_script_runner.py` owns them.
- **The timing plan's resolved values** — which scope supplied
  each bound. `test_script_timing.py` owns them.
- **Property binding** — the source order and the kind rules,
  which depend on the invocation rather than the text.
  `test_binding.py` owns them; `invalid-at-preflight/` holds only
  the parse half.
- **Warnings** — unreachable phases, shadowed conditions, unused
  properties. The blueprint corpus grew a `// warns:` marker for
  this; the same marker is the obvious extension here and no
  fixture needs it yet.
