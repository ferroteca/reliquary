<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# TASKS

The pledged work backlog. A **proposed** task lives in the issue
tracker — <https://github.com/ferroteca/reliquary/issues> — which is
the only queue a proposed task has (D43): the tracker is a task's
proposed state and this file is its pledged one. So nothing parks
here awaiting a verdict; arriving *is* the verdict.

**Everything in this file is pledged** — the one vocabulary
([README.md](README.md)) applying here exactly as in the
directories. An entry is in the *pledged* state, so entering it is
approving it: nothing waits on a verdict, nothing needs a citation
or a decision of its own, and there is nothing to promote. The
directory is not its home because `proposed/` and `pledged/` hold
*demand and capability*, argued at length, and a task is none of
those — free-standing work too small to be a feature and too small
to need the argument. That kind distinction is the distinguisher,
not size.

**This file is the third work input queue** (D43, widening D39's
two), and adding to it is governed by the gate covering all writing
under `planning/` — weighing most here, this being the one governed
act that grants approval with no argument behind it.

**A queue holds what waits.** Work that arrives already done never
appears here: there is nothing to schedule, only a decision to make,
and an entry filed and closed in one act is ceremony.

**Anything is struck when it is done** (D45, generalized by D52) —
tasks, audits, restructures and rounds alike. Its record is its
commit, its CHANGELOG line, and the D-numbers it produced, so it
leaves this file by deletion and nothing is parked. The same holds
for the **work-item breakdowns inside a pledged feature**: when the
feature delivers, its list is deleted with its F-number rather than
archived. A record whose reasoning outlives the work is a decision,
and decisions live in [DECISIONS.md](DECISIONS.md) — kept beside
the work instead, a summary drifts from what it summarizes and a
reader has no way to tell.

**There is no order here.** Nothing in this file is scheduled, and
nothing claims priority over anything else; whoever picks work up
picks whatever they like. The one ordering that does bind is a
feature's: **work that only makes sense as part of one pledged
feature lives with that feature**, in
[pledged/FEATURES.md](pledged/FEATURES.md), and has to be done to
complete it — F1's items are the standing example. A
task here that merely *relates* to a feature is still free to be
picked whenever.

Housekeeping (D38) is the same instinct one size smaller: work tiny
enough and obvious enough that it needs no entry here **at all**,
approved as a class in advance, with the commit as its record. This
file is where the pre-approved work that is still worth writing
down goes. The full intake machinery — the raw queues, the
housekeeping test, and how pledge is recorded — is in
[README.md](README.md).

**Refused work is not recorded here** (D52). Entry to this file
*is* approval (D43), so a rejected task is one that never
entered — refusal happens at the door, and its record is the issue
that was closed or the [DECISIONS.md](DECISIONS.md) entry that
argued it, that file already being the guard against
re-litigating.

