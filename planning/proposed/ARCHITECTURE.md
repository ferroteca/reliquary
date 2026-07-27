<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Proposed architecture

> **Status:** the staging ground for changes to the architecture —
> new principles, model changes, retirements — argued here before
> anything is pledged. **Nothing here is pledged, and nothing is worked
> from here.** The lifecycle mirrors the use-case one
> ([proposed/USE-CASES.md](USE-CASES.md)) and runs across three
> locations: drafted here, then **pledged** — moved to
> [pledged/ARCHITECTURE.md](../pledged/ARCHITECTURE.md), the move
> itself the record — then in force, moved again into root
> [ARCHITECTURE.md](../../ARCHITECTURE.md), which sits at the
> repository root because it describes current reality: the shipped
> system's model, and only the principles the project honors
> today.
>
> All three share one global P-namespace; numbers are permanent
> and never reused, and no placeholder is left behind by either
> move. A principle in force is clarified, retired, or superseded —
> never changed in nature — while a proposed one may still be
> reshaped freely here (its number stays; work already scheduled
> against it is re-checked in the same edit). The second move is
> **automatic on full delivery** (D34), and full delivery, not
> pledge, is its trigger: a partly-honored principle stays in
> the pledged file, since the standing list is an implementation
> claim. A dead proposal is recorded in
> [DECISIONS.md](../DECISIONS.md) and triggers the same
> planning-doc sweep, its P-number the search key.

## Open proposals

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
(TASKS.md; planning/pledged/design/recorder.md), so the recorder gets a
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

WHAT PLEDGING WOULD COST, stated plainly so it is priced
before it is granted: the Horizon in-band file operations stop
being unjustified deferral and become demanded work — a roadmap
item citing P16, which under D23 is this proposal's pledge.
They are currently sequenced against the second backend, which
left the numbered arc the same day (D33), so pledge would
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
   case in force or pledged", which keeps it inside the
   existing lifecycle.

Statement (candidate; the reach question above may narrow it):

> - **P16 — Reliquary is the only interface to a machine.**
>   Every interaction a use case depends on goes through
>   Reliquary — its CLI, its API, its scripts. Out-of-band
>   access to a machine's host state stays possible and stays
>   unmediated, but no goal the project has pledged may
>   *require* it: a use case that must reach around Reliquary
>   to be met names a capability gap, and the gap is what gets
>   fixed. Handing a machine off is not a breach — export ends
>   Reliquary's ownership on purpose. (Normative home: TBD on
>   pledge.)

**P17 — Guest files are named in the guest's terms** — drafted
(add, 2026-07-23; the owner's proposal, verbatim: *"When a
Reliquary performs file actions on a guest VM on behalf of a
user, the guest files are referenced in terms of the guest OS,
not the host OS."*). Adjudication pending. It pairs with
**P16** above and is deliberately separate: P16 says the
in-band route must exist, P17 says what its addresses look
like. Either can be pledged without the other.

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
first act, on pledge, is to reopen that address form before
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
>   pledge.)

**P18 — Mechanism, not content** — drafted (add, 2026-07-24, the
exec-run round; D36). Reliquary ships no standardized authored
content — no blessed scripts of any kind (readiness, test,
install), no reusable script library. The codex holds *examples*
to copy a first draft from (P4), nothing more; a library of
reusable authored automation is a different project's job. This
sharpens P4 (residency — the codex never feeds automation) and
G2 (no test-result vocabulary) into one boundary about
*authorship*: Reliquary supplies the machine, the drive
mechanics, and the value channels, and attaches no meaning to
what runs through them. Already the shape of the project's own
stack — a guest driver and a test-framework parser each live
outside the machine layer, consuming its interfaces — which is
what a real principle looks like on the way in. It is the same
"computation lives outside Reliquary" the authored-input ceiling
(P14) draws, turned toward *output* and *reusable content*: the
consuming project owns both.

> - **P18 — Mechanism, not content.** Reliquary provides
>   mechanism — machines, drive and file transports, the value
>   channels in and out — and never standardized content. No
>   blessed scripts of any kind, no reusable authored library:
>   the codex carries examples to copy a first draft from (P4),
>   and anything reusable is the consuming project's or another
>   project's to build. Reliquary attaches no meaning to what
>   runs through its mechanisms; computation and interpretation
>   live on the caller's side of the seam (G2). (Normative home:
>   TBD on pledge.)

### Tracked

- **Sharpen P3 from "guest agents" to "transport agents"** —
  tracked (recorded 2026-07-24, the exec-run round; D36). P3
  today says Reliquary consumes native guest agents and never
  builds its own; the fast file-transport thread found the same
  logic binds the *host* side of a transport agent — Reliquary
  builds neither side, sourcing the transport externally (an
  existing tool, then a dedicated project) and providing only the
  control-plane seam. Fold into P3's wording if the fast-transport
  work schedules.

