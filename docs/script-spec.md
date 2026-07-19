<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The script spec

> **Status:** this documents the planned reliquary script format.
> The scripting language is not implemented yet; details may still
> change before first release.

A reliquary script automates a guest: it types at it, watches its
screen, swaps its media, and moves files across the VM seam.
Scripts live in `<reliquary_home>/scripts` — one text file per
script, named `<name>.rqs` — and run against a named machine:

```text
<reliquary_home>/scripts/
└── freedos-plain-install.rqs
```

```powershell
reliquary script msdos freedos-plain-install
```

`script` starts the machine if it is not already running, then
executes the script in order. The machine stays running when the
script ends unless a step stopped it — no command implicitly
tears a machine down.

Scripts follow the same ownership philosophy as
[machine declarations](machine-spec.md) and
[media definitions](media-spec.md): a script is a small, authored
file you own — reliquary reads it and never writes it — worth
versioning and sharing alongside the media definitions it relies
on.

## The model

A guest being automated — an installer especially — is a
sequence of moments where it needs information: a menu choice, a
keystroke, a command, a disk swapped in. A script is that
sequence written down, and every statement serves one of two
roles:

- **inputting the information** — `enter`, `type`, `press`,
  `select`,
  `run`, `attach`/`detach`, `stage`; or
- **knowing when the right time is to input it** — `wait`,
  `on`, `expect`: the observation that the guest is ready.

Put shortly: the script **watches and inputs**. A watch point,
when it matches, triggers one of two things:

