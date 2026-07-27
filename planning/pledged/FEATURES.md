<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Pledged features

Large capability that is **pledged but not yet built**, each
carrying the work breakdown that delivers it. A feature arrives here
by being moved out of
[proposed/FEATURES.md](../proposed/FEATURES.md) — the move is the
pledge and the commit is its record ([README.md](../README.md))
— and leaves by being delivered.

Pledged is not scheduled: the numbered milestone arc ended with
milestone 9, so nothing below is queued or dated. The work items are
tasks like any other and answer to the same rules as
[TASKS.md](../TASKS.md); they sit with their feature rather than in
that queue because they are meaningless apart from it.

Each feature carries an **F-number** and must fit in **one sprint**
(D42; the rules are in [README.md](../README.md)). A feature too
large is cut on pledge, the split retiring the parent's number
for a fresh one per piece.

**F17 arrived from [TASKS.md](../TASKS.md)** (owner, 2026-07-27),
by the gate audit of that day, pledged already by sitting in that
file — the move changes where it is housed, not what it is, and
nothing below is newly promised. **It moved on its size, not its
surface.** Touching an interface is no bar to being a task (D45),
and the audit's first reading said otherwise; what disqualifies
F17 from the task queue is that it is seven work items with a
bisection rig among them, which is a feature by any measure. The
script-language residuals travelled with it under that first
reading and **went back**, being genuinely small.

## F1 — The U6 authoring recorder

> **Unusually large — flagged, not cut** (owner, 2026-07-26). On the
> sprint this project runs, its seven work items are not one feature
> but at least seven. It stands as written by decision, and the flag
> is the whole of the treatment; the sequencing note below marks
> where a cut would fall if one is ever wanted.

Use case **U6 — pledged, awaiting delivery** (moved 2026-07-23);
design in [design/recorder.md](design/recorder.md). The one
capability the numbered arc deliberately did not deliver while its
demand was already pledged: the arc ended at milestone 9 with the
recorder unbuilt.

Work items, in rough dependency order:

- Reliquary-owned console viewer over the vnc control plane
  (recording prerequisite: backend display-window input is
  invisible to Reliquary)
- text-mode recorder first (no new language surface: waits from
  VGA scrapes, type/press actions, generated-comment
  uncertainty flags)
- runner run-to-point / breakpoint / human-takeover machinery
  (also the failure report's "take over from here" suggested
  next command)
- round-trip: fragment emission anchored by playback position;
  opt-in surgical apply at the anchor (never regenerate, never
  text-merge)
- landmark catalog shape: decided (DECISIONS.md, the wrinkle
  round; [design/landmarks.md](../proposed/design/landmarks.md)) —
  implementation rides the asset spec work
- run-events: handover event kinds (script/human control
  passing); a capture session is one run record with mixed
  drivers
- CLI record command family + API twins land together (parity)

**Sequencing note.** The console viewer rides the VNC control
plane, which is itself unbuilt — it arrives with the GUI era (F5,
[proposed/FEATURES.md](../proposed/FEATURES.md)). The text-mode
recorder is what can proceed without it. That reference runs *up*
the lifecycle, which D42 treats as a flaw rather than a dependency —
tolerated here alongside the size, and noted so it is not mistaken
for the normal shape. The text-mode half is the part that depends on
nothing unpledged.

## F17 — Input pacing before guest input

> Moved from [TASKS.md](../TASKS.md)'s Design section by the
> 2026-07-27 gate audit — **on its size**. It adds a keyword to the
> scripting language, which is no bar to being a task (D45); what
> puts it here is the seven-item breakdown below, a bisection rig
> among them. Serves
> **U14**, **U20** and **U12** — all three in force since D46,
> which retires this citation's conditional half — a script
> that cannot reliably land a keystroke serves none of them — on
> language goals **G1** and **G5**. Raised by milestone 9's FreeDOS
> install failure (owner, 2026-07-24); the design was settled in
> that day's question round and stands as written.

THE PROBLEM, with evidence. `freedos-install.rlqs` waited for the
installer's welcome screen and then `press enter`, and the
keystroke was swallowed — the installer paints the screen *before*
it starts reading the keyboard. The wait timed out 30s later at the
next step; pressing Enter by hand, seconds after, advanced it
immediately. Reproduced on the pre-milestone tree, so this is
structural rather than a regression. It was worked around by
switching that one line to `select "Yes"`, which is feedback-driven
and re-reads the screen between keys — which is also *why* every
other confirmation in that script already worked.

THE OWNER'S POSITION. This will be very common — "wait for
<this>, then do <that>" needs a gap between the two — and authors
should not have to code that gap every time. A standard delay
belongs in the system; only *changing* it should require writing
anything.

THE FRAMING THAT MAKES IT LEGAL. This is **not** a `delay` verb,
and the language's prohibition on one stands.
[script-spec.md](../../docs/spec/script-spec.md)'s Timing section
already ends "Screen polling and input-event pacing remain
control-plane-owned; the script does not tune them" — and a gap
between observing a screen and delivering the next input *is*
input-event pacing. G1 supplies the argument: agentlessly, the
guest's *input* readiness is unobservable where its output is not,
so a control plane that types the instant a screen paints asserts
something it cannot know. The mechanism is half-present already —
`send_keys` paces at 0.06s *between* key events; what is missing is
the pause before the *first* one. `stable=` is the wrong tool: it
strengthens the observation where the need is to pace the actor, it
costs a poll interval plus its duration, it changes what the author
is asserting, and it must be written on every wait — the burden
being objected to.

