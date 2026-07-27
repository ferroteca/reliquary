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

Four of the 39 invalid fixtures cannot name their rule. Each
carries `# id: none`, and the harness asserts the marker in
**both** directions — a fixture naming an id must be rejected by
exactly that id, a fixture saying `none` must be rejected by a
diagnostic that still has none — so a marker cannot outlive the
gap it records.

Three are [D55](../../../../planning/DECISIONS.md)'s remainder,
measured rather than estimated. script-spec.md requires that
**every** diagnostic carry a stable dotted identifier; the two
lexical/grammar rejections (`s1-*`) and the header-cardinality
diagnostic (`s3-duplicate-header`) carry none. The static rules
and the node signatures gained theirs on 2026-07-27; the lexer,
preflight and runtime have not. The count is asserted, so it
moves down as ids land and a move upward means one was lost.

The fourth is a different finding, filed here because the corpus
is what found it. `s8-branching-with-a-condition` — `wait "x" { … }` —
is rejected by the **grammar**, with `'{' is not valid here`, and
`script_validation._statement` carries a `wait.branching-condition`
arm for the same case that is therefore unreachable. The grammar's
own header says the S-numbered rules stay above it *"where a
diagnostic can cite its id — encoding them here would trade named
errors for 'unexpected token'"*, which is precisely the trade this
clause makes. Two defensible fixes (loosen the production so
validation sees it, or accept the parse error and delete the dead
arm); the spec calling S8 a rule "the grammar cannot carry" points
at the first.

## Fixture headers

```rlqs
# invalid: an observation carries exactly one condition
# rule: S7
# id: obs.two-channels
# spec: Syntactic restrictions
```

`# id:` is the assertion — the diagnostic that must reject the
fixture. `# rule:` is the S-number that id serves, checked against
the spec's own rule list so the two cannot drift. `# id: none`
marks a diagnostic with no identifier yet, and is asserted to stay
true.

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
