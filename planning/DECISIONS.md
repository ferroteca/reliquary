<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# DECISIONS

The adjudicated design-decision record, and the guard against
re-litigating: anything recorded here as killed, declined or
superseded is not revisited without new evidence, argued through
the surface-change rule ([SURFACES.md](SURFACES.md)).

**This is a working file, not an archive.** Every entry must earn
its place by the value it carries *today*, and an entry is
rewritten — in current spellings, against the current surface — as
readily as it is added. Git history holds what each said when it
was written, so nothing is lost by keeping the live text current,
and a record too large to search stops being a guard against
anything.

**Ask where the rule's normative home is before asking which
D-number it takes.** A rule with a home — a principle, a use case,
a specification, AGENTS.md — is *written there*, and the commit
that writes it is the record; an entry restating it is the second
register this machinery refuses to keep. Neither a decision to
change the vision nor a decision to align with it earns an entry.
What is left for an entry is the part with no home: a **contested
call with a rejected alternative**, kept because the guard against
re-litigating is real, plus the condition that would reopen it.
That is a paragraph, not a page.

A LIFECYCLE ACT ALONE EARNS NO ENTRY. Proposing, pledging,
promoting, delivering: location states the status and the commit
that moves the item is the record, so delivery evidence belongs in
that commit's message. Only a ruling made in the act's course — a
contested clause reading, a scope call, a withdrawal — is recorded
here, as the ruling rather than the promotion around it.

Decisions are numbered in the order first recorded — D1 the
earliest — and a number is never reused; the list reads
newest-first, so the top entry carries the highest number and a new
entry prepends with the next free one. The D-number is the
decision's citation handle everywhere: a decision generally
supports use cases (U-numbers), architectural principles
([ARCHITECTURE.md](../ARCHITECTURE.md), P-numbers) or language
goals (G-numbers), and names what it supports; it may also cite the
application surfaces (S-numbers), features (F-numbers), tasks
(T-numbers) and the script-validation rules (V-numbers). Design
docs, specs and code commits justify choices by citing D-numbers.

An entry only PARTLY overruled stays where it is, the amending
entry governing and a bracketed pointer at the affected clause
naming it. An overruled or no-longer-relevant decision moves to the
Retired decisions section at the bottom, its note naming what
overruled it — a retired decision binds nothing but remains the
record.

**Retired vocabulary in entries not yet swept.** This decode is
scaffolding, not policy: it shrinks as entries are brought current,
and an entry that has been rewritten needs none of it. **Interfaces**
/ `INTERFACES.md` is what D85 renamed the application surfaces and
`SURFACES.md`; **PRINCIPLES.md** is root `ARCHITECTURE.md` (D50);
**ROADMAP** is the roadmap dissolved into these directories on
2026-07-26; **accepted** is **pledged** (D44); **Milestone N** is the
numbered arc that ran 1–9 and now schedules nothing (D33). One is a
genuine ambiguity rather than a dated word: an `S<n>` in an unswept
entry may be a **script-validation rule**, which D84 renumbered to
`V<n>` one for one, where today's S1–S8 are the application
surfaces — so read an S-number by its entry's date until the sweep
reaches it.

## Open questions

Questions awaiting adjudication — the front of this record rather
than a separate one, since what settles them is an entry below.
Nothing here binds anything; a question leaves this section by
becoming a D-number, and the commit that moves it is the record.

A question that gates a specific unbuilt feature is **not** here: it
sits in that feature's own "Decide first" block, in
[proposed/FEATURES.md](proposed/FEATURES.md) or
[pledged/FEATURES.md](pledged/FEATURES.md), because it is the design round
to run before that feature's deliverables start. What follows is
what gates nothing in particular.

### Still needed

- **Friendly machine aliases**: machine identity is already
  human-readable (`<blueprint>-<n>`); still open is whether
  listings and selectors additionally offer docker-style generated
  word aliases, or whether numbered ids plus blueprint selection
  make them unnecessary.

### Deferred to 1.0

- **Format versioning**: pre-1.0, user documents carry no
  version field and no `$schema` field (settled, owner 2026-07-21;
  the horizon moved from beta to 1.0 with the compatibility rule,
  D25, on the same argument:
  a pinned schema reference is a version field in disguise, and a
  pre-1.0 document has no format vintage — the only schema that
  matters is the installed Reliquary's, which editors bind by file
  association; an embedded pin would go stale in seeded files
  under never-overwrite and let the editor pass what Reliquary
  rejects). When compatibility guarantees arrive — no earlier than
  1.0 — the leading candidate spelling for the version field is
  `$schema` as a versioned URL: one field declaring the document's
  format version and binding editors to the matching published
  schema.

### Watches — re-ask as these harden

Standing questions rather than pending decisions: each is a design
pressure to re-examine as the surface around it firms up, and none
is waiting on an answer today.

- GUI/landmark assets forming a new authored artifact class
  (hardened 2026-07-21: .rlql is the fourth authored extension —
  the INTERFACES listing is due at the asset-spec/realignment
  pass)
- the adapter API becoming world-facing
  (design/backend-adapter.md is INTERNAL by decision,
  owner 2026-07-21 — a real third-party adapter story elevates
  it into the INTERFACES inventory through the interface-change
  rule, never by drift)
- **two norms for one semantic surface** (raised 2026-07-26).
  `docs/spec/cli.md` and `docs/spec/api.md` are both normative for
  what ARCHITECTURE.md calls one semantic surface. P6 states the
  parity symmetrically and the twin-name rule derives only
  *names*, so nothing says which wins if the two disagree on
  **semantics**. **Both stay normative for now** (owner): they
  align very closely, so the risk is dormant rather than absent.
  Re-ask when they first diverge, or when a second binding lands —
  the resolutions available are naming one of them normative and
  the other derived (the API is the natural pick, and this needs
  no move to code-as-norm), adding a tie-break clause, or placing
  the semantics in one document both specs present.

## Decided

