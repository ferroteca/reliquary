<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The script spec

> **Status:** This document is the source of truth for the redesigned
> script surface adopted in July 2026. It supersedes the earlier
> milestone-one syntax (`state`, `->`, `done`, `expect`, `regex`
> strings, colon headers, comma-separated modifiers, bare media
> names, and the bare `stopped` condition) completely; pre-1.0,
> there is no compatibility between the two surfaces and none is
> planned. The parser, the static rules, the timing plan, and the
> runtime speak this surface, and so do the shipped built-in and
> example scripts:
> `src/reliquary/codex/scripts/freedos-install.rlqs` is
> the reference script, and the files under
> `planning/design/script-examples/` catalog known residual rough
> edges in this surface. Properties and their binding and the full
> transcript contract remain later milestones; details may still
> change before first release.

A Reliquary script automates a guest operating system: it watches
observable guest and machine state, sends input, swaps media, and
moves files between the host and the guest. Scripts are authored
files with the `.rlqs` extension, identified by that extension.
They resolve from the `scripts` directory, searched recursively;
that directory defaults to `<home>/scripts` and can be changed with
`--scripts-dir`. If a script isn't found there, Reliquary does not
fall back to the built-in codex — the codex is only reached through
`seed-script`, or through a blueprint that names it
(docs/spec/asset-resolution.md). Each script is one `<name>.rlqs`
file. A run selects its machine with `--machine <id>`, or with
`--blueprint <name>` when that blueprint has exactly one machine:

```powershell
rlq run-script install --blueprint freedos
```

After preflight, `run-script` resolves its machine — creating one
if `--blueprint` names a blueprint that has none yet — and brings it
to the state the script's [`machine` header](#header) expects: it
starts a stopped machine if the script expects `running`, and fails
if the script expects `stopped` but the machine is running. It then
executes the script. The machine is left in whatever state the last
executed step put it in; on failure, it's left in its observed state
for diagnosis too — no command tears it down automatically. The
embedding API's equivalent function is `run_script`, which takes the
same identifiers: the CLI and the API accept the same inputs for
this operation.

Scripts are authored documents: Reliquary reads them but never
rewrites them, with one exception. The authoring recorder's opt-in
"fragment apply" feature (U6;
[recorder.md](../../planning/proposed/design/recorder.md)) inserts a
captured fragment at its playback anchor point and changes no other
byte. Scripts belong in version control next to the machine
blueprints they depend on, including those blueprints' media
components.

## Primary language goals

Every language decision is judged against these. They are numbered
so later decisions, reviews, and spec sections can cite them, and
so a proposed feature can be rejected by naming the goal it costs.

- **G1 — No agent runs inside the guest.** The guest is a black
  box: Reliquary can only watch it and type at it, never install
  anything inside it to help. No feature may depend on the guest
  cooperating. This is a permanent requirement
  ([AGENTS.md](../../AGENTS.md); U10), not a current limitation.
- **G2 — Non-computational.** No expressions, variables,
  arithmetic, functions, or general-purpose loops. Anything
  computational belongs in Python via the embedding API, which
  remains a first-class surface.
- **G3 — Checkable before the machine starts.** Parsing, binding,
  control-flow analysis, and whole-script capability preflight all
  complete before the first guest input. The authored graph is
  explicit and finite even when a run cycles.
- **G4 — Readable while it runs.** A run is usually long,
  unattended, and watched by someone who wants to know where it is.
  The language's own structure — named phases, the pending
  observation, declared budgets — must be enough to answer "where
  am I, what is it waiting for, how long has it got" without extra
  syntax.
- **G5 — Works the same regardless of backend or control plane.** A
  script says "wait for this text"; the machine's backend and
  selected control plane decide how that's actually observed.
  Verbs describe intent, not the specific keypresses or pointer
  events that implement it.
- **G6 — Small and unambiguous.** Brevity, succinctness, structure,
  clarity. One concept, one spelling. Every added piece of syntax
  has a cost, so deletion is the preferred fix over addition.
- **G7 — Grows coherently.** New capabilities extend observation and
  action without adding a second control-flow model or a second
  syntax. Growth stays explicit and preflightable.

## The procedural–declarative seam

The language is deliberately a hybrid of two halves — a declarative
half and a procedural half — split at a specific boundary. Where
that boundary falls is the most load-bearing decision in the
design: most of the language's prohibitions exist only to keep the
two halves from bleeding into each other. The rule itself is stated
with the language model below; this section explains why it's drawn
where it is.

Everything knowable before the run starts is declared: the
platform, the machine state the script expects, which phases exist,
their timing budgets, the media it needs, the inputs it binds.
Everything the guest dictates is procedural: which key to send,
what text to wait for, the order its own installer screens arrive
in. The boundary falls exactly where our knowledge ends:

| concern | paradigm | why |
|---|---|---|
| machine shape | declarative (the blueprint) | ours, and knowable |
| which phases exist, their budgets | declarative | ours, and knowable |
| media and property references | declarative | ours, and knowable |
| keystrokes and observations within a phase | procedural | the guest's installer dictates the order |
| which route the run takes | procedural choice over a declarative graph | the guest chooses at run time |

**Why not fully declarative.** OS installation already has a mature
declarative form: Kickstart, preseed, AutoYaST, Windows
`unattend.xml`. In each of those, the author states what the
installed system should look like and the installer does the rest.
Where one of those exists for a guest, it's strictly better, and
Reliquary does not invent a competing declarative install language
to replace it. For guests that accept an answer file, Reliquary
serves it the way Packer does today: from a local HTTP server that
the installer fetches from ([http-serve.md](http-serve.md)).
Procedural keystroke scripting is for the guests where no
answer-file format exists: DOS, Win9x, and similar. G1's "no agent
in the guest" requirement is about the control plane — Reliquary
can't depend on a guest agent or other cooperating software for
observation and input — not a ban on using an installer's own
native answer-file mechanism. Using Kickstart (or its kin) is that
native mechanism; it doesn't replace agentless scripting for guests
that don't have one.

**Why not fully procedural.** A plain imperative script — the
AutoHotkey or Expect style — would be shorter to specify and
wouldn't need a phase concept at all. It's rejected because it
gives up G3 and G4 together: a straight-line script with ad-hoc
loops has no shape a tool can statically analyze, and no named
units to report progress against. The declarative half is what
lets a run be checked before it starts and read while it runs.

**The tensions this creates, and that we accept.** These are real,
not papered over; several are already catalogued as open problems
in [`script-examples/`](../../planning/design/script-examples/):

- `phase` is a declarative construct whose body is procedural. That
  mix isn't hidden — it's the point.
- A sequential phase is procedural and a reactive phase is
  declarative, but both are written with the same `phase` keyword.
  Rather than give the two a combined meaning, the language forbids
  mixing them within one phase.
- The declarative/procedural split also shows up in the handler
  keywords: `on` is a case inside a branching `wait`, and `always`
  is a standing rule inside a reactive phase. Same shape, two
  different lifetimes — which is why they're spelled differently.
- Declarative timing scopes annotate procedural statements, so you
  can't always tell an observation's effective time limit just by
  looking at that line (`script-examples/03`, still open).
- The procedural verbs `insert`, `eject`, and `set-boot` change
  declarative machine state that outlives the run, deliberately
  making a machine diverge from its blueprint until something
  restores it. The `set-` prefix marks that this change persists —
  that's why it's spelled that way.
