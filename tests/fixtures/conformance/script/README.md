<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The script conformance corpus

The valid/invalid corpus for the **`.rlqs` scripting language**,
specified in
[docs/spec/script-spec.md](../../../../docs/spec/script-spec.md).
Every fixture here follows that spec. Harness:
[test_script_corpus.py](../../../test_script_corpus.py).

This corpus was written for P24 to answer a specific question, not just
to add coverage: **does the [blueprint corpus](../blueprint/README.md)'s
pattern generalize to scripts?** The answer is below — this README is
the record of that finding.

## The buckets

| directory | the assertion |
|---|---|
| `valid/` | parses and validates |
| `invalid/` | rejected at parse, **by the diagnostic id the fixture names** |
| `invalid-at-preflight/` | parses clean; rejected once a machine, a namespace, or an invocation is in scope |

The third bucket exists for the same reason as the blueprint corpus's
third bucket: a rule that needs a resolved value would fail a
parse-time check for the wrong reason if it were mixed into
`invalid/`. Giving it a separate bucket is more honest than testing it
with a weaker check.

## One fixture, one node

Every fixture is its own pytest node, named after its file, in every
check that runs against it — for example
`test_a_rejection_carries_the_id_the_fixture_declares[v7-two-conditions.rlqs]`.
That means you can run one fixture on its own, in every check at once:

```powershell
uv run pytest tests/test_script_corpus.py -k v7-two-conditions
```

This naming is itself part of the assertion, not just presentation: a
loop of fixtures inside one `subTest` test reports a single pass
whether it checked all of them or only half — which is exactly how the
blueprint corpus ended up running against the parser but not the schema
([D106](../../../../planning/DECISIONS.md)). Both corpora gather their
fixtures through one helper, `tests/corpus.py`, which is also where the
bucket counts are pinned — 22, 53, and 6 — so a bucket that stops
loading is a collection error, not a still-green run over nothing. When
you add or retire a fixture, update both the pin and the counts here.

## What generalized, and what got stronger

The overall shape carried over without any real argument needed —
buckets, headers naming the rule and its spec section, one harness
reading them. The scripting language is a document format like
blueprints are, so that part was never the hard half of the question.

What's new is the middle column in the table above. The blueprint
corpus can only assert that a fixture was *rejected*; its own README
states the cost of that plainly — an invalid fixture that fails for the
*wrong* reason is a false pass, and a header is what lets a reviewer
catch it. Here, the header stops being documentation and becomes an
assertion: a fixture declaring `# id: obs.two-channels` must be
rejected by exactly that diagnostic. A reviewer is no longer the thing
doing the checking.

That paid off right away. Three fixtures in the first draft were being
rejected by the wrong rule — for example, `finish` inside a linear
script trips V10 before the V8 or V9 clause the fixture was meant to
test — and the harness caught all three by name. Under the blueprint
corpus's weaker assertion, those three fixtures would have passed, and
kept passing even after the rules they claimed to test stopped working.

**So the pattern does generalize, and the ids are what make it worth
generalizing.** That's the reusable conclusion: a corpus is only as
useful as how precisely it can pin down a failure, and diagnostic ids
are what buy that precision.

**The corpus came first, and that's why the ids are shaped the way
they are.** It was originally written against the V-numbers alone, and
that worked but was too blunt: a V-number names a whole *rule*, and V7
alone covers six different diagnostics, so a fixture that only asserted
`V7` couldn't distinguish "no condition" from "unknown channel." That's
the concrete case for why the dotted id scheme needed to be finer than
the rule numbers rather than just a renaming of them — a question left
open by the defect behind
[D55](../../../../planning/DECISIONS.md), answered here by trying the
coarser, rule-only version first and finding it wasn't enough.

## What the corpus measured on the way

It started with four fixtures that couldn't name their own rule, and
now has none: all 53 fixtures name the diagnostic that rejects them.
The corpus was written first and the ids were added afterward, which
turned out to be the order that made the ids correct — see below.