- D118 — NO DRIVE-SCOPED SETTINGS SECTION; A DRIVE IS ADDRESSED
  THROUGH THE BACKEND'S OWN HATCH — DECIDED (owner, 2026-08-22)
  and delivered the same day, closing the "per-drive backend
  settings" open question. Supports U22; P25. Extends D92's
  overlap rule.

  The question was whether a drive-scoped section has a case the
  machine-scoped one cannot serve. **It does not**: every per-drive
  knob is one backend's spelling (QEMU's `cache=`, `aio=`,
  `serial=`; VirtualBox's `--nonrotational`), so P25 keeps all of
  them behind the backend's pin, and the backend's own addressing
  reaches a drive from there — QEMU's `-set drive.<slot>.<option>=
  <value>`, verified on the installed QEMU to target a named drive
  and to refuse unknown options and ids itself. What stood in the
  way was the adapter's: hard disks rendered without `id=`, and
  the overlap rule did not see through `-set`. Both close with
  this — every drive carries `id=<slot>`, and a `-set` on a
  property `drives` renders is refused naming `drives`, the same
  second-source rule as `-drive`. No blueprint anywhere uses
  `backend-settings` yet, so this is settled on the design's terms
  rather than a case.

  WEIGHED AND DECLINED: **a drive-scoped section** — two places
  for one backend's vocabulary, with the overlap rule to restate
  per scope. REOPENS on a backend whose per-drive configuration
  has no addressable form from its machine-level hatch;
  VirtualBox's hatch is empty today and will be judged when it
  exists.

- D117 — NO INCLUDE MECHANISM; THE CORPUS HAS NOT EARNED ONE —
  DECIDED (owner, 2026-08-22), closing the "cross-script reuse"
  open question. Supports (none) — a refusal; argued from G2, G3,
  G6 and D104's construct bar.

  The question asked whether repeated behaviour justifies a
  constrained include, with real scripts to establish the need,
  and a named desire on record (owner, 2026-07-21): complex
  scripts split into interacting files, like source files.
  **Measured, the corpus does not establish it**: seven scripts
  (four codex, three of the owner's) repeat exactly two idioms —
  boot to prompt (`start` / `wait "C:\>"`) and power off
  (`enter "fdapm poweroff"` / `wait machine=stopped`), two lines
  each at three sites — and the one larger candidate, the owner's
  install script, is the codex's *diverged* copy (a different
  loader, an `eject` moved), which P18's copy-out makes the
  expected pattern. A construct to save two lines fails D104's
  bar, and G6 makes surface the scarce resource. What "interacting
  files" can mean here is already served outside the language,
  where G2 puts composition: a harness runs `ready`, its own
  steps, then `verify`; `machine` headers state each script's
  precondition; variables and properties carry data.

  WEIGHED AND DECLINED — **`run @script`, script-as-statement**:
  a verb executing a *linear* script in place, headers checked
  statically, recursion refused so the graph stays a finite tree
  (G3), no parameters (G2), every statement keeping its file and
  line plus the call site. The least-bad shape, recorded so a
  reopening starts from it rather than from a handler-splicing
  macro or a phase import (whose `goto` targets couple it to the
  importer, and whose decoupling is a function). REOPENS on a
  script in the corpus reusing a unit that is **larger than an
  idiom, identical across its sites rather than a diverged copy,
  and self-contained without transition coupling** — evidence,
  not desire.

- D116 — `rlq wait` IS THE VERB, ON EVERY AXIS — DECIDED (owner,
  2026-08-22) and delivered the same day, striking T31. Supports
  U14; P6, P11. Completes the script-language-identity exception for
  one verb.

  The manifest maps `wait` to `wait_text` as the language's verb
  spelled on the CLI, and cli.md promised the verb's spellings — yet
  the command shipped a different wait on four axes: always a
  regex, across the joined screen, un-normalized, on sight, no
  machine channel; the references said `REGEX`. T31 filed the gate;
  the round found the rest. **The whole verb closes**, because S1
  says the CLI owns no semantics and the Interaction spec says each
  verb is defined once and referenced: the argument is parsed by
  `parse_script("wait <text>")` — the grammar by construction, no
  second condition parser — and lowered to the handle stratum,
  `wait_text` matching one normalized row under the stability gate
  and `Machine.wait_stopped` observing the VM gone, the lifecycle
  marking the phase after, the runtime's own split.

  TWO RULINGS THAT RODE ALONG: **the shell eats the language's
  quotes**, so bare text is the literal spelling and is re-quoted
  with the language's escapes, a `${key}` keeping the language's
  meaning (refused: properties are a script's); and **`wait_stopped`
  is a `Machine` method with no module-level export**, because the
  family table has one face per command and the family's true twins
  are the control-plane design's — REOPENS there.

  WEIGHED AND DECLINED: **gate and expiry only** (T31 as filed) —
  the spec would keep claiming a verb the command was not;
  **screen channel only, the machine channel refused** — one
  spelling left script-only for no reason the spec could state.

- D115 — THE STABILITY RULE BINDS READINESS — DECIDED (owner,
  2026-08-22) and delivered the same day, striking T30. Supports
  U14; P11. Extends D75's rule to the readiness wait.

  `wait_ready` was the one prompt wait in the system that answered
  on sight: `execute` holds a prompt until the screen under it
  settles (F45, D75), the script `wait` verb gates every
  observation by default, and the menu machinery reads twice. T30
  asked whether the rule binds readiness, the hazard being weaker —
  nothing sliced, a caller merely early. **It binds**, because the
  rule is about the screen and not the actor: what the caller does
  next does not change whether the screen was finished, and the
  case that needs it is exactly D113's customized guest, whose
  `AUTOEXEC.BAT` with `ECHO ON` paints the prompt and then the
  command on one row, the standard shape matching in between.

  WEIGHED AND DECLINED: **a lighter "held for one quiescence
  window"** — it is the same gate, `ScreenStability`'s default
  window being that window; no second mechanism exists to build.
  **A finding that the boot does not need it** — stock FreeDOS
  runs `@ECHO OFF`, so a hands-on boot reads fine either way, which
  is why that observation cannot carry the decision. **Tuning on
  the twin** (`stable=`/`stability=`) — `execute` exposes none; the
  axis is the language's. OBSERVED, NOT TAKEN: `rlq wait` /
  `Machine.wait_text` answer on sight while the verb they are the
  face of gates — filed as **T31**, decided by **D116**.

- D114 — READINESS IS A TWIN, NOT THE EMBEDDING-ONLY EXCEPTION —
  DECIDED (owner, 2026-08-22) and delivered the same day, striking
  T29. Supports U14; P6. Sharpens D90 at the adapter.

  `AgentlessGuestExec.wait_ready` had no CLI face, and T29 asked
  whether the twin was owed or the method was the carve-out P6
  tolerates. **The twin is owed**: P6 refuses a capability absent
  from one surface "unless another principle in force forbids it
  crossing", and no principle does — the one standing exception,
  the codex verbs, has P18 behind it and this had nothing. The
  shell's nearest spelling, `rlq wait "C:\>"`, is a weaker wait
  (a pattern, anywhere on screen) and not a respelling, so S1's
  "universal automation path" genuinely lacked the capability.
  `Session.exec` was already this exact veneer over the sibling
  method, so the twin is `rlq wait-ready` ↔ `Session.wait_ready`
  by the identity rule, sharing `exec`'s preflight.

  THE RULING THAT RODE ALONG: the adapter's expiry becomes
  `WaitExpired` (D90) rather than plain `RunFailure` — it is a wait
  and the boot may still arrive; the class subclasses `RunFailure`,
  so no caller's handler changes.

  WEIGHED AND DECLINED: **the carve-out** — it would amend P6 with
  a second named exception resting on no principle, and grow the
  manifest an exception class for a method on a type, which its
  shape does not have because the gap escaped the suite only by
  `AgentlessGuestExec` being classified as a type. REOPENS when an
  agent-backed adapter lands whose readiness is reported rather
  than observed: the twin's `prompt=` is then meaningless on that
  platform and the flag's contract needs restating.

- D113 — READINESS LEARNS A CUSTOMIZED PROMPT FROM THE CALLER —
  DECIDED (owner, 2026-08-22) and delivered the same day, striking
  T28. Supports U14; P10, P11. Completes D112 at the public
  surface.

  `execute` learns a customized prompt from the screen it types
  into (D112); `wait_ready` has no such screen, and it is the
  readiness idiom the README and `docs/dos-automation.md` teach
  before `execute`, so a guest whose `AUTOEXEC.BAT` sets
  `PROMPT [$P]$G` failed the documented idiom at its first line
  (T28). **The caller declares it at the call**:
  `wait_ready(timeout=90, *, prompt=None)`, `prompt` being the
  exact bottom-row text the guest draws, `None` keeping the
  standard shape. That is the script language's own stance — the
  codex `ready` script states its evidence as `wait "C:\>"`, and
  "what ready means is the workflow's own business, never
  reliquary's" — moved to the API: the actor who customized the
  guest says what ready looks like, at the one call that needs
  it. Declared rather than guessed (P10), an exact row rather than
  a pattern (D112's refusal of the wider door), a plain string
  every binding language can carry (api.md's second principle),
  and S2 alone. The expiry names what it waited for.

  THE RESIDUE, STATED: a prompt carrying `$T` or `$D` changes
  every second and equals no text, for `wait_ready` and `execute`
  alike. OBSERVED, NOT TAKEN: `wait_ready` has no CLI twin, which
  api.md's first principle says every public capability has —
  pre-existing, and `exec` never needs it (its precondition is
  "running"); and `wait_ready` confirms no stability under a
  prompt where `execute` does (F45). Filed as **T29** (decided by
  **D114**) and **T30** (decided by **D115**) (owner, 2026-08-22).

  WEIGHED AND DECLINED:

  - **A blueprint field** (`platform-settings.prompt`, S4) —
    heavier, would have the blueprint describe the installed
    system's runtime configuration rather than the machine, and
    D112's no-demand finding for `execute` still stands; the move
    if a second site ever needs the same declaration.
  - **Readiness as stability** — any bottom row once the screen
    stops changing; declined because a boot menu, a "Press any
    key", and a stalled driver are all stable screens, the false
    positive P11 refuses at the moment it is likeliest.
  - **Retiring `wait_ready` for `machine.wait_text`** — declined:
    the protocol seam is right (an agent adapter answers readiness
    by the agent reporting in, not by a screen), and `wait_text`
    matches anywhere on screen with no prompt semantics. It stays
    the general authored wait and the guides now say so.
  - **A regex, fullmatch on the bottom row** — would serve `$T`
    prompts at the cost of the wider door and a Python-flavoured
    value, and would diverge from `execute`'s exact-row rule.

- D112 — A PROMPT IS THE STANDARD SHAPE, OR THE ONE THE GUEST WAS
  AT — DECIDED (owner, 2026-08-22) and delivered the same day.
  Supports U14; P10, P11. Sharpens D75, which made completion need
  evidence this command landed and left "a prompt" as one pattern.

  `exec`'s completion detection recognized one shape, `X:\path>`,
  so a guest whose `AUTOEXEC.BAT` customizes the prompt waited out
  every command's full timeout (issue #9; the transcript corpus's
  custom-prompt capture). Two sources may now say the prompt is
  back, and no third: the **standard DOS shape**, what every
  unconfigured DOS draws and what lets `CD` — which changes the
  prompt's *text* — complete; and **exactly the prompt the guest
  was sitting at** when the command was sent, whatever its shape.
  The second is the guest's own statement of what its prompt looks
  like, an observation rather than an inference from appearance
  (D72), so it needs no pattern and nothing declared, and it is
  what makes a customized guest usable from its first command.

  THE RESIDUE, STATED (P11): a command that changes a customized
  prompt — `PROMPT` itself, or `CD` under `[$P]$G` — returns to
  text neither source has evidence for, and the wait expires
  naming both shapes it waited for, so the reader does not go
  looking at the guest, which ran the command perfectly well. The
  corpus pins it: the `PROMPT [$P]$G` capture keeps recording the
  expiry as a stated limit, and a new capture of `VER` at the
  customized prompt pins the success. `wait_ready` keeps the
  standard shape alone — it has no earlier screen to read a
  customized prompt off. That is a residue on the **public**
  surface, not a dead method: nothing inside `src/` calls it, but
  it is exported from the package root and is the readiness idiom
  the README and `docs/dos-automation.md` teach before `execute`,
  so a guest that boots to a customized prompt fails the
  documented idiom at its first line. Filed as **T28** rather than
  left here (this sentence first called the method uncalled, which
  was true of `src/` and misleading about the surface).

  WEIGHED AND DECLINED:

  - **A declared prompt pattern in the blueprint**, which would
    close the residue and is the P10-clean shape for configuration
    — declined for now as a blueprint surface change (S4) with no
    demand on record: no use case in force names a customized
    prompt, and the only evidence is this corpus finding. It is
    the move if a guest ever demands it, on that demand.
  - **A declared pattern only, refusing every other prompt by
    name** — the issue's "honest and cheap" option; declined
    because it leaves every customized guest unusable without a
    declaration when the guest's own screen already says what its
    prompt is.
  - **A wider pattern** — declined outright: any row ending in `>`
    becomes a completion signal, the false positive P11 refuses.

- D111 — THE ECHO IS WHERE THE PROMPT WAS — DECIDED (owner,
  2026-08-22) and delivered the same day. Supports U14; P10 (as
  D72 sharpened it), P11 (as D75 applied it).

  `exec` located a command's echo by appearance — scanning upward
  from the bottom for "a row ending with the command that carries
  a `>`" — and a file whose last line is the echo of the command
  that types it won that scan: the file's real content was
  discarded and `exec` returned an **empty** result with no error
  (issue #7; the corpus's echo-lookalike capture), the spec
  violation P11 forbids. The run already holds better evidence
  than looks. The command is typed at the prompt the screen ended
  with before it was sent, so the echo is **that prompt row with
  the command appended** (wrapped by the cell when longer than the
  screen is wide, per issue #8), and it sits **where the prompt
  was**: the rows above it are the rows that were above the
  prompt, less whatever scrolled off the top. Everything the
  command prints lands below its echo, so a row that merely spells
  the same text has the command's own output above it and is never
  taken for the echo — and the same command run twice, the first
  echo still on screen, finds the second for the same reason. The
  `>`-in-the-row heuristic goes with the scan direction: the prompt
  is known text now, not a shape.

  THE RESIDUE, STATED: output longer than a screenful whose first
  visible row is such a lookalike is accepted as the echo, nothing
  being left above it to contradict it; it was wrong before as
  well, and it is named in the corpus README rather than hidden.

  WEIGHED AND DECLINED:

  - **Remembering the row the live wait first saw the echo on**
    (issue #7's own hint) — declined because it depends on the
    poll catching the echo before fast output scrolls it, where
    the screen read before typing is always there and places the
    echo exactly.
  - **Scanning top-down by appearance** — declined: it finds the
    first row that looks right, and the same command run twice
    then returns the previous run's output with the new echo
    inside it. The rows-above test is the rule; the scan order is
    incidental.

- D110 — GUI AUTOMATION'S DEMAND IS U5; F63 IS CUT OUT AND F5
  KEEPS ITS NUMBER — DECIDED (owner, 2026-08-21). Supports U5.
  The pledges of U5 and F63 are lifecycle acts and are not
  recorded here (D63); this is what was adjudicated in their
  course — the adjudication F5's banner had left open since the
  2026-07-27 sweep.

  THE DEMAND. U5's customized-installation remainder underwrites
  the GUI half of the era: a localized installer is a different
  installer showing different text — on a graphical setup,
  different pixels — which is exactly what the plane, pointer
  input, and landmarks exist to drive. WEIGHED AND DECLINED:
  reading U10's "the screen is the assertion surface" as reaching
  graphical installs — U10 is agentless install-testing, pledged
  after the banner was written, and stretching it would be the
  citation-written-to-fit the banner warns against; it reopens
  only if a GUI install-test scenario arrives as its own demand.
  ALSO DECLINED: pledging U6 alongside — it commits the whole
  recorder (F1) for a plane U5 already demands.

  THE CUT. F63 (the VNC control plane on QEMU, screen and
  keyboard) is cut out and pledged; **F5 keeps its number and the
  remainder**, the U5/U21 shape (D64) rather than the F3 full
  split — a full split spends a fresh number per piece, and only
  one piece is being pledged, so renumbering work that stays
  proposed would spend the sequence on nothing. The full split
  still happens where it belongs: piece by piece, at each later
  pledge.

  THE DESIGN CALLS made in the same round, kept here with their
  rejected alternatives now that the delivery swept the design
  document that first carried them (the norm is
  docs/spec/blueprint-model.md; the mechanism is
  `src/reliquary/rfb.py` and the QEMU adapter):

  - **An in-tree minimal RFB client, no new dependency.** The
    subset is pinned because Reliquary launches the server it
    connects to: the 3.8 handshake, security None, forced 32bpp
    true colour, Raw-only updates, `KeyEvent` — no `PointerEvent`
    until the pointer feature pledges. WEIGHED AND DECLINED:
    `vncdotool` (drags in Twisted for a subset we control both
    ends of) and `asyncvnc` (an asyncio surface and a thin
    ecosystem for the same subset).
  - **Loopback, no VNC auth**, identity staying QMP's job with
    `query-vnc` cross-checking the recorded endpoint. WEIGHED AND
    DECLINED: a per-start password via `set_password` — VNC auth
    is single-DES, security theater on loopback, and the threat it
    would answer (another local process racing the port) is what
    the identity verification detects; one more secret with
    custody rules for no gain.
  - **The declared `control-planes` list is an ordered
    preference**: requirement semantics unchanged, the first entry
    driving the session's carriers, the default unmoved. WEIGHED
    AND DECLINED: refusing more than one declared plane until a
    readiness waterfall exists — a vocabulary restriction that
    would take a second surface change to lift, for no protection
    the capability check does not already give.

- D109 — THE GUEST'S OWN FONT IS AN AUTHORED ASSET, AND ITS BYTES
  CROSS ON A DRIVE — DECIDED (owner, 2026-08-19, the U25 pledge
  round). Supports **U25** and **U27**; P10, P12, P14, P16, S3, S8.
  Adopts
  [design/authored-binary-assets.md](design/authored-binary-assets.md)'s
  shape for its second kind, which is the proposal that document
  said each adopting kind still owes. Bounded by **D108**, whose
  file-content carve-out it applies rather than reopens.

  Four calls, and the draft named the two it left open: what a
  font's declaration states, and how the bytes leave the guest.
  Both are answered here, because the journey lands with the pledge
  and a journey names commands.

  **The demand is two use cases, not one with two doors.** U25 as
  drafted named a font *taken from the guest* and a font *the author
  supplies*, deliberately, because neither door covers what the
  other does: asking needs a prompt, and an installer paints before
  any prompt exists in that boot. But a journey states one path —
  the fewest steps that reach the goal, options belonging to a guide
  — so the second door became **U27**, a goal someone pursues in its
  own right rather than a branch inside U25's steps. Neither half
  changed in substance, and **F61 delivers both**; only the dump
  (F62) is U25's alone. This is the U24/U26 shape, one round later
  and for the same reason.

  **The bytes cross on a drive the author supplied.** A
  directory-source media attaches a host directory, the guest writes
  `FONT.BIN` into it, and the author reads it off their own disk —
  exactly what D108 settled for a file crossing the boundary, and it
  costs no new mechanism at all. Two prices are accepted and named
  rather than argued away: directory-source drives are QEMU-only, so
  the *dump* is bound to QEMU while the asset it produces is
  portable to every backend; and the file lands once the machine
  stops, which an authoring act performed once per guest font can
  afford.

  WEIGHED AND DECLINED: **a UART pointed at a host file.** It is the
  better transport on the merits — portable across both reference
  backends, raw bytes, no filesystem tooling — and it is declined
  for what it drags in rather than for what it does. `serial-console`
  sits in the control-plane vocabulary (`document.py`) with nothing
  behind it; a declared serial device is new blueprint surface plus
  endpoint lifecycle, a feature of its own, and a write-only file
  sink bolted on for one authoring act would settle the serial
  plane's shape sideways, before the plane is argued. Also declined:
  **an image swapped live and opened with the author's own tools** —
  portable and equally mechanism-free, but getting 4096 bytes out of
  a FAT image is a step the journey cannot state as one command.

  WHAT WOULD REOPEN IT: the serial plane being designed for its own
  reasons, or a directory-source drive reaching a second backend.
  Either makes the dump portable, and the QEMU bound above is the
  only thing this call is paying.

  **A script names the font with `font @name`, a statement stating a
  prefix.** From that point in the run forward the fonts named are
  tried first and the host's follow; a second `font` replaces the
  prefix rather than appending. It is a new action kind in an
  existing node shape, which is what G7 prices cheaply.

  WEIGHED AND DECLINED: **a `with font @name { … }` head.** The
  scoped block is the obvious neighbour, and it is wrong on the
  construct's own terms: the head vocabulary is closed at three
  names, every one of them a durable machine change the scope exists
  to *undo* (D104), and a font changes nothing on the machine, so
  there is nothing to put back and no reason for the block. Also
  declined: **a header declaration.** Cheapest of the three and
  statically obvious, and it cannot express the finding the case
  rests on — the painting authority changes mid-boot, the firmware
  paints the earlier screens in a different face, and only the
  script knows when.

  **The declaration states the codepage, and the match order becomes
  a priority.** Beyond the cell size — 256 glyphs of 16 rows and 512
  of 8 being the same 4096 bytes, so geometry is declared and never
  inferred (P10) — a bank declares what its indices *mean*, and a
  cell matched in an authored bank decodes through it. The host's
  own banks keep today's mapping, so nothing already recorded moves.
  The two halves are one call: the recognizer currently unions every
  bank's shapes and takes the globally nearest, with order breaking
  ties alone, and under that rule "the bank that matched" names
  nothing and a named font could only *add* a chance for a
  near-match to beat the true glyph. First-bank-inside-the-threshold
  is what makes both the narrowing and the decode mean anything.

  WEIGHED AND DECLINED: **cell size alone**, leaving matched codes
  with today's meanings. Materially smaller — nothing in the text
  pipeline, the transcripts, or the fixtures moves — but it meets
  the case only for a guest whose face differs while its code points
  do not, and "a prepared codepage, a localized installer" is the
  case's own example: the glyph would be found and the wait would
  still miss.

- D108 — A MACHINE'S FILE CONTENT LEAVES RELIQUARY, AND THE VOLUME
  MAPPING GOES WITH IT — DECIDED (owner, 2026-08-16). Supports
  U14, U20; P16, P18. Amends **U14** and **P16**, strikes **P17**
  and **P27**, and withdraws **F41**.

  Reliquary declares a machine's drives, materializes them and
  moves their media; it does not read or write what is inside one,
  and it maps no volume to a guest drive letter. A consumer needing
  a file across the boundary supplies the drive and moves the file
  itself — a directory-source media attaching a host directory, an
  image swapped live with `insert-media --file`, or the machine
  directory D5's out-of-band door already hands back, opened with
  the consumer's own tools. **Remanence is the tool named**, and it
  leaves the runtime closure with the layer that wrapped it: a
  consumer uses it directly rather than through Reliquary.

  WEIGHED AND DECLINED: **keeping the directory-source half of the
  file family**, which needs no at-rest access at all. It would
  have kept the drive-letter map alive to address it — the volume
  mapping this decision removes — so half the family costs nearly
  the whole mechanism, and the surviving half would be QEMU-only.
  Also declined: **a narrowed `describe-drives`** reporting the
  declared and chosen facts alone. `list-machines --json` already
  carries them, and a report shaped by what was deleted is a
  remnant rather than a stated need; a per-machine inspection
  command is argued on its own merits or not at all.

  WHAT WOULD REOPEN IT: a use case that cannot be completed with
  values, declared drives and live media swap. **F15 is the
  pressure point** — it now answers with a drive key rather than a
  guest letter, and a demand for the letter back is a demand for
  the mapping back.


- D106 — THE SUITE IS PYTEST-NATIVE — DECIDED (owner, 2026-08-13).
  Supports **P11**'s reading, as D95 read it across: a check that
  silently does not run is a capability gap failing open. Amends
  AGENTS.md's stdlib-`unittest` preference, whose normative text
  lands with the migration.

  **The dependency was never the argument, and it was the one being
  made.** AGENTS.md already holds that a test-only dependency is a
  hard requirement of the suite — `jsonschema` is one — so a count
  settles nothing. What settles it is the failure that very rule was
  written for: the conformance corpus ran against the parser and
  *not* the schema while claiming the two cannot drift, and 135
  fixtures across two checks inside `subTest` is a run whose halved
  form looks exactly like its whole one. Parametrised, every fixture
  is a collected node and the count is the assertion. The opt-in
  integration tier is the same shape — a marker states a deliberate
  tier where `skipUnless` states an accident, which is why that tier
  needs an exact skip count asserted around it today.

  WEIGHED AND DECLINED: **pytest as the runner only**, keeping the
  `TestCase` classes. It is nearly free and keeps `python -m unittest
  tests` working for anyone unpacking the sdist — and buys none of
  the above, the corpus staying inside `subTest` and the tier staying
  a skip, which are the two things the change is for. WEIGHED AND
  DECLINED: **staying on unittest**, the same position with the
  dependency saved.

  Two costs taken deliberately. `python -m unittest tests` stops
  working, so verifying an unpacked sdist needs the dev group — in
  the same round as **D105**, which is what put the suite in the
  sdist — taken because pytest is packaged everywhere a packager
  works. And **plugin autoload is turned off in the project's own
  configuration** rather than left to whoever runs it: a suite
  shipped to strangers must not collect differently in their
  environment than in this one.

  Reopens on nothing here. The stdlib preference stands everywhere
  else: this is one dependency judged compelling, not the bar
  lowered.

- D105 — THE SDIST CARRIES THE SUITE, NOT THE GOVERNANCE — DECIDED
  (owner, 2026-08-13). Supports **P11**'s reading: a claim nobody can
  check is not a claim. Amends **D96**, whose `planning/` half stands
  and whose wheel half is untouched.

  **D96 read the ecosystem as neutral on the sdist, and it is not.**
  An sdist is conventionally the artifact a stranger can build *and
  verify* from, and downstream packagers run the upstream suite at
  package-build time — the convention runs the other way from the
  entry that dropped it, which weighed the wheel's settled rule and
  the file count without weighing that. And the count argued
  `planning/`, not the suite: 187 of 280 files was governance and
  fixtures counted together, and governance alone is what has no
  business in a stranger's hands.

  WEIGHED AND DECLINED: leaving the suite out and resting on `uv
  build`'s completeness gate, which was D96's answer to what shipping
  it bought. The gate is kept, and is still how a source archive's
  completeness is proved — it simply never argued for *withholding*
  the suite, only that nothing was lost by doing so. What was lost is
  the packager's run, on a platform this project never tests.

  WEIGHED AND DECLINED: **moving the script-example catalogue to
  `docs/`** so the documented-example tests could still read it —
  taken at first on the reading that a corpus the code is checked
  against is a norm, and abandoned on reading the catalogue, which
  holds *unresolved* design problems and deletes them on resolution.
  That is governance, and shipping it is what this entry's other half
  refuses. **The test moved instead**, to `tests/source_tree/`, which
  ships nowhere: a test that reads what no artifact carries should be
  unable to run outside the repository rather than guarded into a
  quiet pass. The rule that leaves is AGENTS.md's, where it governs
  every such test rather than this one catalogue.

  Reopens if the suite acquires a requirement a packager cannot
  reasonably meet. **D106**'s pytest is not one.

- D104 — A SCOPED MACHINE-STATE CHANGE IS A BLOCK, AND ITS RESTORE
  OBEYS THE STOPPED-ONLY RULE — DECIDED (owner, 2026-08-13, the U24
  pledge round). Supports **U24** and **U26**; P14, S3. Bounded by
  **D15**'s Q1, which it does not reopen.

  **The demand is two use cases, not one with a failure clause.**
  U24 as drafted carried the run-ends-as-it-began guarantee inside
  its own path, which the happy-path rule forbids: a use case is one
  simple path, and a deviation is never a clause in one. Of that
  rule's two homes the guarantee went to a **use case of its own**
  (U26), not to a principle. WEIGHED AND DECLINED: P28. The rule
  genuinely holds on every outcome and every surface — the revert
  after a *successful* run is the same rule running where nobody
  looks — but the half a user meets is a goal they pursue, and a
  principle would have stated the mechanism when what was missing
  was the demand. Neither half changed in substance, and F54
  delivers both.

  Two contested calls, both made against the recommendation, and the
  arguments they beat are recorded because each was strong enough to
  be raised again.

  **The spelling is a `with` block** wrapping phases in a phased
  script and statements in a linear one, its head one of `insert` /
  `eject` / `set-boot` written as it is written today. WEIGHED AND
  DECLINED: a **`scope=run` modifier** on those three verbs, which
  costs P14 nothing at all — a `key=value` modifier is the shape
  `exclude=` and `stability=` already have, so no construct is added
  and V2/V14 carry it with no new id. It was declined because it can
  only ever scope to the *run*, and the thing U24 names is a stage;
  a mechanism that cannot express the unit the demand is written in
  is cheap for the wrong reason. Also declined: a **header
  declaration** (`boot cdrom0 hdd0`), which covers the boot order
  alone — leaving media, half of U24's class, needing a second
  mechanism — and puts durable-state policy in the one place
  script-spec.md deliberately keeps it out of.

  **The scoped boot head is `boot` and states a prefix**, not
  `set-boot` and not a whole order: what a stage has to say is
  "boot the CD first", and an author should not restate an order
  they are not changing (owner, same day). The drives named come
  first in the order given and the machine's own order follows.
  WEIGHED AND DECLINED: reusing `set-boot` as the head. That verb
  *replaces* the order, so the scoped form would carry different
  semantics under an identical spelling — the one thing a closed
  grammar cannot afford, since a reader has no way to tell which
  meaning is in front of them. A distinct word costs one name in a
  vocabulary that has room for it, and `set-boot` keeps its
  meaning unchanged.

  WEIGHED AND DECLINED, having been raised and withdrawn in the
  same round: **promoting a whole drive kind**, so that one word
  moved every CD-ROM at once. The head takes slot keys, and a
  machine with two optical drives names both. It was withdrawn as
  more than the demand needs, and the collision it would have had
  to route around is worth recording — a bare `cdrom` is already
  the blueprint's alias for `cdrom0`, so the kind could not have
  taken the obvious spelling, and every remaining one bought a
  third way to say a drive.

  **The scope is dynamic, not lexical**: it holds while control is
  inside the group, whichever way control arrived. A lexical reading
  was declined on mechanics rather than taste — every phase body ends
  in a transition, so a scope that closed at the end of its text
  would revert at the first `goto` and express nothing an install
  could use.

  **A boot restore requires a stopped machine**, and an exit reached
  with the machine running fails the run naming what it could not
  undo. WEIGHED AND DECLINED: letting the runtime's own restore write
  the state document behind a running machine, on the argument that a
  restore claims no live effect and only sets what the next start
  reads. Declined because D15's Q1 made the boot order stopped-only
  as a property of the machine rather than as a courtesy to the
  author, and a second writer operating under a different rule is
  exactly how such a guarantee erodes — the next exception argues
  from this one. The accepted cost is real and named: a run that
  otherwise succeeded can fail at its last act, and the remedy for an
  author handing back a live machine is to say so in the script's own
  shape. **T27 defangs most of it** by moving the same verdict to
  parse time, which is why F54 depends on that analysis.

  **What reopens the restore rule** is D15's Q1 itself: if the boot
  order ever gains a live effect, or the stopped-only guard is
  revisited for its own reasons, this clause is decided again with
  it and not before.

- D103 — THE ADAPTER SEAM'S KEY VOCABULARY IS QEMU'S QCODE SET —
  DECIDED (owner, 2026-08-13). Supports P11. Leaves P25 untouched:
  that governs the blueprint's portable vocabulary, and the script
  language's `press` names stay portable.

  **The seam was already QEMU's and said it was portable.** Three
  docstrings and the seam's own design note claimed the vocabulary
  crossing it was a portable set QEMU happened to match. It was
  not: `control_display._PLAIN` emits `spc` and `ret`,
  `script_runner.resolve_key` translates the language's names into
  QEMU's above the seam, and the VirtualBox adapter's scancode
  table is keyed by `ret`, `spc`, `pgup` and `pgdn` with no entry
  for `enter` or `space`. **That table is the evidence**: the one
  adapter the contract was written for was built against what
  arrives rather than what was declared, so the claim had already
  failed its only test.

  WEIGHED AND DECLINED: making the seam genuinely portable —
  respelling the control plane's tables, moving the QEMU map into
  its adapter, rekeying VirtualBox. It needs a vocabulary that does
  not exist: `PORTABLE_KEY_NAMES` covers 31 named keys while the
  seam also carries punctuation, letters and digits, so the honest
  version invents a third naming scheme no backend speaks natively,
  for no behavioural gain on either backend. Naming the seam after
  the reference backend is the cost paid instead, and it is paid
  once.

  REOPENS on a backend whose input API cannot express a qcode name,
  or a second adapter author who needs spellings this set does not
  reach — at which point the third vocabulary earns its keep and
  this is the entry to overrule.

- D102 — BLUEPRINTS USE JSON5, NOT JSONC — DECIDED (owner,
  2026-08-05). Supports U4, U5; G2. Amends D18's input-format
  choice; its computational-growth rule remains in force.

  **JSON5 is the authored blueprint grammar.** JSONC is an ecosystem
  label rather than one settled grammar: even its draft specification
  makes trailing-comma support optional, while Reliquary's former
  wording had to define a project-specific dialect. A published JSON5
  grammar gives authors and independent tooling one external contract
  to implement. The parser still rejects `NaN` and both infinities:
  blueprint values remain ordinary JSON data after parsing.

  WEIGHED AND DECLINED: retaining the narrow JSONC dialect for editor
  familiarity. That remains a useful configuration-file convention,
  but it does not outweigh a specified grammar for Reliquary's own
  authored format. Reopens only on evidence that the required editor
  and schema workflow cannot support JSON5 without a material loss of
  the authoring experience.

- D101 — THE SCRIPTS MAP IS THE BLUEPRINT'S, READ AT INVOCATION —
  DECIDED (owner, 2026-08-02). Supports U1, U14; P6, P11.

  A label map names which instructions to run, not what a machine
  is, so it sits outside the shape baseline beside `parameters`
  rather than inside it: read from the blueprint at each invocation,
  absent from machine state and from the digest. The normative home
  is [instance-model.md](../docs/spec/instance-model.md); what is
  recorded here is the contested call, because the code had drifted
  the other way and a reader could reasonably take the drift for
  intent — cli.md already resolved a label against "the blueprint's
  `scripts` map", and U5's parameters design was written on the
  premise that the scripts map was read at invocation.

  WEIGHED AND DECLINED: making `parameters` read from state instead,
  which buys symmetry by breaking the half that was right — a
  parameter edit would then need an `apply` to reach the run that
  binds it. Reopens only if a machine is shown to need its label map
  pinned against blueprint edits, which is the shape argument this
  call says does not apply to it.

- D100 — F12 AND F44 ARE REJECTED OUTRIGHT — DECIDED (owner,
  2026-08-02). Supports P8. Retires both numbers (D23, no stub).

  Neither backend earns its cost. **F44** (`replay`) offered cheap
  hypervisor-free reruns, which hold only while neither the script
  nor the guest behaviour changes; what survives that caveat is
  catching reliquary's own interpretation-layer regressions against
  a frozen capture, and that is F43's job already. **F12**
  (`simulator`) names one real pain — consumers monkeypatching
  `start_machine`/`stop_machine`/`exec` — but its own decide-first
  left the feature undesigned (what shape a guest-output responder
  takes under P6 and P7), a cost disproportionate to a convenience
  for test authors.

  WEIGHED AND DECLINED: leaving both parked in `proposed/`. That
  shelf holds live arguments waiting on demand, not settled maybes.
  Either capability reopens by winning its own argument from
  scratch, never by reviving these.

- D99 — A DEMAND DRAFTED TO SATISFY THE GATE IS NOT A DEMAND —
  DECIDED (owner, 2026-08-02). Supports P8.

  P8 requires demand before a feature so that features answer needs,
  rather than needs being reverse-engineered from features someone
  already wanted. Drafting a use case *in order to* clear the
  citation requirement inverts the rule while appearing to satisfy
  it: the gate reads as passed, and the thing it exists to prevent
  happens one level removed. A drafted use case earns its number by
  describing a need that exists independent of whatever cites it.
  Found when F44's pledge round drafted U23 for exactly that reason
  — F44 withdrew, U23 struck, its number spent (D23, no stub).

  WEIGHED AND DECLINED: narrowing U23 to F12's monkeypatch thread
  instead of striking it. That thread is real but is F12's alone,
  and a use case kept alive to justify a feature nobody had argued
  for repeats the error in smaller print.

- D98 — A CAPTURE IS NOT A RUN RECORD, AND ITS FORMAT IS NOT A
  SURFACE — DECIDED (owner, 2026-08-01, the F13 pledge round).
  Supports P22; **bounds D36**.

  **The contested call is whether D36 reaches this.** D36 deleted
  persisted run output outright — `run-events.jsonl`,
  `transcript.txt`, the `runs/` archive — and S7 now states the
  contract as "a run drives the machine and returns its output to
  whoever started it, storing nothing." F42's `--record <path>`
  writes screens to disk, which looks like exactly that refusal.
  It is not: what D36 refused was **persistence as async's
  substrate**, a record written so another process could follow a
  run, and it refused it for want of demand. A capture is written
  only where a maintainer names a path, is read by nothing at
  runtime, and answers a demand D36 never weighed — P22's gate over
  a heuristic layer that cannot be tested on fabricated input. D36
  stands untouched for every run that does not ask.

  **The transcript format is deliberately not an application
  surface**, and that refusal is recorded because it leaves no other
  trace: a reader who finds `.rlqt` files and goes looking for the
  `docs/spec/` entry should learn here that none was ever written.
  No norm, no stability guarantee, no compatibility obligation — a
  change to it is housekeeping, not a surface change. What *is*
  surface is the invocation alone (S1 and S2, landing together under
  P6). The rejected alternative was a maintainer-only
  `RELIQUARY_RECORD` environment hatch, which would have left D36
  and S7 untouched by leaving the capability ungoverned — an
  undocumented spelling behaving like surface without being weighed
  as any, in a project whose other `RELIQUARY_*` variables are all
  specified.

  **What reopens it is F44**: the moment a caller runs flows off a
  transcript, the format becomes something the world depends on, and
  it takes the vetting rule and a `docs/spec/` norm with it. That is
  the whole of what F44 defers, and why the format's standing is
  stated now rather than discovered then.

- D97 — THE LIST FAMILY SHOWS ITS DESCRIPTIONS; THE DROP EXIT IS
  DECLINED — DECIDED (owner, 2026-08-01). Supports U11; P6, P11.
  Resolves the deferral D88 parked as T8.

  T8 offered two exits: specify the human display, or drop
  `description` from every surface, `--json` included. Dropping is
  **declined while U11 stands** — "read a description" is a
  use-case clause in force, so that exit is an amendment of the
  use-case list dressed as a display cleanup, and it reopens only
  by winning that amendment first. The display settled: **an
  indented, wrapped description line beneath each entry**, never a
  column — a fixed-width column of unbounded free text is exactly
  what D88 refused, and truncation loses the words being read
  for — applied as a uniform rule wherever a listing's noun
  carries a description (`list-codex`, both `list-scripts` forms,
  `list-blueprints`), with `list-blueprints`' record gaining
  `description` and `platform` so `--json` carries what the human
  view shows (P6). A `describe-*` detail verb was weighed and
  declined: full text at one command per entry read is the wrong
  ergonomics for scanning a library, and a new command family
  needs a demand a wrapped line already meets. The normative
  wording lands in docs/spec/cli.md with the implementation that
  strikes T8.

- D96 — RELEASED ARTIFACTS CARRY NO TESTS — DECIDED (owner,
  2026-07-30). [Its sdist half is overruled by **D105**: the suite
  ships in the sdist again, and only the wheel and the `planning/`
  clauses below still govern.] Supports P21's instinct applied to
  what is shipped rather than what is depended on. The wheel already
  excluded the suite; the sdist grafted it deliberately, and **that
  half was never adjudicated** — it accreted through `MANIFEST.in`,
  and AGENTS.md and `check_dist.py` then described it as settled,
  `check_dist` going as far as to *require* it. Two-thirds of the
  source distribution was tests: 187 of 280 files.

  [Overruled by D105.] **The contested call is what replaces the
  sdist gate.** Shipping
  the suite bought one real thing — "unpack the sdist outside the
  tree and run the suite there," the check that the source package
  was complete — and dropping it has to answer for that. It is
  answered structurally rather than replaced: `uv build` builds the
  wheel *from* the sdist, so an archive missing anything the build
  needs fails at build time. The gate was never the tests passing;
  it was the archive being complete, and the build proves that
  without shipping 187 files to do it.

  `PLANNING/DESIGN` WAS THE TELL (owner: "'planning' docs in
  published test package is a solution to a problem, it's part of a
  problem"). It was grafted so the suite could parse the
  script-example catalogue out of an unpacked sdist — maintainer
  governance shipped to a stranger to serve a test run nobody
  performs. It goes with the suite, and `check_dist` now **forbids**
  both trees in both artifacts rather than requiring them in one.
  [D105 keeps the `planning/` half of that and drops the other: the
  suite is required in the sdist and forbidden in the wheel.]
  `docs/` stays: documentation in a source package is conventional
  and is not a test.

  Effective from the next release. **The 0.1.0.dev6 sdist on PyPI
  carries the tests** and cannot be changed — a version is immutable
  once published — so the record should not read as though this were
  retroactive.

- D95 — THE SUPPORTED FLOOR IS 3.12, AND IT IS DROPPED RATHER THAN
  FIXED — DECIDED (owner, 2026-07-30). Supports P11's reading, which
  AGENTS.md already applies to host platforms: an untested version is
  an unclaimed capability, not a quiet promise. `>=3.9` was published
  and had never been run; the first run failed on **3.9 and 3.10**
  (`keyring` reaches `platform.win32_ver()`, which shells out on those
  versions and trips the suite's own no-subprocess guard) and on
  **3.11** (39 errors: a `MappingProxyType` dataclass default, which
  3.11 rejects as unhashable). 3.12, 3.13 and 3.14 pass.
  **Fixing rather than dropping was WEIGHED AND DECLINED** (owner:
  "if there is *any* doubt, just drop"): 3.11 needs a `default_factory`
  and 3.9/3.10 need the guard taught about `platform`'s internals,
  both cheap, neither worth a support claim nothing was asking for.
  Reopen by fixing those two and lowering the floor — the floor run in
  AGENTS.md "Required checks" is what would keep it honest.

- D94 — TWINE GOES WITH THE UV ADOPTION — DECIDED (owner,
  2026-07-30). Supports P21, which binds infrastructure as well as
  packages. The adoption itself needs no entry: uv owning the
  environment and the release path is stated in AGENTS.md
  "Development environment" and "Required checks", and the commit is
  its record. **What earns this entry is one contested call.**
  Keeping twine for `twine check` was weighed and declined: its
  rendering job is an RST problem and `readme` is `README.md`, where
  CommonMark has essentially no failing input; the index validates and
  **rejects** bad metadata itself; a rejected upload does not consume
  the version, so the cost of learning at upload is a retry; and
  `tools/check_dist.py` remains the project's real artifact gate.
  A pre-flight duplicate of a server-side check, against a format that
  does not fail, is what P21 refuses. **Reopen if the readme stops
  being markdown** — an RST description puts `twine check`'s original
  purpose back in force. Poetry, PDM and Hatch were declined in
  passing: each gives the lock, none gives interpreter provisioning,
  and Poetry wants its own `pyproject.toml` dialect where this project
  already writes PEP 621 and PEP 735.

- D93 — FIRST-CLASS BLUEPRINT VOCABULARY REQUIRES GENERAL
  APPLICABILITY ACROSS BACKENDS — DECIDED (owner, 2026-07-30),
  overruling **D91** the day it was delivered and removing its
  devices axis. Supports P8; adds **P25**.

  THE BAR: a device or adapter name becomes a first-class field
  only where it applies across multiple backends. What one backend
  alone provides stays behind that backend's pin in
  `backend-settings` — reachable, at the price of portability, and
  that price is the pressure that grows the vocabulary one name at
  a time. Seeding `virtio-console` and `virtio-net` was declined on
  the same bar: a vocabulary admitted because one backend exposes
  it is a vocabulary that records the wrong fact.

- D92 — THE HATCH IS HONORED, THE RENDERER IS THE VALIDATOR, AND A
  LONE SECTION NARROWS — DECIDED (owner, 2026-07-30) and delivered
  the same day, retiring F28. Supports U22; P10, P11.
  `backend-settings` is normative in the blueprint field reference
  and AGENTS.md.

  Three rulings with no other home:

  - **The renderer *is* the validator.** `settings_args` both
    validates and renders, which is what makes a section a create
    accepted one a start applies — two code paths would drift.
  - **A lone section narrows the backend walk**, but by *presence*
    and never by content: declaring settings for one backend pins
    assignment to it without the settings themselves being read as
    requirements.
  - **Only the assigned backend's section is judged.** No adapter
    can speak for another's vocabulary, so an unknown key is
    refused only where an adapter owns the section.

- D90 — A RUN'S OUTCOME IS A POSTCONDITION, A WAIT IS A POLL, AND
  AN EXPIRED WAIT IS BOTH A FAILURE AND A TIMEOUT — DECIDED
  (owner, 2026-07-30) and delivered the same day, retiring F30.
  Supports U14; P11.

  The three are one ruling about **what a word promises**. An
  outcome describes the state the run left behind, not the path it
  took; a wait is a poll and never a subscription, so it reports
  what it saw when it looked; and an expired wait is *both*
  classifications at once rather than being forced into one — a
  taxonomy that made a caller choose would lose the half it did not
  pick, which is the reporting failure P11 refuses.

- D89 — THE OUTCOME PROBE IS RELIQUARY'S OWN TEXT, AND ITS SCOPE
  IS STATED — DECIDED (owner, 2026-07-30) and delivered the same
  day, retiring F26. Supports U14, U22; P6, P10, P11, G2.

  `--check` asks the guest whether a command signalled failure, and
  both halves of the answer are **text reliquary composed and read
  back** — the sentinel is a word reliquary said, not one the
  command did. That is what keeps the feature inside G2 and P18: no
  meaning is read into guest output.

  **Its limit is stated rather than papered over** (P11): a
  mistyped command leaves ERRORLEVEL untouched and so reads as
  success. Recognizing the shell's own "Bad command or file name"
  would mean curating guest output spellings, which a localized DOS
  makes unbounded — the guessing P10 refuses.

- D88 — AUTOSEED IS DELETED; U1 IS TWO COMMANDS AND P4 IS
  ABSOLUTE AGAIN — DECIDED (owner, 2026-07-30). Supports P4, P18,
  U11. **Supersedes U1's text** (reshaped in place under its own
  number, as D61 did), **clarifies U11**, and **amends D59** by
  retiring its seeding axis.

  Nothing resolves out of the codex, on either surface and under no
  flag: the directories are the sole sources, a miss fails closed,
  and the refusal names `rlq seed-blueprint <name>` where the
  library holds it. The rule's home is **P4** and AGENTS.md.

  - **A no-new-knob alternative** that reproduced both former modes
    and kept P4 absolute — declined for making seeding a silent
    consequence of resolution. A knob that can be turned on is one
    CI turns on, and a silently supplied blueprint is a bug that
    surfaces on someone else's machine.
  - **"A codex blueprint is read where it lies rather than copied
    out"** goes with it: with no fallback there is nothing to read,
    and an unseeded name is refused rather than resolved.

- D87 — THE CODEX IS NOT AN API BINDING; P6 GAINS ITS FIRST NAMED
  EXCEPTION — DECIDED (owner, 2026-07-30). Supports P4, P18, U11;
  **amends P6**.

  The codex verbs — `seed-blueprint`, `seed-script`, `list-codex` —
  are **CLI-only**, and the exception is named in
  [api.md](../docs/spec/api.md) rather than left as an omission a
  reader might take for an oversight. WHY: a library that changes
  in a point release is not something a program may bind against,
  so exporting the verbs would invite exactly the programmatic
  dependence the codex refuses to promise. Naming the exception is
  what keeps P6 a rule with one hole rather than a rule with
  unrecorded slack.

- D86 — TASKS ARE ITEMIZED; A T-NUMBER EVAPORATES, AND THE
  SEQUENCE STATES ITS OWN HIGH-WATER MARK — DECIDED (owner,
  2026-07-29). Supports P23. Applies D42's handle rule to tasks.

  - **Reuse** (lowest-free, the way machine ids are allocated) —
    declined: an id that names one thing at a time is fine for a
    machine and useless for a citation, where a struck task's
    number appearing again makes the record ambiguous.
  - The sequence **starts at T8** because T0–T7 were spent by an
    earlier per-list numbering that ran three times; beginning
    above them is what keeps every T-number in the record resolving
    to exactly one thing.

- D85 — THE WORLD-FACING BOUNDARIES ARE THE **APPLICATION
  SURFACES**, ITEMIZED S1–S8 — DECIDED (owner, 2026-07-29).
  Supports P8, P23, P24. Normative in root
  [ARCHITECTURE.md](../ARCHITECTURE.md).

  Renaming "interfaces" to **application surfaces** and itemizing
  them S1–S8 turns the housekeeping surface test from a *judgement*
  into a **lookup**: a contributor asks whether the change touches
  a numbered item, not whether it feels world-facing. A test that
  needs judgement is a test that gets skipped by whoever is in a
  hurry, which is precisely the population housekeeping serves.

- D84 — THE SCRIPT-VALIDATION RULES MOVE OFF S: S1–S14 BECOME
  V1–V14 — DECIDED (owner, 2026-07-29). Supports (none): a rule
  id's letter is a vocabulary choice that no use case or principle
  demands. Recorded because **D85 needed the letter** and because
  the ids are world-facing, so the change is a break rather than a
  tidy-up.

  WHY THE RULES MOVED RATHER THAN THE SURFACES. D85 gives the
  application surfaces the letter **S**, and S was taken: the
  `.rlqs` static rules had held it since the dotted ids landed
  (D55). Two live S-sequences was the one option refused outright —
  `S6` would have named both the reference-check rule and the run's
  returned output, with *this file* citing both — because that is
  exactly the ambiguity the never-reuse discipline exists to
  prevent. Of the two, the rules moved: the surfaces are the outer
  boundary a governance lookup resolves against, while a validation
  rule is language-internal.

  V FOR VALIDATION, AND THE NUMBERS DO NOT MOVE. V1–V14 map one for
  one onto S1–S14 — the letter changes, the number never does — so
  every historical citation decodes mechanically (S6 is V6) and no
  renumbering has to be looked up. The **S15 retired by D5** (the
  `results` header, dropped with `stage`/`collect`) stays retired
  and no V15 is ever issued, so a search for either still resolves
  to one thing.

  WHAT IT COST, ITEMIZED. Around 230 live references: the
  diagnostic-id map in `script_nodes.py`, the rule citations in
  `script_validation.py`, `script_parser.py`, `binding.py`,
  `facts.py` and the grammar's comments, the normative rule list in
  script-spec.md, 41 conformance fixtures (the `# rule:` header
  *and* the filename prefix), four harness regexes, and the two
  corpus READMEs. **The ids are world-facing** — a diagnostic cites
  its rule and the corpus asserts on the id — so this is a clean
  pre-1.0 break under P9: no alias, no dual spelling, every
  reference moved in the one change and the suite green (1110
  tests, the one sanctioned skip).

  A THIRD MEANING FOUND IN PASSING, AND SPELLED OUT INSTEAD. The
  blueprint corpus README's `S2`/`S3` are **milestone stages** —
  vocabulary dead since D33 — not rule ids, and they were rewritten
  in words ("the second stage") rather than renumbered: left alone
  they would have read as application surfaces the moment D85
  landed. Caught by auditing the pattern's matches before running
  it, which is the reason to audit.

  FOLDED: this entry and the preamble's decoder;
  normative [script-spec.md](../docs/spec/script-spec.md) (the rule
  list and the ids-are-finer section); `script_nodes.py`,
  `script_validation.py`, `script_parser.py`, `script_grammar.lark`,
  `binding.py`, `facts.py`; the script conformance corpus (41
  fixtures renamed and rewritten, its README) and the blueprint
  corpus README; `test_script_corpus.py`,
  `test_script_spec_conformance.py`, `test_script_validation.py`,
  `test_script_timing.py`, `test_script_nodes.py`,
  `test_script_parser.py`, `test_binding.py`, `test_facts.py`,
  `test_dry_run.py`; [AGENTS.md](../AGENTS.md); and the CHANGELOG's
  unreleased section.

