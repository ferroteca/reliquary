<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The script spec

> **Status:** Spikes 8–10 implement parsing, the QEMU/DOS runtime
> (`wait`/`expect`, input verbs, `screenshot`, `start`/`stop`), and
> `rlq --blueprint|--machine script <label>` wiring with per-invocation
> run records under `cache/machines/<id>/runs/`. Embedded media blocks,
> property-bound inputs, reactive `on`, and the full transcript contract
> remain later milestones; details may still change before first release.

A reliquary script automates a guest: it watches observable guest
and machine state, supplies input, swaps media, and moves files
across the VM seam. Scripts live in
`<reliquary_home>/scripts`, one `<name>.rqs` file per script, and
run against a machine selected with `--machine <id>` or, when the
blueprint has exactly one machine, `--blueprint <name>`:

```powershell
rlq script freedos-plain-install --blueprint msdos
```

After preflight, `script` installs embedded media definitions,
resolves its machine (creating one when `--blueprint` names a blueprint
with no machine yet), starts it if it is not already running,
then executes the script. The machine stays running afterward
unless a step stopped it. Failure likewise leaves the machine in
its observed state for diagnosis; no command implicitly tears it
down.

Scripts are authored documents: reliquary reads but never rewrites
them. They belong in version control beside the machine blueprints and
media definitions on which they depend.

## The language model

The language is a deliberately constrained, domain-specific
programming language. It has sequencing, branching, named states,
and explicit state transitions, but no expressions, mutable
variables, arithmetic, user-defined functions, or general-purpose
loops. Its job is guest automation, not computation.

The basic rhythm is **observe, then act**:

```rqs
wait "What is your preferred language"
select "English (United States)"
```

- **Observations** establish that the guest or machine has reached
  a known state: `wait`, `expect`, and reactive `on` handlers.
- **Actions** deliver intent-level input or perform supporting host
  operations: `enter`, `type`, `press`, `select`, `attach`,
  `detach`, `stage`, `collect`, `screenshot`, `start`, and `stop`.

Intent-level verbs remain above portable input events. `select`
means choosing a visible menu entry, not sending a guessed number
of Down keys. The selected control plane composes the necessary
key press and release events and owns their pacing. Pointer actions
will follow the same model when GUI automation arrives.

The authored control-flow graph is statically finite, but a run may
be unbounded when transitions form a cycle. Execution is
inspectable and replay-oriented, not inherently deterministic: the
guest and the timing of observable states can choose among declared
routes. The transcript records the route actually taken.

Anything computational belongs around scripts in Python: choosing
which script to run, deriving response values, repeating a failed
job from a known machine state, parsing results, and integrating
with other tools. Inputs supply immutable data to a script;
they do not add expression or decision syntax.

## Script shapes

A script uses one of two shapes. Mixing them is a parse error.

### Linear script

A linear script has top-level statements, executed in order. It is
the normal form for a known sequence:

```rqs
description: "Confirm that the installed DOS system boots"
platform: dos
timeout: 2m

wait "C:\>"
screenshot booted
enter "fdapm poweroff"
wait stopped
```

The first failing statement ends the run. Reaching end of file
completes it.

### State-machine script

A state-machine script declares named states and an explicit
initial state. Top-level executable statements are not allowed:

```rqs
description: "An installer with a reboot loop"
platform: dos
initial: cd-boot
timeout: 30s

state cd-boot {
    # ordered statements
    -> partitioning
}

state partitioning {
    # ordered statements
    done
}
```

