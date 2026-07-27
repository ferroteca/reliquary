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
| `invalid/` | rejected at parse, **citing the rule the fixture names** |
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
catch that." The script language has stable rule ids, so the
header stops being documentation and becomes an assertion: a
fixture declaring `# rule: S7` must be rejected by a diagnostic
citing `(S7)`. A reviewer is no longer the check.

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

## What the corpus measured on the way

Six of the 39 invalid fixtures cannot name their rule. Each
carries a `# cites: no` line saying why, and the harness asserts
the marker in **both** directions — a fixture without it must cite
its rule, a fixture with it must not — so a marker cannot outlive
the gap it records.

Five are [D55](../../../../planning/DECISIONS.md) measured rather
than argued. script-spec.md requires that **every** diagnostic
carry a stable dotted identifier; parse errors (`s1-*`), the
header-cardinality diagnostic (`s3-duplicate-header`), the
duplicate-modifier diagnostic (`s4-repeated-modifier`) and the
signature arm of S2 (`s2-modifier-outside-signature`) carry none.
The count is asserted, so it moves in one direction as ids land
and a move the other way means a diagnostic lost one.

The sixth is a different finding, filed here because the corpus is
what found it. `s8-branching-with-a-condition` — `wait "x" { … }` —
is rejected by the **grammar**, with `'{' is not valid here`, and
`script_validation._statement` carries an S8 arm for the same case
that is therefore unreachable. The grammar's own header says the
S-numbered rules stay above it *"where a diagnostic can cite its
id — encoding them here would trade named errors for 'unexpected
token'"*, which is precisely the trade this clause makes. Two
defensible fixes (loosen the production so validation sees it, or
accept the parse error and delete the dead arm); the spec calling
S8 a rule "the grammar cannot carry" points at the first.

## Fixture headers

```rlqs
# invalid: an observation carries exactly one condition
# rule: S7
# spec: Syntactic restrictions
```

`# rule:` is the assertion. `# cites: no -- <why>` marks a rule
the implementation cannot name yet, and is asserted to stay true.

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
