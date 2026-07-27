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

- **Diagnostics carry no stable identifier — every surface but
  the script one** (found 2026-07-27 by finishing the script
  surface's pass; D55's requirement, D58's reach).
  [script-spec.md](../docs/spec/script-spec.md) requires an id of
  *every* diagnostic. The script surface now has them — 82 static
  plus 43 preflight and runtime, the corpus asserting each in both
  directions — and nothing else does.

  **This is D58's consequence, not a new demand.** The four error
  classes used to be read as tiers of a script run, so the id
  requirement was read as the script surface's too. D58 made the
  classes describe every surface, and the requirement travelled
  with them: a malformed blueprint is a STATIC ERROR exactly as a
  malformed script is, so it owes an id on the same terms. The
  population went from 30 to 288 without a single new rule being
  written.

  **Measured, not estimated.** Diagnostics carrying no id:

  | module | what it diagnoses | without an id |
  |---|---|---|
  | `document.py` | the blueprint document | 97 |
  | `machines.py` | the machine verbs | 53 |
  | `lifecycle.py` | the VM's own lifecycle | 26 |
  | `properties.py` | the properties file | 15 |
  | `cli.py` | invocation shape | 13 |
  | `machine.py` | the guest console | 12 |
  | the remaining 11 | assets, media, DOS addressing, … | 29 |

  245 across 17 modules. The count is a one-command measurement —
  walk every `raise` and look for a `rule_id` keyword — so it can
  be re-derived rather than trusted.

  **The scheme needs nothing new; the subjects do.** The prefix is
  the subject, never the error class or the tier, and that rule
  held when `media.` and `machine.` arrived — `media.unknown` is
  one id whether the resolution namespace lacks the media or a
  script's `insert` names it. The blueprint surface is the one
  place needing an argued answer: `document.py`'s 97 are field
  and shape rules over a JSON document, and whether their subject
  is the field (`drives.`, `boot.`, `location.`), the document
  (`blueprint.`), or the rule class is the real question. Guessing
  it 97 times is how a namespace goes bad.

  **Where to start, and why it is not the biggest module.**
  `properties.py`'s 15 are a closed, well-understood family and
  `PropertiesError` is already one class; they would settle the
  pattern for a non-script surface cheaply. `cli.py`'s 13 are
  invocation shape and mostly want one subject. `document.py` is
  last, after its subjects are argued.

  **A located diagnostic is the other half, and only the blueprint
  surface lacks it.** `ScriptParseError` carries line and column;
  the runner's `_Located` cites a statement. A blueprint diagnostic
  carries neither, and `jsonc.loads` hanging `lineno`/`colno` on a
  raised `StaticError` as plain attributes is the stopgap that
  proves the need rather than meeting it.

  **What is already true** (do not redo it): `rule_id` lives on
  `ReliquaryError`, so every class has the field and nothing needs
  a new one; the spec's prefix list carries `media.` and
  `machine.`; and `RULE_OF` maps the static tier alone by
  construction, S-numbers naming syntactic restrictions only, so a
  preflight id absent from it is correct rather than missing.

  **The index is still not the gap.** Deferring the id *index* to
  beta stays where the spec says it; generating it is cheap now
  that ids are a field rather than message text.

### Small items

*(Emptied and struck on 2026-07-27, as the audits, the restructures
and the adjudications were before it. The two orphaned blueprint
rules were the last entry standing, and taking them found the reason
they resisted promotion: both described capability that does not
exist. The `controller` caveat was correctly gated — no machine can
mix controller types — and its constraint now sits with F2's device
growth, plus a guard in `platform_dos.drive_letters` asserted by
test so the invariant is local rather than borrowed from a gate three
modules away. The backend/format table was **not** gated: a blueprint
naming `virtualbox` was accepted and materialized qcow2, which made
the document right and the code wrong, so an unwired backend is now
refused like an unwired controller (P11) and the table's three
unbuilt rows are intent recorded against F2 and F3.*

*Neither was promoted, which was the entry's own question: a rule
about unbuilt capability belongs with the work that would build it,
not in a spec that states what exists.)*