- **input events** — the statements that follow an ordered
  `wait`, or the action of a reactive
  [`on` handler](#on--reactive-condition-action-pairs); or
- **a state transition** — a [`->`](#transitions) on a handler
  or in a state body, an
  [`expect`](#expect--branch-on-what-appears) choosing its
  branch, a bare `wait` advancing the sequence.

Nothing else ever happens: no watch point computes, stores, or
decides beyond these two consequences, which is what keeps a
script readable as a plan.

Beneath the verbs, every input reduces to **input events** — the
small portable vocabulary of primitives a guest actually
receives: key press and release today; pointer move and button
press and release when the GUI era arrives. Verbs state intent
(`enter` a command, `select` an entry); the selected control
plane
composes and delivers the events, owning their pacing — old
guests drop input delivered at host speed, and feeding them at a
survivable rate is the control plane's job, never the script's.

In an **ordered sequence**, watching and inputting are separate
statements — wait for the screen, then answer it:

```rqs
wait "What is your preferred language"
select "English (United States)"
```

In a **reactive context**, the two fuse into the
condition–action pair — one line, condition then action:

```rqs
on "Drive C: does not appear to be partitioned.": select "Yes"
```

Either way: one observed right time, one delivery of input. This
is why the language has no blind delays and no sleep verb —
timing comes from watching the guest, never from guessing — and
why everything else in the vocabulary (`screenshot`, `collect`,
lifecycle verbs) is supporting cast around delivering input at
the right time — not the point of the language.

Seen whole, the guest is a **state machine**, and the script is
that machine written down:

- **[States](#state--ordered-body-ambient-handlers)** hold an
  ordered body — the sequence for that phase — plus reactive
  handlers, each armed at its position in the body and active
  until the state ends.
- **[Transitions](#transitions)** (`->`) move between named
  states: on a handler ("when this screen appears, answer it and
  go there") or in the body ("at this point, go there"). An
  installer phase that loops — a mid-install reboot replaying
  the same menus — is a transition back to the state that
  handles them: the loop is drawn, not duplicated.

Reactivity is always **scoped to its state** — there are no
global "whenever X, do Y" declarations and no open-ended
dispatch loop. The machine is finite, explicit, and fully
written down, and the transcript records the route actually
taken: every state entered, every handler fired, every
transition followed.

The model is also what makes the GUI era an extension rather
than a redesign: image matching is a new way of *knowing when*,
and pointer input a new way of *inputting* — new observations
and new inputs slotting into the same rhythm.

## Its own syntax — and not a programming language

Scripts are a **line-oriented text format**, not JSON and not a
general-purpose language. Machine declarations and media
definitions are data, and stay JSON; a script is sequential
prose — read top to bottom, one statement per line — and gets a
syntax built for that:

- **Comments.** `#` starts a comment (own line or end of line) —
  installer scripts need margin notes ("this menu replays after
  the reboot"), and a data format has nowhere to put them.
- **Text is just text.** A watch pattern is the literal screen
  text you are waiting for; nothing in it needs escaping.
  Matching by regular expression is the opt-in exception
  (`wait regex "…"`), not the default.
- **The pair fits on a line.** `on "…": select "Yes"` is the
  condition–action pair exactly as the model describes it.

The syntax is small and parsed fail-closed: a malformed line
rejects the script before step one, naming the line and what was
expected.

What the language deliberately is **not** is programmable. There
are no variables, no expressions, no arithmetic, and no loops
beyond drawn state transitions:

- **Deterministic and inspectable.** A script is a fixed,
  finite machine; the guest chooses the route, never the
  meaning. When a run fails, the transcript names the failing
  line — quoted verbatim — plus the screen state and a
  screenshot. Scripts must be debuggable from the transcript
  alone.
- **Backend- and control-plane-agnostic.** A statement says
  *what* — "wait for this text", "run this command" — and the
  machine's backend and selected
  [control plane](machine-spec.md) decide *how* it is observed
  or delivered. Nothing in a script names a hypervisor.
- **Small on purpose.** The language exists to sequence guest
  automation. Anything computational — deciding *which* script
  to run, generating inputs, parsing collected results — belongs
  in Python via the embedding API, which remains a first-class
  surface. A Python program that calls three scripts with logic
  in between is the intended shape for complex jobs, not a
  bigger script language.

One script, one target: each OS version and edition gets its own
install script. There are no parameters to mutate a script's
behavior — a script that would need flags should be two scripts,
or Python.

## A first example

A script that boots a machine to a DOS prompt and runs a program
staged on its virtual FAT drive:

```rqs
description: Run CHKDSK and capture the output
platform: dos

wait "C:\>"
run "chkdsk c: > d:\chkout.txt"
screenshot
stop
collect chkout.txt results/
```

A script is header lines followed by statements, one per line
(states and other blocks in braces, as shown below). Statements
run strictly in order; the first that fails ends the script.

## The script file

### Header

Header lines come before the first statement:

- **`description: <text>`** — optional. One line saying what the
  script does; shown when the script runs and in the transcript.
- **`platform: <platform>`** — optional. The guest platform this
  script is written for (`dos`, `win9x`, `winnt`). When present,
  running the script against a machine of any other platform
  fails before the first step. A script is always written *for*
  one platform — declaring it just makes the mismatch fail fast.
- **`timeout: <seconds>` / `delay: <seconds>`** — optional.
  Script-wide [timing defaults](#timing-timeout-and-delay).

There is no version marker
([no backward compatibility before beta](machine-spec.md#format-stability-none-yet)),
and no name field — **the script's name is its file name**
without the `.rqs` extension, exactly as a machine's name is its
declaration file name.

### Lines, strings, and blocks

- **One statement per line.** A statement is a verb and its
  arguments, followed by comma-separated
  [modifier](#timing-timeout-and-delay) clauses. One rule reads
  the punctuation: **a colon binds — a condition to its action
  (`on "…": select "Yes"`), a setting to its value
  (`timeout: 300`); a comma separates clauses:**

  ```rqs
  wait "Please select your keyboard layout", timeout: 300
  ```

- **`#` comments**, full-line or trailing. Comments are the
  annotation mechanism; the transcript shows each executed line
  as written.
- **Strings are double-quoted plain text.** Text is just text:
  `"C:\>"` is the four characters `C`, `:`, `\`, `>`. Exactly
  three escapes exist — for the three characters that carry
  syntax:

  | escape | meaning                                       |
  |--------|-----------------------------------------------|
  | `\"`   | a literal `"` (the string delimiter)          |
  | `\<`   | a literal `<` (not a [key token](#type--type-text)) |
  | `\\`   | a literal `\` (so `\<` can follow a real backslash) |

  Any other backslash is literal: `"C:\FDOS"` is exactly
  `C:\FDOS`. For the harder cases there is the fully raw form,
  `r"…"` — as in Python: **no** escapes and no
  [`<key>` tokens](#type--type-text), every character
  between the quotes literal (its one limit: it cannot contain a
  `"`). Simple arguments — key names, state and drive and media
  names, paths without spaces — are written bare.
- **Blocks use braces.** A `{` at the end of a line opens a
  block; a matching `}` alone on a line (with any trailing
  modifier clauses) closes it. `state` bodies, `expect`
  branches, and multi-action handlers all brace their blocks.
  Indentation is yours to choose — the braces carry the
  structure.

### Watch patterns: literal by default

A watch pattern — the argument of `wait`, `on`, and `expect`
branches — is **literal screen text**: the words as the guest
displays them, matched case-sensitively within a screen row,
with runs of whitespace treated as one (screens pad and center
with spaces; invisible padding must not break a match).

```rqs
wait "Welcome to FreeDOS 1.4 (LiveCD)"
```

Nothing is escaped, because nothing means anything: dots,
parentheses, brackets, backslashes are themselves. When literal
text is not enough — anchoring, alternation, a pattern over
varying text — the `regex` keyword selects a Python regular
expression instead:

```rqs
wait regex "installed [0-9]+ of [0-9]+ packages"
```

Regex patterns use the same quoted-string rules, so `\s`, `\.`,
and friends are written exactly as in Python. A regex needing a
literal backslash is where the raw string form earns its keep —
`regex r"C:\\>"` matches the text `C:\>`, the pattern written
exactly as Python's `re` would receive it.

Besides the screen, a watch condition can observe **machine
events** — bare keywords, no quotes, because they are not text:

```rqs
wait shutdown
```

One event exists: **`shutdown`** — the guest powered the machine
off. It is observed through the backend's management interface
and is universal: every backend reports a machine ceasing to
run. (A guest *reboot* is deliberately not an event — most
hypervisors' management interfaces don't surface a guest reset
at all; the machine simply stays "running" through it. A script
handles a reboot the portable way: by watching for the screen
the reboot leads to.)

### Timing: `timeout` and `delay`

Timing is first-class and **scoped**. Two settings cover it:

- **`timeout`** — seconds an observation may take before the
  step fails: a `wait` condition (screen text or machine
  event), `run` completion, a state's next watch point, an
  `expect`'s first match.
- **`delay`** — seconds of pacing: the interval between screen
  observations, and the settle pause between a condition
  matching and the input that answers it. A fast-repeating menu
  wants a short `delay`; a slow-redrawing guest wants a longer
  one. Pacing is *never a gate*: the language has no blind
  sleeps, and `delay` makes nothing wait **for** anything —
  conditions do that.

Each is written two ways:

- **As a directive line** — `timeout: 300` on its own line — it
  sets the default for the rest of its scope: the whole script
  in the header, the containing block inside one.
- **As a modifier clause** — `…, timeout: 300` at the end of a
  statement — it applies to that statement alone. A block's
  modifiers go after its closing brace, exactly where any
  statement's go.

Scopes nest, innermost wins: script header, then each enclosing
block's directives, then the statement's own modifiers.

A block's *own* `timeout` — after its closing brace — is
distinct from the defaults directive inside it, and the two say
different things; both are often wanted at once. "This phase
must complete within 20 minutes, and no single screen inside it
may take more than 5" is:

```rqs
state formatting {
    timeout: 300
    …
}, timeout: 1200
```

The trailing `timeout` bounds the whole state — time to exit,
however many handlers fire meanwhile; for an `expect`, time to
its first branch match. The directive inside bounds each
individual observation: a stretch where nothing matches for 5
minutes fails early, long before the 20-minute budget — catching
a hung screen fast while still allowing a slow phase its full
time. Both fail with the state named; the diagnostics say which
bound was exceeded.

Initial defaults: `timeout` 60; `delay` is the selected control
plane's pacing unless a scope sets it — pacing has a
per-control-plane reality (VGA scraping and VNC framebuffers
observe differently) that an unset `delay` respects.

### Retries — there are none

There is deliberately no retry modifier. A statement either
completes within its timeout or the script fails with a full
diagnostic; re-running a failed script is the retry. Loops exist
only as drawn state transitions — an installer that replays a
phase transitions back to the state that handles it. Verbs that
operate by feedback (notably
[`select`](#select--choose-in-a-cursor-menu)) iterate internally
until they succeed or time out — that is the verb's mechanics,
not script-level control flow. Anything that genuinely needs
retry-with-logic belongs in Python, wrapped around script runs.

## The verb vocabulary

The vocabulary is the proven primitive set of reliquary's
existing automation surface, organized by the
[model](#the-model): verbs that observe readiness, verbs that
input, and the supporting cast. Each verb maps to a capability
the machine's configured control planes must provide; a
statement whose capability no configured control plane supplies
fails closed, naming the verb and the missing capability — never
silently degrading.

### `wait` — wait for screen text

```rqs
wait "Welcome to FreeDOS 1.4 (LiveCD)"
wait "C:\>", timeout: 300
```

Waits until the guest's visible screen text shows the literal
pattern ([matching rules](#watch-patterns-literal-by-default);
`wait regex "…"` for a regular expression). This is the workhorse
of installer scripting: every prompt, menu, and completion
message is a watch point — observed however the machine's
control plane observes text (VGA text memory on QEMU's agentless
display; other backends their own way). The input statements
that answer the awaited screen simply follow the `wait`.

A quoted pattern always means literal screen text, and `regex`
always means a regular expression; other observation forms —
image matching for GUI guests — will arrive as sibling keyword
forms (`wait image <needle>` is the reserved shape), never by
reinterpreting an existing one (see
[how the vocabulary grows](#how-the-vocabulary-grows)).

### `on` — reactive condition–action pairs

```rqs
on "Drive C: does not appear to be partitioned.": select "Yes" -> partitioning
on "Please insert disk 2": attach floppy install-disk-2
```

The condition–action pair, valid inside a
[`state`](#state--ordered-body-ambient-handlers): from the
moment execution reaches the handler's line, whenever the
pattern appears — as many times as it appears, until the state
ends — the action's input is delivered. An
action needing more than one verb takes a brace block:

```rqs
on "Setup is ready to continue": {
    enter "Y"
    wait "Copying files"
}
```

With a [`-> target`](#transitions), the pair is also an exit:
answer the screen, leave the state. The condition takes any
watch form, including the
[`shutdown` event](#watch-patterns-literal-by-default).

### `enter` — enter a line

```rqs
enter "fdapm poweroff"
enter "Y"
```

Types the string into the guest and presses Enter: `enter` means
"enter a line" — the common way to answer a prompt or issue a
command. `enter "…"` is exactly `type "…<enter>"`.

### `type` — type text

```rqs
type "A:"
type "<down><down><enter>"
```

Types exactly the string, nothing implicit: plain text and
`<key>` tokens, delivered verbatim. Use it for partial input a
later statement completes, and for sequences whose ending the
script controls token by token.

In both verbs, text is plain text and a **`<key>` token**
presses a named key — `<enter>`, `<esc>`, `<tab>`, `<up>`,
`<f8>`, a chord as `<ctrl+c>` — using the same portable key
vocabulary as [`press`](#press--press-keys). An unrecognized
token is a parse error naming the token (a typo like `<entre>`
can never reach the guest); a literal `<` that starts no token
is written `\<` — or use a raw string, `type r"a < b"`, which
types every character literally with no tokens at all. Key
tokens exist only in `enter` and `type` strings — watch patterns
and `run` commands take no keys, so `<` is literal there.

### `press` — press keys

```rqs
press enter
press down down enter
press ctrl+c
```

Presses a sequence of keys. Each argument is a key name, or
names joined with `+` pressed together as a chord — the same key
vocabulary as `enter`/`type`'s `<key>` tokens, bare:
`press enter` is exactly `type "<enter>"`. Use `press` when the
input is only keys; `type` when keys punctuate text; `enter` to
enter a line. Key names are
reliquary's own portable vocabulary (`enter`, `esc`, `tab`,
`up`, `down`, `left`, `right`, `f1`–`f12`, `ctrl`, `alt`,
`shift`, letters and digits, …) — each backend translates them
to its native input mechanism.

### `select` — choose in a cursor-menu

```rqs
select "Install to harddisk"
select "Plain DOS system", exclude: "with sources"
```

Selects an entry in a cursor-key menu by its visible label
(literal text, like a watch pattern): the verb reads the screen,
moves the highlight with the arrow keys until the labeled entry
is highlighted — verifying by visible feedback after every
keypress — and presses Enter. Prefer selecting the wanted entry
by name over blindly accepting a default with `press enter`: the
label is checked, the default is not.

- **`exclude: "<text>"`** — text that disqualifies an
  otherwise-matching entry (distinguishing `Plain DOS system`
  from `Plain DOS system with sources` above).

### `run` — run a command and await completion

```rqs
run "chkdsk c: > d:\chkout.txt", timeout: 600
```

Runs a command in the guest and waits for it to complete. The
string is plain command text — no key tokens; `<` and `>` are
the guest shell's. *How* is the selected control plane's
business: the agentless DOS control plane types the command and
waits for the prompt to return; a guest-agent control plane
executes it through the agent and awaits the exit status. Where
a control plane can report an exit status, a nonzero status
fails the step; where it cannot (the agentless DOS path has no
exit codes), completion is prompt return and the limitation is
the control plane's documented behavior — never an invented
success.

### `state` — ordered body, ambient handlers

```rqs
state cd-boot {
    wait "Welcome to FreeDOS 1.4 (LiveCD)"
    select "Install to harddisk"
    wait "What is your preferred language"
    select "English (United States)"
    on "Drive C: does not appear to be partitioned.": select "Yes" -> partitioning
    on "Drive C: does not appear to be formatted.": select "Yes" -> formatting
}
```

A state is a phase of the guest's life, and holds two kinds of
line:

- **The ordered body** — ordinary statements (`wait`, `select`,
  `type`, …), run in order from the top each time the state is
  entered. This is the phase's known sequence.
- **`on` handlers** — reactive pairs, **armed positionally**:
  a handler becomes active when execution reaches its line, and
  stays active until the state ends. Handlers written at the top
  of the block are active from entry; a handler placed after a
  body statement cannot fire until that statement has run — so a
  screen that only makes sense later in the phase cannot be
  answered early. At every observation the armed handlers are
  checked first (in declaration order; first match fires), then
  the body's current watch point — an armed handler can fire
  between any two body statements, and may fire repeatedly.
  Handlers cover the phase's *unordered* screens: prompts that
  may appear at any point from their arming on, screens whose
  order the guest decides.

`state <name>` binds the name transitions target; a bare
`{ … }` block is an anonymous state (its contents say what it
is), identified in diagnostics by line number. Timing directives
(`timeout: 300`) inside the block scope its observations; the
block's own bound trails the brace (`}, timeout: 600`).

States do not nest, and there are no `on` handlers outside a
state. The transcript records each entry, every body statement
and handler firing in the order the guest evoked them, and the
exit taken; on failure, diagnostics name the state, the pending
watch points, and which handlers had fired.

#### Transitions

`->` moves the script to a named state. It appears in two
places:

```rqs
on "You must reboot your computer": select "Yes" -> cd-boot
```

— on a handler: answer the screen, leave the state — and in the
body, trailing a statement ("do this, then go") or alone:

```rqs
state partitioning {
    wait "You must reboot your computer"
    # guest reboots; the LiveCD menu sequence replays
    select "Yes" -> cd-boot
}
```

— at a point in the body: reaching the `->` transitions, after
the statement it trails (if any) completes.
Transitions may go to any named state, including backward — a
loop in the guest (a reboot replaying menus) is drawn as a
transition back to the state that handles those screens, and the
replay costs nothing: entering a state runs its body afresh.

A state exits in one of two ways:

- **A transition fires** — from a handler or the body.
- **The body completes** in a state with no `->`-bearing
  handlers: the state is done, and the script continues after
  the block. (A state that *has* transition handlers idles after
  its body, watching, until one fires — its exits are the
  transitions; the block timeout bounds the idle.)

The machine is finite, explicit, and fully written down: `->`
targets only named states, and every transition is recorded in
the transcript.

### `handlers` / `use` — name a reactive block, reuse it

When several states pass through the same screens — an installer
whose menu sequence precedes every phase — the shared handlers
are defined once, as a named top-level block, and spliced into
each state that needs them:

```rqs
handlers livecd-menus {
    on "Welcome to FreeDOS 1.4 (LiveCD)": select "Install to harddisk"
    on "What is your preferred language": select "English (United States)"
}

state partition {
    use livecd-menus
    on "Drive C: does not appear to be partitioned.": select "Yes"
    on "You must reboot your computer": select "Yes" -> partition
}
```

- **`handlers <name> { … }`** — a top-level definition (beside
  the states, conventionally before first use) containing only
  `on` handlers. It is a named block, not a statement: defining
  it does nothing until a state uses it.
- **`use <name>`** — inside a `state` block, splices the named
  block's handlers at that position, exactly as if they were
  written there — they arm at the splice point, and declaration
  order still decides first-match priority, so a state can put
  its own handlers before or after the shared ones.

`use` is splicing, not calling: no arguments, no nesting (a
`handlers` block cannot `use` another), and no `use` outside a
`state`. A state may `use` several blocks and add its own
handlers around them. The transcript attributes each firing
through its origin (state, block, handler), so reuse costs no
debuggability.

### `expect` — branch on what appears

For divergence *within* an ordered sequence, without leaving the
state: `expect` waits until any one of several patterns matches,
runs that branch's statements, and continues after the block.
Each branch is a pattern and its actions — inline for one,
a brace block for several, empty for none:

```rqs
expect {
    "Drive C: is formatted":
    "does not appear to be formatted": {
        select "Yes"
        wait "Press a key..."
        press enter
    }
}, timeout: 120
```

The first branch whose pattern matches wins. If no pattern
matches within the block's timeout, the step fails like any
other. An empty branch is valid — "this screen may appear;
nothing to do."

`expect` exists for small forks — a prompt whose wording depends
on disk state, an optional extra screen. When the fork is a real
phase change, prefer [states and transitions](#transitions),
which name the branches and can rejoin; and anything resembling
decision logic belongs in Python. Branches cannot contain
`state` blocks or nested `expect`.

### `screenshot` — capture the screen

```rqs
screenshot
screenshot after-package-selection
```

Captures the guest screen into the machine's
`cache/machines/<name>/screenshots/` directory — under the given
name, or a step-numbered default. Screenshots are transient
diagnostics ([no retention promise](machine-spec.md)); collect
the ones you want to keep. Failing steps capture a screenshot
automatically — explicit `screenshot` steps are for documenting
success paths.

### `attach` / `detach` — change media

```rqs
attach cdrom freedos-1.4-livecd
detach cdrom
```

Attaches a media item to a drive slot, or detaches whatever the
slot holds. The first argument is a
[drive slot](machine-spec-reference.md) (`cdrom`, `floppy1`, …),
`attach`'s second a [defined media item](media-spec.md); the
item is fetched and hash-verified on demand like any other media
resolution. These are **runtime changes**: they update the
machine's state document, not its declaration, and the next
`start`
[reconciles back to the declaration](machine-spec.md#reconciliation-at-start).

### `stage` / `collect` — move files across the seam

```rqs
stage payloads/AUTOTEST.EXE
collect RESULTS.LOG results/
```

`stage` places host files where the guest can reach them;
`collect` retrieves guest files to the host. `stage` takes a
host path (relative paths resolve from the script's directory);
`collect` takes a path on the exchange drive and an optional
host destination directory (default: the current directory).
Paths with spaces are quoted. The mechanics are
control-plane-owned: the agentless path uses the machine's
staged virtual-FAT drive, with that mechanism's timing rules
(staged content snapshots when the machine starts; guest writes
are readable after it stops — so a `collect` on the agentless
path implies the machine has been stopped); a guest-agent
control plane moves files live. A script that needs live file
exchange on a machine whose control planes cannot provide it
fails closed at the `stage`/`collect` step.

### `start` / `stop` / `restart` — machine lifecycle

```rqs
stop
start
restart
```

- **`stop`** stops the machine from the host — the hypervisor
  equivalent of the power switch.
- **`start`** starts it again (a script begins with the machine
  running, so `start` only follows a `stop`).
- **`restart`** is exactly `stop` + `start` — the cycle
  agentless file exchange needs between staging and collecting.

Guest-initiated lifecycle needs no verb at all — it is
*watched*, not commanded, through
[machine events](#watch-patterns-literal-by-default). A clean
shutdown is the guest's own command plus the observation:

```rqs
enter "fdapm poweroff"
wait shutdown, timeout: 120
```

Prefer this ending over `stop` whenever the guest has disk state
worth flushing. A guest-initiated *reboot* needs no observation
of its own: the machine keeps running through it, and the script
watches for the screen the reboot leads to.

## Failure and the transcript

Every run writes a transcript: each executed line (verbatim,
with its line number), what it observed, and how long it took —
including, per state, every entry, handler firing, and
transition. When a step fails, the transcript ends with:

- the failing line, quoted, with its line number;
- the reason (timeout, unmatched pattern, missing capability,
  nonzero exit status);
- the final screen text as the control plane last observed it;
  and
- a screenshot, captured automatically into
  `cache/machines/<name>/screenshots/`.

Fail closed, name the problem — the same
[validation stance as the machine spec](machine-spec.md#validation-fail-closed-name-the-problem).
Parse errors (an unknown verb, a malformed line, an unbalanced
brace, an unrecognized `<key>` token, a `->` naming no state)
reject the script before step one, naming the line; capability
errors name the verb, the machine's backend, and the missing
capability.

## How the vocabulary grows

The verb set above is text-mode complete, not final: GUI guests
are a declared long-term goal (screenshot-based matching,
pointer input — see the roadmap), and the language is designed
so that era arrives **additively**, never by changing what an
existing script means. This is a **very high design priority** —
the GUI era must never require a breaking redesign of the
language, and a proposed feature that can't satisfy the rules
below is rejected on that ground alone. Three rules bind every
future extension:

- **A quoted watch pattern is frozen.** `wait "…"`, `on "…"`,
  and expect branches mean literal screen text today and
  forever, and `regex "…"` a regular expression. New observation
  or input forms take sibling keyword forms (`wait image
  <needle>` is the reserved shape for image matching) or new
  verbs (`click`, `drag`); an existing form is never
  reinterpreted.
- **New behavior arrives as new verbs and new optional
  modifiers.** A statement written today never gains different
  behavior from a modifier it doesn't use.
- **Everything stays capability-gated.** New verbs demand their
  capability (pointer input, image matching) from the machine's
  control planes and fail closed where it is missing — exactly
  as today's verbs do — so a script and a machine from different
  eras produce a named capability error, never silent
  misbehavior.

(Before beta, reliquary keeps
[no backward compatibility](machine-spec.md#format-stability-none-yet)
and may still reshape anything. These rules are design
discipline for the format's growth, so the text-first language
never needs a breaking redesign to admit the GUI era.)

## A complete install script

The FreeDOS 1.4 plain install, end to end — the script form of
reliquary's founding workflow, written as the installer's own
state machine: boot the LiveCD, take the partitioning pass, let
the reboot replay the menus, take the formatting pass, install,
and shut down. It expects a machine declared with a blank hard
disk and the LiveCD attached (see the
[machine-spec cookbook](machine-spec-cookbook.md)), and it
leaves that disk holding an installed, bootable FreeDOS:

```rqs
description: FreeDOS 1.4 plain install from LiveCD
platform: dos
timeout: 30

state cd-boot {
    wait "Welcome to FreeDOS 1.4 (LiveCD)"
    select "Install to harddisk"
    wait "What is your preferred language"
    select "English (United States)"
    wait "Welcome to the FreeDOS 1.4 installation program"
    press enter
    on "Drive C: does not appear to be partitioned.": select "Yes" -> partitioning
    on "Drive C: does not appear to be formatted.": select "Yes" -> formatting
}

state partitioning {
    wait "You must reboot your computer"
    # guest reboots; the LiveCD menu sequence replays
    select "Yes" -> cd-boot
}

state formatting, timeout: 600 {
    wait "Press a key..."
    press enter
    wait "Please select your keyboard layout"
    press enter
    wait "What FreeDOS packages do you want to install?"
    select "Plain DOS system", exclude: "with sources"
    wait "We are now ready to install FreeDOS 1.4."
    select "Yes"
    wait "Installation of FreeDOS 1.4 is now complete.", timeout: 600
    select "Yes"
    wait "Load FreeDOS with JEMMEX (more compatible)"
    press enter
    wait "C:\>"
    screenshot
    enter "fdapm poweroff"
    wait shutdown
}
```

The second visit to `cd-boot` — after the reboot — takes the
other exit on its own: the drive is partitioned now, so the
"not formatted" handler fires instead, and the machine moves to
`formatting`. The loop is drawn, not duplicated.

The complete recipe — this script with its media definition,
machine declaration, and verification script — lives in the
repository's [examples/](../examples/README.md) directory.

Verification is its own script — boot the installed disk (the
declaration minus the LiveCD, or after a `detach`), wait for
`C:\>`, shut down — because one script does one thing.

## Python remains first-class

The embedding API is not the fallback for what scripts cannot do
— it is the other half of the design. Scripts cover the
deterministic, replayable middle of a job; Python covers
judgment around it: choosing machines and scripts, generating
per-run inputs, parsing collected results, looping, branching,
integrating with test frameworks. The Python surface can run
scripts, and everything a script statement does remains
individually callable.

## Sharing

A script travels with its inputs: the script file, the media
definitions it relies on (hash-pinned — see
[the media spec](media-spec.md#sharing)), and the machine
declaration it targets are together a complete, verifiable
recipe small enough to check into version control. Payload files
stay out; everyone fetches and verifies their own.