- D82 — THE PROJECT IS GPL-3.0-ONLY, RELICENSING IS RESERVED, AND
  CONTRIBUTIONS ARE ASSIGNED — DECIDED (owner, 2026-07-29).
  Supports none: no use case or principle demands a licence, and
  the reasoning is the owner's alone. The policy is normative in
  AGENTS.md, `CONTRIBUTING.md` and `CLA.md`.

  The rule that governs everything downstream: **vet against a
  commercial dual licence, and say only "relicensing" out loud.**
  The question to ask of any external source is *could this ship
  inside a proprietary product?* — never *is this GPL-compatible?*,
  which has a comfortable answer far more often and is therefore
  the wrong question. Judging correctly costs nothing when a
  dependency is first considered and cannot be revisited at any
  price afterwards.

  - **AGPL-3.0-only** — declined: it closes a narrow hole at the
    cost of adoption the project needs more.
  - **Assignment with no fallback** — declined: some jurisdictions
    bar assignment, so an exclusive sublicensable licence is the
    automatic fallback.

- D81 — STATICALLY REACHABLE MEANS THE GUEST DECIDED NOTHING; THE
  CHECK FAMILY IS GUARDED, NOT MERELY GONE — DECIDED (owner,
  2026-07-29) and delivered the same day. Supports P6, P9, P11.

  A handler body is the **guest's** decision, not the plan's, so no
  static pass can promise it runs; the report counts what it could
  not reach rather than implying a completeness it cannot have.

  **Deleted spellings are guarded, not merely removed** — a purge
  test holds them retired. A name deleted without a guard comes
  back by autocomplete and by memory, and the second arrival looks
  like a feature rather than a regression.

