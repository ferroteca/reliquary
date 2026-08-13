<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
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
leaves this file by deletion and nothing is parked. **Not a
retrospective either**: a note explaining what an emptied group
used to hold is the same parking one paragraph further on, and it
has to be edited every time the work it accounts for moves. The
same holds for the **work-item breakdowns inside a pledged
feature**: when the feature delivers, its list is deleted with its
F-number rather than archived. A record whose reasoning outlives
the work is a decision, and decisions live in
[DECISIONS.md](DECISIONS.md) — kept beside
the work instead, a summary drifts from what it summarizes and a
reader has no way to tell.

**There is no order here.** Nothing in this file is scheduled, and
nothing claims priority over anything else; whoever picks work up
picks whatever they like. The one ordering that does bind is a
feature's: **work that only makes sense as part of one pledged
feature lives with that feature**, in
[pledged/FEATURES.md](pledged/FEATURES.md), and has to be done to
complete it. A task here that merely *relates* to a feature is
still free to be picked whenever.

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

The queue proper is [Pledged](#pledged) below — grouped by kind
because the actor and the gate differ, though the grouping is not
a running order.

Standing questions to re-ask as the design hardens are not tasks
and live with the decision record, under
[DECISIONS.md](DECISIONS.md)'s open questions.

## Every task is itemized

**A task carries a T-number** (D86) — `T8 — Widen the drive report`,
number and name together, the way an F-number reads, at whatever
heading depth its group sits at. A
task is an item like any other, and D42's rule reaches it for
D42's reason: every item that can be depended on needs a handle,
because a heading someone may reword is not something to point
at. The number is what a commit cites, what another task points
at, and what survives this file's own regrouping — the groups
below are kinds rather than a running order, so an entry may move
between them, and without a number its heading text is the whole
of its identity.

**The number is issued at entry**, which for a task is the pledge
itself: a task has no proposed state under `planning/` (D43), so
there is no earlier moment to issue one at, and the idea that
preceded it carries the tracker's own issue number instead. That
is the one asymmetry with an F-number, which is issued at
proposal and travels into `pledged/` unchanged.

**And it evaporates on delivery**, with the work rather than
outliving it. That is D42's second handle class: a use case, a
principle and a decision persist, so their numbers are permanent,
while a feature names work not yet done and its handle goes when
the work lands. A task is work, so a struck task takes its number
with it (D52). **Evaporating is not reusable** — the number
retires and is never issued again, so a T-number surviving in a
commit message can never resolve to something else later, and
gaps in the sequence are history rather than a promise.

**T-numbers are issued against the sequence ledger**
([SEQUENCES.md](SEQUENCES.md); owner, 2026-07-31), which holds the
high-water mark this file used to state — take the next number
there and advance it in the same edit. The reasons the mark must
be stated at all — the queue empties, a struck task's only record
is its commit (D52), and a search sees only the branch it stands
on — live with the ledger, along with the sequence's T8 start.

## Pledged

Grouped by kind, because the actor and the gate differ: an audit
is mechanical, a defect needs no pledge because the norm it
violates already is one. A group with nothing in it is not listed:
an empty heading is a record of retired work, which this file does
not keep.

### Restructures

#### T15 — Merge `blueprint.py` and `script.py` into `authoring.py`

`blueprint.py` authors and removes `.rlqb` files; `script.py` holds
one verb, `delete_script`, and sits inside the `script_*` language
family it has nothing to do with. They are the same shape — author
or remove a user-owned file, failing closed while something still
refers to it — written apart: `delete_blueprint` refuses while
machines of the blueprint exist, `delete_script` while blueprints
reference the script, one rule-id grammar across the two
(`blueprint.has-machines`, `script.has-blueprints`).

Merge both into **`authoring.py`**, holding `new_blueprint`,
`add_media`, `delete_blueprint` and `delete_script`. It pairs with
`assets.py`, which resolves and reads what this writes.

Publish `library._referenced_scripts` as `referenced_scripts` in
the same change — the package's one cross-module module-private
access, which `script.py` reaches to walk home blueprints. The
helper stays where it is: it is the codex seed closure's own
question, used by `seed_blueprint`, and the authoring path asks
the same question of a different file.

`tests/test_blueprint.py` and `tests/test_script_authoring.py`
merge to `tests/test_authoring.py` — the second already imports
from both modules, which is the merge the test tree had already
made.

No application surface moves: no CLI command, no `Session` method,
no exported name, no rule id, so [SURFACES.md](SURFACES.md) does
not trigger.

#### T16 — Rename `machine.py` to `machine_handle.py`

The package spells its collective engine modules in the plural —
`media.py`, `properties.py`, `backends.py`, `machines.py` — and
`machine.py` is the sole singular, holding the `Machine` handle
and its console verbs rather than a family engine. With
`machine_state.py` and `drives.py` beside them there are now four
modules in that neighbourhood to read past, and `machine_handle.py`
supplies the pairing the substrate wants: where a machine lives at
rest, and how one is spoken to while it runs.

The rename stands on readability alone, which is the whole of what
is left. `machine.py` no longer imports `machines` — it takes
`read_vm_state` from the substrate — so the cycle is already gone
and nothing structural waits on this. Turn the deferred
`from .machine import Machine` imports in `machines.py` into
ordinary ones in the same change, now that nothing requires them
to be deferred.

Five import sites, one test line (`tests/test_core.py`), and
AGENTS.md. The six module-level free functions are exported at the
root and are **not** touched — respelling those would be a surface
change and is a separate question. Nothing else moves: no CLI
command, no `Session` method, no rule id.

#### T17 — Split `cli.py`'s `main()` and derive the command list

`main()` is 466 lines that build 48 subparsers before doing
anything. Underneath the length is the reason to touch it: **the
48 command names are written three times in this file** — the
`_COMMANDS` frozenset that drives `_reorder_argv`, the
`add_parser` calls, and the `if arguments.command ==` arms in
`_dispatch` — and only the first is pinned to anything.
`test_command_manifest.py` checks `_COMMANDS` against
`command-manifest.toml` in both directions; the parsers and the
dispatch arms are held by hand. All three agree today, so this is
a latent hazard rather than a defect, and the two gaps fail
differently: a missing `_COMMANDS` entry silently stops leading
flags being reordered, while a missing dispatch arm raises a
fault — loud, but only for whoever runs the command, which is
what the test below turns into a static check.

Three parts, one change:

1. `_build_parser()` plus nine family builders, following the
   comment groups `main()` already carries — machine, script,
   authoring, media, property, listing, state, file, console.
   Registration order is `--help` order, so the call order is
   load-bearing. `main()` keeps argv handling, parse, context,
   session, `_dispatch` and the five exception arms.
2. **Derive `_COMMANDS`** from the built parser's subcommand
   choices and delete the hand-written frozenset. Measured: the
   whole of `main(["--version"])`, parser construction included,
   is 10ms against a 423ms `import reliquary` — so a throwaway
   parser at import costs under 3%, and `main()` still builds its
   own so `_prog_name()` reads `sys.argv[0]` when it does today.
   `test_command_manifest.py` keeps reading `cli._COMMANDS`
   unchanged.
3. A test walking the source for the dispatch arms and comparing
   them to the registered commands, the way `test_errors.py`
   already walks every `raise` in the package. That leaves one
   hand-kept list, mechanically pinned.

**The split is what makes any of this checkable**: nothing can
enumerate the registered commands today, because `main()` builds
the parser inline and never hands it back.

`_dispatch` itself is not split — 145 lines reading as one routing
table, and splitting it would create the fourth list this exists
to reduce. **Weighed and declined:** a full
`(name, configure, handle)` table deleting every duplicate list.
The 48 commands have heterogeneous argument shapes (`run-script`
alone carries a 35-line description, an epilog and a formatter
class), `_dispatch` is not a pure lookup — the nine console
commands share an `_interaction_target` step — and after the three
parts above what remains is one pinned list.

No application surface moves: no command, flag, help string or
exit code, so [SURFACES.md](SURFACES.md) does not trigger. The
oracle is byte-identical output from `rlq --help` and all 48
`rlq <command> --help`, captured before and diffed after —
stronger than the suite here, since AGENTS.md already validates
documented syntax against `--help`. Independent of T15 and T16.