The file is one section, [Pledged](#pledged) — the queue proper,
grouped by kind because the actor and the gate differ, though the
grouping is not a running order.

Standing questions to re-ask as the design hardens are not tasks
and live with the decision record, under
[DECISIONS.md](DECISIONS.md)'s open questions.

## Pledged

Grouped by kind, because the actor and the gate differ: an audit
is mechanical, a defect needs no pledge because the norm it
violates already is one. (Two further groups — the restructures,
then the adjudications — were struck on 2026-07-27 as each
finished: D46–D51 are the adjudications' record, and D50 the
restructures'.)

### Governance — audits

*(Emptied and struck on 2026-07-27, as the restructures and the
adjudications were before it. The supports retrofit was the last
one standing and it is done: every live entry in
[DECISIONS.md](DECISIONS.md) now names the use cases, principles
or goals it supports — 54 of 56, the two exceptions being the
retired D2 and D17, which bind nothing and which the file's own
practice already exempted. The third audit had left on the same
day into [F7](proposed/FEATURES.md).*

*The class it audited for is not struck with it — the
traceability rule stands, and new entries carry supports from the
start. What retires is the standing backlog of entries written
before the rule existed.)*

### Defects

A gap against a *standing* principle is a bug: the principle is
already its demand, so these need no pledge, only fixing. A gap
against a **shipped spec** is the same class and sits here too —
where `docs/spec/` and the code disagree the spec is right and the
code has the bug, so the norm is already the demand.

- **Diagnostics carry no stable identifier — the second pass**
  (found 2026-07-27 by D55; the scheme and the static rules landed
  2026-07-27, this is what they left).
  [script-spec.md](../docs/spec/script-spec.md) requires an id of
  *every* diagnostic; 52 now exist and the rest do not.

  **The scheme is settled — do not reopen it.** The entry's
  original question was whether `S5` becomes a dotted id or the
  dotted scheme covers only what has none. It was a false choice:
  an S-number names a **rule** and an id names one **diagnostic**
  under it, S7 being one restriction with six ways to break it. So
  they are different granularities rather than rival schemes, no
  renaming happened, a message carries the id alone, and
  script-spec.md's rule list carries the mapping. `RULE_OF`
  (`script_nodes.py`) is the same mapping in code, held to the
  spec by test. The prefix is the subject — `obs.`, `flow.`,
  `name.`, `prop.`, `wait.`, `handler.`, `time.`, `key.`,
  `node.`, `http.` — never the error class, the namespace being
  shared across classes.
  The argument that settled it came from the conformance corpus,
  which was written against the S-numbers first and could not tell
  `obs.missing-condition` from `obs.unknown-channel`.

  **What remains, measured.** Raise sites carrying no id:

  | module | tier | without an id |
  |---|---|---|
  | `binding.py` | preflight | 7 |
  | `resolve.py` | preflight | 10 |
  | `script_runner.py` | runtime | 12 |
  | `script_timing.py` | static | 1 |

  Everything decided from the script text alone is done — the
  lexer, the grammar, the node signatures and the static rules,
  82 ids across `script_nodes.py`, `script_parser.py` and
  `script_validation.py`. What is left is the two tiers that need
  more than the text in scope, which is also why no parse fixture
  can reach them: they belong to the corpus's
  `invalid-at-preflight/` bucket, and giving them ids is what lets
  that bucket assert a reason rather than only "parses clean".

  `script_timing.py`'s single site is static and simply was not on
  the earlier pass's path; it is a one-line fix whenever.

  **No longer blocked** (2026-07-27, D58). The prerequisite is
  delivered: the four error classes now describe every surface, and
  all four modules above carry **zero** builtin raises — every
  diagnostic in them is in the taxonomy, so an id on one names a
  rule for something the CLI reports as an error rather than as a
  crash. What this entry said here — that only `binding.py`'s 7
  were typed and the rest raised plain `ValueError` / `KeyError` /
  `RuntimeError` — is no longer true of the code.

  **The first move is a place to put an id, not the typing.** That
  is what doing the prerequisite revealed: `rule_id` is a field on
  `ScriptParseError` alone, and the taxonomy classes have none. So
  the 30 sites now have a class and nowhere to carry an identifier,
  and the pass opens by giving the preflight tier a
  located-and-identified error of its own — the shape
  `ScriptParseError` already has for the static tier, which is why
  the 82 static ids were cheap. Whether the runtime tier wants the
  same or reuses `ScriptRuntimeError`'s location is the second
  question.

  The blueprint surface wants the same thing and has no more than a
  stopgap: `jsonc.loads` hangs a malformed document's line and
  column on the raised `StaticError` as plain attributes, which
  works and is not a scheme. A located blueprint diagnostic belongs
  in this pass.

  **The prefix design is done too** — `lex.` for what the
  tokenizer rejects, `syn.` for line, block and document shape,
  with the typing layer reusing `node.`, `prop.` and `http.`. A
  preflight tier will want its own; nothing else is open.

  **The corpus is the meter, not a guess.**
  `reliquary_tests/fixtures/conformance/script/` marks each
  unidentified case `# id: none` and asserts it in both
  directions. **It reads zero today**, down from six: every one of
  the 39 invalid fixtures names the diagnostic that rejects it.

  **One defect surfaced and is asserted rather than filed.**
  A branching `wait` carrying a condition is rejected by the
  *grammar*, so it reports `syn.unexpected-token` and the
  `wait.branching-condition` arm in `script_validation` is
  unreachable — the trade `script_grammar.lark` warns about in its
  own header. The fixture carries `# caught-by: S1`, asserted in
  both directions, so whichever fix lands retires the marker.

  **The index is still not the gap.** Deferring the id *index* to
  beta stays where the spec says it; generating it is cheap now
  that ids are a field rather than message text.

### Small items

Small, obvious, just haven't met the bar for scheduling (the
section formerly named Wishlist, then Backlog). Parked non-GitHub
issues land here. Most would qualify as housekeeping (D38) and
need no entry at all once someone picks them up.

- **Two blueprint rules that need arguing, not relocating** (left
  behind 2026-07-27 when the other orphaned norms were promoted).
  Both live only in the descriptive field reference, and both read
  as **commitments** rather than restatements — which is the line
  the audit warned about: relocating a rule unchanged passes P23's
  clarify test, and asserting a new one does not.
  - **`controller`'s ordering caveat**: *"slot order is
    authoritative only within a controller type; across mixed
    types the guest's firmware decides and Reliquary cannot
    promise a global disk order."* That constrains what Reliquary
    may promise about guest disk order, which is a claim, not a
    restatement — and it is a **second source of the drive-letter
    ambiguity** filed against P17 above, which names only the
    multi-volume case. Whoever takes either should read both.
  - **The backend→format table** (qcow2 / VDI / VMDK / VHDX)
    behind "format-portable by construction". Binding four
    backends to four formats is a commitment about three backends
    that do not exist yet.
  Neither is urgent: they are stated in a descriptive document
  today and would be stated in a normative one after, so nothing
  is unspecified in the meantime — what changes is whether the
  code is free to diverge from them.