- The [`with` block](#scoped-machine-state-changes) gives one such
  change a declarative scope and undoes it at the end of that
  scope, applying the same declarative/procedural split to the
  divergence described above. It's also the only construct in the
  language whose scope is **dynamic**: every phase body ends in a
  transition, so a lexical scope would already have been undone by
  the time a `goto` happened.

**The prohibitions that keep the two halves from mixing.** Each one
exists to stop the procedural half from eroding the declarative
half:

- No author-side conditionals: the only decisions that matter are
  the guest's, expressed as observations of what it actually
  showed — never as logic the script author wrote (G2).
- Inputs supply data and can never select a branch, a phase, or a
  path, so the graph stays static (G3, P19).
- No fallthrough and no anonymous phases, so every route is named
  and searchable (G3, G4).
- No `sleep` or `delay`: every pause has to be justified by an
  observation, never by a guess about how fast the guest is (G1,
  G5).
- No implicit machine teardown: a failed run leaves its state in
  place for diagnosis instead of cleaning up the evidence. A `with`
  scope is not an exception to this — it only cleans up exactly
  what the author wrote the scope around, and the run reports what
  it took.

OS installation automation is expressed as install and verify scripts
attached to machine blueprints. Media acquisition (download, hash-verify,
cache under `cache/media/`) stays a host-side capability the language can
invoke, with pinned hashes kept in shared definitions or directly inside
the script.

## The language model

The language is a deliberately constrained, domain-specific
programming language. It has sequencing, branching, named phases,
explicit phase transitions, and scoped machine-state changes, but
no expressions, mutable
variables, arithmetic, user-defined functions, or general-purpose
loops. Its job is guest automation, not computation (G2).

The basic rhythm is **observe, then act**:

```rlqs
wait   "What is your preferred language"
select "English (United States)"
```

- **Observations** establish that the guest or machine has reached
  a known state: `wait`, in its single-condition and branching
  forms, and reactive `always` handlers.
- **Actions** deliver input or perform supporting host operations:
  `enter`, `type`, `press`, `select`, `click`, `insert`, `eject`,
  `set-boot`, `set`, `screenshot`, `start`, and `stop`.

Every action verb describes intent, not raw input events. `select`
means choosing a visible menu entry, not sending a guessed number
of Down keys; `click` means a spot on a matched landmark, not a
guessed pixel. The selected control plane works out the actual key
or pointer events needed and paces them (G5).

Three design rules govern the whole language:

- **One shape.** Every line of a script is a *node*: a name,
  positional arguments, `name=value` properties, and optionally a
  block. That single pattern is the entire structural grammar.
- **Spelling reveals role.** Every token class has exactly one
  spelling, and every punctuation mark exactly one role, so a
  reader can classify any token without needing context. See
  [lexical rules](#lexical-rules).
- **Nouns declare, verbs act.** Declarative nodes (headers,
  `property`, `phase`) start with a noun; imperative nodes start
  with a verb. The declarative part of a script always comes before
  the imperative part, and the grammar enforces that order.

That third rule reflects a deliberate split: **a script is
declarative about everything Reliquary controls, and procedural
about everything the guest controls.** What's knowable before the
run starts is declared: the platform, the expected machine state,
which phases exist, their budgets, the properties it binds. What
the guest dictates is procedural: which key to send, what text to
wait for, the order its own installer screens arrive in. The guest
is a black box that can't be configured — only watched and typed
at — so interacting with it necessarily takes the form of a
sequence of actions; everything else is a description. Several
rules below exist to keep that split intact: a phase is either
sequential or reactive but never both, properties can supply data
but never select a branch or a phase, and there are no author-side
conditionals, because the only decisions that matter are the
guest's. The reasoning behind this is laid out above, under "The
procedural–declarative seam".

The authored control-flow graph is statically finite, but a run may
be unbounded when transitions form a cycle. Execution is
inspectable and replay-oriented, not inherently deterministic: the
guest and the timing of observable states can choose among declared
routes. The transcript records the route actually taken.

Anything computational belongs around scripts in Python: choosing
which script to run, deriving property values, repeating a failed
job from a known machine state, parsing results, and integrating
with other tools. Properties supply immutable data to a script;
they do not add expression or decision syntax.

## Processing model

A script passes through a fixed pipeline: **lex → parse → desugar
→ validate → bind → preflight → execute**. Tokens form nodes
([lexical rules](#lexical-rules)); nodes parse under the typed
grammar; [derived forms](#derived-forms) rewrite them to the core
language; validation and binding check what follows; and the
[execution model](#execution-model) gives the result its run-time
meaning.

Every rule in this spec falls into one of three enforcement tiers:

- **Legality rules** — checkable from the script text alone: the
  lexical rules, the grammar, and the
  [syntactic restrictions](#syntactic-restrictions) (V-ids).
  Violating one of these is a STATIC ERROR.
- **Machine rules** — need something beyond the script text to
  check: the media namespace, the filesystem, a machine or
  blueprint, explicit property values. Capability preflight, slot
  and drive existence, property binding, and media reconciliation
  all live here
  ([validation and preflight](#validation-and-preflight)).
  Violating one of these is a PREFLIGHT ERROR, raised before any
  guest input.
- **Dynamic semantics** — the meaning of execution itself
  ([the execution model](#execution-model)). What goes wrong here
  is a RUN FAILURE.

`run-script --dry-run` has exactly two modes, one per checkable
tier: without a machine, it applies every legality rule; with
`--machine`/`--blueprint` (and optionally explicit property
values), it also applies the machine rules. **That's why the
machine selector is optional under `--dry-run` and required for a
real run** — whether you supply it is how you tell Reliquary which
tier to check. Dynamic semantics are only exercised by an actual
run. See [error classes](#error-classes-and-exit-codes) for how the
tiers show up to callers.

## Lexical rules

- Files are UTF-8 text. A UTF-8 BOM is accepted but not required;
  LF and CRLF line endings are equivalent.
- One node occupies one line. A `{` at the end of a line opens a
  block; a `}` alone on a line closes it.
- `#` begins a comment outside a quoted string or regex.
- Identifiers use ASCII letters, digits, `.`, `_`, and `-`, must
  start with a letter, and are case-sensitive. Reserved node names
  (headers, declarations, and verbs) cannot name phases or
  property keys.
- Modifiers are written `name=value`, space-separated, after the
  positional arguments. There are no commas and no colons anywhere
  in the language.
- Durations require an explicit unit: `ms`, `s`, `m`, or `h`.
  Values must be positive; fractional values are allowed. Numbers
  never appear without a unit.
- The grammars below are over **tokens**. A run of spaces or tabs
  separates tokens and carries no other meaning, including at the
  start of a line: block indentation and column-aligned headers
  are alignment, not syntax.
- Exactly two things must be written with no space around them:
  `name=value` and `key+key` are each one token. `timeout = 5m` is
  not a modifier — `timeout` would read as a positional argument —
  and is a parse error, as is `ctrl + c`.
- A token ends at whitespace, `{`, `}`, or the line terminator,
  except that `"..."` and `/.../` end at their closing delimiter.
  No token spans a line. Tokens are maximal munch: `5ms` is one
  duration, never `5m` followed by `s`.
- `eol` is emitted at each line terminator (LF or CRLF) and at end
  of file, so a final line without a trailing newline parses. A
  line holding only whitespace and/or a comment emits no `eol` and
  is invisible to the grammar below.

Every token class has one spelling:

| spelling | meaning | examples |
|---|---|---|
| bare word | keyword or script-internal name | `phase`, `goto formatting`, `cdrom0`, `press enter`, the `stopped` in `machine=stopped` |
| `"..."` | literal text crossing the guest boundary | `wait "C:\>"`, `enter "fdapm poweroff"` |
| `/.../` | regex match | `wait /[0-9]+ files copied/` |
| `@name` | external reference, resolved from the media namespace | `insert cdrom0 @freedos-livecd` |
| `$key` | a declared property's bound value | `insert floppy1 $supplemental-disk` |
| `name=value` | modifier of the node it follows | `timeout=5m`, `machine=stopped`, `exclude="with sources"` |
| `5m`, `500ms` | duration | `wait machine=stopped timeout=2m` |

### Strings

Ordinary strings are double-quoted. Backslashes in DOS and Windows
paths are literal by default. Three escapes exist for syntax-bearing
text:

| escape | meaning |
|---|---|
| `\"` | literal `"` |
| `\\` | literal `\` |
| `\${` | literal `${` rather than a property reference |

Any other backslash is literal. Inside a string, a property reference
is written `${key}` and is expanded only where the containing
argument accepts it; a `$` not followed by `{` is literal. String
content is only ever text: key presses are never written inside a
string — that's what `press` is for.

There is no raw-string form. Backslashes are already literal, so a
raw form would only save the `\${` escape — adding a whole second
string syntax just to save one escape isn't worth it, and it would
break the rule that a token is classified by its first character.

Expanded text must be representable by the selected input control
plane. An unmappable character is a named input error, never a
silent replacement.

### Regexes

A regex is written between slashes and cannot span lines:

```rlqs
wait /installed [0-9]+ of [0-9]+ packages/
```

`\/` produces a literal slash; every other character, including
backslashes, passes through to the regex engine unchanged. The
dialect is Python's `re` syntax. That's stated here deliberately as
part of the language's contract, not left as an implementation
detail: an implementation written in another language must still
provide this exact dialect, not substitute whatever regex flavor
its own host language uses. A regex is a screen condition;
`machine=` accepts only a machine-state word. Property references are
never expanded inside a regex.

### References

`@name` references a media by name. It resolves through the
blueprint namespace — the `media` specs across the `.rlqb` files in
the active source — and is never carried inside the script itself.
A media name is a `media-name` token, not a plain `name` token: it
can start with a digit (`@86Box`), because the `@` sigil has
already told the parser what kind of token this is, something a
bare word can't do on its own. A property key can't start with a
digit, because it also appears bare at its `property` declaration
line, where a leading digit would instead be read as a duration.
That's the entire difference between the two (D24). `$key`
references a declared [property](#properties) and must stand alone
as a whole argument; inside strings, use the braced form `${key}`
instead. Dotted keys are valid in both forms. The `property`
keyword itself is written bare at the point where a property is
declared; the `@` and `$` sigils only appear where a value is used.

## Core grammar

Every line of every script is one structural shape:

```text
node = name , { argument } , { modifier } , [ block ] ;   (* informative *)
```

This is the shape a parser recognizes before it looks at types.
What's actually legal is defined only by the typed grammar below,
together with the static-validation rules that follow it. This
first grammar just describes structure — what a line looks like;
the typed grammar is what decides whether a script is admissible.

Every block holds nodes. The one exception is milestone 5's HTTP
`content` declaration, which doesn't use a block: it attaches
either a raw triple-quoted body, or a `from=` source file whose
lines get served as an installer answer file
([http-serve.md](http-serve.md)). A script never carries JSON
directly: media are supplied as `media` components in the
blueprint, landmark declarations are their own authored files
resolved from the active source (docs/spec/asset-resolution.md),
and answer files are `content` entries with either an inline body
or a file-backed one.

On top of that node shape, a typing layer supplies the rest of the
language definition:

- **Ordering.** Header nodes come first, then `property`
  declarations, then planned `http` declarations, then either
  top-level statements (a linear script) or `phase` nodes (a phased
  script). Mixing the two body kinds is a parse error.
- **Signatures.** Each node name fixes its argument types, allowed
  modifiers, and whether it takes a block. The complete signature
  tables follow; an argument or modifier outside a node's
  signature is a parse error. The tables are reference summaries —
  the typed grammar and the
  [syntactic restrictions](#syntactic-restrictions) below are what
  actually govern.

Header nodes:

| node | argument | notes |
|---|---|---|
| `description` | string | optional human-facing text |
| `platform` | name | required |
| `machine` | `running` or `stopped` | expected starting machine state |
| `entry` | phase name | required in a phased script, forbidden in a linear one |
| `timeout` | duration | script-wide observation default |
| `deadline` | duration | wall-clock budget for the whole run |
| `pacing` | duration | script-wide gap before guest input |
| `stability` | proportion | script-wide quiescence gate on observations |

Declarations:

| node | arguments | modifiers | block |
|---|---|---|---|
| `property` | optional `text`/`media`/`secret`, key | `prompt` | — |
| `http` | — | `port-min`, `port-max` | `content` entries |
| `content` | name, string URL path, optional `"""` opener | `indent`, `from` | text body, or — with `from` |

Statements:

| node | arguments | modifiers | block |
|---|---|---|---|
| `wait` | one condition (string/regex, or `machine=` state) | `timeout`, `stable`, `stability` | — |
| `wait` | — (no condition; its handlers carry them) | `timeout`, `stability` | `on` handlers |
| `on` | one condition | `stable`, `stability` | statements |
| `always` | one condition | `stable`, `stability` | statements |
| `goto` | phase name | — | — |
| `finish` | — | — | — |
| `http` | `start` plus optional content names, or `stop` | — | optional `content` entries for `start` |
| `enter` | string | `pacing` | — |
| `type` | string | `pacing` | — |
| `press` | key names | `pacing` | — |
| `select` | string | `exclude`, `pacing` | — |
| `screenshot` | optional name | — | — |
| `insert` | slot, `@media` or `$property` | — | — |
| `eject` | slot | — | — |
| `set-boot` | drive keys | — | — |
| `set` | variable key, string | — | — |
| `start` | — | — | — |
| `stop` | — | — | — |
| `font` | one or more `@font`/`$property` references | — | — |

And the two block declarations, the phase and the scope:

| node | arguments | modifiers | block |
|---|---|---|---|
| `phase` | name | `timeout`, `deadline`, `pacing`, `stability` | statements, or `always` handlers |
| `with` | a head — `boot` plus drive keys, `insert` plus a slot and a `@media`/`$property`, or `eject` plus a slot | — | phases in a phased script, statements in a linear one |

### Grammar (normative)

The signature tables above expand into this complete EBNF grammar.
Every production here is an instance of the one node shape. A
parser is free to parse structurally first and type-check
afterward, but this grammar, together with the static rules below,
is what decides what's actually legal:

```text
script          = { header } , { property-def } , { http-def } ,
                  ( linear-body | phased-body ) ;

header          = "description" , string , eol
                | "platform" , name , eol
                | "machine" , ( "running" | "stopped" ) , eol
                | "entry" , name , eol
                | "timeout" , duration , eol
                | "deadline" , duration , eol
                | "pacing" , duration , eol
                | "stability" , proportion , eol ;

property-def    = "property" , [ "text" | "media" | "secret" ] ,
                  property-key , [ prompt-mod ] , eol ;
prompt-mod      = "prompt" , "=" , string ;

http-def        = "http" , { http-mod } , block-open ,
                  content-def , { content-def } , block-close ;
http-mod        = ( "port-min" | "port-max" ) , "=" , port ;
content-def     = "content" , name , string ,
                  ( { inline-content-mod } , triple , content-text ,
                    triple , eol
                  | from-mod , eol ) ;
inline-content-mod
                = "indent" , "=" , ( "dedent" | "literal" ) ;
from-mod        = "from" , "=" , string ;
port            = digit , { digit } ;

linear-body     = linear-unit , { linear-unit } ;
linear-unit     = statement | linear-scope ;
phased-body     = phased-unit , { phased-unit } ;
phased-unit     = phase | phased-scope ;
(* A scope wraps the enclosing shape's own units. Which shape a
   `with` opens is not decidable at its head, so an implementation
   may parse one permissive unit list and decide it with V2 and
   V10; this grammar states the legal shapes. *)
linear-scope    = "with" , scope-head , block-open ,
                  linear-unit , { linear-unit } , block-close ;
phased-scope    = "with" , scope-head , block-open ,
                  phased-unit , { phased-unit } , block-close ;
scope-head      = "boot" , slot , { slot }
                | "insert" , slot , ( media-ref | property-ref )
                | "eject" , slot ;
phase           = "phase" , name , { timing-mod } , block-open ,
                  ( sequential-body | reactive-body ) ,
                  block-close ;
timing-mod      = ( "timeout" | "deadline" | "pacing" ) , "=" ,
                  duration
                | stability-mod ;

sequential-body = statement-list ;
reactive-body   = always-handler , { always-handler } ;
always-handler  = "always" , condition ,
                  [ "stable" , "=" , duration ] ,
                  [ stability-mod ] , block-open ,
                  statement-list , block-close ;
statement-list  = { statement } ;

statement       = observation | action | transfer ;
transfer        = "goto" , name , eol | "finish" , eol ;
observation     = "wait" , condition , { watch-mod } , eol
                | "wait" , [ "timeout" , "=" , duration ] ,
                  [ stability-mod ] ,
                  block-open , handler , handler , { handler } ,
                  block-close ;
handler         = "on" , condition ,
                  [ "stable" , "=" , duration ] ,
                  [ stability-mod ] , block-open ,
                  statement-list , block-close ;
watch-mod       = ( "timeout" | "stable" ) , "=" , duration
                | stability-mod ;
pacing-mod      = "pacing" , "=" , duration ;
(* A proportion, not a duration: it carries no unit, which is what
   keeps `stable=2s` and `stability=0.99` two words for two axes
   rather than one word for two meanings (G6). *)
stability-mod   = "stability" , "=" , proportion ;
proportion      = digit , { digit } , [ "." , digit , { digit } ]
                | "." , digit , { digit } ;

condition       = string | regex
                | "machine" , "=" , machine-state ;
machine-state   = "stopped" ;

action          = "enter" , string , [ pacing-mod ] , eol
                | "type" , string , [ pacing-mod ] , eol
                | "http" , ( "start" , { name } | "stop" ) ,
                  eol
                | "http" , "start" , block-open ,
                  content-def , { content-def } , block-close
                | "press" , key , { key } , [ pacing-mod ] , eol
                | "select" , string ,
                  [ "exclude" , "=" , string ] ,
                  [ pacing-mod ] , eol
                | "click" , media-ref ,
                  [ "spot" , "=" , string ] ,
                  [ pacing-mod ] , eol
                | "screenshot" , [ name ] , eol
                | "insert" , slot , ( media-ref | property-ref ) ,
                  eol
                | "eject" , slot , eol
                | "set-boot" , slot , { slot } , eol
                | "set" , variable-key , string , eol
                | "start" , eol
                | "stop" , eol
                | "font" ,
                  ( media-ref | property-ref ) ,
                  { media-ref | property-ref } , eol ;

block-open      = "{" , eol ;
block-close     = "}" , eol ;
media-ref       = "@" , media-name ;
property-ref    = "$" , name ;
property-key    = name ;
variable-key    = name ;
key             = key-name , { "+" , key-name } ;

name            = letter , { letter | digit | "." | "_" | "-" } ;
media-name      = ( letter | digit ) ,
                  { letter | digit | "." | "_" | "-" } ;
duration        = number , ( "ms" | "s" | "m" | "h" ) ;
number          = digit , { digit } ,
                  [ "." , digit , { digit } ]
                | "." , digit , { digit } ;
string          = '"' , { str-char | escape | interpolation } ,
                  '"' ;
escape          = "\" , ? any character except a line
                        terminator ? ;
interpolation   = "${" , name , "}" ;
regex           = "/" , { regex-char | regex-escape } , "/" ;
regex-char      = ? any character except "/", "\", and a line
                    terminator ? ;
regex-escape    = "\" , ? any character except a line
                        terminator ? ;
```

`interpolation` is recognized only where the argument accepts it —
never in a regex. `slot`, `key-name`,
and `machine-state` values are `name` tokens whose closed
vocabularies (drive slots, the portable key set, machine states)
are checked by validation, not the grammar; `property-key` values
are `name` tokens whose dot-separated segment structure (each
segment starting with a letter) is likewise validation's rule. The
three words of `scope-head` are `name` tokens too — a word is a
keyword only where a node name may start, so `insert` after `with`
is an ordinary word and the head vocabulary is V14's closed set
rather than the grammar's.

### Terminating statements

A statement is *terminating* when it ends the flow of control
through its statement list. Exactly three are:

1. `goto`;
2. `finish`;
3. a branching `wait` in which every handler body ends in a
   terminating statement.

No other statement is terminating. The recursion in (3) is one
level deep, because no handler body may contain a branching
`wait`. A statement list *terminates* when it is non-empty and its
last statement is terminating.

Two rules follow, checked by static validation:

- A terminating statement is the last statement of its statement
  list. A statement written after one is unreachable and is an
  error.
- The statement list of a sequential phase terminates. A linear
  script's does not: reaching end of file completes the run, and
  that is its one spelling — `goto` and `finish` are both invalid
  in a linear script.

### Syntactic restrictions

These are the legality rules the grammar cannot carry — enforced
by static validation over the parse tree rather than encoded in
the CFG. Each has a stable id; diagnostics cite them:

- **V1** — syntax is well formed: no unknown node names, no
  unbalanced blocks.
  Ids: the lexer's — `lex.unterminated-string`,
  `lex.unterminated-regex`, `lex.unterminated-content`,
  `lex.unclosed-reference`, `lex.invalid-reference`,
  `lex.invalid-token`, `lex.invalid-duration`,
  `lex.spaced-modifier`, `lex.modifier-missing-value` — and the
  shape layer's: `syn.brace-not-alone`, `syn.unmatched-close`,
  `syn.unclosed-block`, `syn.open-brace-position`,
  `syn.expected-node-name`, `syn.argument-after-modifier`, plus
  `syn.unexpected-token` and `syn.unexpected-end`, which are the
  grammar's own rejections and name a token rather than a rule.

- **V2** — every argument, modifier, and block fits its node's
  signature, including each timing modifier's placement per the
  [placement matrix](#timing) and the units a `with` block may
  wrap in each script shape.
  Ids: `node.modifier-not-allowed`, `node.timing-placement`,
  `node.modifier-not-a-duration`, `node.modifier-not-a-string`,
  `scope.head-arguments`, `scope.wraps-the-wrong-unit`.

- **V3** — each header appears at most once; `entry` appears
  exactly in phased scripts.
  Ids: `flow.entry-in-linear`, `flow.entry-missing`,
  `syn.duplicate-header`.

- **V4** — no node carries the same modifier name twice; a
  repeat is an error, never a last-wins override.
  Id: `node.duplicate-modifier`.

- **V5** — names are valid and unique in their namespaces:
  reserved node names are not identifiers, property keys are
  declared once per script and are not spelled `text`, `media`,
  or `secret`, user-declared property keys do not use the
  reserved `rlq` or `reliquary` namespaces, durations are
  positive, and a scoped `boot` prefix names each drive once —
  by slot, so an alias and its indexed form are one drive.
  Ids: `name.reserved-node`, `name.duplicate-phase`,
  `name.duplicate-property`, `name.property-is-a-kind`,
  `name.property-reserved-namespace`,
  `name.variable-reserved-namespace`, `time.non-positive`,
  `prop.secret-default`, `prop.dead-default`, `prop.unknown-kind`,
  `drive.boot-duplicate`.

- **V6** — every `$` reference names a declared property or a
  Reliquary-owned run property in a reserved namespace made
  available by the script's declarations.
  Ids: `prop.undefined-reference`, `prop.secret-reference`,
  `prop.derivation-cycle`, `prop.http-without-block`. The
  `${key}`-in-a-statement half is unenforced — a named gap.

- **V7** — an observation carries **exactly one** condition — a
  bare string/regex beside a `machine=` modifier, or two
  `machine=` modifiers, are errors — the condition precedes any
  timing modifier, the channel is known, and its value is of the
  right kind (a state word for `machine=`, never a string).
  Ids: `obs.missing-condition`, `obs.two-channels`,
  `obs.not-a-condition`, `obs.unknown-channel`,
  `obs.screen-named`, `obs.wrong-kind`.

- **V8** — a branching `wait` carries no condition of its own,
  has at least two handlers, and appears nowhere inside a
  handler body. The recursion `handler → statement →
  observation` is deliberate: the grammar stays context-free and
  the depth limit is a static rule, not a parse rule.
  Ids: `wait.branching-in-handler`, `wait.too-few-handlers`, and
  `wait.branching-condition` — the last unreachable today, the
  grammar rejecting that shape first.

- **V9** — a construct appears only where it is legal: `on` only
  inside a branching `wait`, `always` only directly inside a
  reactive phase, a phase is sequential or reactive and never
  mixed, and no `with` scope stands inside another on the same
  target.
  Ids: `handler.mixed-phase`, `handler.on-outside-branching-wait`,
  `handler.always-outside-reactive-phase`,
  `scope.doubled-target`.

- **V10** — the two script shapes never mix; `goto` and `finish`
  are invalid in a linear script; every `goto` names a declared
  phase; `entry` names exactly one.
  Ids: `flow.transfer-in-linear`, `flow.goto-undeclared`,
  `flow.entry-undeclared`, `flow.mixed-shapes`.

- **V11** — the [terminating-statements rules](#terminating-statements):
  nothing follows a terminating statement, and a sequential
  phase's statement list terminates.
  Ids: `flow.unreachable-statement`, `flow.phase-falls-through`.

- **V12** — a phased script whose transition graph contains a
  cycle declares a header `deadline`.
  Id: `flow.cycle-without-deadline`.

- **V13** — watch patterns are non-empty and regexes compile.
  Ids: `obs.empty-pattern`, `obs.uncompilable-regex`.

- **V14** — closed vocabularies hold by name: key names are from
  the portable set, a `with` head is one of `boot`, `insert` and
  `eject`, `insert`/`eject` name removable
  (floppy/cdrom) slots, `set-boot` names drive slots, and
  interpolation appears only where the argument accepts it.
  Ids: `key.not-portable` (the `press` vocabulary) and
  `scope.unknown-head` (the scope heads); the insert/eject and
  boot slot vocabularies are preflight's.

- **V16** — the `http` declaration and its `content` entries are
  well formed: the port range is sane, content names are unique
  and their guest paths absolute, normalized and unique, a body
  is inline or `from` a readable relative file — never both,
  never neither — and `http start`/`stop` name declared content.
  The semantic detail is [http-serve.md](http-serve.md)'s; this
  rule is its static face. (V15 was never issued; the gap is
  history, not a rule.)
  Ids: `http.content-no-body`, `http.content-two-bodies`,
  `http.duplicate-content-name`, `http.duplicate-content-path`,
  `http.duplicate-declaration`, `http.empty-body`,
  `http.from-missing`, `http.from-not-relative`,
  `http.from-reference`, `http.from-traversal`,
  `http.from-unreadable`, `http.indent-not-a-mode`,
  `http.indent-on-file-body`, `http.no-content`,
  `http.path-not-absolute`, `http.path-traversal`,
  `http.port-not-a-number`, `http.port-out-of-range`,
  `http.port-range-inverted`, `http.reference-in-path`,
  `http.start-without-content`, `http.stop-takes-nothing`,
  `http.undeclared-content`, `http.unknown-action`.

- **V17** — **a stopped-only verb is never reached while the
  machine is running**, in every case where the static check can be
  sure whether it's reached at all. `set-boot` and a scoped `boot`
  head both write the machine's launch-time firmware boot order,
  and that only works while the machine is stopped. Because the
  script's `machine` header declares the starting state, and the
  language knows which verbs start and stop the machine, the check
  can work out — from the text alone — whether the machine is known
  to be stopped or running at any given point. A scope's **exit**
  is checked the same way its entry is; the exit is the half
  authors don't expect, since it's reached not just by finishing
  the scope normally but by every failure path too.

  **The check only fires where a static pass can actually be sure,
  and stays silent everywhere else.** Whether control reaches a
  handler body (`on` or `always`) is the guest's decision at run
  time, so the check doesn't judge anything inside one — and it
  doesn't count a phase as reached if the only way to reach it is
  through a handler's `goto`. That's the same boundary the check
  uses everywhere. A handler body is still walked to work out its
  *effect* on the machine's state: if two different paths through
  the script leave the machine in different states, the check marks
  that point `unknown` and refuses nothing there. Wrongly refusing a
  valid script would be worse than letting the mistake surface
  later — so when the static check can't be sure, it lets the run
  proceed, and the same rule still runs at run time to catch
  anything the static check couldn't rule on.

  A `wait machine=stopped` that completes has *observed* the machine
  stopped, so from that point on the check treats it as stopped —
  that's based on an actual observation, not a guess, and it matches
  how every script that powers a guest off from the inside is
  already written: it ends with exactly that wait.
  Id: `machine.must-be-stopped` — **the same id the run-time check
  uses**. It's one rule with one meaning either way; what V17 adds
  is catching it earlier, not changing what it means.

The grammar is line-oriented and LL(1) over the token stream in
[lexical rules](#lexical-rules), given one lexical rule: a bare
word immediately followed by `=` is a modifier-name token. Without
it the node shape is not LL(1) — an argument and a modifier name
are the same token until the `=` is seen, as in
`phase formatting timeout=5m`. All static validation —
terminating-statement checking, transition targets, capability
preflight, timing resolution — runs over the typed tree before any
machine starts.

### Derived forms

The surface language is defined by rewriting: a small set of
derived forms desugar — over parsed nodes, never over text —
into a smaller core, and every rule thereafter is stated once,
against the core (G6):

- `enter "s"` ⇒ `type "s"` followed by `press enter`.
- A bare string or regex condition ⇒ that condition on the
  screen channel — the default channel's only spelling, made
  explicit in the core.
- A linear script ⇒ a phased script with one implicit phase as
  its entry, whose statement list ends in an implicit `finish`
  (end of file ⇒ `finish`). The implicit phase has no name and
  cannot be targeted; `goto` and `finish` stay illegal in the
  authored linear surface (V10).

Desugaring is definitional, not observable: diagnostics, the
transcript, and the run event stream always name the authored
surface — the source line as written, never the rewritten core.

## Header

Header nodes precede property declarations and executable
content:

```rlqs
description "FreeDOS 1.4 plain install from LiveCD"
platform    dos
machine     stopped
entry       startup
timeout     30s
deadline    45m
```

- `description` is optional human-facing text.
- `platform` is required. It fails preflight when the target
  machine declares another platform. A future genuinely
  platform-neutral script may use an explicitly defined portable
  platform value; omission never means portable.
- `machine` declares the machine state the script expects when it
  starts. The default is `running`: `run-script` starts a
  stopped machine before executing. `stopped` requires a stopped
  machine — a running machine fails preflight rather than being
  implicitly powered off — and the script performs its own explicit
  `start`, typically after inserting the media it needs. An install
  script that must insert its installer medium before first boot
  declares `machine stopped`. There is deliberately no separate
  "must not be diverged" precondition: whether a diverged machine
  is a problem is the operator's call, not the script's, and
  `apply` is the documented way to fix it — a script header never
  encodes divergence policy.
- `entry` names the phase where a phased script begins. It is
  required in a phased script and forbidden in a linear one.
- `timeout` optionally changes the script-wide observation default
  from `60s`. See [timing](#timing).
- `deadline` bounds the whole run's wall clock. It is the backstop
  for legitimate transition cycles — a reboot loop that never
  converges fails here rather than running forever — and it is
  therefore *required*, not optional, in a phased script whose
  transition graph contains a cycle: a cyclable run is unbounded
  without it, and validation rejects the script rather than let
  the backstop be forgotten. Acyclic and linear scripts may omit
  it.
- `pacing` optionally sets the script-wide gap before guest
  input, which phases and input verbs may narrow. See
  [timing](#timing).
- `stability` optionally changes the script-wide quiescence gate
  from `0.99` — the proportion of the screen that must be holding
  still before a sample is one a condition is judged on. It is a
  **proportion, not a duration**, and carries no unit. See
  [timing](#timing).

Each header may appear at most once. The file name supplies the
script name. There is no format-version field before 1.0 because
the planned format carries no compatibility promise yet.

## Script shapes

A script uses one of two shapes, and mixing them is an error
(V10). Which shape a script is, is decided by whether it declares
any phase; a `with` block wraps the units of whichever shape it
is in and never changes it.

### Linear script

A linear script has top-level statements, executed in order — and
whatever [scopes](#scoped-machine-state-changes) wrap runs of
them. It is the normal form for a known sequence:

```rlqs
description "Confirm that the installed DOS system boots"
platform    dos
timeout     2m

wait "C:\>"
screenshot booted
enter "fdapm poweroff"
wait machine=stopped
```

The first failing statement ends the run. Reaching end of file
completes it — the linear script's only ending. `goto` and
`finish` are both invalid in a linear script: there are no phases
to name, and end of file already spells completion — the language
refuses a second spelling for it.

### Phased script

A phased script declares named phases and an explicit `entry`
phase. Top-level executable statements are not allowed; the only
other thing that may stand beside a phase is a
[`with` block](#scoped-machine-state-changes), which holds
phases:

```rlqs
description "An installer with a reboot loop"
platform    dos
entry       cd-boot
timeout     30s

phase cd-boot {
    # ordered statements
    goto partitioning
}

phase partitioning {
    # ordered statements
    finish
}
```

A sequential phase's statement list
[terminates](#terminating-statements): its last statement is a
`goto <phase>`, a `finish`, or a branching `wait` whose every
handler body itself terminates. Named phases never fall
through in textual order. `entry` must name exactly one declared
phase. Duplicate, missing, and unreachable phases are validation
errors or warnings as described under
[validation](#validation-and-preflight).

A phase is either **sequential** or **reactive**:

- A sequential phase contains ordinary ordered statements,
  including branching `wait` blocks, ending explicitly in `goto`
  or `finish`. It cannot contain direct handlers.
- A reactive phase contains only `always` handlers. Every handler
  is active from phase entry. A handler may transition, finish the
  script, or complete its action and return to the same reactive
  phase. It cannot contain an interleaved ordered body.

If a handler should only become relevant later, the script enters a
smaller phase at that point. Handler activation is therefore
visible in the phase graph rather than hidden in statement
position.

There are no anonymous phases and no implicit phase entry.

## Properties

A script declares the properties it consumes. References supply
their bound values to statements; control flow itself never
changes based on a property. The name declared in the script *is*
the property key that every [source](script-properties.md) uses —
there's no separate namespace for script input versus everything
else (owner, 2026-07-21 — the property-construct round). A dotted
key (like `identity.full-name`) joins the shared personal
vocabulary; an undotted key is scoped to the script by convention.
Every source that can supply a property value uses these same
keys.

```rlqs
property identity.full-name prompt="Registered owner"
property media supplemental-disk prompt="Supplemental disk"
property secret products.windows-98.install-key
```

A declaration is `property [type] <key>` with optional
`prompt=` and `default=` modifiers. The type is one of three:

- `text` — immutable text supplied to action arguments such as
  `enter`, `type`, and `select`. It cannot parameterize watch
  conditions, phase names, paths, or control flow. `text` is the
  default when the type is omitted.
- `media` — the name of a defined media item, valid only where a
  media argument is expected, such as `insert`.
- `secret` — protected immutable text. It may be expanded only in
  `enter` and `type`; its value and expanded argument are omitted
  from transcripts and diagnostics.

The three type words are reserved in the type position; a key
spelled exactly `text`, `media`, or `secret` is rejected with a
named diagnostic. `prompt=` is the user-facing text the
interactive ask presents; the key is shown when it is omitted. A
key is declared once per script — a duplicate declaration is a
static error — and referenced as often as needed, so one bound
value serves every use of the key.

`default=` declares the key's *derivation*: the script's own
answer for when no outer source supplies one. Its value is a
quoted string using the reference grammar shown below: literal
text, `${key}` references to other declared keys, and the `rlq.*`
system facts
([script properties](script-properties.md#property-sources)). A
derivation is not an expression — no transforms, no conditionals —
and it's resolved statically: references between defaults form a
dependency graph checked at parse time, a cycle in that graph is a
static error, and a reference to a key that's neither declared nor
a system fact is also a static error. At binding time, a
derivation whose references all resolve successfully answers the
key. A literal default always resolves — so `default="paul"`
simply stops resolution right there — while a derivation that
touches an empty or unavailable fact does not resolve, and the key
falls through to the interactive ask. `default=` can be repeated:
the candidates are tried in the order they're declared, and the
first one that resolves supplies the key. This is alternation
based on whether a candidate is available, never on the value it
produces, so a curated fact can be preferred over a raw fallback
(`default="${rlq.host.full-name}"
default="${rlq.env.FULLNAME}"`). A literal candidate anywhere
except last is a static error, because every candidate below it
could then never be reached. A `secret` declaration can't carry
`default=`, and no derivation may reference a secret key.
`prompt=` and `default=` work together: the prompt is simply never
shown unless the derivation fails to resolve.

References use `$key` as a whole argument and `${key}` inside
strings; dotted keys are valid in both forms:

```rlqs
enter "setup /owner=${identity.full-name}"
insert floppy1 $supplemental-disk
type "${products.windows-98.install-key}"
```

A `media` property must occupy the whole media argument; it
cannot be interpolated into text. A `text` property may appear
more than once in an ordinary quoted string. Property references
are not
expressions and cannot control watch conditions, transitions, or
phase selection. A `secret` property follows the text
interpolation rules only inside `enter` and `type`.

That prohibition also limits what any source is allowed to
customize: no property, whatever supplies it, can redirect a
script at a different-language installer, since every one of that
installer's screens would differ from what the script expects.
Localizing a blueprint to a different language is a *composition*
seam, owned by the machine blueprint — it's the blueprint that
picks which media/script pair runs. Value seams (property values)
only ever supply data; each script still stands alone against the
one guest it was written for (U5; see [customization
seams](../blueprint-guide.md#customization-seams)).

### The property sources

Before the machine starts, Reliquary binds each declared property
from the first source that has an answer for it. Every kind of
source that can supply a value is tried in one fixed order; each
rank in that order answers for a different owner (owner,
2026-07-21 — the property-construct round). This list is
normative; other documents summarize it and link here:

1. **An explicit CLI value** — *the caller's* answer for this
   invocation: a repeatable `--property <key>=<value>`; the
   equivalent API calls take the same values through their
   in-memory `properties=` mapping (CLI and API accept the same
   inputs here). This beats every other source, including the
   blueprint's own design. Supplying a key twice is an error, and
   every explicitly supplied key must be declared by the running
   script — an unknown key is a preflight error, never something
   silently ignored.
2. **A [blueprint
   parameter](../blueprint-reference.md#parameters)** — *the
   design's* answer, for every machine of the blueprint: either a
   direct value, or a *redirect* (`{"property": "<key>"}`) that
   resolves a different key through the remaining sources below.
   Parameters never chain through other parameters, and a redirect
   replaces resolution of the declared key entirely — it never
   falls back to the declared key's own value.
3. **The environment** — `RELIQUARY_PROPERTY_*` ([spelling and
   mangling](script-properties.md#property-sources)): *the
   session's* standing values, and the way CI injects values. An
   ambient environment variable never overrides a value the
   blueprint designed in; the explicit `--property` flag above is
   the only thing that overrides the design.
4. **The user properties file** — `user.properties`, or the file
   named by `--properties <path>`: *the person's* durable values
   and secret markers ([script properties](script-properties.md)).
5. **The declared derivation** — *the script's* own computed
   answer: the declaration's `default=` candidates, tried in the
   order they're declared, each resolved with the reference
   grammar over literal text, other declared keys, and the
   `rlq.*` system facts ([Properties](#properties)). The first
   candidate whose references all resolve answers the key — a
   literal candidate always resolves, so declaring one means
   stopping here — while a candidate that touches an empty or
   unavailable fact does not resolve, and if no candidate answers,
   resolution falls through to the next source.
6. **The interactive ask** — one prompt per still-unresolved key,
   shown using the declaration's `prompt=` text. The answer serves
   every reference to that key for this run, and is never written
   back anywhere.

Nothing binds without a script asking for it (owner, 2026-07-21,
restated by this round): no value reaches a script unless a
declaration names its key, and the only environment channel is the
declared `RELIQUARY_PROPERTY_*` spelling, ranked below the
blueprint's own design.

This order itself is fixed at this surface — it's part of the
language's meaning, with each rank settling a real disagreement
about precedence, not something a caller can reconfigure. How the
model can still grow without changing this order — new tiers at
positions the design decides, multiple providers within one tier,
programmatic injection through the embedding API with mandatory
provenance — is recorded alongside the operator-side mechanics
([script
properties](script-properties.md#growth-the-order-is-fixed-but-three-routes-let-it-grow);
planning/DECISIONS.md, 2026-07-23).

Prompting the user requires an interactive context: stdin and
stderr both have to be ttys — the prompt text is written to
stderr, and the answer is read from stdin (the CLI's output
discipline, docs/spec/cli.md) — and only under the interactive
progress renderings (`auto`/`pretty`). Without that (no terminal,
or an explicit `plain`/`jsonl` progress selection), a property
that's still unbound fails before execution starts, so a run can
never hang on a hidden prompt. A blueprint's designed values
override a person's own standing defaults — a blueprint that fixes
its user name as "testuser" keeps that fixed on every machine
built from it — while an explicit `--property` overrides even the
blueprint's design, for that one run (U5). A `media` property is
resolved after the rest of binding is done, and a media prompt
lists only the media names valid for that property.

Ordinary properties are stored as plain strings. Secret properties
keep only a marker in the properties file; their actual values
live in the host's credential store instead. `text` and `media`
declarations need an ordinary stored value, while `secret` needs a
secret-store entry — mismatching the two fails outright rather
than silently exposing protected data. Blueprint parameters follow
the same rule, and a `secret` declaration can never take a direct
value straight from a blueprint — the [field
reference](../blueprint-reference.md#parameters) states the
blueprint-side rules for this. A secret value can never travel
through `--property`, because command-line arguments leak into
process listings and shell history — the same reasoning behind the
`set-property` command's own rule. The environment variable path
may carry one (and is flagged as a plaintext risk when it does),
the API's in-memory mapping may carry one, and the interactive
prompt reads one without echoing it to the screen. See the
[script-properties specification](script-properties.md) for the
file format, maintenance commands, exact failure rules, and the
security boundary.

The transcript records property keys, redirect targets, and which
source supplied each one (flag, parameter, environment, file, or
ask) — never the values themselves. For a `secret`, it also leaves
out the entire expanded argument, redacts the value from any
textual diagnostics, and suppresses automatic failure screenshots
taken afterward. An explicitly requested screenshot, and the
guest's own display, logs, or command history, can still expose
guest-entered data.

## Execution model

How a running script behaves is defined over **samples** — the
control plane's discrete readings of the machine — not over
continuous time. This section is the language's dynamic
semantics: what the observation constructs in the sections that
follow mean at run time, which clocks govern them, and the event
stream every run emits.

### Samples and episodes

A **sample** is one reading of a channel at one instant: a
decoded, normalized screen for the default channel; a backend
state report for `machine=`. The control plane owns when samples
are taken — polling cadence, like input pacing, is never the
script's business (G5) — and the language guarantees exactly two
things about it:

- **Freshness.** An observation consults only samples taken while
  it is armed. A match can never be satisfied by machine state
  observed before the observation existed.
- **At least one.** An observation's timeout cannot expire before
  at least one sample has been taken for it. A timeout always
  means "samples were taken and none satisfied the condition,"
  never "no one looked."

Beyond those, cadence is deliberately unspecified. What happens
between samples has no semantics: a message the guest shows and
withdraws entirely between two samples was never shown, as far
as the script is concerned. The spec is honest about this rather
than implying continuous observation.

A condition **holds at a sample** when its matcher accepts that
sample's content — the normalized substring or regex row match
for the screen, the state word for `machine=`. An **episode** of
a condition is a maximal run of consecutive samples at which it
holds: it begins at the first holding sample after a non-holding
one (or after arming), and ends at the next non-holding sample.
Episodes are the unit of reaction; every rule below is stated
over them.

### Dispatch

Execution is single-threaded and run-to-completion. While a
statement list is executing there is no dispatch: no handler
fires, and no dispatch samples are taken. Observation happens at
these points:

- A **single-condition `wait`** arms its condition and samples
  until a fresh sample holds — success — or its timeout expires.
  With `stable=`, success requires more: the sample's episode
  must have lasted at least the stated duration, measured from
  the episode's first sample. An episode that ends early simply
  ends; the next episode starts its own hold clock.
- A **branching `wait`** arms every handler's condition. At each
  sample, conditions are evaluated in declaration order; the
  first that holds fires its handler, and the wait is over — the
  remaining handlers were never anything but candidates.
- A **reactive phase** arms every `always` handler at phase
  entry. At each dispatch sample, armed handlers are evaluated
  in declaration order; the first whose condition holds — and
  whose `stable` requirement, if any, is met — fires. Its
  statement list runs to completion, uninterrupted; a `goto` or
  `finish` in it takes effect immediately; otherwise dispatch
  resumes in the same phase, at the next sample.

**Firing consumes the handler for its episode.** A fired handler
re-arms only after a later dispatch sample at which its
condition does *not* hold; it may fire again at the episode that
begins after that. Because no dispatch samples are taken during
a handler's action, an episode that begins and ends entirely
inside one — the screen flickered while the script was typing —
was never sampled and never happened: a condition still holding
at the first post-action sample is conservatively the same
episode, and the handler stays consumed. What was not sampled
did not happen. This is what makes a persistent screen safe:
however long "Insert disk 2" stays displayed, its handler fires
exactly once per appearance.

`select` is an observation-bearing action: its feedback watches
(candidate rows, highlight movement) are ordinary observations
under this model, sampled and clocked like any other, within the
statement's effective timeout.

### Clocks

Five clocks exist, and one gate that is not a clock. Each is
checked at **boundaries** — dispatch samples and statement starts —
never mid-delivery:

| clock | starts | satisfied / expires |
|---|---|---|
| observation `timeout` | when its observation arms | expires at the first boundary past the duration with no success |
| `stable` hold | at each episode's first sample | satisfied at the first sample where the episode's age reaches the duration |
| reactive interval (`timeout` on a reactive phase) | at phase entry, and again each time dispatch resumes after a handler action | expires when the duration passes with no handler firing |
| phase `deadline` | at each activation (each entry to the phase) | expires when the activation's wall clock exceeds the budget |
| run `deadline` | at run start | expires when the run's wall clock exceeds the budget |

**`stability` is the sixth entry and deliberately not a clock**: it
is a proportion of the screen rather than a span of time, and it
gates *which samples count* rather than bounding how long something
may take. A sample whose screen has not settled to the effective
proportion is **not a sample any condition is evaluated against** —
it is skipped and the wait keeps looking. In a branching `wait` an
unsettled frame evaluates *none* of the handlers, which is why the
gate belongs to the sample and therefore to the container.

Two consequences follow, and both are normative:

- **The gate never causes a failure on its own.** Where the gate
  has had no chance to measure at all — a bound so short that no
  window could be observed — the condition is evaluated on what is
  there, so the invariant above holds: a timeout still means
  samples were taken and none satisfied the condition, never that
  nobody looked.
- **Where it has measured and the screen is moving, expiry is
  declared and says so.** The diagnostic names the gate and the
  proportion reached, because otherwise the two ways a wait can
  expire — the condition never matched, or it matched only on
  frames the gate skipped — are indistinguishable from outside.

Expiry produces the failure the [timing section](#timing)
promises: the diagnostic names the expired clock and the scope
that supplied it.

**Whether a deadline can cut an operation off partway through
depends on which side of the guest boundary it's on.** Input
delivery is atomic: once a verb starts sending events — a `type`
string, a `press` sequence, a `select` traversal step — the
delivery runs to completion even if a deadline passes in the
middle of it; the expiry is only declared at the next boundary. A
command cut off half-typed would leave the guest in a state no
observation could account for. Host-side operations are the
opposite: a media fetch never crosses into the guest, so it aborts
cleanly the moment a deadline hits, no matter how long it had been
running.

### The run event stream

Every run emits one normative event stream: JSON Lines, where each
event carries a sequence number, a timestamp, elapsed time, and a
kind. This is **live output** to whatever's driving the run, never
a file Reliquary writes to disk itself (owner, 2026-07-24; D36: a
run returns its output and stores nothing on its own; a persisted
`run-events.jsonl` file and a run directory are planned but not
built yet, proposed/FEATURES.md "Asynchronous runs"). Under
`--progress jsonl`, or through `run_script`'s event iterator, this
stream *is* the machine-readable output. The pretty and plain
console displays, and any transcript a caller chooses to keep, are
just *renderers* of this same stream — nothing shown on any of
those surfaces can go beyond what the stream itself carries.

Spans in the stream mirror the activation tree defined by the
clocks above: one run span (matching the run deadline's scope),
one span per phase activation (matching the phase deadline's
scope), and one span per observation (matching its timeout's
scope). At minimum, every runtime emits:

- preflight identification: the selected backend, and the
  control plane serving each operation;
- run and phase-activation span starts and ends, and `goto` /
  `finish` transitions;
- observation arm, match (with the matched row and elapsed
  time), and timeout;
- a scope's entry and its restore (`scope.enter`,
  `scope.restore`), naming the target and what value the exit
  restored it to — the underlying change itself is reported as an
  ordinary action, so these two events are the only place that
  records *that it happened inside a scope*;
- handler fires, and each action's start and completion — input
  deliveries, `insert`/`eject`/`set-boot`, `start`/`stop`,
  `screenshot`. An `insert` event names the media it actually
  mounted, so a `$property` argument reports the **resolved**
  media name, not the property's name: both the `@` and `$`
  sigils name something definite in the script text, but `@` is
  fixed at authoring time while `$` isn't resolved until the run
  happens — the event stream is where that difference becomes
  visible;
- progress updates only where a real total exists — media fetch
  bytes, `select` traversal steps — never a made-up denominator:
  renderers show phases and observations as "elapsed / limit"
  pairs, not progress bars;
- once, when a run first knows them: the **quiescence guard's**
  measured cadence, the decoration window that cadence earned, and
  whether the gate stood down for want of one it could observe
  (`guard.cadence`, above under `stability`) — measured rather than
  configured, so it cannot be reported before a screen is read;
- on failure: the condition or action that was pending, the clock
  that expired and the scope it came from, **every scoped change
  the run put back**, the route taken along with phase revisit
  counts, the nearest-miss screen row, the reason the last screen
  couldn't be read (when it couldn't), **how many of its cells
  matched no glyph** (when any didn't), the automatic screenshot
  reference, and the suggested next command. Three of these — the
  nearest-miss row, the unreadable-screen reason, and the
  unmatched-glyph count — answer different cases rather than
  serving as alternatives to each other: a screen with rows has a
  nearest miss; a screen with no rows at all — the guest painted in
  a video mode the display plane can't describe — has the captured
  shape reported instead; and a screen that *did* arrive, but was
  drawn in a font the host doesn't have (**U25**), has rows that
  were only partly substituted, so its nearest miss is measured
  against text that was never actually read. A recognized screen is
  a measurement, and a low-confidence reading can't be told apart
  from a good one just by looking at it — so a failure report never
  claims silence where it actually had something to say, and never
  claims more certainty than it has. A backend that reads resolved
  characters straight out of text memory isn't recognizing glyphs
  at all, so it reports zero unread cells;
- reserved, designed but not yet emitted: `screen`'s CLI-only read
  kind, waiting on the guest-console commands to carry an event
  stream at all (today only `run-script` and `fetch-media` do);
  and, once the backlogged record model lands (D36), interaction
  runs' neutral `ended` terminal event and the authoring
  recorder's (U6) handover kinds, which mark control passing from
  script to human and back, so a capture session is one record
  even though different things were driving it at different
  points. A reserved kind has no constant in the implementation
  yet: the vocabulary the code actually declares is the vocabulary
  it emits.

Events carry their originating statement's source line and line
number wherever one exists (owner, 2026-07-22) — action,
observation, and transition events all name the line they're
executing — so a transcript line can always cite where it came
from. Events carry property keys and which source supplied them,
never the bound values themselves; the same secret-handling rules
apply to the stream as apply to transcripts.

The event stream is a contracted machine-readable surface (owner,
2026-07-22): starting at 1.0, it can only grow — new event kinds
and new fields may appear in any release, an existing field never
changes type or meaning, and removing or renaming one is a
breaking change. Consumers must ignore event kinds and fields they
don't recognize. Before 1.0, the shapes just track this spec, with
no stability promise yet. The human-facing renderings
(`pretty`/`plain`) are deliberately not part of this contract; the
actual machine surfaces are this event stream (as live output),
the `--json` documents, and exit codes (docs/spec/cli.md;
persisted run-record files are dropped until persistence lands,
D36).

## Observations

### Channels

A **channel** is what an observation watches. The guest's screen
is the **default channel**, and it is unprefixed: a string or
regex condition *is* a screen observation, and that is the only
spelling a screen observation has. Every other channel — the
machine's own state today; a serial console later — is not the
default, and is always named as a prefix:

```rlqs
wait "C:\>"              # the screen: the default, unprefixed
wait /[0-9]+ files/      # the screen, matched by regex
wait @setup-page         # the screen, matched as an image
wait machine=stopped     # the machine: non-default, always named
```

| channel | observes | condition spelling |
|---|---|---|
| the screen (default) | the guest's visible display | string, regex, or `@landmark`, unprefixed |
| `machine=` | machine state reported by the backend | `stopped` |

Machine state has exactly one spelling, `machine=stopped`; there
is no bare `stopped` condition. This split is deliberate for two
reasons: a bare word and a quoted string in the same argument
position must never mean two different kinds of observation, so
the non-default kind is always named — and the default (the
screen) is *only* ever unprefixed, because letting it have a
second, prefixed spelling would recreate the exact ambiguity this
rule exists to avoid.

An observation carries exactly one condition. To wait for the
first of several, including conditions on different channels, use
the [branching `wait`](#wait), where each handler carries its
own:

```rlqs
wait timeout=5m {
    on "Press a key..."  { press enter }
    on machine=stopped   { goto powered-off }
}
```

New observables arrive as new channel names, and new matchers as
new value spellings, rather than as new
syntax; see [how the vocabulary grows](#how-the-vocabulary-grows).

### Normalized text matching

A quoted screen pattern is a case-sensitive, normalized literal
text match against one visible screen row:

```rlqs
wait "Welcome to FreeDOS 1.4 (LiveCD)"
```

The control plane decodes screen cells to Unicode, trims trailing
cell padding, and collapses each run of whitespace to one space.
The literal pattern is normalized the same way and then searched as
a substring within each row. Patterns do not span rows.

This is deliberately called a **normalized text match**, not an
exact or fully literal screen match. It ignores layout padding but
does not ignore case or punctuation.

Regular expressions are opt-in through the regex literal:

```rlqs
wait /installed [0-9]+ of [0-9]+ packages/
```

A regex runs against each normalized row. The first matching row
satisfies the condition.

When several handlers could match the same screen snapshot,
the first declaration wins. Validation warns about obvious literal
shadowing; regex overlap cannot generally be proven.

### Landmark matching

A `@name` in condition position watches the screen as an **image**:

```rlqs
wait @setup-page stable=500ms timeout=2m
```

The name resolves to a `.rlql` landmark — one declaration owning the
geometry, with its variant renderings beside it — and the condition
holds when the guest's screen matches it. It stands wherever a screen
condition stands: a single-form `wait`, an `on` arm, an `always`
handler; it carries `stable=` and `timeout` like any screen
condition; and it is one condition per observation like any other.

This is the third **value spelling** of the one screen channel, not a
new channel and not new syntax — the growth rule's own shape (see
[how the vocabulary grows](#how-the-vocabulary-grows)). There is no
negation form, as there is none anywhere in the language.

The declaration, the match, the region regimes and the nearest-miss
report are specified in **[landmarks.md](landmarks.md)**, which is
normative for them. Three rules belong here, because they are the
language's:

- **Kind is checked at binding.** The `@` pool is one namespace
  across media, fonts and landmarks, so the *use* decides which kind
  a name must be. A `@name` in condition position resolving to a
  media or a font is refused naming the use and the kind
  (`landmark.wrong-kind`), exactly as a landmark name in `insert`
  position is (`media.wrong-kind`) and in `font` position
  (`font.wrong-kind`). A name nothing in the pool holds is
  `landmark.unknown`.
- **Capability is preflighted at the condition's granularity.** A
  landmark condition requires framebuffer capture from the control
  plane driving the machine; a plane that captures none refuses the
  condition by name, before any guest input
  (`machine.plane-no-framebuffer`). A script that watches no landmark
  asks the plane for nothing.
- **The cursor needs no rule yet.** No verb moves the guest's cursor,
  so a run leaves it where the guest drew it — which is where the
  author's capture shows it — and capture and run agree by
  construction. The parking contract that will keep that true once
  pointer verbs exist is stated in
  [landmarks.md](landmarks.md#the-cursor) and lands with them.

### Machine state

`machine=stopped` is the initial machine-state condition:

```rlqs
wait machine=stopped
```

It means that the backend reports the machine no longer running. It
does not by itself prove that shutdown was graceful; the preceding
guest action supplies that intent. There is deliberately no
`machine=running` condition: `start` is synchronous, and no other
observable transition produces the running state, so the condition
would have nothing to wait for — if a real use appears it arrives
as an ordinary vocabulary addition under the growth rules.

```rlqs
enter "fdapm poweroff"
wait machine=stopped timeout=2m
```

A guest reboot is not a special event or verb. The script issues
the guest's own command or input and watches for the screen that
follows:

```rlqs
enter "reboot"
wait "login:"
```

### `wait`

`wait` is the language's one observation construct, in two forms.
The single-condition form succeeds when its condition holds at a
fresh sample and
fails when its timeout expires:

```rlqs
wait "C:\>"
wait /[0-9]+ files copied/ timeout=5m
wait machine=stopped
```

A script that needs to know a console command completed waits for
output uniquely produced by that command or for the resulting guest
state; `enter` itself makes no completion claim. Beware the echo:
the guest displays the command line the script typed before the
command has done anything, so a pattern containing the script's
own input can match that echo — wait for text only the command's
*effect* produces.

The branching form waits for the first of several conditions,
executes that handler's body, then continues after the block unless
the body ends in `goto` or `finish`:

```rlqs
wait timeout=2m {
    on "Drive C: is formatted" {
        press enter
    }
    on "does not appear to be formatted" {
        select "Yes"
        wait "Press a key..."
        press enter
    }
}
```

This is the classic Expect semantic — one command covering the
single- and multi-pattern cases — under one verb. A branching
`wait` requires at least two handlers: a single condition is a
plain `wait`, and the language refuses a second spelling for it.
An empty handler body is the explicit no-action branch.

### `on`, `always`, and reactive phases

`on <condition> { ... }` binds a condition to an action inside a
branching `wait`; `always <condition> { ... }` declares a standing
rule directly inside a reactive phase. Both use the same condition
spellings as `wait` — an unprefixed string or regex for the
screen, or a named non-default channel such as `machine=stopped` —
and the same handler shape: one branch form, two arming keywords,
and the first word carries the lifetime. An `on` fires at most
once — the first match ends its `wait` — while an `always` stays
armed until the phase transitions. Each keyword is legal only in
its own container: an `on` directly inside a phase, or an `always`
inside a branching `wait`, is a validation error, so a handler's
lifetime is always recoverable from its own text.

A handler body — in a branching `wait` or in a reactive phase —
contains ordered statements and single-condition `wait`s, and may
end in `goto` or `finish`. It may not contain a branching `wait`.
Branch nesting stops at one level on purpose: further structure
belongs in the phase graph, where `goto <phase>` and
`phase <phase>` find it, rather than in indentation depth.

A reactive phase is a set of handlers, all armed from phase entry:

```rlqs
phase copying timeout=5m deadline=30m {
    always "Please insert disk 2" {
        insert floppy1 $supplemental-disk
        press enter
    }
    always "Installation complete" {
        select "Reboot"
        goto first-boot
    }
}
```

Handlers are evaluated in declaration order; dispatch is
single-threaded and run-to-completion, and a fired handler is
consumed for its episode — re-arming only after a sample at which
its condition no longer holds, as the
[execution model](#execution-model) defines precisely. This
edge/episode rule prevents a persistent confirmation screen
from generating repeated input on every sample. A handler action
may
contain ordered statements, including single-condition `wait`, but
no handler is dispatched recursively while the action runs.

Handler conditions accept the same channels as `wait`. A `stable`
modifier strengthens the condition:

```rlqs
always "Installation complete" stable=1s {
    goto first-boot
}
```

## Timing

The timing model in one sentence: **`timeout` bounds the time to
the next observed event, `deadline` bounds the total wall clock of
the construct it annotates, `stable` strengthens one observation,
`stability` decides which samples an observation may be judged on,
`pacing` sets the gap before guest input, and there is no
`delay`.** When each clock starts, where it is
checked, and how expiry is declared are defined by the
[execution model's clock table](#clocks).

The four families scope differently, and where you write one
decides what it applies to:

- **Per-observation settings (`timeout`, `stable`) are lexically
  scoped.** An observation bound is a parameter of an observation,
  so writing `timeout` on a container sets the default for every
  observation the container lexically contains. Resolution is
  innermost-wins, decided entirely at parse time:

  ```text
  statement > branching wait > phase > header > built-in 60s
  ```

  A reactive phase's `timeout` bounds each interval with no handler
  firing — still the time to the next observed event.
- **A budget (`deadline`) is dynamically scoped to one
  activation.** It applies exactly where written, is never
  inherited, and never resets on progress. Each entry to a phase
  starts a fresh budget, so a legitimately revisited phase is
  budgeted per visit; the header `deadline` is the backstop that
  bounds the whole run, cycles included.
- **Input pacing (`pacing`) is lexically scoped** like the first
  family, and applies to the five guest-input verbs:

  ```text
  statement > phase > header > built-in 0.1s
  ```

  There is no branching-`wait` rung: an observation container
  cannot carry `pacing`, because pacing paces the actor and a
  `wait` acts on nothing. A guest-input verb inside a handler
  therefore inherits from its phase or the header, skipping the
  `wait` that contains it.
- **The quiescence gate (`stability`) is lexically scoped** like
  the first family, and applies to observations:

  ```text
  statement > branching wait > phase > header > built-in 0.99
  ```

  It **does** have a branching-`wait` rung, and that is where it
  diverges from `stable` rather than from `pacing`: `stable`
  qualifies a *match*, so a container carrying it is meaningless —
  there is no condition to hold — while `stability` qualifies the
  *frame a compare runs on*, and a frame exists at every sample.
  That is also what makes a built-in default possible at all, so
  the gate is written nowhere in an ordinary script.

  **The number falls out of the geometry.** A text screen is
  80 × 25 = 2000 cells, so one row of text is 80 of them — 4% —
  and any threshold looser than `0.96` would call a screen settled
  while a line is still being drawn into it. Screen furniture costs
  an order of magnitude less: a cursor 1 cell, a clock 8, a
  percentage counter 4. `0.99` sits in that gap, above furniture
  and below content. **`stability=0` turns the gate off** for the
  observation that carries it, which is the escape for a screen the
  default refuses; it is legal precisely because it costs nothing,
  not even the window establishing quiescence would take.

  **A slower cadence may be imposed, and the host decides — not the
  script.** The gate has a second, unwritten requirement: telling
  decoration from content is *recurrence*, a cell changing three
  times inside the decoration window, and a change is only ever
  recorded at a sample. So the guard needs a **minimum viable
  cadence** — with the built-in one-second window and its safety
  margin, one screen read every ~0.17s. A script cannot ask for
  this and cannot waive it; it is a property of how the machine's
  backend reads a screen.

  There are two ways a backend can read a screen, and they differ
  by an order of magnitude. Where the backend has VGA text memory,
  the guest has already resolved its own characters, so a read is
  effectively free — measured at **16ms or less**, comfortably
  inside what's needed. Where the screen has to be **interpreted
  from a framebuffer** — the GUI-only case, where a screenshot is
  decoded and matched against a bank of glyphs — a read costs the
  better part of a second, measured at **~0.83s**, roughly five
  times the minimum. A run on that slower path ends up with a
  slower cadence imposed on it by the host, and the runtime adapts
  to that rather than pretending it isn't happening:

  - the measured cadence is rounded **up** — to the nearest second
    where screens are interpreted, to 0.1s where they're read from
    text memory, because the jitter on the two paths differs by
    that much, and a window sized off noisy measurements would
    judge two identical runs differently;
  - the decoration window **widens** to match what that cadence can
    actually observe, so the guard keeps working instead of
    switching off — and within the wider window, a slow reader
    recognizes exactly the same decoration a fast one would;
  - past a cap, the window stops widening, because "changed three
    times recently" would stop meaning decoration and start meaning
    a screen that's being painted in stages instead. When a cadence
    can't be accommodated within that cap, the gate **stands down**
    for the run: every sample gets judged, exactly as it would have
    before the gate existed. The gate never causes a failure on its
    own, at any cadence.

  **The run reports which of these happened**, once, on the event
  stream (`guard.cadence`; [the stream's
  vocabulary](#the-run-stream)) — naming the cadence it measured,
  the window that cadence earned, and whether the gate stood down.
  Otherwise a guard that had quietly gone inactive would look
  identical to one that had actually passed, and an author who
  wrote `stability=` would have no way to find out the host
  couldn't honor it.

Where each word may appear, and what it means there — any other
placement is a parse error:

| written on | `timeout` | `deadline` | `stable` | `stability` | `pacing` |
|---|---|---|---|---|---|
| header | default for all observations | budget for the run | error | default for all observations | default for all guest input |
| `phase` | default within the phase | budget per phase entry | error | default within the phase | default within the phase |
| single-condition `wait` | bound on this observation | error | hold requirement on this match | gate on this observation's samples | error — it delivers no input |
| branching `wait` | bound on reaching the first match | error | error — put it on the `on` | gate on this wait's samples | error — it delivers no input |
| `on` / `always` | error — the container owns the waiting | error | hold requirement on this condition | gate on this handler's samples | error — put it on the input verb |
| `enter` / `type` / `press` / `select` / `click` | error | error | error | error — it compares nothing | gap before this delivery |
| every other statement | error | error | error | error — it compares nothing | error — it delivers no input |

**`stability` and `pacing` mirror each other**, and the table above
is the clearest place to see it: each one only appears on the kind
of statement whose risk it addresses. `pacing` protects the side
that's acting, so it only lives on the five verbs that deliver
input; `stability` protects the side that's comparing, so it only
lives on observations. Neither overlaps the other's territory, so
neither word needs to mean something different depending on where
it's written.

Three placements are rejected deliberately rather than tolerated:
`deadline` on a single observation would be an exact synonym for
`timeout` (a scope containing one observation has identical bound
and budget), and a language should refuse two spellings for one
meaning; `stable` on a container is meaningless because only a
match can be required to hold; and `pacing` on an observation or a
host-side verb names a delivery that does not happen there.

`timeout`, `deadline` and `stable` must each be a **positive**
duration — a bound of zero asks for what can never happen.
`pacing` is the exception: `0s` is legal and means "this guest is
ready, do not wait". It is an interval rather than a bound, and an
author who knows a screen is entitled to say so; refusing it would
only yield `pacing=1ms`, which says the same thing less honestly.
`stability` is not a duration at all: it is a proportion between
`0` and `1` inclusive, and both ends are meaningful — `1` demands a
frame with no change whatever, `0` turns the gate off.

Because per-observation and pacing resolution are fully lexical,
the effective timeout of every observation and the effective gap
before every guest input are computable at parse time (G3, G4):
`run-script --dry-run` reports the resolved timing plan —
including a `guest input` section naming each verb's pacing and
the scope that supplied it — and a timing
failure names which clock expired and the scope that supplied it —
an observation timeout from a statement, a phase deadline from its
declaration, or the run deadline from the header.

`stable` requires a watch condition to remain matched for the
stated duration before succeeding:

```rlqs
wait "Formatting" stable=2s
```

**`stable` and `stability` measure two different things, not two
spellings of the same thing**, and knowing the difference tells
you which one you want. `stable` asks whether a *matched
condition* is the lasting state rather than a passing one;
`stability` asks whether the *frame* the comparison ran on can be
trusted at all. A condition can match perfectly on a screen that's
still half-painted — that's the case only `stability` catches. And
a screen can be perfectly still while showing text that's about to
be overwritten — that's the case only `stable` catches. Neither
one covers the other's case, which is why **`stability` doesn't
replace `stable`**, and why one word couldn't do both jobs: telling
a duration from a proportion only by whether the author wrote `2s`
or `0.99` would be one spelling doing two different things, and
**G6** rules that out.

In practice the gate absorbs most *uses* of `stable=`, this
example among them: what an author usually means by
`wait "Formatting" stable=2s` is "do not act on this until the
screen has stopped moving", which the default now does without
being written. `stable` becomes the rarer tool for the case it
alone answers, rather than an unnecessary one.

There is no generic sleep or delay verb, on principle (G1, G5): a
blind
pause encodes a guess about guest speed that will be wrong on
another host. Every pause must be justified by an observation;
`stable` strengthens one rather than blindly pausing after it.

**`pacing` is not that forbidden `delay` verb, and the rule against
`delay` still stands.** The distinction is between a pause an
author deliberately *inserts as a step*, and a pause that's simply
part of *how input gets delivered*. A `delay` verb would be the
first kind: a step in the script sitting between two others,
encoding a guess about how long something takes. `pacing` is the
second kind — the control plane's own gap before it starts typing,
which happens whether or not anyone writes the word `pacing` at
all. What the language adds is the ability to tune that existing
gap, not the ability to insert a new one.

The gap exists because, without an agent in the guest, a guest's
readiness to *receive* input can't be observed, even though its
output can (G1): an installer paints its welcome screen before
it's actually reading the keyboard, so a control plane that starts
typing the instant a screen appears is asserting something it has
no way to know. `send_keys` already paces the gaps *between* key
events; this is the missing pause before the very first one.
Screen polling stays entirely the control plane's own business,
with no author-facing tuning; pacing the first input event is also
the control plane's business, but this one is tunable, as shown in
the placement table above.

A swallowed first keystroke is this gap being too short, and it
does not surface as an input failure: the verb completes, having
delivered, and what fails is the *observation after it*, timing
out on a screen that never advanced. Raise `pacing` on the phase
that meets that screen — or, where one fits, prefer a
feedback-driven verb: `select` re-reads between keys, so it
accommodates a guest that was not yet listening rather than
estimating how long it would take to start. The built-in 0.1s is
a floor rather than an estimate of any screen's readiness, so a
guest that needs more is expected to say so rather than to be
predicted.

## Input verbs

All input verbs share one delivery contract: the selected control
plane composes the concrete events and owns their pacing, and the
verb completes when the control plane has delivered them — making
no claim that the guest consumed or acted on the input.
Completion claims belong to the observation that follows, and an
unmappable character is the named input error the
[lexical rules](#lexical-rules) promise, never a silent
substitution.

Every verb in this section pays the pacing gap before its first
key or pointer event, and each accepts `pacing=` to tune it
([Timing](#timing)). The five are `enter`, `type`, `press`,
`select` and `click`; the supporting operations below are not
guest input and pay nothing. `select` and `click` are both
observation-bearing — each delivers *and* observes, `select` a
cursor-key menu, `click` a landmark — so each carries a `timeout`
for its search and a `pacing` for its delivery, and each appears
twice in the resolved plan.

### `enter`

```rlqs
enter "fdapm poweroff"
enter "setup /owner=${owner-name}"
```

Types the expanded string and presses Enter. It sends input only;
it does not assert that a command started, completed, or succeeded.
Completion is an explicit subsequent observation.

`enter "..."` is equivalent to `type "..."` followed by
`press enter`.

### `type`

```rlqs
type "A:"
type "1"
```

Types text with no implicit ending. Text is all `type` sends —
keys are `press`'s job, and a sequence mixing them is written as
alternating `type` and `press` statements, each single-role:

```rlqs
type  "A:"
press enter
```

### `press`

```rlqs
press enter
press down down enter
press ctrl+c
```

Presses a sequence of keys. Names joined by `+` form a chord.

The portable key vocabulary is one closed set, owned by the
language and used only after `press`:

```text
enter esc tab space backspace
up down left right
insert delete home end pageup pagedown
f1 f2 f3 f4 f5 f6 f7 f8 f9 f10 f11 f12
ctrl alt shift
```

Single printable characters are not key names — they reach the
guest as text through `type` or `enter`, except as the
non-modifier member of a chord (`ctrl+c`). A control plane that
cannot deliver a listed key is a named capability failure at
preflight; the vocabulary is never per-platform.

### `select`

```rlqs
select "Install to harddisk"
select "Plain DOS system" exclude="with sources"
```

Selects an entry in a cursor-key menu by normalized visible label.
It identifies candidate rows, rejects any containing `exclude`,
moves the highlight using observable feedback, and presses Enter.
Zero candidates, multiple remaining candidates, an undetectable
highlight, or traversal without progress are named failures; the
verb never guesses. `select` is an observation-bearing action: its
feedback watches run under the statement's effective `timeout`,
resolved by the same lexical rules as any observation, and a
failure names that clock and its source scope.

### `click`

```rlqs
click @welcome-screen
click @component-list spot="continue"
```

Finds a landmark and delivers a left click at one of its declared
spots, then parks the cursor (F66). Its *search* — matching the
landmark on stability-gated frames — runs under the statement's
effective `timeout`, resolved by the same lexical rules as any
observation; a search that matches nothing times out visibly, the
same safe-failure asymmetry landmarks chose, with no pointer event
ever delivered. Its *delivery* — the click, then the park move —
pays `pacing`, exactly as the other input verbs do.

**Spot naming.** A landmark declaring exactly one spot needs no
`spot=`; more than one makes it required, and `spot=` naming
nothing in the declaration is a static error — the referenced
`.rlql` is loaded and checked at preflight, before the machine
starts (G3).

**Capability.** `click` requires everything a landmark condition
does (framebuffer capture on the driving control plane) plus two
more: pointer input on that plane, and
`devices.pointer0: virtual-tablet` on the machine (see
[blueprint-model.md](blueprint-model.md)) — an absolute event needs
an absolute device, so a relative `emulated-mouse` machine is
refused by name rather than attempted with a calibration guess.
Every refusal lands before the first guest input (G3).

**For now: only a single left click.** `button=`, `count=`, and a
drag verb are natural future additions (G7) that nothing currently
demands. Adding them later won't require changing the backend
adapter interface, since that interface already supports arbitrary
button masks and event sequences — only the script-facing
vocabulary would need to grow.

## Phase transitions

`goto <phase>` transfers control to a declared phase. In a
sequential phase it must be the final reachable statement. In an
`on` body it ends the action immediately:

```rlqs
goto formatting
```

`finish` successfully ends the script:

```rlqs
finish
```

There is no implicit fallthrough and no transition attached to the
end of another action. Keeping transitions as explicit statements
makes the phase graph searchable — `goto formatting` finds every
entry into a phase, `phase formatting` finds its declaration — and
removes precedence ambiguity.

## Supporting operations

### `screenshot`

```rlqs
screenshot
screenshot after-package-selection
```

Captures the screen and returns it to the caller — the CLI writes
it to a caller-named path (or a default under the machine
directory), the API returns the image (D36: a run stores nothing,
so there is no run-directory screenshots folder). Failing
observations capture a screenshot automatically, carried in the
run's returned output.

### `insert` and `eject`

```rlqs
insert cdrom0 @freedos-livecd
insert floppy1 $supplemental-disk
eject cdrom0
```

These change what medium occupies a declared **floppy or CD-ROM**
slot and record the change in the machine's state document, not
its blueprint. Hard-disk slots are never targets: `insert` and
`eject` address removable slots only. Slot names, ranges, and the
alias/canonical rule are defined once, in the
[blueprint field reference](../blueprint-reference.md);
`set-boot` keys use the same vocabulary. The verbs never create or remove
the drive itself: drives are guest-visible hardware the blueprint
declares — an installer-driven blueprint declares the slot empty
(`"cdrom0": null`) — and an `insert` or `eject` naming a missing
or non-removable slot fails static preflight, before any guest
input. `insert` into an occupied slot, and `eject` from an empty
one, are run errors: media state is explicit, and a swap is
written as `eject` then `insert`. `insert` accepts a media
reference (`@name`) or a `media`
property (`$key`); bare media names are not valid. Resolution uses
the ordinary shared catalog, then fetches and hash-verifies the
item as needed. Both verbs work on a running machine (a media
change the guest observes) and on a stopped one (the medium present
at the next `start`).

**Insertions are definitive machine state.** An `insert` persists
across `stop`/`start` exactly like an installer's writes to a hard
disk: the machine has diverged from its blueprint, and stays
diverged until a later `insert`/`eject` changes the slot again or
[`apply`](../blueprint-guide.md#applying-blueprint-edits) returns
the machine to its blueprint. A script that changes machine state
it should not leave behind — an install script's installer CD —
either restores it explicitly, conventionally with `eject` as its
final step, or gives the change a
[scope](#scoped-machine-state-changes), which restores it on every
outcome including the ones no final step reaches.

**What a failure leaves behind is therefore the author's choice,
and it is a real trade.** An *unscoped* change is left in place for
diagnosis and resumption; `apply` is the one-command recovery when
a diverged machine should return to its blueprint shape. A *scoped*
change is put back before the run ends, so the machine is found as
it was and the state a diagnostician might have wanted is gone —
which is why the failure report names every restore the run
performed. Neither is the safe default: leaving an installer CD
attached is how the next boot runs the installer again, and taking
it back is how the screen that failed stops being reproducible.

### `set-boot`

```rlqs
set-boot hdd0 cdrom0
set-boot cdrom0
```

`set-boot` replaces the machine's boot order with the listed drive
keys (canonical or alias form), persisted in the machine's state
document — the verb *sets configuration* rather than performing an
immediate action, and its name says so. Every key must name a
drive the machine already
declares; duplicates are rejected. The machine must be stopped —
the new order takes effect on the next `start`, and **a `set-boot`
the static check can prove is reached with the machine running is
refused before the run starts** (V17) rather than five minutes
into an install. Like
`insert`/`eject`, the change diverges the machine from its
blueprint until a later `set-boot`, or
[`apply`](../blueprint-guide.md#applying-blueprint-edits), restores
it.

Most install scripts never need this: an installer-carrying
blueprint boots its optical drive ahead of the disk, and the script
ejects the medium once the disk is bootable, so the disk takes its
turn without any boot depending on firmware falling *past* a
device. Falling through is not something to rely on — firmware is
reliably willing to skip an **empty** drive and nothing more, and a
disk partitioned without an active partition, which is the state an
installer leaves behind before its reboot, is where the two
reference backends part company. The verb exists for scripts that
genuinely need a different order than the blueprint's default.

### Scoped machine-state changes

```rlqs
with boot cdrom0 {
    phase startup { … }
    phase cd-boot { … }
}
```

`insert`, `eject` and `set-boot` change the machine durably and
leave it changed. A `with` block gives one such change a **scope**,
and the scope undoes it: the head names the change, the block names
what it holds for, and leaving the block puts the target back to the
value it held on entry.

**The head vocabulary is closed at three names**: `boot`, `insert`
and `eject`. The last two are the verbs above, written exactly as
they are written as statements and carrying exactly their
signatures, so a scoped `insert` answers to the same slot rules, the
same media resolution, and the same preflight.

**`boot` states a prefix, and is deliberately not `set-boot`.** The
drives it names come first, in the order given, and the machine's
own order follows for everything else — so `with boot cdrom0` over a
machine ordered `["hdd0", "cdrom0"]` boots `["cdrom0", "hdd0"]`, and
an author never restates an order they are not changing. Naming more
than one drive pins a longer prefix. Every key must name a declared
drive, as `set-boot`'s must, and each key names a drive once — by
slot, so an alias and its indexed form are the same drive.
`set-boot` is untouched and still *replaces* the order: two
spellings, two meanings, which is the one thing a closed grammar
cannot afford to blur.

**A `with` block wraps whatever unit the surrounding script already
uses** — phases in a phased script, statements in a linear one, and
nested `with` blocks in either. That's also what gives the language
a word for a **stage**: a group of phases wrapped together. It's
the only way to express that grouping at all, since an install's
stage spans multiple phases, and every phase body has to end in a
transition.

**The scope is where control is, not where the text is.** It holds
while control is inside the group; it is entered by reaching any
phase in it, including by `goto` from outside, and left by reaching
a phase outside it or by the run ending. Re-entry re-applies. In a
linear script, where there is no `goto`, this reduces to the text.

**On exit the target returns to the value it held on entry**, on
every outcome the runtime reaches: `finish`, a failure, and a
cancellation at a boundary. A host crash restores nothing, and
[`apply`](../blueprint-guide.md#applying-blueprint-edits) remains
its recovery — exactly as for an unscoped change.

**Restoring the boot order requires a stopped machine.** The boot
order is launch-time firmware configuration, and it's stopped-only
as a property of the machine itself, not just as a courtesy to the
author — so the scope's restore doesn't get an exemption from that
rule; exempting it would just be a second, unguarded way to write
the boot order. If the scope's exit point is reached while the
machine is running, that **fails the run**, naming the change it
couldn't undo. Wherever the static check can prove that exit point
is reached while running, it's an authoring-time refusal instead
(V17), which is where most such mistakes actually get caught.
What's left over is real and accepted: a run whose route the guest
chose can still fail on its very last act, and the fix is to
structure the script itself so the stage ends with the machine
down. Media restores carry no such rule — `insert` and `eject`
work whether the machine is running or stopped, so a media restore
can happen live while the machine is up.

**One scope per target.** The boot order counts as one target no
matter how many drives a `boot` head names; a medium's target is
its slot, so an `insert` and an `eject` on one slot collide. Two
scopes on the same target, nested or overlapping, are refused;
scopes on different targets nest freely.

Entry and the restore are reported on the [run event
stream](#the-run-event-stream) (`scope.enter`, `scope.restore`), and
a failure report names every restore the run performed. That's not
just decoration: what a scope restores is state a diagnostician
would otherwise have found still on the machine, so a run that
restored it has to say so explicitly.

### `set`

```rlqs
set result "PASS"
set build "${tag}"
```

`set` records a **machine variable** — the script's channel back to
the host for one small value (U14/U20). The key is a name outside
the reserved `rlq` and `reliquary` namespaces; the value is a
string, which may interpolate a bound property. The variable lands
in the machine's state document, where any process reads it with
`get-machine-var` (twin `get_machine_var`) while the run is still
going or long after it ends.

Variables are **cleared at each `start`**, so a variable always
reflects what the current boot produced, never what a previous boot
left behind. The names and values both belong entirely to whoever
is consuming them: Reliquary just stores them and attaches no
meaning of its own to either (G2, P18).

**This is also how "readiness" gets signaled.** Reliquary ships no
readiness *policy* of its own — what "ready" means belongs to
whatever workflow is being built on top of it, not to Reliquary
(P18) — so a consumer's own script signals it by calling `set` on a
variable as its last step.

How the host reads a variable back depends on who set it, and there
are two supported shapes rather than one hand-written polling loop:

- **The run that sets it is the same run you're waiting on.**
  `run-script <label> --expect ready=yes` ties the run's own
  success to that variable: the run blocks until it finishes, so by
  the time it returns, the value is final — and a run that never
  sets the variable raises an error immediately, rather than being
  discovered later by a caller who reads `get-machine-var` and
  finds nothing there. One call gets you a failure that names the
  key, what was expected, and what was actually found.
- **Someone else sets it** — a run driven from another thread, or
  one you're only observing rather than the one that owns it.
  `wait-machine-var ready` polls until the variable appears, which
  is the only case where a polling interval actually means
  anything.

An unset variable and a machine that's never been run both read the
same way through `get-machine-var`, deliberately. What the two
verbs above add is a way to say explicitly that the silence
*wasn't* expected.

### `font`

```rlqs
font @guest
font @installer $localized-face
```

`font` states a **prefix**, in force from that point in the run
forward: the named fonts (`.rlqf`, an authored asset resolved
through the ordinary catalog — [asset-resolution.md](asset-resolution.md))
are tried before the host's own, in the order given (F61, D109). A
second `font` **replaces** the prefix outright rather than appending
to it — an author who wants two fonts in force at once names them
together on the one statement. It takes one or more `@font` or
`$property` references, the same typed pair `insert` accepts; a
literal `@name` naming no font in the active source fails static
preflight, before any guest input, exactly like `insert`'s
`media.unknown` (below).

**The list order is a real priority order, not a tiebreak rule.**
The recognizer tries fonts in list order (authored fonts first,
then the host's own) and stops at the first one whose best match
for a cell falls inside its distance threshold; a font named later
in the list is only consulted once every earlier one has missed.
That's what makes naming a font *narrow down* the answer, rather
than just add one more candidate shape to a single big search
across everything. It's also what makes a per-font codepage well
defined: without a fixed order to decide it, there would be no way
to say which font actually matched a given cell. A font's
declaration states what its raw bytes can't: the cell geometry, and
which codepage its indices mean. A cell matched through a given
font is decoded using that font's codepage; the host's own built-in
fonts keep their existing mapping unconditionally.

`font` is deliberately not a `with` head: the three heads the
language has are all durable machine changes that a scope exists to
undo, and a font changes nothing on the machine — there's nothing
for a scope to put back (see [Scoped machine-state
changes](#scoped-machine-state-changes) above). It's equally not a
header declaration, because a header can't say *when during the
boot* the active font should change — only the script itself knows
that.

**A wrong font says so.** The failure report's unread-cell count
gains the fonts the last read was matched through, in the order
they were tried, so a script that named the wrong face is told what
was actually consulted rather than left with a silent timeout (P11).

### File exchange — a named omission

The language deliberately has no file-exchange verbs (owner,
2026-07-22). Moving files across the host/guest boundary is the
caller's job, not the script's — the same way interpreting what a
run produced is the caller's job (G2). While a machine is stopped,
on every control plane, its drives and shares are just plain host
state: a [share](media-spec.md#the-media-component) *is* its host
directory (F68), and drive images are readable and writable with the
user's own ordinary tools. So file exchange is ordinary host work
done outside the script, against the machine directory
(`get-machine-dir` reports where that is; the contract for it is
in [the instance model](instance-model.md)). Leaving this out of
the language also keeps every quoted string in a script meaning
one thing: string content is guest-facing text, never a host path.

**This isn't a CLI or API capability either** (D108). Reliquary
never places a file onto a machine's drives or shares, never reads
one back, and never maps a volume to a guest drive letter, on any
surface: a machine's file content is deliberately outside what
Reliquary handles (**P16**'s carve-out). A caller that needs to move
a file in or out has to supply the device and move the file itself —
by declaring a share whose media is a host directory (F68), by
swapping an image live with `insert-media --file` (U20), or by
opening the machine directory that `get-machine-dir` reports with
their own tools. A future live guest-agent transfer feature would
get its own distinct capability, with an explicitly stronger
guarantee than any of this. None of that changes the *language*,
though: the omission described above stands, and reopening it
would be a separate language decision, governed by the growth
goals.

### `start` and `stop`

```rlqs
stop
start
```

`stop` is a host-side hard power-off and should be used only when a
clean guest shutdown is unavailable or when offline exchange is
required. `start` starts a stopped machine as its state document
describes it — including media inserted earlier in the script or a
previous run. Starting an already-running machine or stopping an
already-stopped one is an error.

There is no `restart` or `reboot` verb. A guest reboot is guest
input (`enter "reboot"`, a menu choice, or the appropriate key
sequence) followed by observation of the resulting screen. A hard
power cycle, when genuinely wanted, is written explicitly as
`stop` followed by `start`, making both its destructiveness and its
reconciliation behavior visible.

## Validation and preflight

Parsing and static validation enforce the legality rules — the
[lexical rules](#lexical-rules), the grammar, and the
[syntactic restrictions](#syntactic-restrictions) V1–V16 — from
the script text alone, before the machine starts. With more in
scope, preflight further rejects, naming what it needed:

- media references (`@name`) naming no media the namespace
  defines (the media namespace);
- `font` references (`@name`) naming no font the source defines
  (`font.unknown`, the font namespace — F61);
- landmark references (`@name` in condition position) naming no
  landmark the source defines (`landmark.unknown`, the landmark
  namespace — F65) — and, in any of the three positions, a `@name`
  that resolves to *another* kind of the one pool, refused naming
  the use and the kind (`landmark.wrong-kind`, `media.wrong-kind`,
  `font.wrong-kind`);
- a landmark condition on a machine whose driving control plane
  captures no framebuffer (`machine.plane-no-framebuffer`, a
  machine) — capability at the condition's granularity, so a script
  watching no landmark is unaffected;
- `click` on a machine whose `devices.pointer0` is not
  `virtual-tablet` (`machine.pointing-device-not-tablet`), or whose
  driving control plane cannot deliver a pointer event
  (`machine.plane-no-pointer-input` — a separate question from
  framebuffer capture, since a plane can hold one without the
  other) (F66, a machine);
- `click spot=` naming nothing the landmark declares
  (`landmark.spot-unknown`), and a `click` with no `spot=` where
  the landmark declares zero or more than one
  (`landmark.spot-required`, the lone-spot default applying only
  where exactly one exists) (F66, a landmark);
- `insert`/`eject` slots and `set-boot` drives the target
  machine does not declare — a `with` head answering to the rule
  of the action it spells, and a scoped `boot` prefix to
  `set-boot`'s (a machine);
- explicit `--property` keys the running script does not declare,
  keys given twice, and still-unbound noninteractive properties
  (the explicit values);
- malformed blueprint parameters, direct blueprint values on
  `secret` properties, and parameter kind mismatches (a
  blueprint);
- environment-name collisions between consulted keys, kind
  mismatches at the file source, and required secret credentials
  unavailable from a secure host
  store (the property sources).

Every one of those checks needs more than the script text alone.
What the text alone can decide is settled before preflight is even
reached — V17 included: if the static check can prove a
stopped-only verb runs while the machine is up, that's a legality
error, not a preflight one, and the machine it would have needed is
never even consulted.

Static analysis warns about unreachable phases, reactive phases
with no possible exit, obvious shadowed literal conditions, a
regex containing no regex metacharacters (write the string form),
properties
that are declared but unreferenced, and — with a blueprint in
scope —
blueprint parameters matching no declared property of any script
in its `scripts` map.

After binding properties, preflight computes every capability the
script may require and compares the complete set with the machine's
configured backend and control planes. Capability failure occurs
before the first input, naming every unsupported verb and required
capability; a script never runs halfway before discovering that a
later statement is impossible.

```text
rlq run-script <script_name> --dry-run
    [--machine <id> | --blueprint <name>]
    [--property <key>=<value>]... [--properties <path>]
```

performs parsing and static analysis — including the resolved
timing plan, each observation's effective timeout and which scope
supplied it, and a count of the statements no static pass can
guarantee will actually run — without executing the script,
changing the user's properties, accessing secret values, or
writing any file. Supplying a machine (and any explicit property
values) also runs typed binding — reporting which source supplied
each declared property (flag, blueprint parameter — direct or
redirect — environment, file, or ask) — and capability preflight.
This source-aware checking reports whether a property is present,
its kind, and which source supplied it; it never reveals the
property's actual value. Its two modes correspond to the two
checkable tiers described in the
[processing model](#processing-model). The embedding API's
equivalent is `run_script(dry_run=True)`, which returns a
`DryRun` object rather than a `ScriptRun`. `start_script` is the
API's counterpart to `run-script --detach`: it returns a run
handle whose operations the CLI's `run` family mirrors, and
`attach_run` reopens that same handle from a fresh process — the
CLI and the API accept the same identifiers throughout.

### Error classes and exit codes

Every failure this surface can produce belongs to one of three
classes, matching the enforcement tiers — which are not this
surface's alone, as the generalization below sets out:

| class | tier | exit code |
|---|---|---|
| STATIC ERROR | legality rules (V-ids) | 2 |
| PREFLIGHT ERROR | machine rules | 3 |
| RUN FAILURE | dynamic semantics | 4 |

`0` is success; `1` is reserved for Reliquary's own faults; `5` is
a cancelled run — a deliberate `run cancel` (API
`cancel()`) that ended the run at an event boundary with a
`cancelled` terminal event, neither success nor RUN FAILURE. The
classes are the CLI's exit codes and the API's
exception taxonomy — one mapping, under parity: Python spells it
`StaticError` / `PreflightError` / `RunFailure` / `RunCancelled`
under the `ReliquaryError` root every deliberate Reliquary error
subclasses (docs/spec/api.md), and exit `1` is precisely
an error outside those four.

**These three classes aren't specific to scripts** (D58). They're
named after a run's enforcement tiers, but they apply unchanged
across every surface in Reliquary, because the question that
decides which class applies never actually mentions a script: is
this settled by the authored input alone? does the world satisfy
that input? did the work itself fail? So a malformed blueprint is
a STATIC ERROR exactly like a malformed script is; naming a
machine that doesn't exist is a PREFLIGHT ERROR exactly like naming
an undeclared drive slot is; and a failed image transfer is a RUN
FAILURE with no script run involved at all. A capability that
Reliquary declares but hasn't actually implemented yet is a
PREFLIGHT ERROR: the request itself is legal, and the world —
which includes what this particular build implements — just
doesn't satisfy it.

Exit `1` therefore always means a **bug in Reliquary itself**,
never a mistake by the caller, and it can happen two ways, both of
them Reliquary's own fault: a deliberate `InternalError` (Python)
— an invariant Reliquary caught itself violating, with no user
input that could have fixed it — or a genuine accident: an
exception that was never wrapped as a `ReliquaryError` at all.
Every deliberate `raise` in the package lands somewhere in the
`ReliquaryError` hierarchy, so `except ReliquaryError` remains the
documented catch-all; an unwrapped builtin exception is the one
case that slips past it, caught only by whatever invariant the
language runtime itself enforces.

Every diagnostic
carries a stable dotted identifier naming its rule
(`obs.two-channels` style); identifiers share one namespace
across the classes, and the full id index is deferred to beta.

**Diagnostic ids are more fine-grained than the V-numbered rules.**
A V-number names a whole restriction; an id names one specific
diagnostic under it — V7 is one rule, and `obs.two-channels` is
just one of the six ways to break it. These aren't two competing
schemes: a message only ever carries the id, and the
[syntactic restrictions](#syntactic-restrictions) section lists
which ids enforce each V-numbered rule, which is how a reader gets
from one to the other. An id's prefix names its subject, never its
error class or which surface raised it, because the same prefix
namespace is shared across all of them: `obs.`,
`wait.`, `handler.`, `flow.`, `name.`, `prop.`, `time.`, `key.`,
`node.`, `http.`, `media.`, `font.`, `machine.`, `platform.`,
`progress.`, `store.`, `lex.`, `syn.`, `ref.`, `value.`, `field.`,
`drive.`, `blueprint.`, `image.`, `screen.`, `script.`, `dir.`,
`command.`.

Every subject past the script language's own is a noun the rest of
the model already uses, rather than a name invented for the
occasion. From the blueprint document
(`docs/spec/blueprint-model.md`): `ref.` for the `${…}` grammar,
`value.` for what a field's value has to be, `field.` for the
document's field vocabulary, `drive.` for drive keys, slots and the
boot order, `blueprint.` for the document as a whole. From the rest
of the system: `image.` for a materialized disk image, `screen.` for
what the guest displays, `script.` for a script file, `dir.` for one
of the six working directories, `machine.` for a machine and its
phases, `media.` for a media and its payload, `platform.`,
`progress.`, `store.`, and `command.` for one command sent to a
guest — its outcome, and whether that outcome could be read at all.

`command.` is the subject a *guest command* takes, where `screen.`
is what the guest displayed: `screen.no-echo` says the rows cannot
be attributed, and `command.signalled-failure` says the command
itself reported failure. Two facts about two different things, which
is why the second did not take the first's prefix.

Two families the blueprint document could have taken new subjects
for took existing ones instead: its name-charter rules are `name.`
and its media semantics are `media.`, those being the same rules
already named elsewhere.

**This list is closed and enforced.** A diagnostic whose subject
is not on it does not get a new prefix invented for it in passing;
the list grows by an edit here, and a test holds the code and this
list to each other in both directions — an id with an unlisted
subject fails, and a listed subject nothing raises fails too.

This subject-based naming is exactly what lets **one rule keep one
id across every surface it applies to** — that's its whole
purpose. `media.unknown` fires both where the resolution namespace
defines no such media, and where a script's `insert` names one
that doesn't exist: one underlying condition, one id, one answer
for a caller asking what went wrong. `name.duplicate-property`
covers both a script that declares a property twice and a
properties file that defines the same key twice.
`machine.not-running` covers the CLI, the script runner, and the
machine verbs alike. If the prefix had instead named the
enforcement tier or the surface that raised it, each of these
would need two or three different ids for what is really one rule,
and a caller would have to already know which layer caught the
problem before it could even tell what went wrong.

An id is a **contract**: it is what a consumer switches on, so it
is stable where the message text is not. The message wording,
like every human rendering, is uncontracted and free to improve.

Coverage on this surface is complete: the lexer, the grammar, the
node signatures, the static rules, and — since the error classes
generalized to every surface (D58) — the preflight and runtime
tiers too, property binding and media resolution included. The
script conformance corpus
(`tests/fixtures/conformance/script/`) holds it there by
refusing to let a fixture claim an id that is absent, or omit one
that has arrived.

**Every surface is covered.** Generalizing the error classes
generalized this requirement with them: a malformed blueprint is
a STATIC ERROR like a malformed script, so it owes an id on the
same terms — as do the machine verbs, the VM lifecycle, the guest
console, the properties file and the credential store. All of
them have one. Three assertions hold it there rather than a
measurement having to be repeated: every deliberate raise in the
package carries an id, every id's subject is one this list names,
and both conformance corpora check that the id a fixture declares
is the id that fires.

**Blueprint diagnostics are located too** (D70). A script
diagnostic cites a line and column, or the statement it came from;
a blueprint diagnostic cites its field breadcrumb *and* the line
and column that field was written at, rendered with the same
layout — `<path>:<line>:<column>: error: <message> (<id>)`, with
the source line and a caret underneath it. The field breadcrumb
didn't move into that rendered layout — it stays in the message
text, because the breadcrumb says *which field*, and the
line/column say *where in the file*, and those are two different
questions.

Position is **optional and its absence is not a defect**. It comes
from the document's text, so a blueprint loaded from a path has
one and a value handed straight to the API does not — there is
nothing to point into, and citing nothing is the honest answer.
Other surfaces stand where they stood: a preflight diagnostic
about the media namespace has no document position to cite and
carries an id alone.

The grammar's own rejections are the least specific ids in the
whole scheme: `syn.unexpected-token` and `syn.unexpected-end` name
a token, not a rule, because a token is all a parser actually
knows at that point. That's the cost of keeping the V-numbered
rules layered above the context-free grammar rather than folded
into it, and it shows up exactly where you'd expect: a construct
the grammar itself refuses can't carry the id of whichever V-rule
it happens to violate.

## The run's output and failure

A run drives the machine and **returns its output** to whoever
started it; it stores nothing on disk (owner, 2026-07-24; D36).
That output is the [event stream](#the-run-event-stream) —
rendered live to whatever's driving the run (pretty for a person,
jsonl for a program) — and it's gone once the run ends. There's no
run directory, no persisted `run-events.jsonl` or `transcript.txt`,
no retention policy, and no `run` management command family:
persistence is what a cross-process follower would need to read
from, and letting a process that didn't start a run follow it
anyway is asynchronous work still in the backlog
(proposed/FEATURES.md "Asynchronous runs", D35/D36) — that's also
where the entire record model now lives (the `runs/<n>/` archive,
monotonic numbering, retention, `list-runs`/`run status`/`run
delete`, and interaction runs). As of milestone 9, nothing is
stored: each run returns straight to its own caller, which is
exactly what keeps the multithreaded case free of needing a shared
store.

The stream ends with a **terminal event** stating the outcome:
success, a failure class, or cancelled — Ctrl-C on a foreground
run emits a `cancelled` terminal event, exits `5`, and leaves
the machine as-is but for the
[scoped changes](#scoped-machine-state-changes) it puts back,
which the cancellation names. Under `jsonl` the last line is the
machine-readable result; there is no separate result mode. On
the API, `run_script` / `exec` return a typed result and raise
by error class ([error classes and exit
codes](#error-classes-and-exit-codes)).

On failure the returned output carries the pending condition or
action, the clock that expired and the scope that supplied it
(statement timeout, phase deadline, or run deadline), final
observed screen text, machine state, and an automatic screenshot
when available.

**Whatever a run produces belongs to the consumer**, never to a
record Reliquary keeps: the returned value, a small value read
back from a machine variable, or a whole disk image swapped out
and read with the caller's own tools. Reliquary attaches no
meaning to any of it, and has no test-result vocabulary at all —
no pass/fail schema, no result parsing (G2). A loop built directly
on the primitives needs no special bracket to be recorded: the
caller's own driving code, collecting each call's returned output,
already *is* the record. Choosing what to run, per run, travels as
ordinary script properties; detailed results come out as whatever
files and values the caller itself produces. It's the consumer's
job, not Reliquary's, to keep, organize, or discard any of it (P4,
P18).

There is no automatic retry. Re-running an installation against a
partially modified disk is not generally safe and is not described
as a retry. The caller deliberately resumes, recreates the machine,
or runs again according to that workflow's documented recovery
semantics.

### Interaction runs — the recording bracket

A loop built directly on the primitives needs no recording bracket
as of milestone 9: each command returns its own output, and the
caller's own driving code, collecting those outputs, already is
the record (D36). A `begin-run`/`end-run` bracket that would
record such a loop into one persisted run record is part of the
record model, which moved to the asynchronous-runs backlog along
with the rest of persistence (proposed/FEATURES.md "Asynchronous
runs", D35/D36); it comes back if that work gets scheduled.

U14's unit-test loop works fine without it: which tests to run,
per run, travels as ordinary script properties (`--property` or
the `properties=` mapping, interpolated through property
references); detailed results are a caller-authored artifact
(JUnit XML, TAP) that the caller takes directly — swapped out as a
disk image and opened with its own tools (U20), read off a share's
directory on the host, or captured as text through `exec` — and the
caller is responsible for keeping it.
Reliquary deliberately has no test-result vocabulary of its own —
no pass/fail schema, no result parsing (G2). Granularity comes
from the run's own structure: one iteration is one returned
output.

## How the vocabulary grows

The current vocabulary is a foundation to build on, not a promise
that every future feature has to squeeze into an already-frozen
grammar before real-world use has even tested it. Before beta,
actual use of the language may still reshape it, as long as that
reshaping stays coherent.

The intended post-beta growth discipline is (G7):

- existing observation forms keep their meanings;
- **a new channel names a new non-default observable surface; a
  new value spelling names a new matcher over the default
  surface.** A serial stream becomes `wait console="login:"` — a
  new prefixed channel, because it is a different observable.
  Image matching became a landmark reference, `wait @setup-page`
  — a new value spelling, because it is a different matcher over
  the same screen. Neither is a new construct or a positional
  keyword;
- new action kinds use explicit sibling forms following the same
  node shape, as `click` does (F66) beside `select`;
- **a new construct is argued as one.** `with` is the only block
  form added since the vocabulary was set, and it earned that
  standing by expressing a unit — a *stage*, a group of phases —
  that no modifier on an existing verb could name (D104). The
  cheaper spellings were weighed and declined for saying something
  narrower than the demand, which is the bar a second construct
  meets or does not;
- new behavior never appears merely because a script omitted a new
  modifier; and
- capability requirements remain explicit and preflightable —
  at the granularity of the condition, not only the channel: a
  text condition needs text readback, a landmark reference needs
  framebuffer capture, and a condition the selected control plane
  cannot observe is a named capability failure before the first
  input.

This rule is the reason machine state is spelled `machine=stopped`
rather than as a bare keyword: the non-default observable is
always named, so a script that later watches a serial console
reads the same way as one watching the machine — while the screen,
the default, keeps exactly one spelling per matcher.

Image matching and pointer input extend observation and action;
they do not introduce a second control-flow model or any new
punctuation role.

## Complete FreeDOS install example (non-normative)

```rlqs
description "FreeDOS 1.4 plain install from LiveCD"
platform    dos
machine     stopped
entry       startup
timeout     30s
deadline    45m

with boot cdrom0 {

    phase startup {
        insert cdrom0 @freedos-livecd
        start
        goto cd-boot
    }

    phase cd-boot {
        wait   "Welcome to FreeDOS 1.4 (LiveCD)"
        select "Install to harddisk"
        wait   "What is your preferred language"
        select "English"
        wait   "Welcome to the FreeDOS 1.4 installation program"
        select "Yes"                # feedback-driven: a bare `press
                                    # enter` here is drawn before the
                                    # installer reads the keyboard

        wait {
            on "Drive C: does not appear to be partitioned." {
                select "Yes"
                goto partitioning
            }
            on "Drive C: does not appear to be formatted." {
                select "Yes"
                goto formatting
            }
        }
    }

    phase partitioning {
        wait   "You must reboot your computer"
        select "Yes"
        goto cd-boot
    }

    phase formatting timeout=5m deadline=20m {
        wait   "Press a key..."
        press  enter
        wait   "Please select your keyboard layout"
        select "US English (Default)"
        wait   "What FreeDOS packages do you want to install?"
        select "Plain DOS system" exclude="with sources"
        wait   "We are now ready to install FreeDOS 1.4."
        select "Yes"
        wait   "Installation of FreeDOS 1.4 is now complete."
        eject  cdrom0               # before the reboot, not after:
                                    # the stage boots cdrom0 first, so
                                    # the disk is only reached once the
                                    # drive is empty
        select "Yes"
        goto hd-boot
    }

    phase hd-boot {
        wait   "Load FreeDOS"
        select "Load FreeDOS with JEMM386 (Expanded Memory)"
        wait   "C:\>"
        screenshot installed
        goto shutdown
    }

    phase shutdown {
        enter "fdapm poweroff"
        wait  machine=stopped timeout=2m
        finish                      # the eject already returned
                                    # cdrom0; the scope returns the
                                    # boot order behind this line
    }
}
```

The blueprint declares `cdrom0` empty and boots
`["hdd0", "cdrom0"]` — that's what the machine *is*: a system that
boots its own hard disk. **Booting from the installer is true of
this particular install, not of the machine itself**, so the
script is where that fact belongs: `with boot cdrom0` puts the
optical drive ahead of the blueprint's own order for the whole
install, and puts the order back once the run ends. The scope
wraps the phases, rather than sitting inside just one of them,
because the stage spans multiple phases — the `cd-boot` ⇄
`partitioning` cycle crosses between them twice — and every phase
body has to end in a transition anyway.

**The `eject` is what actually hands the disk its turn.** While
the scope holds, every boot takes the optical drive first, so the
hard disk only gets reached once that drive is empty — no boot in
this run ever depends on firmware skipping past a partitioned
disk. Ejecting during `formatting`, rather than after the reboot
selection, keeps the eject off that reboot's critical path. The
guest-driven reboot itself is expressed through the installer's
own menu selection and the screen that follows, not through any
Reliquary reboot command — it belongs entirely to the guest: the
machine itself never stops, so firmware reads the same boot order
it was launched with, again.

The second visit to `cd-boot` reaches the other branch of its
closing `wait` because the disk has been partitioned.

The scope's exit point is reached in `shutdown`, with the guest
already powered off — which is exactly what restoring the boot
order requires. If the script had handed back a running machine
instead, the run would have failed on its very last act, naming
the boot order it couldn't put back.

Verification is a separate script that needs no machine
reconfiguration at all: the install already returned both the
medium and the boot order, so the machine is back in its blueprint
shape, and a plain `start` boots the installed hard disk right
past an empty optical drive. The verify script also declares
`machine stopped` and issues that `start` itself. If a run was
interrupted before it could restore anything — a host crash, which
no scope survives — `apply` is what returns the machine to its
blueprint shape.

## Sharing

A shareable blueprint/script bundle consists of its script, the
machine blueprint (its media, source, and archive components ride
inside it), and the landmark declarations it references, plus
optionally an example properties file containing only non-sensitive
illustrative values. A script carries no JSON, so a bundle is a
small set of files beside each other rather than a single document.
The user's own properties file, secret values, and
host payload files exchanged with machines stay out of the
bundle and version control. A script's declarations name its property keys, but every
recipient supplies their own values. Media remains hash-pinned and
independently fetched.