One fixture carries `# caught-by:` instead of `# id:`, and it records a
real defect the corpus found. `v8-branching-with-a-condition` — the
script `wait "x" { … }` — is meant to exercise V8, but it's actually
rejected by the **grammar** before V8 can fire, so its id is
`syn.unexpected-token`, and the `wait.branching-condition` arm in
`script_validation` can never be reached. `script_grammar.lark`'s own
header explains that the V-numbered rules live above the grammar
*"where a diagnostic can cite its id — encoding them here would trade
named errors for 'unexpected token'"*; this fixture is exactly the
trade-off that warning describes. There are two defensible fixes:
loosen the grammar production so validation can see this case, or
accept the parse error and delete the now-unreachable code. The spec's
own description of V8 as a rule "the grammar cannot carry" points
toward the first fix. The `# caught-by:` marker is checked in both
directions, so it will retire itself automatically once either fix
lands.

The preflight and runtime tiers now carry ids too — 43 diagnostics
across `binding`, `resolve`, `script_runner`, and `script_timing`. They
were added once the error classes were generalized across every
surface (D58), which is what gave each class a name worth building a
rule id from. So the `invalid-at-preflight/` bucket no longer just
asserts that a fixture parses: it runs preflight — first the machine
rules, then noninteractive binding — and checks the id that comes out,
in both directions, the same as the parse bucket does. Two new subjects
arrived with this work, `media.` and `machine.`, and `media.unknown` is
deliberately the same id whether the resolution namespace is simply
missing the media, or a script's `insert` command names media that
doesn't exist — one condition, one answer, for whoever is consuming the
id.

Every *other* surface still has no ids. The requirement is the spec's,
and it traveled with the error classes, so the blueprint document
parser, the machine verbs, the VM lifecycle, and the properties file
all owe ids on the same terms — roughly 245 diagnostics in total. That
gap is filed as a defect to fix, not left here as a footnote. Nothing
about the id scheme itself needs to change for them; the blueprint
surface will need its own set of subjects, and choosing those is the
remaining work.

## Fixture headers

```rlqs
# invalid: an observation carries exactly one condition
# rule: V7
# id: obs.two-channels
# spec: Syntactic restrictions
```

`# id:` is the assertion — it names the diagnostic that must reject the
fixture. `# rule:` names which rule of the script language the fixture
violates, and the two have to agree: the id has to actually serve that
rule, which is checked against the spec's own list, so neither one can
drift away from the other unnoticed.

Two markers record a gap instead of a rule, and both are checked in the
direction that lets them retire themselves:

- `# id: none` — the diagnostic doesn't have an identifier yet. None
  remain in either bucket today; the marker stays available for a
  surface that hasn't had its ids assigned yet, and because it also has
  to be possible to say a diagnostic has *lost* its id.
- `# caught-by: S<n>` — a different layer rejects the script before the
  rule's own diagnostic gets the chance to, so the id that fires serves
  a *different* rule than the one the fixture is meant to exercise. One
  fixture currently has this marker.

## What this corpus deliberately does not cover

A fixture that is a single parsed file can't reach any of these. Their
absence from this corpus is not a coverage gap:

- **Runtime behavior** — samples and episodes, handler re-arming, clock
  expiry, the failure report. These need an actual machine;
  `test_script_runner.py` covers them.
- **The timing plan's resolved values** — which scope supplied each
  bound value. `test_script_timing.py` covers them.
- **Property binding** — the source order and the kind rules, which
  depend on the invocation rather than just the script text.
  `test_binding.py` covers them. `invalid-at-preflight/` drives binding
  far enough to check which diagnostic rejects an unanswerable
  property, and no further than that.
- **Warnings** — unreachable phases, shadowed conditions, unused
  properties. The blueprint corpus grew a `// warns:` marker for this
  case; the same marker would be the obvious way to extend this corpus,
  but no fixture needs it yet.
