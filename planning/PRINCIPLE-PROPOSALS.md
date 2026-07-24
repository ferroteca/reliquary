<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Principle proposals

> **Status:** the staging ground for changes to the governing
> principles. Nothing here is in force: the standing list —
> [PRINCIPLES.md](../PRINCIPLES.md), at the repository root
> because it describes current reality — holds only the
> principles the project honors today. The lifecycle mirrors
> the use-case one
> ([planning/USE-CASE-PROPOSALS.md](USE-CASE-PROPOSALS.md)):
> proposed and in-force principles share one global
> P-namespace, numbers are permanent and never reused, a
> principle in force is clarified, retired, or superseded —
> never changed in nature — while a proposed one may still be
> reshaped freely here (its number stays; work already
> scheduled against it is re-checked in the same edit), and a
> proposal moves over when the project actually honors it,
> with no placeholder left behind. That move is **automatic on
> full delivery** (D34): whoever lands the milestone or task that
> makes the code honor a principle promotes it in the same
> change — adds it to the standing list, deletes it here, records
> the move in DECISIONS.md — rather than holding it for a separate
> sign-off. Full delivery, not acceptance, is the trigger: a
> partly-honored principle stays here, since the standing list is
> an implementation claim. A dead proposal is recorded in
> [DECISIONS.md](DECISIONS.md) and triggers the same
> planning-doc sweep, its P-number the search key.

## Open proposals

### Accepted — awaiting delivery

**P5 — The feedback split** — accepted; moved from the
standing list 2026-07-23 by the delivery pass: the principle
is run-scoped, and the machine-readable run rendering does not
exist yet — no run-events stream, no `--progress` renderers
(the flag appears only in an error message today). The query
half (`--json`) is real, but the run half is milestone 9's
work, whose scheduling — it cites the split — is this
proposal's acceptance. P5 returns to the standing list when
milestone 9 lands. Statement and prose verbatim:

> - **P5 — The feedback split.** One run, two renderings: pretty
>   and legible for a person, machine-readable and just as
>   timely for a program — neither scraped from the other.

> Alongside these runs a feedback split (P5). Reliquary's runs
> are long, and whoever drives one gets timely progress —
> presented for the driver. A person at the CLI (U1, U5) gets
> pretty, legible, real-time progress; an automating program
> (U3, U4) gets machine-readable output that is just as timely.
> The two are renderings of the same run, and neither is
> derived by scraping the other: the pretty rendering is never
> what a program parses, and the machine rendering is never
> what a person is left to read.

**P14 — The expressive ceiling** — accepted (add, 2026-07-23;
the format re-examination round, D26). The principle-sized
kernel of a rule the project has been applying channel by
channel without ever stating it as one. THE ARCHITECTURE IS
P15'S — three authored channels and one invocation channel —
and P14 governs THE AUTHORED THREE ONLY, the invocation channel
being floored rather than capped and staying with P6/P7. What
P14 adds is that each authored channel holds a CEILING, and
that the refusals are symmetric: a spec never grows
expressions, a script never nests a second format, a property
never gains a transform.

WHERE IT ANCHORS — P14 asserts nothing new. It is what three
principles ALREADY IN FORCE require of the authored inputs,
gathered into one standing rule so they survive pressure that
arrives one convenient feature at a time:

- **P7, the binding constraint.** A pillar that grows a
  language becomes hard to EMIT from C or Java — reading it
  needs a parser, writing it needs the language. That is
  precisely why D26 declined HCL2, whose writer exists only in
  Go.
- **P6, one semantic surface.** Specs are documents the
  embedding API writes as well as reads. A spec that must be
  evaluated before it means anything can be read but not
  emitted, and the CLI/API twinning breaks on the half that
  cannot be written.
- **P4, the artifact-residency split.** Automation artifacts
  are source in the consuming project's tree — and source is
  what a schema checks and an editor completes. A spec needing
  evaluation before it can be checked stops behaving like the
  checked-in source P4 requires.

Two more govern how it operates rather than why it exists:
pressure against a ceiling routes to a decision under the
interface-change rule (**P8**), and the window in which a
breach is still recoverable closes at 1.0 (**P9**).

The instances, each argued alone at the time and none of them
citing the others:

- **The script channel** got a purpose-built, line-oriented DSL
  rather than an embedded general language, and D12 then
  refused JSON islands inside it — a data format nested in the
  logic channel is the same breach seen from the other side.
- **The spec tree** stays logic-free (D18), with in-tree
  function objects (the CloudFormation `Fn::` shape) and
  string templating (the Helm shape) permanently rejected.
- **The spec strings** close at two fixed productions (D26 as
  corrected by D27), so an operator-bearing reference is a
  parse error and not a judgment call.