Settled in the 2026-07-24 question round (owner):

- **Scope: header > phase > statement**, the same lexical ladder
  `timeout` uses — innermost-wins, resolved at parse time, reported
  by `check-script`. A column in the placement matrix, not a second
  model.
- **Applies to every guest-input verb** — `enter`, `type`, `press`,
  `select`. One invariant needing no context: before typing at an
  agentless guest, let it settle. Host-side verbs (`insert`,
  `eject`, `set-boot`, `screenshot`, `start`, `stop`, `set`,
  `http`) are not guest input and do not pay it.
- **Default 0.1s for now, expected to be revisited.** The number
  will swing wildly — a plain text screen renders quickly, a
  colourful exploding TUI menu very slowly — so the default cannot
  serve every screen by construction, which is itself the argument
  for the per-phase and per-statement override carrying real weight
  rather than being speculative generality.
- **The term is *pacing***, which is the spec's own word for it:
  the language adopts a term the design already used rather than
  coining one, and the name says plainly which half of the model it
  belongs to — it paces the actor, it does not strengthen an
  observation. The rejected candidates are worth keeping: `settle`
  read best on meaning but sat a near-homophone away from `stable`
  in one small vocabulary, on the opposite half of the model — a
  real G6 cost; `ready` reads naturally but collides with the
  resting machine phase.

Work items:

- bisect the interval that reliably lands a keystroke on the
  installer screen that motivated this. No evidence yet fixes the
  number: what is known is that "immediately" is too little and
  "several seconds later" is enough, and the rig is cheap to stand
  up now
- the parse-time plan — pacing resolved on the same ladder as
  `timeout`, every guest-input verb carrying its effective value
  and the scope that supplied it
- `check-script` reports it beside the timing plan
- the runtime pause, before the first key event of every
  guest-input verb
- settle the residual spelling nit, which is this feature's and not
  a reopening: whether the token spells `pacing` or `pace` in both
  positions (`pacing 300ms` in a header, `press enter pacing=300ms`
  on a statement). Lean `pacing` for both — one spelling everywhere
  (G6), and a *pace* is naturally a rate where what is being set is
  an interval
- [script-spec.md](../../docs/spec/script-spec.md)'s Timing section
  is the normative home: the placement matrix, and the "there is no
  `delay`" paragraph amended to distinguish the absent *verb* from
  control-plane pacing
- a D-number recording the interface-change triage. As it stands:
  no use case is cost and several are served — an easy approval
  under the interface-change rule

## F23 — In-band listing and whole-tree file transfer

> **Pledged 2026-07-27 by D57**, which pledged **P16** and priced
> it: these two operations are the only places the shipped
> QEMU/DOS workflow fails P16's test, so they stop being deferred
> convenience and become owed work. Promoted out of
> [proposed/FEATURES.md](../proposed/FEATURES.md)'s Horizon, where
> they had been sequenced against the second backend; **that
> coupling is cut** — the second backend left the numbered arc
> with D33, and P16 does not wait on it. Serves **U14** and
> **U20**, demanded by **P16**.

THE GAP, IN P16'S TERMS. A consumer that needs to know what files
a stopped machine's drive holds, or to move a whole tree in or
out, has no verb to ask. It must open the drive directory itself —
which is exactly what P16 forbids Reliquary to require. Single-file
exchange is already served (`put-file` / `get-file`, milestone 9),
so the gap is precisely listing and bulk.

THE VERBS: `list-files` / `get-files` / `put-files` (twins
`list_files` / `get_files` / `put_files`), stopped-machine
operations under CLI–API parity.

**THE ADDRESSING MUST BE REDESIGNED, NOT RESUMED.** D5's rough
`<drive-key>:<path>` shape is illegal: **P17 refuses it**, armed
D47, because `hdd0:` is a blueprint key no guest ever says. The
shipped verbs address in guest terms (`A:\JOB.BAT`) and these must
match — one address vocabulary, not two spellings of it. F15 is
the neighbour that settles the same question from the other side.

The rest of D5's shape stands: images reached through the
adapter's at-rest filesystem access, directory-source media
directly; capability-honest per call, so a drive whose filesystem
the adapter cannot read fails **by name** (P11); `media` drives
excluded; directories recursive; no record custody — files land
where the caller says.

Work items:

- the guest-terms address form these share with `put-file` /
  `get-file`, settled once for all five verbs
- `list-files`, and what it returns: the shape is a contracted
  `--json` document under P7, so it is designed before it is built
- `get-files` / `put-files` over a directory-source drive, the
  path the shipped single-file verbs already take
- the same over an image through the adapter's at-rest access,
  where the filesystem may be unreadable and must fail by name
- `get-files`' destination default, which D5 left to this round
- CLI and API twins land together (parity)
- P16's promotion rides this work (D34): when these land, P16
  moves to the root list with its residue — backends with no
  vvfat equivalent — filed as a defect in the same change
