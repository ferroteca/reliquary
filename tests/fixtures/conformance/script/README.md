<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
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

## One fixture, one node

Every fixture is a collected pytest node **named for its file**, in
each check that judges it —
`test_a_rejection_carries_the_id_the_fixture_declares[v7-two-conditions.rlqs]`.
So a fixture is run on its own while it is being fixed, in every
check at once:

```powershell
uv run pytest tests/test_script_corpus.py -k v7-two-conditions
```

The naming is the assertion rather than presentation: a loop of
fixtures inside one `subTest` test reports the same single pass
whether it checked all of them or half, which is how the blueprint
corpus came to run against the parser and not the schema
([D106](../../../../planning/DECISIONS.md)). Both corpora gather
their fixtures through one helper, `tests/corpus.py`, which is also
where the bucket counts are pinned — 22, 53 and 6 — so a bucket that
stops loading is a collection error rather than a green run over
nothing. Adding or retiring a fixture updates the pin and the tallies
here together.

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
script trips V10 before the V8 or V9 clause under test — and the
harness named all three. Under the blueprint corpus's assertion
they would have passed, and gone on passing after the rules they
claimed to exercise stopped working.

**So the pattern generalizes, and the ids are what make it worth
generalizing.** That is the reusable conclusion: a corpus is worth
as much as the precision of the failure it can assert, and
identifiers are what buy that precision.

**The corpus came first, and it is why the ids are the shape they
are.** Written against the V-numbers, it worked but blunted: an
V-number names a *rule*, and V7 has six diagnostics under it, so
a fixture asserting `V7` could not tell "no condition" from
"unknown channel". That is the concrete argument for the dotted
scheme being finer than the rules rather than a renaming of
them — the question [D55](../../../../planning/DECISIONS.md)'s
defect left open, answered by trying the coarse version first.

## What the corpus measured on the way

It opened with four fixtures that could not name their rule and
now has none: all 53 name the diagnostic that rejects them. The
corpus was written first and the ids followed, which is the order
that made them right — see below.

One fixture carries `# caught-by:` instead, and it records a
defect the corpus found. `v8-branching-with-a-condition` —
`wait "x" { … }` — exercises V8 and is rejected by the
**grammar**, so its id is `syn.unexpected-token` and the
`wait.branching-condition` arm in `script_validation` is
unreachable. `script_grammar.lark`'s own header says the
V-numbered rules stay above it *"where a diagnostic can cite its
id — encoding them here would trade named errors for 'unexpected
token'"*; this clause is the trade it warns about. Two defensible
fixes (loosen the production so validation sees it, or accept the
parse error and delete the dead arm); the spec calling V8 a rule
"the grammar cannot carry" points at the first. The marker is
asserted in both directions, so it retires itself when either
lands.

The preflight and runtime tiers now carry ids too — 43 diagnostics
across `binding`, `resolve`, `script_runner` and `script_timing`,
landed once the error classes generalized to every surface (D58) and
gave them a class worth naming a rule for. So the
`invalid-at-preflight/` bucket no longer asserts only that a fixture
parses: it runs preflight — the machine rules, then noninteractive
binding — and asserts the id that comes out, in both directions like
the parse bucket. Two new subjects arrived with them, `media.` and
`machine.`, and `media.unknown` is deliberately the same id whether
the resolution namespace lacks the media or a script's `insert`
names it: one condition, one answer for a consumer.

What has no id is every *other* surface. The requirement is the
spec's and it travelled with the classes, so the blueprint document
parser, the machine verbs, the VM lifecycle and the properties file
owe ids on the same terms — some 245 diagnostics, filed as a defect
rather than left here as a footnote. Nothing about the scheme
changes for them; the blueprint surface will want subjects of its
own, and choosing them is that work.

## Fixture headers

```rlqs
# invalid: an observation carries exactly one condition
# rule: V7
# id: obs.two-channels
# spec: Syntactic restrictions
```

`# id:` is the assertion — the diagnostic that must reject the
fixture. `# rule:` is what the script violates, and the two must
agree: the id has to serve that rule, checked against the spec's
own list so neither can drift.

Two markers record a gap instead, and both are asserted in the
direction that retires them:

- `# id: none` — the diagnostic has no identifier yet. None remain
  in either bucket; the marker stays for a surface that has not had
  its ids yet, and because a diagnostic *losing* one has to be
  expressible.
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
  `test_binding.py` owns them. `invalid-at-preflight/` drives
  binding far enough to assert which diagnostic rejects an
  unanswerable property, and no further.
- **Warnings** — unreachable phases, shadowed conditions, unused
  properties. The blueprint corpus grew a `// warns:` marker for
  this; the same marker is the obvious extension here and no
  fixture needs it yet.