- **The property channel** put it most bluntly of the three,
  and had done so before this round noticed:
  script-properties.md already reads *transforms in derivation
  syntax are permanently out — normalization lives in a fact's
  definition, arbitrary computation in the embedding API's
  provider seam*. The same rule and the same escape, written
  for values. Its authored source sits lower still —
  machine-rewritten `key=value`, which left JSON behind because
  a file a program rewrites needs less, not more (D18).

What the ceiling does NOT forbid matters as much, or it will
be misread as hostility to every convenience: a bounded
declarative construct that ENRICHES VALUES may land as data
and be expanded by Reliquary — a variant matrix on the
GitHub-Actions shape, say — argued on its own when it earns
its keep (D18). What the ceiling refuses is computation that
DECIDES STRUCTURE. And a construct can still die for reasons
the ceiling knows nothing about: the `children` glob D18
floated was killed by D22 on the static-catalog rule — a name
may never depend on a download — which is not P14's doing and
must not be recorded as such. Computation itself lives OUTSIDE
all three channels — in the caller's own language, reached
through either door (G2). It is not a Reliquary capability, so
it is not an API-only one either, and the CLI user's host
language is the shell, which P7 already requires be easy to
drive Reliquary from.

THE DANGERS ARE OBSERVED, NOT HYPOTHETICAL, and naming them is
the point — a ceiling nobody can price is a ceiling that gets
traded away. Helm charts are Go templates rendered to text
before anything parses them as YAML: Kubernetes publishes an
excellent schema and a chart cannot use it, indentation becomes
the template engine's problem rather than the format's, and
errors report against rendered text the author never wrote.
CloudFormation carries `Fn::` objects and `!Sub` shorthand as
two spellings of one thing, forever, because removing either
would break stacks in the field. HCL2's expression language is
fluent to author and effectively unemittable outside Go, which
is the P7 failure D26 declined it on. EVERY ONE OF THESE
ARRIVED ONE WELL-JUSTIFIED FEATURE AT A TIME — no maintainer
approved a template engine; each approved a default, then a
conditional, then a filter. That ratchet is what the closure
exists to stop, and it is why the moment to refuse is before
the first request rather than during it, when the request will
have a real user and a good case behind it.
Locally the bill would fall on U4 and U5 (the published
schema's validation and completion, which is what the plain
format was chosen to buy), on P6 (an embedding API that can
read blueprints but no longer emit them), and on P7. And it is
PRICED BY THE CALENDAR: pre-1.0 a breach is still recoverable
under D25, and at 1.0 it stops being — so the window in which
this principle is cheap to hold is the window the project is
in right now.

TWO OF THE THREE ARE ALREADY HONORED: the script channel in
landed code — the language is the constrained one it was
designed to be, growing under G7 — and the property channel in
normative design, its refusal written before this round found
it. ONLY THE SPEC CHANNEL WAITS, and on one deliverable:
milestone 7's parser, honored when it refuses an
operator-bearing reference. The milestone's citation of P14 is
this acceptance, and P14 joins the standing list when the
milestone lands. What is deliberately NOT in it: how far a
reference may *reach*, which is a different axis with the
opposite economics (widening is cheap, narrowing is not) and
stays a design call. THE GUARD AGAINST CONFUSING THE TWO is one
question — does the change alter what may appear BETWEEN the
braces, or only WHERE the braces may appear? Take one field,
`controller`, and two requests against it. Admitting `${key}`
there, which D26's trim currently refuses, is POSITION: it is
granted or refused on whether a named case has finally appeared,
and P14 must never be cited against it, because P14 does not
govern reach at all — nor does it license narrowing reach, on
which it is equally silent. Admitting `${key:-ide}` there is
BODY: refused by P14 outright whatever the demand, and it
routes to a layer decision instead. Note it PASSES the
character class — `:` and `-` are both legal — and is refused
by the production, the text before the first colon being the
qualifier and `key` not being one. The class screens; the
productions decide (D27). The first is a design call that can be taken back; the
second cannot, which is the whole reason they are governed
differently. Statement:

> - **P14 — The expressive ceiling.** Each of P15's three
>   authored channels holds an expressive ceiling, and none
>   takes on another's job: a spec never grows expressions,
>   closed in its tree and its strings alike; a script never
>   nests a second format; a property never gains a transform.
>   Ceilings are stated as closed grammars ahead of the
>   pressure, because every request to raise one arrives
>   individually well justified and a channel that grants them
>   one at a time cannot take them back. When a ceiling binds
>   the answer is a layer — arriving as its own kind, never as
>   a wider dialect of the channel it feeds — argued under the
>   interface-change rule and chosen then, never pre-committed.
>   Computation lives outside all three, in the caller's own
>   language. A ceiling governs what a channel may *say*, never
>   how widely an already-permitted form may be *used*. This is
>   what P4, P6, and P7 require of the authored inputs, held as
>   one standing rule. (Normative:
>   planning/design/machine-blueprint.md "Format stability",
>   planning/design/script-spec.md "How the vocabulary grows";
>   D12, D18, D26.)