- D80 — A DRY RUN REFUSES WHAT A CREATE REFUSES, AND HASHES
  NOTHING — DECIDED (owner, 2026-07-29) and delivered the same day.
  Supports U7; P7, P10, P11. Normative in
  [cli.md](../docs/spec/cli.md).

  A dry run is the same evaluation with nothing committed: it
  refuses what a create would refuse *where* a create would refuse
  it, with two deliberate exceptions, each a thing it **cannot do**
  rather than a severity judgement — an unbound location is
  reported unevaluated because it must never prompt, and under
  `backend=` an absent backend is reported rather than raised
  because that flag asks whether the blueprint would work *there*.

  **It hashes nothing**: `cached` is presence, not verification.
  Verifying would make a read-only check pay a real cost and would
  report a stronger fact than the flag's own question asks for.

- D79 — F11 IS CUT IN TWO; A DRY RUN IS A DOCUMENT, NOT A STREAM —
  DECIDED (owner, 2026-07-29). Supports U7; P6, P9, P10, P11.
  Normative in [cli.md](../docs/spec/cli.md).

  `--dry-run` flips a command from a stream to a **document**:
  `--json` becomes legal because it prints exactly what the twin
  returns, while `--progress` and `--display` are refused — a plan
  has no stream to render and no window to show.

  - **`--dry-run` on one command only** — declined because pledged
    is not scheduled: the flag means the same thing everywhere it
    appears or it means nothing.
  - **Reporting only the statically decidable part** — declined: a
    reader cannot tell what was omitted, and the counts stop
    describing the script the caller wrote. The report states its
    own limit instead (`3 statements not statically reachable`),
    which is P11 at the report level.

- D75 — A PROMPT IS NOT COMPLETION, AND UNATTRIBUTABLE OUTPUT IS A
  FAILURE — DECIDED (owner, 2026-07-28) and delivered the same day.
  Supports U12, U14, U9; P11.

  `wait_ready` returns *because* a prompt is on screen, so a
  completion test that asks only for a prompt is satisfied by the
  one already there and hands back the boot's output as though it
  were the command's. Completion therefore needs evidence **this**
  command landed: its echo, or a screen that changed since it was
  sent.

  And where the echo was never seen at all, the rows above the
  prompt are **refused rather than returned**: a plausible tuple of
  somebody else's text is worse than an error, because nothing
  downstream can tell it is wrong.

- D72 — P10 SHARPENS: GUESSING IS THE VIOLATION, AND A GUEST'S
  ANSWER ABOUT ITSELF IS AN OBSERVATION — DECIDED (owner,
  2026-07-28) and armed the same day. Supports U14, U20; P11, P16.

  P10 forbids **guessing**, not reading. A value the guest states
  about itself is an observation and may be used; what is refused
  is inference from appearance — deducing a filesystem from a
  screen, a platform from a banner. The distinction matters because
  the naive reading ("never ask the guest") would bar reading
  anything on the host at all — an image's format, a file's size —
  which involves no guest and is the most reliable fact available.

- D70 — THE BLUEPRINT SURFACE IS LOCATED; POSITIONS RIDE ON THE
  PARSED CONTAINERS — DECIDED (owner, 2026-07-28) and delivered the
  same day. Supports U4, U11; G6; P6, P8.

  A diagnostic names where in the file the fault is, and the
  position rides on the **parsed container** rather than on a
  re-scan of the text: a second pass over the source to find a line
  number can disagree with the parse that produced the error, and a
  diagnostic pointing at the wrong line is worse than one pointing
  nowhere.

- D69 — THE PACING BISECTION IS REFUSED; THE 0.1s DEFAULT IS
  DELIBERATE, NOT PROVISIONAL — DECIDED (owner, 2026-07-28).
  Supports U14, U20, U12; G1. **Amends D60's** stated reason.

  **What is refused is the *method***: standing up a bisection to
  tune a default treats a number as an empirical fact about
  hardware when it is a floor chosen for a reason. The variance
  lives in the *readiness mechanism* — an installer arming its
  keyboard handler, a shell entering its read loop — not in paint
  speed, so a measured number would be measuring the wrong thing
  and would look authoritative while doing it.

  [Amended: this left nothing covering paint speed, which is what
  **F48**'s `stability=` gate now guards — pacing is left with
  readiness alone, which is what makes 0.1s an honest floor.]

- D68 — P3 SHARPENS TO BOTH SIDES; THE LINE IS THE AGENT, NOT THE
  SIDE — DECIDED (owner, 2026-07-28) and armed the same day.
  Supports P3.

  Reliquary consumes the agents guests already have and **builds
  none**, on either side of the seam: the refusal is about
  *authoring an agent*, not about which machine the code runs on.
  Stated as a side, the principle would have refused host-side
  helpers that are not agents at all while permitting a guest-side
  one that plainly is.

  What was refused with it: churning P3 for a hypothetical. The
  sharpening landed only because a real case tested the wording.

- D67 — THE SEAM EXTRACTION'S RULINGS: A GENERIC VM IDENTITY, NO
  PORT ABOVE THE SEAM, AND STUBS THAT CLAIM NOTHING — DECIDED
  (owner, 2026-07-28). Supports U7, U1; P7, P11, P12. Normative in
  AGENTS.md, "VM ownership".

  - **Nothing above the seam reads a port.** Keeping `port=` as an
    ordinary parameter was declined: a port is one adapter's shape
    of an endpoint, and a caller that can name it is a caller
    written against QEMU.
  - **A stub adapter claims no capability**, so assignment passes
    over it even where the backend is installed. A stub that
    claimed capability would be discovered as a failure at
    materialization, which is the honesty P11 exists to force.

- D66 — THE BACKEND PRIORITY ORDER RANKS AGENTLESS SCRIPTABILITY
  — DECIDED (owner, 2026-07-28). Supports U7, U12, U1; P3, P11.
  F2's decide-first, settled in the act that pledged it, so the
  feature reached the shelf carrying none.

  THE ORDER: **QEMU, VirtualBox, VMware Workstation, Hyper-V**,
  for default assignment when a blueprint names no `backend`. It
  breaks ties among candidates already available *and* capable —
  assignment walks the list and takes the first that is both — so
  it never stands in for a capability check (P11), and an explicit
  `backend` skips the walk entirely.

  WHY AGENTLESS SCRIPTABILITY IS THE RANK. The proposal said "best
  scriptability"; sharpened, the criterion is the *agentless*
  plane, and the reason is when the choice is made. Assignment
  happens at materialization, before any guest exists, and the
  install that follows is agentless by definition — P3's arc has
  agentless operation preparing a guest and a native agent taking
  over only once one is inside it. A backend's agent story is
  therefore worth nothing at the moment of assignment, and for the
  guests U12 and U1 actually drive it is worth nothing ever: DOS-era
  systems stay agentless permanently.

  THE RANKING, BACKEND BY BACKEND. QEMU is first on evidence
  rather than preference — it is the only adapter with a full
  control plane set, and F2 exists because the seam is read off
  it. VirtualBox second: `VBoxManage` covers lifecycle, scancode
  input, screenshots and serial redirection, the closest match to
  the set scripts already rely on, with VNC behind the extension
  pack. VMware Workstation third: it exposes VNC but no comparable
  scancode surface. Hyper-V last, and not by prejudice — it has no
  VNC at all (a capability failure, never an emulation), which
  leaves it with no agentless display plane, and F5 keeps it
  deliberately last for the same reason.

  WEIGHED AND DECLINED: ordering by host ubiquity. U7's own text
  invites it — "a Windows laptop with Hyper-V already enabled" —
  and on the most common host it would default to the least
  scriptable backend, which is the wrong outcome for the one thing
  a default has to serve: U1's single command reaching a usable
  machine through U12's unattended install. Ubiquity is already
  honored where it belongs, in availability probing; it is not a
  tie-break among the available.

  ALSO DECLINED: no default at all, requiring an explicit
  `backend`. U7 says the machine materializes on whatever capable
  backend the host offers, and U1 claims the journey is one short
  command; a required field costs both.

  TWO OF THE FOUR ARE STUBS at F2 (work item 4, raising
  `NotImplementedError`), so the order's tail is **intent recorded
  now**, not shipped behavior — the same pattern as F3's VDI
  format table, and honest for the same reason: the record says
  what the project means before the code can prove it.

  FOLDED: pledged/FEATURES.md (F2's decide-first becomes settled
  text) and pledged/design/backend-adapter.md (the assignment
  section's open question becomes the order, with its per-backend
  ground).