Every reachable path through a sequential state ends explicitly with
`-> <state>` or `done`; a final `expect` is valid when every branch
ends that way. Named states never fall through according to their
textual order. `initial` must name exactly one declared state.
Duplicate, missing, and unreachable states are validation errors or
warnings as described under
[validation](#validation-and-preflight).

A state is either **sequential** or **reactive**:

- A sequential state contains ordinary ordered statements and
  `expect` blocks, ending explicitly in `->` or `done`. It cannot
  contain `on` handlers.
- A reactive state contains only `on` handlers. Every handler is
  active from state entry. A handler may transition, finish the
  script, or complete its action and return to the same reactive
  state. It cannot contain an interleaved ordered body.

If a handler should only become relevant later, the script enters a
smaller state at that point. Handler activation is therefore
visible in the state graph rather than hidden in statement
position.

There are no anonymous states and no implicit state entry.

## Header

Header fields precede embedded media definitions, input
declarations, and executable or state content:

- `description: "..."` is optional human-facing text.
- `platform: <platform>` is required. It fails preflight when the
  target machine declares another platform. A future genuinely
  platform-neutral script may use an explicitly defined portable
  platform value; omission never means portable.
- `initial: <state>` is required in a state-machine script and
  forbidden in a linear script.
- `timeout: <duration>` optionally changes the script-wide
  observation default from `60s`.

The file name supplies the script name. There is no format-version
field before beta because the planned format carries no compatibility
promise yet.

## Embedded media definitions

A script may carry media definitions needed by that workflow. Each
block has a definition label followed by the ordinary
media-definition JSON object; the outer opening brace becomes
`media <label> {`:

```rqs
media freedos-livecd {
  "url": "https://download.freedos.org/1.4/FD14-LiveCD.zip",
  "sha256": "2020ff6bb681967fd6eff8f51ad2e5cd5ab4421165948cef4246e4f7fcaf6339",
  "items": [
    {
      "name": "freedos-1.4-livecd",
      "file": "FD14LIVE.iso",
      "sha256": "c48a9dcf4b8e22f44e268a9879745f0bd88c061195ac584e6ef2deb0477f81fb"
    }
  ]
}
```

The label is an identifier and determines the installed file name:
the block above installs as `media/freedos-livecd.json`. It labels
the definition, not an item; an archive definition may still contain
several independently named items.

The body uses exactly the item or archive form documented by the
[media spec](media-spec.md); scripts do not get a second media
schema. Several distinctly labeled `media` blocks are allowed. They
appear after the header and before input declarations.

### Installation into the media library

Checking a script treats its embedded definitions as a prospective
addition to the shared catalog but remains read-only. Running a
script installs them into `<reliquary_home>/media` before fetching
media, reconciling the target machine, or delivering guest input.
Consequently, machine and media commands can use the definitions
after the first run without needing the script in scope.

Installation is fail-closed and non-overwriting:

1. Reliquary parses the whole script, binds responses and user
   properties, completes static and capability preflight, and
   validates every embedded definition against the entire shared
   library in memory. No file has been written yet.
2. If every item in a block is already defined identically anywhere
   in the library, that block is already installed and needs no new
   file. If only some items overlap, installation fails and asks the
   author to split the new and already-shared items into separate
   blocks; writing the mixed block would create duplicate names.
3. Otherwise the label's target path must not exist and none of the
   block's item names may conflict. A differing target file or item
   definition fails with both locations named; scripts never replace
   or override library definitions.
4. All new definitions are written in canonical JSON formatting by
   temp-and-replace. Installation is transactional across the blocks:
   an I/O failure removes files created by that attempt before the
   script proceeds.
5. The library is rescanned, then ordinary resolution, fetching, and
   machine startup begin. Definitions remain installed even if a
   later download or guest step fails; installing them is a durable
   successful pre-run action.

If an embedded definition changes after it has been installed, the
next run fails rather than overwriting the library copy. The user
explicitly removes or edits the shared definition before adopting
the new one. Once installed, definitions are ordinary user-owned
library documents; reliquary never updates or deletes them
implicitly.

A relative `local-path` is resolved from the script's directory
before comparison or serialization, so the installed JSON contains
an absolute path and retains the same meaning outside the script.
Downloads and extracted payloads use the ordinary shared caches.

Inputs are not expanded inside a media definition. Sources and
hashes are authored, reproducible inputs; a `media` input chooses
among names supplied by embedded definitions and the existing
library.

Name collisions never create an override. An embedded item whose
normalized descriptor is identical to a shared or earlier embedded
item coalesces harmlessly. The descriptor includes its payload name
and hash plus its complete direct-source or archive-source context;
unrelated sibling items in the same archive definition do not affect
the comparison. Any difference is an error before installation,
naming both definition locations and the colliding media item.

## Inputs, properties, and response files

Inputs externalize run-specific data while keeping control flow fixed.
Three input types exist initially:

```rqs
input text owner-name, property: "identity.full-name", prompt: "Registered owner"
input media supplemental-disk, prompt: "Supplemental disk"
input secret product-key, property: "products.windows-98.install-key"
```

- `text` is immutable text supplied to action arguments such as
  `enter`, `type`, and `select`. It cannot parameterize watch
  conditions, state names, paths, or control flow.
- `media` is the name of a defined media item. It is valid only
  where a media argument is expected, such as `attach`.
- `secret` is protected immutable text. It may be expanded only in
  `enter` and `type`; its value and expanded argument are omitted
  from transcripts and diagnostics.
- `property` optionally binds the input to a key in the
  [user property registry](property-registry.md). The quoted key is
  literal and cannot contain an input reference.
- `prompt` is optional user-facing text; the input name is used
  when it is omitted.

References use `${name}`:

```rqs
enter "setup /owner=${owner-name}"
attach floppy1 ${supplemental-disk}
type "${product-key}"
```

A `media` input must occupy the whole media argument; it cannot be
interpolated into text. A `text` input may appear more than once in
an ordinary quoted input string. Input references are
not expressions and cannot control `expect`, transitions, or state
selection. A `secret` input follows the text interpolation rules
only inside `enter` and `type`.

Values can be supplied explicitly in a JSON response file:

```json
{
  "owner-name": "Paul Galbraith",
  "supplemental-disk": "freedos-1.4-bonus"
}
```

```powershell
rlq script freedos-plain-install --blueprint freedos --responses answers.json
```

Before the machine starts, reliquary validates the response file,
rejects unknown keys, and binds each input from the first
available source:

1. an explicit response-file value;
2. the property named by `property:`; or
3. an interactive prompt.

Without an interactive terminal, a still-missing value fails before
execution. Response files therefore override personal registry
defaults for one invocation. Prompted values are not written back to
the registry. A media value is resolved after binding, and a media
prompt lists the embedded and existing library names valid for that
response.

Ordinary properties are strings. Secret properties keep only a
marker in `properties.json`; their values live in the host credential
store. `text` and `media` inputs require ordinary properties, while
`secret` requires a secret property. Kind mismatches fail
rather than silently downgrading protected data. See the
[property-registry specification](property-registry.md) for its file
format, maintenance commands, precise failure rules, and security
boundary.

The transcript records input references and source kinds, never
expanded values. For a `secret`, it also omits the entire expanded
input argument, redacts the value from textual diagnostics, and
suppresses later automatic failure screenshots. An explicitly
requested screenshot and the guest's own display, logs, or command
history remain capable of exposing guest-entered data.

Response files may contain sensitive text and should not be assumed
safe to commit. A response-file string may override a `secret` input,
but it is still plaintext in that file; the property
registry is the normal reusable source for protected values.

## Lexical and structural rules

- Files are UTF-8 text. A UTF-8 BOM is accepted but not required;
  LF and CRLF line endings are equivalent.
- One statement occupies one line. A `{` at the end of a line opens
  a block and a `}` alone closes it.
- `#` begins a comment outside a quoted string.
- Identifiers use ASCII letters, digits, `.`, `_`, and `-`, must start
  with a letter, and are case-sensitive.
- Reserved verbs and header names cannot be used as state or input
  names.
- A colon binds a named setting to its value. A comma separates
  positional arguments from modifiers and separates subsequent
  modifiers. When a block verb has no positional argument, its first
  modifier follows the verb directly:

  ```rqs
  wait "Copying files", timeout: 10m, stable: 500ms
  state formatting, timeout: 5m, deadline: 20m {
  expect timeout: 2m {
  ```

  Block modifiers always appear on the opening line, never after
  the closing brace.
- Durations require an explicit unit: `ms`, `s`, `m`, or `h`.
  Values must be positive; fractional values are allowed.
- Paths and human text are quoted. Bare arguments are restricted to
  identifiers, key names, drive slots, state names, input
  references, and machine-event keywords.

### Strings

Ordinary strings are double-quoted. Backslashes in DOS and Windows
paths are literal by default. Four escapes exist for syntax-bearing
text:

| escape | meaning |
|---|---|
| `\"` | literal `"` |
| `\\` | literal `\` |
| `\<` | literal `<` rather than the start of a key token |
| `\${` | literal `${` rather than an input reference |

Any other backslash is literal. Input references are expanded
only where the containing argument accepts them. In `enter` and
`type`, recognized `<key>` tokens produce key input.

The raw form `r"..."` performs no escapes, input expansion, or
key-token recognition. Its one limitation is that it cannot contain
a double quote.

Expanded text must be representable by the selected input control
plane. An unmappable character is a named input error, never a
silent replacement.

### Core grammar

This EBNF fixes the structural grammar; individual verb sections
define their typed arguments and allowed modifiers:

```text
script          = headers, media-definitions, inputs,
                  (linear-body | state-body) ;
headers         = header, { header } ;
header          = description | platform | initial | timeout ;
description     = "description:", string, newline ;
platform        = "platform:", identifier, newline ;
initial         = "initial:", identifier, newline ;
timeout         = "timeout:", duration, newline ;

media-definitions = { media-definition } ;
media-definition  = "media", identifier, json-object-body, newline ;

inputs          = { input } ;
input           = "input", ("text" | "media" | "secret"), identifier,
                   [ comma-modifiers ], newline ;

linear-body     = { statement } ;
state-body      = state, { state } ;
state           = "state", identifier, [ comma-modifiers ], "{",
                  newline, (sequential-body | reactive-body), "}",
                  newline ;
sequential-body = { ordered-statement }, terminal ;
reactive-body   = on-handler, { on-handler } ;

on-handler      = "on", condition, [ comma-modifiers ], "{", newline,
                  { ordered-statement }, [ terminal ], "}", newline ;
expect          = "expect", [ direct-modifiers ], "{", newline,
                  branch, { branch }, "}", newline ;
branch          = condition, ":", "{", newline,
                  { ordered-statement }, [ terminal ], "}", newline ;

condition       = string | "regex", string | "stopped" ;
terminal        = ("->", identifier | "done"), newline ;
```

`initial` is present exactly in `state-body` scripts. Comments and
blank lines may appear between grammatical lines. An `expect` may be
the final element of a sequential body when control-flow analysis
proves every branch terminal; this is the structured equivalent of
the final `terminal` production.

`json-object-body` begins with `{`, ends at its matching `}`, and
uses JSON lexical rules internally. Script comments and input
references have no meaning inside it. Media-definition labels must
be unique within the script.

## Observations

### Normalized text matching

A quoted watch pattern is a case-sensitive, normalized literal text
match against one visible screen row:

```rqs
wait "Welcome to FreeDOS 1.4 (LiveCD)"
```

The control plane decodes screen cells to Unicode, trims trailing
cell padding, and collapses each run of whitespace to one space.
The literal pattern is normalized the same way and then searched as
a substring within each row. Patterns do not span rows.

This is deliberately called a **normalized text match**, not an
exact or fully literal screen match. It ignores layout padding but
does not ignore case or punctuation.

Regular expressions are opt-in:

```rqs
wait regex "installed [0-9]+ of [0-9]+ packages"
```

Regex uses Python's regular-expression syntax and runs against each
normalized row. The first matching row satisfies the condition.
Regex strings use the same string rules; raw strings are useful for
backslash-heavy patterns.

When several `expect` branches or reactive handlers match the same
screen snapshot, the first declaration wins. Validation warns about
obvious literal shadowing; regex overlap cannot generally be proven.

### Machine state

`stopped` is the initial machine-state condition:

```rqs
wait stopped
```

It means that the backend reports the machine no longer running. It
does not by itself prove that shutdown was graceful; the preceding
guest action supplies that intent:

```rqs
enter "fdapm poweroff"
wait stopped, timeout: 2m
```

A guest reboot is not a special event or verb. The script issues the
guest's own command or input and watches for the screen that follows:

```rqs
enter "reboot"
wait "login:"
```

### Timing

Three settings have distinct meanings:

- `timeout` bounds one observation. At script scope it supplies the
  default for each `wait`, `expect`, or reactive state's next
  handler firing. A statement or state modifier overrides it.
- `deadline` bounds total elapsed time in a state or block and never
  resets when progress occurs.
- `stable` requires a watch condition to remain matched for the
  stated duration before succeeding.

Screen polling and input-event pacing remain control-plane-owned;
the script does not tune them. There is no generic sleep or delay
verb. `stable` strengthens an observation rather than blindly
pausing after it.

In a reactive state, `timeout` is the maximum interval with no
handler firing and resets after a handler action completes.
`deadline` always continues from state entry. In a sequential state,
handler activity cannot alter a pending timeout because sequential
states have no handlers.

### `wait`

```rqs
wait "C:\>"
wait regex "[0-9]+ files copied", timeout: 5m
wait stopped
```

`wait` succeeds when its condition matches and fails when its
timeout expires. A script that needs to know a console command
completed waits for output uniquely produced by that command or for
the resulting guest state; `enter` itself makes no completion claim.

### `expect`

`expect` waits for the first matching branch, executes that branch,
then continues after the block unless the branch transitions or
finishes:

```rqs
expect timeout: 2m {
    "Drive C: is formatted": {
        press enter
    }
    "does not appear to be formatted": {
        select "Yes"
        wait "Press a key..."
        press enter
    }
}
```

An empty block is the explicit no-action branch. Branches may
contain ordered statements and may end in `->` or `done`; they
cannot contain states, handlers, or nested `expect` blocks.
Branch conditions accept the same normalized text, `regex`, and
machine-state forms as `wait`.

### `on` and reactive states

A reactive state is a set of condition-action handlers. Handler
actions are always braced; there is no separate inline form:

```rqs
state copying, timeout: 5m, deadline: 30m {
    on "Please insert disk 2" {
        attach floppy ${supplemental-disk}
        press enter
    }
    on "Installation complete" {
        select "Reboot"
        -> first-boot
    }
}
```

All handlers are active from state entry and evaluated in
declaration order. Dispatch is single-threaded and run-to-completion:

1. The first matching, armed handler is selected.
2. That handler is consumed for the current matching episode.
3. Its action completes without interruption from other handlers.
4. A transition or `done` takes effect; otherwise dispatch resumes
   in the same state.
5. The handler cannot fire again until its condition has first become
   unmatched and later matches again.

This edge/episode rule prevents a persistent confirmation screen
from generating repeated input on every poll. A handler action may
contain ordered statements, including `wait`, but no handler is
dispatched recursively while the action runs.

Handler conditions accept the same normalized text, `regex`, and
machine-state forms as `wait`. Observation modifiers appear after
the condition and before the opening brace:

```rqs
on "Installation complete", stable: 1s {
    -> first-boot
}
```

## Input verbs

### `enter`

```rqs
enter "fdapm poweroff"
enter "setup /owner=${owner-name}"
```

Types the expanded string and presses Enter. It sends input only; it
does not assert that a command started, completed, or succeeded.
Completion is an explicit subsequent observation.

`enter "..."` is equivalent to `type "...<enter>"`.

### `type`

```rqs
type "A:"
type "<down><down><enter>"
```

Types text and recognized `<key>` tokens with no implicit ending.
Use it for input containing both text and keys. An unrecognized key
token is a parse error.

### `press`

```rqs
press enter
press down down enter
press ctrl+c
```

Presses a sequence of keys. Names joined by `+` form a chord. The
portable key vocabulary is shared with `type` tokens and is
validated before execution.

### `select`

```rqs
select "Install to harddisk"
select "Plain DOS system", exclude: "with sources"
```

Selects an entry in a cursor-key menu by normalized visible label.
It identifies candidate rows, rejects any containing `exclude`,
moves the highlight using observable feedback, and presses Enter.
Zero candidates, multiple remaining candidates, an undetectable
highlight, or traversal without progress are named failures; the
verb never guesses.

## State transitions

`-> <state>` is a standalone statement. In a sequential state it
must be the final reachable statement. In a reactive handler or
`expect` branch it ends the action immediately:

```rqs
-> formatting
```

`done` successfully ends the script:

```rqs
done
```

There is no implicit fallthrough and no transition attached to the
end of another action. Keeping transitions on their own lines makes
the state graph searchable and removes precedence ambiguity.

## Supporting operations

### `screenshot`

```rqs
screenshot
screenshot after-package-selection
```

Captures the screen in the current run directory. The default name
contains the step number. Repeated explicit names receive an
occurrence suffix rather than overwriting an earlier capture.
Failing observations capture a screenshot automatically.

### `attach` and `detach`

```rqs
attach floppy1 ${supplemental-disk}
detach cdrom
```

These change the running machine and update its state document, not
its blueprint. `attach` accepts a literal defined-media name or a
`media` input. By execution time every embedded definition has
been installed, so resolution uses the ordinary shared catalog, then
fetches and hash-verifies the item as needed.

Runtime attachment changes last only until the next `start`.
`start` reconciles the machine to its resolved baseline, so a
script must not rely on `detach` surviving a stop/start cycle.
Make permanent boot-media changes in the machine blueprint and adopt
them with `apply`
(see [the machine blueprint](machine-blueprint.md#applying-blueprint-edits)).

### `stage` and `collect`

```rqs
stop
stage "payloads/AUTOTEST.EXE"
start

# guest runs and shuts down
collect "RESULTS.LOG", to: "results/"
```

`stage` places a host file on the declared exchange drive;
`collect` copies a guest-produced file from it. Both require the
machine to be stopped on every control plane. This uniform contract
preserves agentless virtual-FAT snapshot and write-back semantics.
Future live guest-agent transfer, if added, will use different verbs
with an explicitly stronger capability rather than silently changing
these verbs' lifecycle behavior.

Stage sources resolve relative to the script directory. Collection
destinations resolve beneath the run's output directory, never the
process working directory. The CLI may select another output root;
script paths cannot escape it.

### `start` and `stop`

```rqs
stop
start
```

`stop` is a host-side hard power-off and should be used only when a
clean guest shutdown is unavailable or when offline exchange is
required. `start` starts a stopped machine after reconciling it to
its baseline. Starting an already-running machine or stopping an
already-stopped one is an error.

There is no `restart` or `reboot` verb. A guest reboot is guest
input (`enter "reboot"`, a menu choice, or the appropriate key
sequence) followed by observation of the resulting screen. A hard
power cycle, when genuinely wanted, is written explicitly as
`stop` followed by `start`, making both its destructiveness and its
reconciliation behavior visible.

## Validation and preflight

Parsing and static validation finish before the machine starts. They
reject:

- malformed syntax, unknown verbs or modifiers, and unbalanced
  blocks;
- duplicate or invalid names and unknown input references;
- conflicting embedded or shared media definitions and definition
  labels whose target files already contain different content;
- a missing or invalid `initial` state;
- transitions to undeclared states;
- mixed linear/state-machine shapes;
- mixed sequential/reactive state contents;
- sequential states with any reachable path lacking an explicit
  transition or `done`;
- invalid key tokens and invalid typed argument positions;
- unknown response keys, missing noninteractive responses, and
  response values of the wrong type;
- malformed property bindings, input/property kind mismatches,
  and required secret credentials unavailable from a secure host
  store.

Static analysis warns about unreachable states, reactive states with
no possible exit, obvious shadowed literal conditions, and inputs
that are declared but unused.

After binding inputs, preflight computes every capability the
script may require and compares the complete set with the machine's
configured backend and control planes. Capability failure occurs
before the first input, naming every unsupported verb and required
capability; a script never runs halfway before discovering that a
later statement is impossible.

```text
rlq check-script <script_name>
    [--machine <id> | --blueprint <name>] [--responses <path>]
```

performs parsing, prospective embedded-media validation, and static
analysis without executing the script, changing the user property
registry, accessing secret values, or writing to `media/`. Supplying
a machine and response file also performs typed binding and capability
preflight. Registry-aware checking reports property presence and kind;
it never reveals a property value.

## Failure, runs, and transcripts

Every invocation creates a unique run directory under:

```text
cache/machines/<machine_id>/runs/<timestamp>-<run_id>/
├── transcript.txt
├── screenshots/
└── output/
```

The CLI may redirect the output root, but transcript paths are always
reported explicitly. A transcript records:

- each executed source line and line number;
- state entries, handler firings, branches, and transitions;
- observations, normalized matches, and elapsed time;
- input names and whether each came from a response, named user
  property, or prompt, but never expanded input values;
- each media definition installed or found identical, its source
  script line and shared-library path, and verified hashes;
- the selected backend and control plane for each operation; and
- every produced screenshot or collected-file path.

On failure it adds the pending condition or action, timeout versus
deadline distinction, final observed screen text, machine state,
and an automatic screenshot when available.

There is no automatic retry. Re-running an installation against a
partially modified disk is not generally safe and is not described
as a retry. The caller deliberately resumes, recreates the machine,
or runs again according to that workflow's documented recovery
semantics.

## How the vocabulary grows

The text-mode vocabulary is a foundation, not a promise that every
future feature must fit an already frozen grammar before the first
implementation has validated it. Before beta, empirical use may
still reshape the language coherently.

The intended post-beta growth discipline is:

- existing observation forms keep their meanings;
- new observation and action kinds use explicit sibling forms, such
  as `wait image <asset>` and future pointer verbs;
- new behavior never appears merely because a script omitted a new
  modifier; and
- capability requirements remain explicit and preflightable.

Image matching and pointer input extend observation and action; they
do not introduce a second control-flow model.

## Complete FreeDOS install example

```rqs
description: "FreeDOS 1.4 plain install from LiveCD"
platform: dos
initial: cd-boot
timeout: 30s

state cd-boot {
    wait "Welcome to FreeDOS 1.4 (LiveCD)"
    select "Install to harddisk"
    wait "What is your preferred language"
    select "English (United States)"
    wait "Welcome to the FreeDOS 1.4 installation program"
    press enter

    expect {
        "Drive C: does not appear to be partitioned.": {
            select "Yes"
            -> partitioning
        }
        "Drive C: does not appear to be formatted.": {
            select "Yes"
            -> formatting
        }
    }
}

state partitioning {
    wait "You must reboot your computer"
    select "Yes"
    -> cd-boot
}

state formatting, timeout: 5m, deadline: 20m {
    wait "Press a key..."
    press enter
    wait "Please select your keyboard layout"
    press enter
    wait "What FreeDOS packages do you want to install?"
    select "Plain DOS system", exclude: "with sources"
    wait "We are now ready to install FreeDOS 1.4."
    select "Yes"
    wait "Installation of FreeDOS 1.4 is now complete."
    select "Yes"
    wait "Load FreeDOS with JEMMEX (more compatible)"
    press enter
    wait "C:\>"
    screenshot installed
    enter "fdapm poweroff"
    wait stopped, timeout: 2m
    done
}
```

The second visit to `cd-boot` reaches the other `expect` branch
because the disk has been partitioned. The guest-driven reboot is
expressed by the installer selection and the resulting screen, not
by a reliquary reboot command.

Verification is a separate script run after editing the machine
blueprint to disable the installer CD and boot from the installed hard
disk, adopted with `apply`
(see [the machine blueprint](machine-blueprint.md#applying-blueprint-edits)).
Runtime `detach` followed by `start` is intentionally not used:
reconciliation would restore the machine's baseline.

## Sharing

A shareable recipe consists of its script, machine blueprint, any
separate shared media definitions, and an example response file
containing only non-sensitive illustrative values. Media definitions
embedded in a script are installed into the recipient's shared
library on first run. Definitions already reused by several scripts
may be distributed directly under `media/` instead. The user property
registry, personal or secret response files, and staged payloads stay
out of the recipe and version control. A script may recommend property
keys, but every recipient supplies their own values. Media remains
hash-pinned and independently fetched.