### Drafted

**P16 — Reliquary is the only interface to a machine** —
drafted (add, 2026-07-23; the owner's proposal, verbatim: *"All
foreseeable interaction with a VM should be through Reliquary.
A known use case which expects out-of-band access to fulfil the
user's goal, would violate this principle."* — "VM" reads as
the house noun **machine**). Adjudication pending; nothing is
folded downstream, and the collision below is the reason to
adjudicate rather than absorb.

WHAT IT ASSERTS is a test on use cases, not on users. Out-of-band
access stays physically possible — a stopped machine's drives
are plain host state and always will be — and a user who wants
to poke at them is not the target. The violation is narrower and
sharper: a KNOWN GOAL THAT CANNOT BE REACHED without leaving
Reliquary. Reaching around the tool is then not a workflow, it
is a capability gap wearing one.

WHAT IT DOES NOT ASSERT, or it will over-read on first citation:
- **Export is a handoff, not a breach.** `export-machine` ends
  with Reliquary letting go on purpose (P1, the U8 draft); the
  artifact leaves its purview by design. P16 governs machines
  Reliquary still owns.
- **The guest's own world is untouched.** Guest logs, guest
  history, and what a person does at a console are the guest's,
  as the transcript-redaction contract already says.
- **It is not the closed input model.** P15 closes how
  *authored input* reaches Reliquary; P16 would close how
  *interaction with a running or stopped machine* does.

ALREADY HONORED IN ONE PLACE, WHICH IS THE ARGUMENT FOR IT: the
U6 recorder's first work item exists for exactly this reason —
"backend display-window input is invisible to Reliquary"
(TASKS.md; planning/design/recorder.md), so the recorder gets a
Reliquary-owned console viewer rather than recording a person
typing into QEMU's own window. That is P16 reasoning, applied
before P16 was stated, and it is what a real principle looks
like on the way in.

WHERE IT COLLIDES — D5, HEAD-ON, and this is the whole
adjudication. D5 (the out-of-band round, owner 2026-07-22)
dropped run collection and made **file exchange out-of-band by
design**: while a machine is stopped its drives are plain host
state, `get-machine-dir` is the door, "Reliquary neither
mediates nor records it", and in-band `list-files` /
`get-files` / `put-files` were deferred to Horizon. D5 reached
that by asking *"what use case cannot be met without it?"* and
answering *"none"*. P16 CHANGES THE QUESTION — from whether the
goal is reachable to whether it is reachable THROUGH RELIQUARY —
and on the new question D5's own answer inverts: U3's
inject-execute-observe loop is a known use case whose file half
is served today only out of band (a vvfat `hostdir` on QEMU;
nothing at all on a backend without one). Under P16 that is a
violation on its face.

WHAT ACCEPTANCE WOULD COST, stated plainly so it is priced
before it is granted: the Horizon in-band file operations stop
being unjustified deferral and become demanded work — a roadmap
item citing P16, which under D23 is this proposal's acceptance.
They are currently sequenced against the second backend, which
left the numbered arc the same day (D33), so acceptance would
also be the argument for scheduling them independently of it.
D5 is not retired by this: its drops (the `results` header,
`stage`/`collect`, record custody) stand on their own reasoning,
and only its out-of-band clause is in question.

OPEN FOR ADJUDICATION:
1. **Reach.** Does "foreseeable interaction" mean file exchange
   specifically, or every touch — a person typing into the
   backend's console window under `--display`, `hmp`, a user's
   own tools on a stopped drive image?
2. **Does the out-of-band route survive?** Permitted convenience
   alongside an in-band route, or retracted as the sanctioned
   answer? (The edges D5 contracted — running drives
   untouchable, media cache read-only, `runs/` append-only —
   are worth keeping either way.)
3. **`hostdir`.** A `hostdir` drive *is* a declared host
   directory: in-band by declaration, or the canonical instance
   of the violation? The answer decides whether QEMU/DOS is
   already compliant or is the first thing to fix.
4. **"Foreseeable."** A principle that binds on foresight needs
   its own test, or it becomes unfalsifiable — probably "a use
   case in force or accepted", which keeps it inside the
   existing lifecycle.

Statement (candidate; the reach question above may narrow it):