- D65 — A PLEDGED DEMAND IS NECESSARY AND NOT SUFFICIENT; F2
  PLEDGES WHOLE — DECIDED (owner, 2026-07-28). Supports U7
  (pledged in this round), P11. The pledges of U7 and F2 are
  lifecycle acts and are not recorded here (D63); U7's argument
  was written in its 2026-07-23 draft and needed no re-making.
  What follows is what was adjudicated in their course.

  THE SIZE CALL. F2 was tested against D42's one-sprint bound and
  pledged **whole**, keeping its number rather than retiring it
  for a piece each. The extraction is bounded twice over: by
  working code — QEMU is the only adapter with a full control
  plane set, so the seam is read off an implementation rather than
  designed — and by a regression oracle that says when it is done,
  all QEMU interaction through the adapter API with the FreeDOS
  install script passing unchanged. Four of the five work items
  are small (autodiscovery, default assignment, stubs, ownership
  verification); the adapter API is the bulk. WEIGHED AND
  DECLINED: cutting the seam from discovery-and-assignment. It
  buys a smaller first commitment at the price of F2's number,
  which backend-adapter.md and several entries cite, and the
  pieces are not independently useful — discovery with no seam to
  assign into delivers nothing.

  NECESSARY, NOT SUFFICIENT. `proposed/FEATURES.md` said pledging
  a feature's use case "is what returns the feature to a numbered
  arc", which reads as sufficiency; that reading is declined. A
  pledged use case makes a feature **pledgeable** and pledges
  nothing itself — each feature still moves by its own decision.
  F3 and F5 both cite U7 and both stay in `proposed/` under a
  pledged U7, which is the test of the rule and not an oversight.
  The converse half is unchanged and is why this round has two
  moves in it: a feature may not be pledged ahead of its demand,
  which is the error D61 undid and the reason F2 waited five days.

  F5's DEMAND GAP NARROWED AND DID NOT CLOSE. [It closed
  2026-08-21: D110 adjudicates U5 as the GUI half's demand.] The
  2026-07-27 sweep
  found F5 the one live traceability violation. U7 reaches part of
  it — U7 names Hyper-V outright, so the last two adapters now
  stand on pledged demand — and reaches none of the rest: the VNC
  plane, the landmark asset spec and pointer input answer to
  nothing in force or pledged, and materializing on the host's
  hypervisor says nothing about driving a graphical installer.
  Recorded as a finding, not an adjudication: the demand divides
  exactly where D42's split would fall, which is for whoever
  adjudicates F5 to use.

  FOLDED: pledged/USE-CASES.md and pledged/FEATURES.md (U7 and F2
  arrive; both shelves stop being empty); proposed/USE-CASES.md
  and proposed/FEATURES.md (both leave; the F2–F6 preamble, F3's
  and F5's banners, F7's two findings, one of which this round
  closes); planning/README.md (the map's design rows);
  `planning/pledged/design/backend-adapter.md` — moved from
  `proposed/design/`, since design travels with what it serves
  (D61), which returns a directory empty since that decision — and
  the backend-adapter links in root ARCHITECTURE.md and
  planning/design/guest-communication.md.

- D64 — U4 DOES NOT CARRY U5's MECHANISM; U5 SPLITS AT THE
  DELIVERY LINE — DECIDED (owner, 2026-07-28). Supports none: a
  use-case adjudication is itself demand.

  A use case states **what the user needs**, never the mechanism
  that serves it, so U4 cannot be read as carrying U5's
  parameterization just because parameterization would serve it.
  U5 split at the line delivery actually reached: the delivered
  half became U21 and the half still waiting on the GUI era stayed
  proposed. Splitting at the delivery line is what keeps the
  standing list true — a half-met use case in force would make the
  root list a claim the code does not support.

- D63 — A LIFECYCLE ACT ALONE EARNS NO ENTRY; THE PROMOTION
  GENRE CLOSES — DECIDED (owner, 2026-07-28). Supports (none) —
  record discipline, demanded by no numbered entry; what it
  aligns with is the cross-project governance standard, which
  carries no local number to cite.

  WHAT STARTED IT (owner): the record is getting large, and *"we
  need a record of any architecture decisions in what they
  promoted, but I don't think we need a decision record of the
  promotion itself. That status is self evident."* The standard
  already says as much — the move is the act, the commit that
  does it is the record, and there is no separate register to
  keep in step — and this record kept one anyway: the promotion
  genre (D37, D46, D47, D49, D51, D57, and the pledging and
  arming clauses of D61 and D62) runs roughly 650 lines, about
  a ninth of the file, written while the machinery was still
  being invented, restating what location and git history
  already say.

  THE RULE. Proposing, pledging, promoting, delivering: no
  entry. Delivery evidence — the clause-by-clause case that a
  use case is actually met, D46's genre — goes in the moving
  commit's message, where the act it evidences lives. What
  still earns an entry is a RULING made in the act's course: a
  clause read one way with the other reading declined (D46's
  media-swap clause), a scope widened (D46's two-to-four), a
  pledge found accidental and withdrawn (D61's whole subject).
  Record the ruling, slim — the entry says what was adjudicated
  and never narrates the promotion around it; D61 under this
  rule is twenty lines, not 150. A decision whose conclusion
  pledges something is untouched: that entry records an
  argument, and the pledge is its consequence.

  WHAT THIS DOES NOT DO. Nothing below moves, retires, or is
  rewritten. The genre's entries stand as written under the
  spellings rule, and their numbers stay citable (D62 cites
  D57; D46 applies D34). D34's promotion-on-delivery rule is
  also untouched: promotion stays automatic, and simply stops
  being narrated here.

  WEIGHED AND DECLINED: retroactively compressing or archiving
  the genre. Retirement moves an entry intact and saves
  nothing, rewriting is forbidden by the record's own
  discipline, and deletion breaks the permanent-handle
  guarantee. An archival split — old entries moved whole,
  numbers intact, to a companion file — is the one compliant
  shrink, and remains available as its own decision, not taken
  here.

  FOLDED: the governance standard (the record's discipline and
  its move-is-the-act clause) and its DECISIONS.md template;
  this file's preamble. Nothing else in the tree changes: the
  rule governs entries not yet written.

- D60 — INPUT PACING IS CONTROL-PLANE PACING, NOT A `delay` VERB —
  DECIDED (owner, 2026-07-24) and delivered 2026-07-27. Supports
  U14, U20, U12. Normative in
  [script-spec.md](../docs/spec/script-spec.md).

  THE DISTINCTION, which is what keeps `delay` refused: a `delay`
  verb is a pause an author *sequences* — a step standing between
  two others, encoding a guess about how long something takes.
  `pacing` is a property of *delivering input*, the gap the control
  plane takes before its first key event whether or not anyone
  writes the word. The language adds the ability to tune that gap,
  not to insert one.

  **The 0.1s built-in is a floor, not an estimate.** The variance
  it was once justified by — paint speed — is not what it covers;
  what makes a guest ready to *read* is the readiness mechanism,
  and no single number serves every screen, which is why the
  per-phase and per-statement overrides carry the weight.

- D61 — THE PLEDGED SHELF IS RE-TESTED ENTRY BY ENTRY — DECIDED
  (owner, 2026-07-27). Supports U8, U11, U12, U13; P8. **Amends
  D44** (its clearing sentence only) and **retires D42's F1
  tolerance**. F1, U2 and U6 withdrew; U1 condensed and promoted.

  THE FINDING, which is why this is an entry rather than four
  lifecycle moves: **the pledges arrived without anyone making
  them.** Before the shelf existed, entries carried their state as
  a word, where *accepted* meant only that the argument had won.
  The restructure filed each by its word — correctly — but F1 had
  no word to be filed by, so it was created on the shelf because
  its work items had nowhere else to go. D44 then changed what the
  shelf *claims*, from agreement to a commitment to deliver, and
  cleared its occupants in one sentence. Nobody ever decided to
  build the recorder. **A shelf whose meaning changes under its
  occupants re-tests them one by one; it does not inherit them.**

  - **Retiring U1 as superseded by U11–U13** — weighed and
    declined: U1 names a command nothing else in force does.
  - **Pledging U8 first**, as the parked plan assumed — declined:
    it commits the project to building export.

- D59 — EVERY WORKING DIRECTORY IS PLACEABLE; P12 AND P4 AMENDED —
  DECIDED (owner, 2026-07-27) and delivered the same day. Supports
  U17, U14, U4; P4, P6. The six placeable directories and the
  derivation cascade are normative in
  [asset-resolution.md](../docs/spec/asset-resolution.md) and
  AGENTS.md.

  **Containment stopped being topology**, which is the durable
  half: with six independent roots, "under the home" is not a claim
  reliquary can make, so P12 was amended to what it can still
  guarantee — reliquary writes only where it was told to, never
  beside the module and never into a source repository.

  Its seeding axis was **retired by D88**, which restored P4 to an
  absolute; the alternative preserved here was rejected for making
  seeding a silent consequence of resolution.

- D58 — THE FOUR ERROR CLASSES DESCRIBE EVERY SURFACE, NOT A
  SCRIPT RUN — DECIDED (owner, 2026-07-27). Supports U9, U14; P6,
  P7, P11. Normative in AGENTS.md.

  What decides a class **never mentions a script**: the authored
  input alone (`StaticError`), the world not satisfying it
  (`PreflightError`), or the work itself failing (`RunFailure`). So
  a malformed blueprint is static and a machine that does not exist
  is preflight, whatever command was run. A taxonomy read as
  script-run phases would have left every non-script surface
  choosing a class by analogy.

  A fifth class for cancellation was refused as one whose whole
  population is a single event; `RunCancelled` is a sibling of
  `RunFailure`, never a subclass.

- D57 — P16 IS PLEDGED; THE TEST IS WHAT A CONSUMER MUST DO —
  DECIDED (owner, 2026-07-27). Supports U14, U20; P11.

  THE TEST, which is the entry's reusable part: a capability earns
  a principle when its absence forces **a consumer to reproduce
  reliquary's own model outside it**. Not when it would be
  convenient, and not when reliquary could plausibly own it — the
  bar is that the caller is currently obliged to re-implement
  something reliquary already knows, and will get it wrong in ways
  reliquary cannot see.

  [P16 gained a carve-out in **D108**: a machine's file
  content is out of purview by design, so the test above is
  asked only of what a machine *is* — its lifecycle, drives,
  media, screen, input and returned values.]

- D55 — THE REASON-BLOCKQUOTE SWEEP IS DROPPED — DECIDED (owner,
  2026-07-27, closing out the Language queue). Supports P8, P23.
  The 2026-07-21 spec-craft round left one editorial proposal
  deliberately open — a sweep giving script-spec.md's rules
  per-rule rationale blockquotes — and it is refused rather than
  finished. Recorded here so it is not re-raised as an oversight;
  it was considered and declined.
  **ITS DEFINITION WAS ALREADY LOST**, which is half the argument.
  The entry naming it points at *"the review output — workflow
  `wf_ac5f89b4-402` journal"*, and a run id resolves only inside
  its own session; no copy exists in the repo. Three entries lean
  on those journals and none is readable. So finishing the sweep
  would have meant inventing what it was, not completing it —
  there is not one `Reason` blockquote in the file to infer the
  shape from.
  THE SUBSTANTIVE GROUND, which stands even if the journal turned
  up tomorrow. **The spec already points at its reasoning**: it
  carries eleven D-number citations at load-bearing spots, and a
  D-number is this project's citation currency by design. A
  per-rule blockquote replaces that pointer with a *copy*, and
  D52 deleted an entire section of TASKS.md on what copies do —
  a summary kept beside what it summarizes drifts, and a reader
  has no way to tell. The cost scales: 51 sections, no test, and a
  normative document is the worst place for prose that can quietly
  stop being true.
  THE NEED IT SERVED IS REAL AND ALREADY MET. A reader weighing a
  proposed change needs to know why a rule exists — which is
  precisely what the interface-change rule sends them to
  DECISIONS.md for, and what the D-citations in the spec make
  reachable in one hop. Where a rule's reason is *not* reachable,
  the fix is a citation, not a paragraph.
  EVIDENCE FROM THE INTERVENING SIX DAYS: script-spec.md went
  through a full realignment, three delivered milestones and this
  week's audits without anyone missing the blockquotes.
  FOLDED: this entry; TASKS.md (the Language bullet dropped, and
  with it the error-id clause it carried — that half is a defect,
  entered under Defects, the *index* staying deferred to beta in
  the spec sentence that already says so). script-spec.md is
  unchanged.

- D54 — `@` VERSUS `$` IS INHERENT AND OBSERVABLE; EXAMPLE 06
  CLOSES — DECIDED (owner, 2026-07-27). Supports P5, P8, G6.
  The last open question in
  [06-media-label-vs-item](design/script-examples/) is settled and
  the example is deleted, the catalogue holding open problems
  only.
  THE QUESTION. `insert` takes its media through either sigil —
  `insert cdrom0 @freedos-livecd` or `insert floppy1
  $supplemental-disk` — and the two look equally definite on the
  page while meaning different things: `@` names a specific item,
  `$` defers the choice to the run. A reader must recall the
  property declaration to know which insert is fixed.
  SETTLED AS THE EXAMPLE ITSELF GUESSED: **inherent, and already
  observable.** Deferral is what a property is *for*, so the page
  cannot say which media a `$` insert will mount without deleting
  the feature. What the example asked for instead — something
  naming the resolved item at insert time — turned out to exist:
  the runtime resolves the binding before building the action's
  detail, so `insert floppy1 $supplemental` emits
  `insert floppy1 @win98-cd`, the resolved name spelled with the
  definite sigil. The observability half was closed by milestone
  9's event stream without anyone noticing it answered this.
  PROMOTED TO NORMATIVE BEFORE DELETING, which is why this carries
  a number rather than being housekeeping. The behaviour shipped
  but **no norm required it**, so it was free to change and the
  example could not be closed against it. script-spec.md's run
  event stream now states it: an `insert` names the media it
  actually mounted, a `$` argument reporting the resolved name and
  not the property's. Same shape as D50's format-stability
  promotion — existing behaviour becoming a rule the
  implementation answers to (P5: the stream is where a run's
  difference becomes visible, and no surface reports what it does
  not carry).
  A COVERAGE GAP CLOSED WITH IT. Nothing tested this. The suite
  had a test for an *unbound* `$` insert failing, and none for a
  bound one reporting its resolved name — so the behaviour the
  spec now requires was resting on one unexamined line. It has a
  test.
  THE EXAMPLE'S OTHER TWO QUESTIONS were closed earlier: the
  label/item split died with embedded media blocks (2026-07-22),
  and rejecting an `@`-reference the namespace does not define
  landed 2026-07-27 as the preflight defect it had always been
  rather than the language task it was filed as.
  FOLDED: this entry; script-spec.md ("The run event stream", the
  action bullet); design/script-examples/ (06 deleted, README's
  table and its resolved-examples note); test_script_runner.py
  (the resolved-name test). CHANGELOG: none — the behaviour is
  unchanged, only its standing.

- D53 — BARE WORDS STAY POSITION-TYPED; TASK [08] IS REFUSED —
  DECIDED (owner, 2026-07-27). Supports P8, P23, G6.

  The proposal was to reserve a keyword list so a bare word could
  be typed without its position. Refused: position already types
  every bare word unambiguously, and a reserved list is a surface
  that grows forever and breaks scripts that used a word before it
  was reserved.

  THE PROCEDURAL HALF, cited since: **a refusal never becomes a
  task**, and the refusal is the *first* option a queued item may
  meet — a queue entry is pre-approved work, not a commitment that
  the work is right.

- D52 — EVERYTHING IS STRUCK WHEN IT IS DONE — DECIDED (owner,
  2026-07-27). Supports P8, P23; **amends D45**.

  `TASKS.md` keeps no Completed section and no Rejected section: a
  queue holds what waits, and the commit that strikes an item is
  its record. **A refusal never becomes a task entry** — it belongs
  here, in the decision record, which is the whole record of a
  refusal. Keeping done work in the queue makes the queue's length
  meaningless as a measure of what is outstanding, and keeping
  refusals there splits the guard against re-litigating across two
  files.

- D51 — U3 RETIRES, SUPERSEDED BY U14 — DECIDED (owner,
  2026-07-27). Supports P8; **completes D36**.

  U3 stated a *preference* for a guest-agent transport. U14 carries
  the same demand — a program driving a machine and reading
  results — with **no transport preference at all**, which is the
  point of the supersession: a use case names what the user needs,
  never the mechanism, and a preference embedded in one is a design
  decision wearing a demand's clothes. What carries the preference
  now is **P3**, a principle, which governs how a native agent is
  consumed if one ever lands without demanding that it land.

- D50 — THE 2026-07-26 RESTRUCTURE'S UNNUMBERED ACTS, ISSUED —
  DECIDED (owner, 2026-07-27). Supports P8, P23; **amends D23**
  (pledge is the move). The restructure dissolved the roadmap into
  these directories, renamed PRINCIPLES.md to root ARCHITECTURE.md,
  and made location the statement of status — all of it normative
  in [README.md](README.md).

  THE RULING, which is why it needed a number at all: **acts that
  change the governance machinery cannot be unnumbered.** The
  restructure had been performed as housekeeping, and housekeeping
  is approved as a class precisely because it touches nothing
  arguable; a change to how the project decides things is the
  opposite of that. Issuing the number retroactively is what makes
  the rebuild citable.

- D49 — P24 RESTATED AND ARMED, AFTER LANDING NOWHERE — DECIDED
  (owner, 2026-07-27). Supports P8, P22, P23; **restores a
  decision made 2026-07-27 in commit `42c8c75` that reached no
  document**, and is the first promotion made under D48's second
  bar.
  WHAT WAS LOST, AND HOW. That commit's message says *"state P24
  in D44 — every enumerated interface carries automated tests
  checking it against its specification, and the suite passes on
  every commit to main — dropping 'to whatever extent possible'
  so the principle can actually be violated, and requiring an
  untestable surface to name its gap."* None of it landed: P24
  never entered ARCHITECTURE.md, the D-number was **reused the
  same day** by D44 (the `accepted/` → `pledged/` rename), and
  the companion edit that bullet describes — adding P24's
  every-commit gate to P22's list of expected knocks — is absent
  from P22 too. The decision existed only in a commit message.
  WHY NOBODY NOTICED, which is the interesting part. The single
  surviving trace is [design/audits.md](design/audits.md), which
  refers to P24 as an accomplished fact — *"armed 2026-07-26 …
  the strongest claim in the list with the thinnest verification
  behind it"* — so the one document that talks about P24 asserts
  it exists. A dangling reference is only findable against
  something; this one pointed at a number that had been silently
  spent, which reads as a valid citation to every check that
  matters. Found while tracing where principles get recorded for
  D48, not by looking for it.
  VERIFIED BEFORE ARMING, by D23's standard — against the code,
  not the docs. Every interface enumerated in "The interfaces"
  carries test modules: CLI (`test_cli`), embedding API
  (`test_machines`, `test_media`, `test_run_script`, `test_core`,
  with `test_old_surface_purge` guarding the deleted one),
  scripting language (the five `test_script_*` modules and
  `test_check_script`), machine blueprint (`test_document` plus
  `test_conformance_corpus`, which runs one corpus against both
  parser and schema so the two cannot drift), script properties
  (`test_properties`, `test_binding`, `test_credentials`,
  `test_facts`), recorded outputs (`test_events`, `test_errors`),
  home layout (`test_home`, `test_assets`). Suite run at
  adjudication: **768 passing, 1 skipped** — the opt-in FreeDOS
  integration test.
  ARMED, NOT PLEDGED — and the residue filed, which is D48's
  second bar doing its first work on the day it was written.
  Pledged would be the false state: the tests exist and the suite
  is green, so the project does honor this as a rule. What it does
  not yet honor evenly is the phrase *"against its
  specification"* — most modules test behavior rather than
  deriving cases from the norm, and only the blueprint has a true
  conformance corpus. audits.md had already named exactly this
  gap; under D48 a named gap against an armed principle is not an
  audit idea, it is a **defect**, and it is entered in TASKS.md
  as one.
  THE SECOND CLAUSE IS HONORED BY DISCIPLINE, said plainly. *"The
  suite passes on every commit to main"* has no machinery behind
  it, because P22 says there is no CI — and P22 now names
  automating this gate as one of the cases expected to knock.
  That is not a weakness in P24; it is the same posture written
  from the other side.
  FOLDED: this entry; ARCHITECTURE.md (P24 stated after P23; P22's
  expected-knocks list gains it, the companion edit `42c8c75`
  intended); design/audits.md (its P24 question corrected — the
  principle was armed today, not on the 26th, and the audit it
  proposes is now the filed defect); TASKS.md (the conformance-
  depth defect entered). No CHANGELOG line: nothing
  release-facing moved.

- D48 — A GAP AGAINST A STANDING ENTRY IS A BUG; THE PROMOTION BAR
  IS TWO BARS — DECIDED (owner, 2026-07-27). Supports P8, P23;
  **sharpens D34**. Normative in [README.md](README.md).

  Promotion runs on **two bars, not one**: a use case moves on
  *full delivery*, a principle on being *honored as a rule* with
  every known residue filed as a defect in the same change. Below
  the root list a shortfall is unbuilt work; at the root list it is
  a bug. Conflating them would let a principle be promoted while
  someone "means to" fix an exception — which makes the standing
  list a statement of intent, and the standing list is the one
  document that has to be a statement of fact.

- D47 — P5, P14, P17 AND P18 ENTER FORCE — DECIDED (owner,
  2026-07-27, the second TASKS.md adjudication). Supports P8, P10,
  P11; applies D34's promotion rule to principles.

  THE BAR, which is what the entry is for: a principle is armed by
  being *honored as a rule*, with every known residue filed as a
  defect in the same change — not by being agreed with. Below the
  root list a shortfall is unbuilt work; at the root list the
  project asserts the code honors it, and a divergence becomes a
  bug. Promoting a principle while knowing of an exception would
  make the root list a wish rather than a claim.

- D46 — U9 AND THE U11–U13 CHUNK TRIO ARE PLEDGED AND IN FORCE —
  DECIDED (owner, 2026-07-27). Supports P6, P7, P8.

  A use case may be **pledged and delivered in one act** where the
  code already meets it: the two moves are separate events, not a
  mandatory interval, and forcing a wait would make the standing
  list lie about what the code does.

  THE RULING WITH TEETH: **a use case is rejected by naming it.**
  An unwritten case cannot be refused, so the sweep that found U9
  and U12 delivered-but-unpledged had to pledge them rather than
  quietly treat delivery as sufficient — which is the defect a
  traceability check would have caught the day milestone 9 landed.

- D45 — THE HOUSEKEEPING BOUNDARY IS HOUSEKEEPING'S ALONE; A SMALL
  SURFACE CHANGE MAY BE A TASK — DECIDED (owner, 2026-07-27).
  Supports P8, P23; **completes D43**. Normative in
  [README.md](README.md).

  Housekeeping's surface test exists to compensate for a class
  **nobody with authority ever reviews** — work approved on sight
  and landed without an entry. The task queue needs no such
  compensation, because only authority may write to it and entering
  an item *is* approving it. So the two gates are not the same gate
  at different sizes: a small surface change may be a task, refused
  from housekeeping for *who reviews it* rather than for what it
  touches.

- D44 — THE SECOND SHELF IS `pledged/`, NOT `accepted/` — DECIDED
  (owner, 2026-07-27). Supports P8, P23. Normative in
  [README.md](README.md).

  **Neither shelf is named after an act.** Both gates need one —
  admitting a document to `proposed/` is an approval too — so a
  shelf named for an act claims words the other gate still has to
  borrow. Both names state what the item *is*: proposed, argued and
  binding nothing; pledged, owed with no date attached.

  The structural reason that settled it: `accepted/` had meant only
  that the argument had won, and renaming it to a commitment to
  deliver changed what the shelf *claimed* about its existing
  occupants — which is what forced the entry-by-entry re-test in
  **D61**. A shelf does not inherit occupants across a change in
  its meaning.

- D43 — WRITING UNDER planning/ IS A GOVERNED ACT; AUTHORITY
  COMPRESSES THE STEPS — DECIDED (owner, 2026-07-26). Supports P8,
  P23; **amends D39** (widening its two queues to three). The three
  queues and the gate are normative in [README.md](README.md).

  THE RULING: the gate weighs most on the **task queue**, because a
  `proposed/` entry admits an argument and commits nothing, and a
  promotion is that argument's conclusion with its reasoning
  recorded — but a task entry *is* the whole vetting with nothing
  behind it. There, authority is all that stands between
  pre-approval and self-approval. So the third queue is refused for
  **who may write to it**, never for what it may contain: a small
  surface change may be a task, and the housekeeping surface test
  is housekeeping's alone.

- D42 — NO ROADMAP; FEATURES CARRY RETIRING F-NUMBERS AND A
  SPRINT-SIZED BOUND — DECIDED (owner, 2026-07-26), completing the
  governance rebuild of that day. Supports P9. The machinery is
  normative in [README.md](README.md).

  WHY NO ROADMAP, which is the part with no other home: a roadmap
  classifies by *when*, where everything in this directory
  classifies by *state*, and it promises an order nothing commits
  to. `pledged/` says the project will do it and says nothing
  whatever about when — a commitment without a date, which is what
  lets the shelf be **wrong**: an item nobody intends to deliver is
  withdrawn or rejected, never left sitting as a pledge nobody
  means.

  The sprint bound bites **at the pledge**, not in `proposed/`, so
  a proposal may be many sprints and cutting it up is part of
  pledging it. An F-number evaporates on delivery and is never
  reused: gaps are history rather than a promise.

- D41 — THE IDENTITY LEDGER IS DELETED; `add-media` AUTHORS A
  DECLARATION — DECIDED (owner, 2026-07-26). Supports P4, P8;
  **amends D22**'s cache clauses.

  **The cache is wholly regenerable, so nothing records where a
  file came from.** Every payload arrived by download or
  extraction, so no verb asks a file's provenance before
  reclaiming it — a ledger would be a second source of truth about
  a directory that can always be rebuilt, and one that goes stale
  silently.

  `add-media` therefore *authors a declaration* rather than
  importing a file: it computes the sha256 and writes the `.rlqb`
  locating the media where it already lies, copying nothing.
  Supplying a file is an authoring act, which is why it belongs to
  blueprint authoring and not to the media cache.

- D40 — CANCELLATION REACHES A HOST TRANSFER BY ITS OWN
  PARAMETER — DECIDED (owner, 2026-07-26). Supports the
  execution model's severability; fixes a gap against a standing
  promise rather than making a new one, so it is a
  gap-is-a-bug fix (D38's exclusion) whose *seam* is the decided
  part. [Retrofitted 2026-07-28 — Supports U12, U13; P5. The
  clause above cites no numbered vision, and the severability it
  names is a *spec* promise rather than a principle
  (docs/spec/script-spec.md — Ctrl-C "leaves the machine
  as-is"), so it gave the entry nothing citable. What the fix
  serves is numbered: U12's long run showing where it is and
  what it waits on while it goes, U13's media fetching and
  verifying itself, and P5's rendering being *timely* — a 294 MB
  download that reports nothing for minutes and swallows Ctrl-C
  fails all three at once.]
  THE DEFECT. planning/ROADMAP.md ("Cancel ends the run, not the
  machine") already promised that on Ctrl-C "input deliveries are
  atomic, **host transfers abort**". They did not. Cancellation
  was a `threading.Event` read only by `_check_clocks` at
  statement boundaries, and `acquire.py`'s transfer loops knew
  nothing of it — so a Ctrl-C during `insert cdrom0 @…` was not
  observed until the download, its SHA-256, the extraction, and
  *its* SHA-256 had all finished. Reported from the field as
  minutes of an unresponsive Ctrl-C on a 294 MB LiveCD fetch.
  Aggravating it, the same statement passed no `events`, so the
  transfer reported no progress at all: silence for minutes reads
  as a hang, which is how it was found.
  THE SEAM, WHICH IS THE DECISION. Cancellation travels as its own
  `cancelled=` keyword — the run engine's `threading.Event`,
  threaded through `insert_media` / `start_machine` / `fetch_media`
  to the chunk loops, checked at every chunk. `None` (a fetch
  outside a run) is uninterruptible exactly as before, so the
  addition is inert wherever it is not passed.
  WEIGHED AND DECLINED: carrying the token on the `EventStream`,
  which is already threaded end-to-end and would have cost ~4
  lines against ~10 signatures. Declined because it couples two
  unrelated properties to one keyword — and that coupling is
  precisely the failure that produced this bug. One call site
  (`_machine_change`) dropped `events` and silently lost progress
  reporting; under the coupled design the same omission would also
  have made a multi-minute transfer uninterruptible, with nothing
  to fail closed on since `events=None` is a supported state. Two
  orthogonal keywords keep the two failure modes independently
  diagnosable, and keep `acquire.py` free of any dependency on run
  control flow.
  CTRL-C ESCALATES. A second interrupt restores the default
  handler and raises at once. The graceful stop is a promise, not
  a trap: the previous handler swallowed every repeat into the
  same flag, so a stop that would not land left killing the
  terminal as the only way out.
  ALSO: `urlopen` gained a 30s timeout. A mirror that accepts a
  connection and then stalls is a failed location, not a reason to
  hang forever — it surfaces as `OSError`, which the alternatives
  loop already treats as one location failing, so the next mirror
  is tried.
  AND THE SCRATCH FILE GOES WITH THE TRANSFER. A transfer writes
  `<destination>.part` and renames it only once whole, so an
  interrupted one stranded that file — previously rare, since
  mid-transfer interruption was barely reachable; now the ordinary
  case. Cleanup was put on *every* incomplete path rather than on
  cancellation alone: there is no resume (the next attempt opens
  the file `"wb"` and starts over), so an abandoned partial is
  never anything but garbage, and a rule that holds only for one
  way of ending would have been the arbitrary one.

- D39 — THE TWO RAW INPUT QUEUES; NOTHING ENTERS ELSEWHERE —
  DECIDED (owner, 2026-07-24). Supports P8; completes D38.
  **Widened to three queues by D43.**

  Nothing flows into the project without starting in a queue, the
  single exception being a small raw commit approved under
  housekeeping. The point is not the count of queues but the
  closure: an idea with no door is an idea that enters by whoever
  happens to be writing, and a rejection then has nowhere to be
  recorded — which is why a refused item's reason is recorded here
  rather than in the queue it left.

- D38 — HOUSEKEEPING IS A STANDING APPROVAL BUCKET — DECIDED
  (owner, 2026-07-24). Supports P8; sharpens TASKS.md's passive
  "small ones may simply be deemed obvious", which named no test,
  no deemer, and no act.
  THE BUCKET. Small code cleanups and small reported defects —
  tiny in scope **and** crystal clear that they are a problem
  needing addressing — are approved as a class, in advance. They
  need no use case, no principle, no issue, and no D-number of
  their own. Whoever lands the work invokes the bucket by naming
  it in the commit; the commit is the record (the CHANGELOG
  follows its own existing rule — a user-visible change earns an
  entry, invisible tidying does not).
  WHAT IT IS FOR: work that has *no citation available*. Tidiness
  with no defect behind it — dead code, a stale path, a clunky
  help string — and defects too small to be worth an issue. A
  defect against a *standing* principle is deliberately **not** in
  this bucket: the principle is already its demand (the
  gap-is-a-bug rule), so it needs no approval, only fixing.
  REJECTION IS A DUTY, NOT AN OMISSION (owner). Anything that
  fails the test is **refused** under housekeeping and routed to
  the governance mechanism — an issue, a use-case or principle
  proposal, the interface-change rule, a roadmap item. This is
  what makes the bucket a gate rather than a shortcut: the
  question is asked on every candidate, and "no" has somewhere to
  go. Also never admissible: a use-case or principle amendment,
  or a design decision.
  THE FIRST TEST IS MECHANICAL, AND IT IS ABSOLUTE (owner,
  2026-07-24): **anything that changes an interface is
  automatically not housekeeping.** It is asked first and answered
  by lookup, not judgement — INTERFACES.md *enumerates* the
  surfaces, so this is a checklist rather than an opinion: the
  four primary interfaces (CLI, embedding API, scripting language,
  machine blueprint) and the supporting world-facing contracts
  (script properties, the codex, the run's returned output, the
  home layout). Touch one and the answer is no, whatever the diff
  looks like. That property is what makes the exclusion hold up
  against the bucket's real failure mode, which is self-assessment
  — "tiny" and "clearly a problem" are judged by whoever wants to
  do the work, and everyone's own change feels like both.
  THE TIE-BREAK, for what survives that test: **doubt escalates.
  If it has to be argued into the bucket, it does not belong in
  it.** Both remaining halves must hold — tiny alone is not
  enough, and obvious alone is not enough.
  THE TRAP, from milestone 9's own landing. Three changes that
  day were all small: the codex install script's `press enter` →
  `select "Yes"` (a defect, no interface touched — housekeeping);
  the guest-console family passing the machine's directory so its
  identity check could pass (restores behavior that never worked
  — housekeeping); and the output-discipline sweep that made
  `create-machine` print `plain-0` rather than "created machine
  plain-0". The third felt smallest and was the only one that
  changed a world-facing contract on every command — it needed
  milestone 9's deliverable behind it, and under this rule would
  be refused. Size is not the test on its own.
  FOLDED: this entry; TASKS.md's preamble (the operative rule
  replacing the passive sentence); INTERFACES.md (the exclusion
  stated where the interface-change rule lives, so the bypass is
  closed at the door it would be walked through).

- D37 — MILESTONE 9 DELIVERS U14 AND U20; BOTH PROMOTE —
  DECIDED (2026-07-24, landing milestone 9). Supports P8, P11,
  P18; applies D34's promotion-on-delivery rule and D36's
  reframing. The milestone landed in full — the return-not-store
  run model, the error taxonomy, live `--progress` feedback, and
  the exec-run mechanics — so by D34 the two use cases it accepted
  move to their standing list as a step of that delivery.
  U14 PROMOTED. The loop it describes runs end to end against a
  live FreeDOS machine: work put in, run from a consumer-authored
  script, and the result read back through a machine variable
  (`get-machine-var`). The `exec` twin landed with it,
  returning the text its command produced, which is the run
  family's parity D36 named. [The in-band file verbs this entry
  also cited as evidence are gone (**D108**), and U14 no longer
  claims a file as the product; the promotion stands on what
  survives.]
  U20 PROMOTED, ITS TRANSPORT PROVEN. The T1 spike ran the swap
  cycle on QEMU/DOS: a live `insert-media --file` swap is *seen*
  by DOS (the directory listing after a swap is the new image's,
  never the previous disk's), and a guest write reaches the host
  image — verified byte-wise after `eject-media`, and again after
  swapping back, each image carrying only its own rounds. No
  reshaping was needed.
  THE ONE CONDITION THE SPIKE FOUND, NOW A GUARD. A floppy drive's
  geometry is fixed when the backend attaches it at launch, and a
  live change does not revise it: a slot launched empty takes
  QEMU's own 2.88M default, so inserting a 1.44M image into it
  live reaches the guest as "general failure" on every read and
  write. Reliquary did not choose that geometry and will not ship
  a silently broken drive (P11), so `start` records the launched
  medium's size and a mismatched live insert fails closed naming
  both sizes and the fix. This is what the spike was *for* — the
  finding became a guard rather than a footnote.
  P16/P17/P18 NOT PROMOTED. The code honors P18 (no shipped
  readiness script, no result vocabulary), but the principles are
  **drafted, adjudication pending**. Promotion presupposes
  acceptance, which is the owner's, so they stay in
  PRINCIPLE-PROPOSALS.md; the implementation is evidence for that
  adjudication, not a substitute for it. [P17 was later armed and
  is now struck outright — **D108**.]
  U3's SUPERSESSION IS DUE, NOT TAKEN. D36 settled that U14
  supersedes U3 alone, and U14 is now delivered — but retiring a
  use case is the lifecycle's Retire clause, an owner
  adjudication, not a step of this delivery. U3 waits in the
  proposals doc with that noted.
  FOLDED: this entry; USE-CASES.md (U14 and U20 added);
  USE-CASE-PROPOSALS.md (both removed, no stub — D23; U3's note);
  ROADMAP (milestone 9 marked complete, the arc with it, the
  spike condition recorded); TASKS.md (T1–T7 marked landed, the
  spike result, the two fixes found in passing); script-spec.md
  (the `set` verb, and the half of the file-exchange omission
  in-band put/get closes — as a CLI/API capability, never a
  language one); AGENTS.md; the machine-state schema
  (`variables`, the anonymous medium); README, CHANGELOG, and
  both references.

- D36 — THE RUN RETURNS ITS OUTPUT — DECIDED (owner, 2026-07-24).
  Supports P4, P6, P8, P18; **amends D35**. Normative in S7 and
  AGENTS.md.

  A run drives the machine and **returns its output to whoever
  started it, storing nothing**. What was deleted with the
  persistence — `run-events.jsonl`, `transcript.txt`, the `runs/`
  archive, retention and the run verbs — was refused for want of
  demand, not disliked: it is async's substrate, and async itself
  had none. It returns with **F6** if U19 is ever pledged.

  [Bounded by **D98**: a `--record` capture is written only where a
  maintainer names a path and is read by nothing at runtime, which
  is a different thing from persistence as async's substrate.]

- D35 — ASYNCHRONOUS RUNS LEAVE THE ARC — DECIDED (owner,
  2026-07-24). Supports P8; follows D33's ground.

  The feedback split (**P5**) is satisfied by the run's own driver
  watching it live, so detaching a run — or following one from a
  process that did not start it — is a **separable** capability no
  use case wrote down. Its demand is the U19 draft; pledging U19
  is what schedules the work back on. [**D36** extended this: the
  persistence such a run needs went with it.]

- D34 — PROMOTION ON DELIVERY IS AUTOMATIC — DECIDED (owner,
  2026-07-24). Supports P8; sharpens D23. THE RULE: when a
  milestone or a task FULLY delivers a use case or a principle,
  moving it from its proposals doc to its standing list is a step
  OF THAT DELIVERY, not a later owner adjudication. D23 already
  said "DELIVERY makes it current and moves it over"; what was
  unstated is that the mover is whoever lands the work, in the
  same change, the moment the code honors the entry. No holding
  it for a separate sign-off.
  THE TRIGGER IS FULL DELIVERY, NOT ACCEPTANCE. A milestone that
  cites a proposal accepts it (D23, acceptance-is-scheduling); a
  milestone whose landed code honors it in full delivers it. The
  two can diverge: milestone 8 accepted both U5 and P13, but only
  P13 is fully delivered — U5's canonical customized-Windows
  scenario waits on the GUI era, so U5 stays
  accepted-awaiting-delivery while P13 promotes. The one who
  lands the work makes that call by the same test the P1–P12
  delivery pass used: does the project honor the entry as the
  code stands today?
  THE MECHANICS (the same for a U and a P): add the entry to its
  standing list at its normative home (root PRINCIPLES.md /
  USE-CASES.md), in number order; DELETE it from the proposals
  doc, no placeholder left behind (D23's no-stub rule); and
  record the move here, the entry's number the search key for the
  planning-doc sweep. A partly-delivered entry does not move —
  the standing lists are an implementation claim (D23,
  implemented-only), so a half-honored entry would be a false one.
  [D48 splits this into two bars: it holds for a use case, while
  a principle promotes at *honored as a rule* with every known
  residue filed in the same change. The tension is inside this
  entry — the test two sentences above, inherited from the P1–P12
  pass, is already the rule-shaped one.]
  FIRST APPLICATION: P13 (property sources) promotes to
  PRINCIPLES.md with milestone 8 — the binding pipeline, the
  layered sources, custody and per-resolution provenance are all
  landed (T1–T5, verified against the code). FOLDED: this entry;
  PRINCIPLES.md (P13 added between P12 and P15);
  PRINCIPLE-PROPOSALS.md (P13 removed from Drafted) and its
  lifecycle preamble; USE-CASE-PROPOSALS.md's parallel preamble;
  ROADMAP milestone 8's note (P13 promoted, U5 still awaiting the
  GUI era). U5's own move waits on its delivery, by this same rule.

- D33 — THE NUMBERED ARC ENDS AT MILESTONE 9 — DECIDED (owner,
  2026-07-23). Supports P8.

  The pillars beyond it — further backends, guest agents, the GUI
  era — were **demoted for lack of use-case backing**, not for
  lack of design: their designs stay settled and stand as written.
  A milestone number is a schedule, and scheduling work no demand
  asks for is how a roadmap acquires items nobody intends to build.
  Scheduling any of them again is the pledge of the use case that
  wants it.

- D32 — THE CONTAINMENT PATH LIVES INSIDE THE BRACES — DECIDED
  (owner, 2026-07-23, milestone 7's S3). Supports P14; RESOLVES a
  contradiction between D22/D24 and D26/D27. Found by running the
  S2 corpus against the first parser written to the spec — which
  is what writing the corpus first was for.
  THE CONTRADICTION: D22 settled the spelling as
  `${media:<name>}/<path>`, path OUTSIDE the closing brace, and
  D24 built on it — "a backslash after `}` is an error naming the
  `/` rule" presupposes the path follows the brace. But D26's
  character class justifies `/` as "separates the containment
  path (exactly one)", which it need not do if the path is
  outside the body at all, and D27's corrected production spells
  the body `qualifier:media-name[/path]`, path INSIDE. Both
  readings were live, and blueprint-model.md inherited both in
  one document — its location table said outside, its closure
  section said inside — WITHOUT THE REWRITE NOTICING. A spec
  contradicting itself about a character position is one an
  implementer resolves by guessing.
  DECIDED: INSIDE. `${media:outer/cd.iso}`. THE GOVERNING
  ARGUMENT IS THE CLOSURE: a qualified reference is whole-value
  only, and with the path inside, whole-value means the string is
  EXACTLY ONE REFERENCE — the closure test sees the entire
  location and nothing trails it. With the path outside, the
  parser must special-case trailing text after a qualified
  reference, distinguishing a path suffix from interpolation the
  reach rules forbid there; that is a second rule, and it lives
  exactly where P14 says a second rule must not accrete. It also
  gives D26's `/` its stated job back.
  WHAT THE OUTSIDE FORM HAD: D22's priority, and familiarity —
  it reads like a path join. Both real, neither structural.
  THE BACKSLASH DIAGNOSTIC SURVIVES, which was the strongest
  objection: `${media:outer\cd.iso}` is the same Windows author
  making the same guess, and the parser names the same `/` rule —
  it is now caught inside the body rather than after it, and the
  message is unchanged in substance.
  RECORDED AS METHOD: the S2-before-S3 ordering (the milestone
  reassessment) is what surfaced this. A corpus written from the
  spec, run against a parser written from the same spec, is a
  differential test of the SPEC — and it failed on the one
  sentence where the spec disagreed with itself.
  FOLDED: this entry; blueprint-model.md (the location table, the
  path-suffix section, the containment example, the resolution
  order example); the S2 corpus fixtures; reliquary/document.py.
  D22, D24, D26 and D27 keep their text; this entry is the
  amendment of record.

- D31 — USE-CASES.md MOVES TO THE ROOT — DECIDED (owner,
  2026-07-23). Supports P8. The use-case list joins PRINCIPLES.md
  at the repository root. THE ARGUMENT IS THE PARALLEL, already
  written into both files: PRINCIPLES.md lives at the root
  BECAUSE IT DESCRIBES CURRENT REALITY — "every principle here is
  real — the project honors it as the code stands today (it lives
  at the root for that reason)" — and USE-CASES.md makes the
  identical claim in the identical shape, implemented-only, with
  everything undelivered in its proposals doc. The two lists have
  one lifecycle, one relationship to the code, and one job as the
  surface every interface change triages against (P8, which D28
  had just made symmetric across them). Leaving one under
  `planning/` said the opposite of what both files say about
  themselves: `planning/` is maintainer-facing plans, and a list
  of what is TRUE TODAY is not a plan. The proposals docs stay in
  `planning/` on the same reasoning — being exactly the plans.
  FOLDED: the move; USE-CASES.md's own links and its
  root-placement note; PRINCIPLES.md, AGENTS.md,
  planning/INTERFACES.md, planning/ROADMAP.md,
  planning/USE-CASE-PROPOSALS.md, planning/proposed/design/recorder.md,
  this file's preamble, and the documentation-rules skill's
  placement list. Historical DECISIONS entries keep their
  `planning/USE-CASES.md` spellings under the spellings rule.

- D30 — THE MEDIA LIFECYCLE COMMANDS: THE NOUN IS THE MEDIA, AND
  TWO DEAD VERBS GO — DECIDED (owner, 2026-07-23). Supports U13,
  P6, P9.

  **There is no `delete-media`**: removing a media is editing the
  `.rlqb` that declares it. A command that deleted a declaration
  would make the blueprint file no longer the statement of what
  exists — the cache is regenerable and the declaration is the
  authored artifact, so the verb would be editing the wrong one of
  the two. `add-media` went the same way later (**D41**): supplying
  a file is authoring a declaration.

- D29 — PARTLY-OVERRULED ENTRIES ARE ANNOTATED, NEVER REWRITTEN
  — DECIDED (owner, 2026-07-23). Supports P23 — retrofitted
  2026-07-27. A convention for this record
  itself, settled on its first instance rather than after the
  second. D27 corrected one clause of D26 — the claim that the
  character class was "the whole closure, and the only test
  needed" — leaving parts A, B, C and E standing. The
  spellings rule offered no guidance for that shape: it governs
  ENTRY-level retirement and word-level drift, not a single
  wrong clause inside a live entry.
  THE RULE: an entry only partly overruled STAYS WHERE IT IS and
  is ANNOTATED — a bracketed one-line pointer at the affected
  clause naming the amending entry, every other clause
  untouched. It is the retirement note's instinct at clause
  granularity. Correcting the prose in place is NEVER the
  answer: an error and its discovery are part of the record, and
  here the most useful part of it — D26's part D listed
  `${key:-x}` as an excluded operator in the same paragraph that
  claimed the class excluded it, which is the whole argument for
  why a stated test must be testable.
  WHY THE SPELLINGS RULE DOES NOT COVER IT: that rule protects
  the record's fidelity to its own moment, and it is not licence
  to leave a WRONG INSTRUCTION standing where a reader arriving
  by search will act on it. A DATED WORD CANNOT CAUSE A BUG; A
  WRONG TEST CAN — and this one was aimed squarely at milestone
  7's next deliverable, where someone greps for the closure,
  finds "the only test needed", and ships a parser accepting
  `${mem:-512M}`. The mirror of this round's own find: a
  boundary nobody stated cannot be checked against, and a stated
  boundary that is wrong is worse than none, because it gets
  checked against and passes the wrong things.
  FOLDED: this entry; the DECISIONS preamble (the convention
  beside the retirement and spellings rules); D26 part D (the
  pointer, its first application).

- D28 — THE INTERFACE-CHANGE RULE COVERS PRINCIPLES — DECIDED
  (owner, 2026-07-23). Supports P8 (which it clarifies). The
  owner: "requests must align to principles or use cases, and a
  change in principles requires vigorous argument, just like the
  use case." HALF OF THAT WAS RECORDED AND HALF WAS NOT.
  RECORDED: demand. The ROADMAP preamble already has every item
  citing a use case (U) or a governing principle (P), "which
  drives work just as well". NOT RECORDED: the vetting side. The
  interface-change rule (INTERFACES.md) was written entirely
  use-case-shaped — "the use-case list is where interface
  changes are argued", triage "by their use-case impact", all
  three tiers use-case framed, and the hard case demanding that
  "Reliquary's use cases change". P8 mirrored it: "triages by
  its impact on the use cases". SO A CHANGE MISALIGNED WITH A
  PRINCIPLE RATHER THAN A USE CASE HAD NO PATH THROUGH THE RULE
  — while PRINCIPLES.md asserted amendments "are argued like
  interface changes", PRINCIPLE-PROPOSALS.md said its lifecycle
  "mirrors the use-case one", and D25 amended P9 explicitly
  under the rule. The practice existed; the rule never
  authorized it. The gap was live through this whole round: D25,
  D27's P15, and P14's reshaping are all principle-level changes
  made under a rule that did not mention principles.
  THE FIX: P8 is retitled "Interface and principle changes are
  vetted" and triages by impact on the use cases AND the
  governing principles; a change misaligned with either is
  argued as the amendment it requires, A PRINCIPLE AMENDMENT AS
  VIGOROUSLY AS A USE-CASE ONE, never as a feature on its own
  merits. INTERFACES.md's rule gains the principle branch
  throughout: the frame ("cannot be phrased as 'the use cases
  should say …' or 'the principles should say …'"), all three
  triage tiers, and the workflow naming PRINCIPLE-PROPOSALS.md
  beside USE-CASE-PROPOSALS.md. One line is added that neither
  document carried: THE TWO CARRY EQUAL WEIGHT, AND NEITHER IS
  EDITED TO FIT A FEATURE SOMEONE HAS ALREADY DECIDED TO BUILD.
  CLARIFICATION, NOT SUPERSESSION — and decided on evidence
  rather than taste, under the lifecycle's own test (a
  clarification is a wording edit no past citation would read
  differently under). P8 has three citations; none reads
  differently, and one reads BETTER: D27 cites "Supports P8" for
  a decision that ADDS A PRINCIPLE, precisely the case the old
  wording did not cover. So no number is retired and none is
  spent. WEIGHED AND DECLINED: superseding P8 with a new
  P-number (the lifecycle's route for a change in nature — the
  retitle and the widened subject argued for it, but the
  citation test governs, and churning a number that nothing
  reads differently is cost without benefit).
  RECORDED AS METHOD: this entry's own change was argued and
  approved before being made, which is the discipline it adds.
  FOLDED: this entry; PRINCIPLES.md (P8); INTERFACES.md (the
  rule's frame, its three triage tiers, and its workflow).

- D27 — THE INPUT MODEL, AND D26'S CLOSURE TEST CORRECTED —
  DECIDED (owner, 2026-07-23). Supports P8; **amends D26** (part D)
  and **adds P15**.

  THE CORRECTION IS THE POINT: D26 closed the string grammar by a
  test that did not hold. A closure argued from "no author would
  write that" is not closure — it is a prediction about authors —
  and the grammar has to refuse the shapes its own character class
  admits, whether or not anyone would write them. P15 was added on
  the same instinct: a rule that leans on taste is a rule that
  cannot be checked.

- D26 — THE REACH TRIM AND THE STRING-GRAMMAR CLOSURE — DECIDED
  (owner, 2026-07-23, the format re-examination round). Supports
  U4, U5; P7, P10. **Amends D18** (its HCL2 decline and its growth
  rule) and **D24** (its reach rule).

  - **HCL2 is declined structurally, not "not yet"** — it moves
    from D18's deferred column to the closed one. YAML, TOML and
    KDL stay declined on their own earlier grounds.
  - **`sha256` stays interpolable** — refusing it was weighed and
    declined; a pinned digest supplied by property is a real
    authoring shape.
  - **`${key:-x}` and its family are closed out**: the character
    class admits them, so the grammar refuses them explicitly
    rather than letting a defaulting operator arrive by accident.

- D25 — THE COMPATIBILITY HORIZON MOVES TO 1.0 — DECIDED (owner,
  2026-07-23). Supports P9 (which it amends). A principle
  amendment, argued and approved as one under the
  interface-change rule — the owner noting the irony of amending
  the standing list he had just ruled is never changed in nature
  (D23), and approving it: a clarification this is not.
  THE RULE: no backward compatibility is provided until a GA 1.0
  RELEASE (was: "at least a beta-quality release"). Through beta
  and the rest of pre-1.0, SOME effort not to break users MAY be
  granted WHEN WARRANTED — but NO PROMISES. Read into the
  operating rule, and vetoable: an effort granted once creates no
  expectation of the next, a clean break stays the default, and
  any cushion is a deliberate exception — the owner's call,
  recorded in the CHANGELOG — never a shim left to accumulate,
  because a shim nobody decided to keep is exactly what the rule
  exists to prevent.
  WHAT MOVED WITH IT: every horizon keyed to beta because it was
  keyed to compatibility — format versioning and the `$schema`
  spelling (ROADMAP "Deferred to 1.0", machine-blueprint.md,
  blueprint-model.md, instance-model.md, script-spec.md's
  format-version paragraph), and the CLI's additive-growth
  contract for machine-readable surfaces (cli.md), which promised
  at beta what the rule now starts at 1.0. The arguments were
  unchanged by the move — a pre-1.0 document has no format
  vintage exactly as a pre-beta one had none. UNMOVED: horizons
  keyed to beta for reasons of their own, not compatibility — the
  error-id INDEX (TASKS.md) is documentation polish and stays
  where it is.
  FOLDED: this entry; AGENTS.md (the normative home, its heading
  renamed); PRINCIPLES.md P9; INTERFACES.md's landing rule;
  ROADMAP roadmap-constraints and the deferral list; api.md,
  cli.md, machine-blueprint.md, media-spec.md, script-spec.md,
  blueprint-model.md, instance-model.md. CHANGELOG entries and
  earlier DECISIONS entries keep the spellings of their time.

- D24 — THE REFERENCE GRAMMAR BATTERY — DECIDED (owner,
  2026-07-23, the milestone-7 decide-first item). Supports U1, U4,
  U5; P11; G3, G6, G7. The grammar is normative in
  [blueprint-model.md](../docs/spec/blueprint-model.md): the
  reference grammar is **closed at two productions**, the character
  class screens and the productions decide, and references are
  refused outright in identity and graph positions and in the
  closed vocabularies.

  The durable part is *why closed*: an open grammar cannot say what
  it refuses, so every extension would arrive as a silent
  reinterpretation of text that already parsed. A media name may
  lead with a digit where a property key may not — the `@` sigil
  classifies the token, while a property key also appears bare at
  its declaration, where a leading digit would lex as a duration.

- D23 — THE USE-CASE LIFECYCLE, AND NO STUB — DECIDED (owner,
  2026-07-23). Supports P8, P23. The machinery it settled is
  normative in [README.md](README.md) — the three locations, the
  clarify/retire/supersede moves, the one global U-sequence — and
  is not restated here. Two rulings have no other home, and both
  are cited downstream:

  - **NO STUB.** A retired or superseded number leaves nothing
    behind: the gap in the sequence *is* the history, and a
    successor names what it carries forward so citations still
    resolve. This is what "no stub, D23" cites, and it is why a
    dead proposal's number is spent rather than reused.
  - **"Deprecated" is rejected** as the vocabulary. A use case is
    *retired* (dropped) or *superseded* (replaced, successors
    named); deprecation implies a grace period this lifecycle does
    not offer.

  WEIGHED AND REVERTED: a separate `planning/ISSUES.md`. The issue
  tracker is the open door and this directory is the project's own
  voice; a third intake here would have split triage across two
  registers.

- D22 — THE BLUEPRINT REVISION ROUND — DECIDED (owner,
  2026-07-23, the second same-day round, superseding the
  four-component shape of the media/composition round before any
  of it was implemented). Supports U4; P10. The shape is normative
  in [blueprint-model.md](../docs/spec/blueprint-model.md).

  Kept: **child-side-only containment** — dropping the batch
  `children` form — was declined as sugar over the one semantic
  rather than a second semantic, so `children` desugars to
  child-declares-parent and both spellings stay.

- D21 — CODEX NAMING: A LAUNCHING POINT, NEVER A VERSION LIBRARY —
  DECIDED (owner, 2026-07-23, closing the open point from the
  generic-blueprint walkthrough). Supports U11; P11 — retrofitted
  2026-07-27. No versioned items in the
  codex — generic `openbsd`, generic `freedos`; "the codex is a
  launching point for real blueprints only" (owner). Entries
  are named for the system; the version lives inside the file
  as the source component's URL and hash (the two-field bump),
  so a codex version bump is a content update under an
  unchanged name, reaching new seeds only — the never-overwrite
  rule keeps existing copies the user's. Concurrent versions,
  pinned vintages, and variants are user/project territory:
  seed, rename, make it real — which dissolves the coexistence
  case that motivated version-bound names. Scripts are named
  for the flow they drive (`freedos-install`), never a release:
  the branching-wait design spans versions by observation, and
  a script's supported span is legible in its own handlers. The
  split rule (generic by default, version-bound on deliberate
  coexistence) was the recommendation; the owner went stronger —
  coexistence in the codex is simply out. The `-plain` variant
  marker dissolves with it: the launching point IS the plain
  install, and variants belong to users. SCOPE (owner): entries
  keep nominal version control points where easy — the adjacent
  url+sha knobs, seam comments pointing at them — acknowledging
  version churn; but the codex NEVER promises a comprehensive
  guaranteed-working asset set across systems and versions
  ("impossible!"): an entry is tested as shipped against the
  one release it tracks; a bumped copy is the user's, aided by
  fail-closed verification and observation-driven scripts,
  warranted by nothing. REALIGNMENT AHEAD (per
  the no-BC rule): `freedos-1.4-plain.rlqb` → `freedos.rlqb`,
  `freedos-1.4-plain-install.rlqs` → `freedos-install.rlqs`,
  and the mentions across script-spec (the reference-script
  pointer), machine-blueprint.md, and cli.md follow at
  implementation realignment. FOLDED: codex.md (the doctrine
  under Naming conventions; the table examples; both
  `run-script` examples).

- D20 — THE DECLARED DERIVATION RANK — DECIDED (owner,
  2026-07-23), settling the forks D19 left pending. Supports P7,
  P13. Normative in
  [script-properties.md](../docs/spec/script-properties.md).

  A declared `default=` derivation ranks **below** every supplied
  source and **above** the interactive ask: it is the script
  author's fallback, so anything the operator actually supplied
  beats it, and it exists precisely so the ask is not reached. Host
  facts (`rlq.*`) are unanswerable-when-empty rather than empty
  strings — a blank username is not an answer, and silently binding
  one produces a run that fails somewhere later.

- D19 — PROPERTY SOURCE MODEL: THE ORDER IS CLOSED, THE SEAMS ARE
  NAMED — DECIDED (owner, 2026-07-23). Supports P7, P13, P21.
  Normative in
  [script-properties.md](../docs/spec/script-properties.md).

  **The source order is closed**, and that is the ruling: a value's
  provenance is a fixed, statable sequence rather than a search
  that stops when something is found. An open order cannot be
  reported — the dry run's `describe_sources` names each key's
  source only because there is one answer to name — and a caller
  debugging a wrong value needs the *rule*, not the outcome.

  Implementation is **bespoke** rather than a configuration
  library: the layering is small, the semantics are the project's
  own, and a dependency would have to be bent to match them (P21).

- D18 — BLUEPRINT FORMAT: THE COMPUTATIONAL-GROWTH RULE — DECIDED
  (owner, 2026-07-23). Supports U4, U5; G2. **Its prior JSONC
  choice is superseded by D102; amended by D26**, which moved HCL2
  from deferred to closed.

  THE GROWTH RULE, which is the durable half: a construct that
  *enriches values* may land as plain data expanded by reliquary;
  **general computation never enters the JSON tree**. It would
  arrive only as a layer producing plain blueprints — generation
  above via the embedding API, or a separately specified evaluation
  layer (Jsonnet the candidate).
  In-tree function objects and string templating are permanently
  rejected: a blueprint that computes is a blueprint no tool can
  read without running it.

- D16 — BLUEPRINT `name` FIELD REINSTATED — DECIDED (owner, 2026-07-22),
  reversing the 2026-07-21 drop. Supports U11 — retrofitted
  2026-07-27. `name` returns as an optional
  human-readable display name for the blueprint, distinct from the
  file-stem identity: the stem stays the one selection key
  (`--blueprint <stem>`) and a machine's id stays `<stem>-<n>`, so
  `name` never selects, never renames, and does not affect machine
  behavior — it feeds `search` alongside `description`, appears in
  listings where a friendlier label than the stem helps, and is
  resolved into the state. WHY: owner — "name should be part of the
  spec, we'll regret not having it at some point"; reserving a
  display label distinct from the stem is cheap now and a naming
  freeze is free before v1, never after (the reserve-space
  principle already recorded here). The original drop's concern (a
  second name can drift from the stem and duplicate the
  description) is accepted as a UX caveat, not a reason to omit the
  field — tools fall back to the stem when `name` is absent. FOLDED:
  machine-blueprint-reference.md (new `name` section; the
  `description` section's "there is no display-name field" claim
  removed and `search` now matches `name` too),
  machine-blueprint.schema.json (`name` property). The
  implementation already carried `name` (the drop was never coded),
  so the milestone-6 field-validation task keeps it and the codex
  `freedos-1.4-plain.rlqb` `name` stays valid.

- D15 — MILESTONE 6 DECIDE-FIRST ROUND — DECIDED (owner, 2026-07-22):
  Supports U1; P8 — retrofitted 2026-07-27.
  The three "Decide first" questions ROADMAP milestone 6 gated its
  implementation on. Interface triage (planning/INTERFACES.md): the
  state ops and the blueprint format are world-facing interfaces;
  Q1 confirms already-specced, use-case-aligned behavior (U1's
  install pattern and mid-run media swaps), Q3 tightens validation
  with no use-case impact (easy approval), Q2 changes no interface
  (internal policy) — no use-case amendment.
  - Q1 RUNNING-MACHINE RECONFIGURATION: insert/eject are
    running-or-stopped, set-boot and apply stopped-only. Hot media
    changes are ALLOWED — an `insert`/`eject` on a running machine
    is a live media change the guest observes; on a stopped
    machine it is a pure state edit reconciled at the next
    `start`. This CONFIRMS the existing contract
    (script-spec.md "Insert and eject": "Both verbs work on a
    running machine ... and on a stopped one"; cli.md / the CLI
    gap-queue item 3's "running-or-stopped for insert/eject"), not
    a change to it. `set-boot` stays stopped-only (a launch-time
    firmware order — no live effect) and `apply` stays stopped-only
    (memory/cpus/drives are hardware topology). Uniform
    stopped-only was WEIGHED AND DECLINED (the recommendation): it
    would have contradicted the already-specced running-or-stopped
    rule and the script language's own live-dispatch semantics,
    where a script drives a running guest and swaps media mid-run.
    CONSEQUENCE — an implementation gap, not a spec change: today's
    `machines.py` guards insert/eject as stopped-only (the
    milestone-1 shortcut), so the milestone-6 work must grow a
    live-QMP change path (identity-verified session) when the
    machine is running, and AGENTS.md's "all three require a
    stopped machine" line is that shortcut, corrected when hot
    insert/eject lands.
  - Q2 CONCURRENT MACHINES: no home-wide limit on machines running
    at once. The per-machine lock and per-start identity model make
    concurrency safe — each machine is its own cache directory,
    backend process, and auto-allocated port — so the honest
    ceiling is host resources (memory, free ports), surfaced as an
    ordinary `start` failure. A configurable cap was WEIGHED AND
    DECLINED: policy surface with no invariant behind it. Folded:
    instance-model.md ("The machine state").
  - Q3 SIZE/BASE ON CDROM: rejected. A `cdrom` drive's only content
    source is `media` (or the empty `null`) — the read-only optical
    medium has nothing to size, difference, or synthesize, so
    `size`, `base`, and `hostdir` all require a writable medium
    (`hdd`/`floppy`), symmetric with `hostdir`'s pre-existing cdrom
    prohibition. This closes the JSON-schema round's open find (the
    schema encoded only the stated rules, and the field reference's
    "meaningful for hdd and floppy" did not prohibit elsewhere).
    Leaving it permissive was WEIGHED AND DECLINED (a nonsensical
    blank/writable-optical shape validating). Folded:
    machine-blueprint-reference.md (`size`, `base`, and the Values
    rule), machine-blueprint.schema.json (`cdromDrive` drops
    `size`/`base`, requires `media`). Enforced in `blueprint.py` at
    the field-reference-validation task.
  Folded across: planning/TASKS.md (the milestone-6 task list — T0
  landed), instance-model.md, machine-blueprint-reference.md,
  machine-blueprint.schema.json.

- D14 — MILESTONE INJECTION: LOCAL HTTP SERVER FOR INSTALLER ANSWER
  FILES — DECIDED (owner, 2026-07-22). Supports U1, U4, U5; G1 —
  retrofitted 2026-07-27. A new ROADMAP milestone 5
  lands Packer's ephemeral local HTTP server for Kickstart /
  preseed / AutoYaST / `unattend.xml` and kin
  (docs/spec/http-serve.md). Former milestones 5–12 renumber
  to 6–13. Interface triage (planning/INTERFACES.md): strong
  alignment with U1 and with U4/U5 where those answer files are
  the installer's native path — easy approval; no use-case
  amendment. Surfaces named: scripting language, CLI/API (run-
  scoped server lifetime), authored-asset layout. Distinct from
  the deleted property-binding "response file" concept (same
  file, THE RESPONSE CONCEPT DELETED). The "Procedural and
  declarative" ROADMAP prose is amended: where answer files
  exist they are served Packer-style rather than competed with;
  G1 remains the agentless control-plane rule, not a ban on the
  installer's own answer-file path. Historical DECISIONS entries
  keep the milestone numbers of their time; forward-looking
  pointers in ROADMAP, TASKS, and design status notes move with
  the renumber. Folded: ROADMAP (synopsis, procedural/declarative,
  milestones 5–13, Horizon, guest-communication closing),
  docs/spec/http-serve.md (new), TASKS forward refs,
  backend-adapter / guest-communication / landmarks status
  banners.

- D13 — PARSER: OWN LEXER + LARK PARSER — DECIDED (owner,
  2026-07-22), following the no-JSON-in-scripts round that made it
  possible. Supports P21 — retrofitted 2026-07-27. The grammar lives in Reliquary/script_grammar.lark,
  mirroring script-spec.md's normative EBNF; Reliquary's own
  tokenizer feeds it through a custom lark lexer. Evidence from
  three probes:
  - a lark grammar carries the whole typed EBNF — headers,
    property declarations, phases, branching waits, reactive
    phases, every action — in ~45 lines under LALR(1). Before the
    island was deleted it could not parse a script at all, which
    is what changed the answer
  - lark's OWN lexer was WEIGHED AND DECLINED: its diagnostics are
    terminal-level ("No terminal matches '4'" where Reliquary's
    says "invalid duration: '45' (durations carry a unit: ms, s,
    m, or h)"), and on one case it mislabelled `timeout` as a
    keypress name. match_examples recovered only 4 of 7 authored
    messages, failing whenever the same mistake followed a
    different verb — it matches parser state, so the corpus grows
    as mistakes × contexts and degrades silently in the gaps
  - the hybrid keeps both: verified that all lexical diagnostics
    survive verbatim through the lark layer
  - `press enter` broke the first attempt — `enter` is both a verb
    and a key name, and a context-free lexer must type it before
    the parser knows it is in `press`'s arguments. Keywords are
    therefore recognized only in node-name position, which is what
    script-spec.md already prescribes ("slot, key-name, and
    machine-state values are name tokens whose closed vocabularies
    are checked by validation, not the grammar")
  - RULE ADOPTED: the grammar owns node names and positional
    argument types; modifiers are uniform in the grammar and
    checked against per-node signatures in the transformer, which
    can name the node and list what it accepts; the S-numbered
    rules stay above the grammar. Encoding S8's two-handler
    minimum in the CFG was tried and reverted — the error became
    "Unexpected token _BLOCK_CLOSE" at the closing brace instead
    of naming the wait. script-spec.md's choice to enforce S-rules
    "over the parse tree rather than encoded in the CFG" is what
    protects the diagnostics, not an implementation detail

- D12 — NO JSON IN SCRIPTS — DECIDED (owner, 2026-07-22).
  Supports U6; G7 — retrofitted 2026-07-27. A script
  carries no embedded assets. The `media <label> { ... }` block
  and the `landmark <name> { ... }` block are both deleted;
  media definitions (`.rlqm`) and landmark declarations (`.rlql`
  plus `<name>.<n>.png` renderings) are authored files of their
  own, resolved beside the script under authored-asset
  resolution and referenced by `@name`. Folded into
  script-spec.md (the "Embedded media definitions" and
  "Installation into the media library" sections deleted, the
  island removed from the core grammar and the normative EBNF),
  media-spec.md, landmarks.md (the embedded form deleted),
  ROADMAP, INTERFACES, USE-CASES U6 (amended), and the
  implementation (the parser's media handling, `EmbeddedMedia`,
  and the node layer's island machinery deleted). The round
  records:
  - the trigger: the install model read as an awkward bolt-on.
    Three separable costs were named — the JSON island as the
    sole exception to the lexical model, the install protocol
    (five-step transactional write, collision and coalescing
    rules, partial-overlap errors, `fetch-media --script`), and
    the label/item split (residual problem [06], where the label
    named an installed file and `@` named an item inside it)
  - deleting media blocks alone was WEIGHED AND DECLINED: it
    would not have removed the island, since embedded landmark
    blocks (landmarks.md, "the same JSON schema as `.rlql` plus
    inline base64 variant data") reinstate it at milestone 12,
    and it would have left two analogous authored assets with
    opposite bundling policies
  - deleting the install while keeping the blocks was WEIGHED
    AND DECLINED for the same reason: it removes the protocol
    but keeps the lexical exception
  - the decisive arguments for deleting both: the island is the
    only carve-out in the node grammar and its removal makes the
    surface uniform and LL(1) end to end; a script is UTF-8
    text, so an embedded rendering must be base64 — measured at
    roughly 12:1 to 100:1 payload-to-procedure for a
    twenty-landmark GUI workflow, and the design had already
    flinched at this with its open "trailing assets zone"
    question; and embedding permanently freezes the asset
    format, since anything carried in a text script can never
    become non-text (the `.rlql` non-text form stays possible
    only if declarations live in files)
  - the "no second schema" justification for embedding was found
    already broken in the small: `.rlqm` files are JSONC while
    the embedded island was strict JSON, because brace tracking
    could not survive a comment — the host format had already
    forced the embedded form to accept less than the file form
  - the single-file-workflow property is GIVEN UP knowingly. Its
    cited support did not hold: U4 describes "the repository
    carries only blueprints, media definitions, and Reliquary
    scripts", a side-by-side repository, and U1's one-command
    path seeds three separate codex artifacts. The real loss is
    casual sharing (pasting a whole workflow into a gist or an
    issue), which was already lost for anything with landmarks;
    a bundle format outside the language stays available as
    additive growth (G7)
  - consequences folded: the label loses its only job, closing
    residual problem [06]; `fetch-media --script` and
    `fetch_media(script=)` are deleted; check-script's
    prospective embedded-media validation and its "writing to
    `media/`" carve-out go; ROADMAP milestone 5 loses
    embedded-install targeting; the recorder emits its draft as
    script plus asset files, one mode instead of two

- D11 — THE JULY 2026 SCRIPT-LANGUAGE REDESIGN — DECIDED (owner,
  2026-07-21). Supports U6; G2, G3, G7. The redesign is normative
  in [script-spec.md](../docs/spec/script-spec.md), which carries
  the typed EBNF and every rule this round settled — so the design
  itself is not restated here. What the entry is for is the shape
  of the change: the old grammar could not parse the reference
  script, and the answer was a statement model replacing the
  terminal production rather than a patch to the productions that
  failed. Later rounds amended much of the detail (D24 the
  reference grammar, D26 the reach and string rules, D60 pacing);
  read the spec, never this entry, for what the language is.

- D10 — GUIDING-PRINCIPLES GAP QUEUE — DECIDED (owner,
  2026-07-21, the necessity/sufficiency panel walked adversarially
  per use case). Supports U1, U2, U4, U5, U6, U14; G2, G3.
  VERDICT, which is the durable part: **the primary application
  surfaces are necessary and minimal** — every gap the panel found
  was a spec lagging the principles rather than a missing surface,
  and each was closed into its spec by the realignment pass. The
  work list itself is spent; the finding is why no surface was
  added to close a gap.

- D9 — BLUEPRINT-SPEC GAP QUEUE — DECIDED (owner, 2026-07-21).
  Supports U2, U4. A work list against the media and blueprint
  specs: the media spec tracked the principles closely and the gaps
  clustered in the blueprint spec. Every item closed into
  [blueprint-model.md](../docs/spec/blueprint-model.md) and the
  blueprint guide/reference, which are normative; nothing was
  refused, so nothing else survives the landing.

- D8 — CLI DESIGN GAP QUEUE — DECIDED (owner, 2026-07-21).
  Supports U1, U3, U4, U14; P6. VERDICT: the two-layer lifecycle
  vocabulary, the parity doctrine, the selection failure modes and
  the no-prompt discipline are sound; the gaps were unnamed
  conventions, and every one has since landed in
  [cli.md](../docs/spec/cli.md). Kept here: the spellings weighed
  and refused, because each is a plausible re-raise.

  - **`run` → `runs`** — declined: no meaning is gained, and `run`
    names run records exclusively.
  - **`--format`** — declined as YAGNI; a pre-beta conversion stays
    free if one is ever wanted.
  - **`--as`** for the new blueprint's name — declined because
    `as=` is a Python keyword; `--name` mirrors as `name=` in every
    binding language.
  - **An explicit `--stdin` flag, and a hybrid** — declined: one
    spelling and zero new surface beat two, and a secret never
    travels as an argv value (process listings, shell history).
  - **The suffix trio** `--blueprint-name` / `--machine-number` /
    `--machine-id` — declined: deletion beat addition.

- D7 — API DESIGN GAP QUEUE — DECIDED (owner, 2026-07-21).
  Supports U14; P6, P7. VERDICT: the twin-name identity rule, the
  `--json` twin's-return rule, pull-only handles and the
  named-omission discipline are sound; the gaps were unnamed
  conventions and unnamed twins, all since homed in
  [api.md](../docs/spec/api.md). The refusals, which are what a
  later round would otherwise re-raise:

  - **A mechanical CLI↔API mirror** — declined: parity binds the
    pair, not each function alone, so a flag need not become a
    parameter of the same name.
  - **`open_run` / `get_run`** — declined for `attach_run`, the
    doctrine's own verb: sync is async plus attach.
  - **A full error-domain tree** — declined as speculation ahead of
    demand; classes grow additively and never as a break. Strict
    `Error`-suffixing declined with it.
  - **A CLI-owned mismatch checkpoint** — declined: the error names
    one file while a refetch is the caller's call.
  - **`cancel()` on drop, and Python `with`-sugar cancel** — both
    declined: GC timing carries no semantics in any binding, and
    the sugar is the same trap opted into. A handle is a follower,
    never an owner.

  The async surface these shape is **F6**, deferred to the backlog
  and unbuilt; the refusals stand with its design.

- D6 — GAP-CLOSURE DESIGN QUEUE — DECIDED (owner, 2026-07-21).
  Supports U1, U5, U6, U14; P6, P7; G2. The five gaps the
  principles queue left standing, worked in leverage order. **Most
  of what it settled has since been deleted rather than shipped**:
  the run-record half — `transcript.txt`, the records archive,
  `--detach` — went with **D36**, and the export half sits unbuilt
  on the Horizon, so those rulings and their refusals guard nothing
  that exists. What survives is what still has a subject:

  - **An outcome line on stdout** — declined as scraper bait. The
    stdout discipline it protects is now S7's.
  - **Direct console-device access for prompting** — declined as a
    platform seam; prompt text goes to stderr and the answer comes
    from stdin.
  - **A writable/read-only flag on a host directory** — declined
    explicitly as *an agent invention the owner never asked for*.
    Recorded because the refusal is about provenance rather than
    design: an unrequested capability does not enter by being
    plausible.

- D5 — THE RUN-COLLECTION DROP — DECIDED (owner, 2026-07-22, the
  out-of-band round; an owner revisit of gap-closure items 2 and 3
  settled through "what use case cannot be met without it?" —
  answer: none; the mechanism was custody and ergonomics, never
  capability; U6 verified untouched — console capture in, authored
  files out). Supports U14 — retrofitted 2026-07-27; the entry
  argues from U3, which D51 retired into U14, and the "U6
  verified untouched" note is a check that nothing broke, not a
  demand. DROPPED wholesale: the `results` header,
  `stage`/`collect` (S15 and the language's only host paths die
  with them — example 05's two-worlds question dissolves: strings
  are guest text only), the CLI pair stage-files/collect-files,
  and record custody — runs/<n>/output/ leaves the record; a
  record is the event stream + transcript + screenshots
  (INTERFACES "Recorded outputs" updated). FILE EXCHANGE IS
  OUT-OF-BAND: while a machine is stopped on every control plane
  its drives are plain host state (a hostdir drive is its
  directory; images are the user's own tools' business);
  Reliquary neither mediates nor records it; the contract with
  its edges (running drives untouchable, media cache read-only
  by doctrine, runs/ append-only, machine state files
  Reliquary's own) is in instance-model.md "The machine
  directory and out-of-band access". NEW QUERY:
  get-machine-dir / get_machine_dir(machine=|blueprint=) — the
  machine's cache directory as an absolute path; any phase,
  standard selectors, --json serializes the string. DEFERRED
  with a roughed shape (ROADMAP "Horizon"): in-band
  list-files/get-files/put-files (twins list_files / get_files /
  put_files), <drive-key>:<path> addressing, at-rest
  capability-honest per call, media excluded, recursive, no
  custody; details (e.g. get-files' destination default) belong
  to that milestone's own round; value concentrates where
  out-of-band thins (non-QEMU backends — no hostdir — and
  non-FAT filesystems), so sequence at or soon after the second
  backend. [**That deferral is closed refused, not pending**: the
  in-band family was built (D62) and then deleted by **D108**,
  which put a machine's file content outside Reliquary's purview.
  The out-of-band door this entry created is now the route rather
  than the fallback.] Named cost accepted: per-iteration artifact history
  is the caller's to keep (U3 already makes the caller the
  interpreter). Use-case triage: no amendment — strong U3
  alignment (interpretation on the agent's side; the record is
  evidence, not a warehouse). Folded: script-spec (action list,
  strings table, header table + prose, grammar, S15 removed —
  S1–S14, severability, event-stream transfer bullet, preflight
  list, "File exchange — a named omission" replacing the
  stage-and-collect section, run-directory tree, per-test
  paragraph, bundle note), cli.md ("The machine directory"
  replacing "File exchange", machine-scoped command list,
  media-naming prose), api.md (surface table row, realignment
  note), ROADMAP ("The CLI" state-ops paragraph + synopsis,
  script-section offline paragraph, primitive-vocabulary list,
  interaction-runs custody phrase, spike-8 out-list, realignment
  deliverable 3, control-plane vvfat note, the Horizon bullet),
  INTERFACES.md (recorded outputs), instance-model.md (new
  section), machine-blueprint.md (runs/ contents twice),
  machine-blueprint-reference.md (hostdir prose + division of
  labor), codex.md (naming prose), planning/design/script-examples/05 rewritten
  as a regression note + README row. Gap-closure items 2 and 3
  annotated SUPERSEDED IN PART above
- D4 — THE USER-PROPERTIES DESIGN ROUND — DECIDED (owner,
  2026-07-21, the docker-comparison round). Supports U1, U4, U5,
  U14; P13. The shape it settled is normative in
  [script-properties.md](../docs/spec/script-properties.md) and
  cli.md;
  what is kept here is the refusals, each a guard against a
  re-raise, restated in today's spellings.

  - **"Registry" is reserved, not rejected.** The concept is *user
    properties*; "registry" reads as a remote artifact-distribution
    service (docker/npm/OCI) and stays free for a future sharing
    service.
  - **Blueprint-only wiring** (compose-style, the script naming no
    key) — declined: every blueprint would re-wire universal keys.
    A script may suggest a key and a blueprint parameter replaces
    it.
  - **`RELIQUARY_<KEY>_PROPERTY`** (suffix form) — declined for the
    prefix `RELIQUARY_PROPERTY_<KEY>`: a grep-able common prefix
    and a self-evident reserved namespace.
  - **One packed environment variable** — declined: it needs a
    quoting grammar, collides with `RELIQUARY_PROPERTIES`, loses
    one-secret-one-variable CI injection, and sits inside platform
    environment-block size limits.
  - **A layer above the home's file** — declined: project defaults
    are blueprint parameters' job, and `--properties` *replacing*
    the home's file is the hermeticity tool, so nothing personal
    reaches a project-controlled run.
  - **Ordinary-only environment** (env barred from secret-bound
    keys) — declined as a refusal that gets worked around; env may
    carry one, in the named warned-plaintext class. Argv never
    does.
  - **JSON and TOML for the file** — declined: every other property
    layer speaks `key=value`, and TOML's dotted keys nest while
    rewrite fidelity would need a dependency. `user.properties` is
    the filename for editor recognition, against the round's own
    recommendation of `properties.rlqp`; the spec names the caveat
    that this is *not* Java properties — no unicode escapes, no
    continuations.
  - **A bulk values file** — declined: repeatable flags and the
    API mapping cover it, and growth stays additive.

- D3 — JSON SCHEMAS FOR THE AUTHORED FORMATS — DECIDED (owner, 2026-07-21,
  design round; all three forks settled on the recommendations).
  Supports U4; P9 — retrofitted 2026-07-27:
  - planning/design/machine-blueprint.schema.json +
    media-definition.schema.json AUTHORED (draft 2020-12,
    self-contained, strict JSON, REUSE.toml-covered; spec examples
    verified against both — 32/32): synchronized companions — the
    prose specs stay normative, schema-valid never implies valid
    (per-document structural subset only; cross-document rules and
    the capability tier stay prose); one media schema covers both
    homes (library file + embedded block, the same forms)
  - $schema field: the formats stay CLOSED pre-beta — a pinned
    schema reference is a version field in disguise; editors bind
    by file association, which tracks the installed Reliquary;
    $schema-as-versioned-URL recorded as the leading candidate
    spelling of the version field at beta (ROADMAP "Decisions
    still needed")
  - validator: the parser stays Reliquary's validator (fail-closed
    diagnostics); a shared valid/invalid fixture corpus runs
    against both parser and schema — at realignment, with the
    static-conformance corpus already queued there
  - spec pins landed with the fold: boot entries unique by slot;
    control-planes entries unique; sha256 hex accepted in either
    case, canonical writes lowercase
  - deferred: machine-state schema + publication mechanics
    (milestone 3 item 6); media/item name, script-label, and
    input-name grammars stay open with the asset-spec work (the
    schemas say non-empty string)
- D1 — RESOLVED (owner, 2026-07-21). Supports (none) — a
  vocabulary decision; no use case or principle demands what a
  thing is called, and the naming class is outside the
  traceability rule's reach (retrofitted 2026-07-27).
  [Amended 2026-07-28 — Supports P18. The naming half of that
  clause stands — no principle demands what a thing is
  called — but this entry settled more than a name. "Canon" was
  rejected for naming an abstract authority where "codex" names
  a bound volume copied from, and that distinction is what P18
  states in its own words: a library of examples, read and copied
  from, never one to build on. P18 was clarified the same day to
  say so about the codex outright — meant to work, never stable,
  names and content alike free to change in a point release, and
  there to start a consuming project's own assets rather than to
  be depended on — which is the principle this entry had none
  of. A
  clarification rather than an amendment (P23's first
  exception): P18 never claimed the codex was stable, so stating
  that it is not changes the reading of no earlier decision.] The
  built-in library is named THE
  CODEX (was "change 'builtin library' concept to 'template
  library' ??"; "canon" was weighed and rejected — codex is the
  artifact, a bound volume copied from, where canon is the
  abstract authority/list) — folded across INTERFACES, USE-CASES, ROADMAP,
  AGENTS, CONTRIBUTING, cli.md, README, and docs
  (builtin-library.md renamed codex.md); Reliquary/builtins/
  package dir renames to codex/ at implementation realignment

## Retired decisions

Overruled or no-longer-relevant decisions. A retired decision binds
nothing, and it is kept only where it still has **teeth** — where
the position it took is one someone could plausibly re-raise, so
the record of its refusal is doing work. One whose subject no
longer exists, or whose surviving insight the overruling entry
already carries, is struck outright rather than kept as furniture;
a gap in the sequence is the history, and git holds the text.
Reopening a retired decision is argued through the surface-change
rule.

- D62 — RETIRED (overruled by D108) — THE IN-BAND FILE FAMILY IS
  COMPLETE; P16 IS ARMED. Supports U14, U20; P16.

  **Kept because its position is the re-raisable one**: that P16
  obliges Reliquary to carry a file across the host/guest boundary,
  which is what armed the principle here and what D108 declined.
  Under the carve-out, a machine's file content is out of purview by
  design, so the five verbs are gone and no use case demands them
  back. Its address ruling — one form for files and directories
  alike, the drive root sayable — died with the letter map it was
  written against, and D5's `<drive-key>:<path>` shape stays dead
  too: nothing addresses inside a volume at all.


- D91 — RETIRED (overruled by D93 the same day it was decided and
  delivered) — A DEVICE IS A DECLARED MODEL, JUDGED AT ASSIGNMENT.
  Supports U22, U4, U14; P8, P10, P11.

  **Kept because P25 and D93 both cite it**, and because its
  refusal is the re-raisable one: a device vocabulary admitted on
  *one* backend's say-so. D91 built exactly that axis and D93
  removed it, replacing the bar with general applicability across
  backends — what one backend alone provides stays behind that
  backend's pin in `backend-settings`. The growth rule D91 got
  right survives in P25: the vocabulary is what demand has asked
  for, never what a backend happens to expose.

  Its own naming refusal stands: **`virtio-rng-pci`** is QEMU's bus
  spelling, not a portable device name, and a vocabulary that
  admits one backend's spellings is the axis D93 closed.