> - **P16 — Reliquary is the only interface to a machine.**
>   Every interaction a use case depends on goes through
>   Reliquary — its CLI, its API, its scripts. Out-of-band
>   access to a machine's host state stays possible and stays
>   unmediated, but no goal the project has accepted may
>   *require* it: a use case that must reach around Reliquary
>   to be met names a capability gap, and the gap is what gets
>   fixed. Handing a machine off is not a breach — export ends
>   Reliquary's ownership on purpose. (Normative home: TBD on
>   acceptance.)

**P17 — Guest files are named in the guest's terms** — drafted
(add, 2026-07-23; the owner's proposal, verbatim: *"When a
Reliquary performs file actions on a guest VM on behalf of a
user, the guest files are referenced in terms of the guest OS,
not the host OS."*). Adjudication pending. It pairs with
**P16** above and is deliberately separate: P16 says the
in-band route must exist, P17 says what its addresses look
like. Either can be accepted without the other.

WHAT IT ASSERTS: a file action names its target the way the
guest's own user would — `C:\DOS\FOO.TXT` on DOS,
`/etc/rc.conf` on OpenBSD — with that OS's separator, roots,
and naming rules. The host's view (which image file, which
offset, which mounted staging directory) is Reliquary's
plumbing and never surfaces as the address.

WHY IT IS A PRINCIPLE AND NOT A SYNTAX CALL: the address is the
part of a file API a user writes by hand and a script commits
to source. A host-flavored address leaks the materialization —
which is exactly the layer P1 says is disposable and the
adapter seam says is the backend's business — into the one
place a workflow is most permanent. It is also the P5/P6
argument applied to addresses: the user names what they mean,
not what Reliquary happens to have on disk.

WHERE IT LANDS — the deferred in-band file family, whose
roughed shape D5 recorded as **`<drive-key>:<path>` addressing**
(`list-files` / `get-files` / `put-files`). That shape is the
host-flavored one this principle would refuse: `hdd0:` is a
blueprint drive key, not anything the guest ever says. So P17's
first act, on acceptance, is to reopen that address form before
it is implemented — cheap now, expensive after (P9's window,
D25's calendar). D5 explicitly left the details to "that
milestone's own round"; this would be an input to it.

THE HARD PART, WHICH IS P10: mapping `C:` to a drive is guest
knowledge, and *nothing is inferred from guests*. The proposal
survives that only if the mapping comes from **declared**
sources — the blueprint's `platform` (platform workflows
already own OS meaning: syntax, completion, readiness) plus
Reliquary's own drive configuration and boot order, which it
assigned. It dies if honoring it would mean probing a guest, or
booting one, to learn where a path points. Worth stating in the
entry itself, since P10 is the principle most likely to be
cited against this one.

OPEN FOR ADJUDICATION:
1. **Where does the mapping come from?** Declared platform plus
   Reliquary's own drive assignment (compatible with P10), or
   does DOS drive lettering — which depends on partitioning the
   guest performed — need a declaration in the blueprint? A
   stopped machine has no guest to ask, and at-rest access is
   the whole point.
2. **Ambiguity and honesty.** When the declared facts do not
   determine a letter, does the call fail closed naming what it
   could not resolve (P11's shape), or is there an escape
   spelling that names the drive directly for that case?
3. **Normalization.** Case rules and 8.3 semantics are guest-OS
   terms too. In scope for this principle, or a design detail
   underneath it?
4. **Exemptions.** `get-machine-dir` returns a host path by
   definition — the out-of-band door (D5). It stays host-flavored
   under either reading, but the entry should say so, since it is
   the obvious apparent counter-example. Same question for a
   `hostdir` drive, which is a host directory *by declaration*.

Statement (candidate; question 1 may add a clause):

> - **P17 — Guest files are named in the guest's terms.** A
>   file action against a machine addresses its target as the
>   guest OS does — that system's paths, separators, and roots —
>   never as the host stores it: not an image file, an offset,
>   or a staging directory. How the address resolves is
>   Reliquary's plumbing and may change with the backend; what
>   the user writes may not. The mapping is built from declared
>   facts — the blueprint's platform and Reliquary's own drive
>   assignment — never from inspecting a guest (P10). Where the
>   declared facts leave an address ambiguous, the call fails
>   closed naming the ambiguity (P11). (Normative home: TBD on
>   acceptance.)

### Tracked

- **Itemize ROADMAP's remaining design principles** — tracked
  (recorded 2026-07-23; previously a candidates note inside
  PRINCIPLES.md). One script, one target; installation media
  is input, disk images are output; dependencies pull their
  weight — each already normative in ROADMAP "Design
  principles", absorbed here under a P-number as it proves
  cross-cutting.
