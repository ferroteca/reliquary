<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
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
> `reliquary/codex/scripts/freedos-install.rlqs` is
> the reference script, and the files under
> `planning/design/script-examples/` catalog known residual rough
> edges in this surface. Properties and their binding and the full
> transcript contract remain later milestones; details may still
> change before first release.

A Reliquary script automates a guest: it watches observable guest
and machine state, supplies input, swaps media, and moves files
across the VM seam. Scripts are authored assets — `.rlqs` files,
identified by extension. They resolve from the `scripts` directory,
walked recursively, which defaults to `<home>/scripts` and is
placeable with `--scripts-dir`; a miss falls back to the built-in
codex while autoseeding is on — the CLI default, and never the
embedding API's (docs/spec/asset-resolution.md).
One `<name>.rlqs` file per script; a run selects its machine with
`--machine <id>` or, when the
blueprint has exactly one machine, `--blueprint <name>`:

```powershell
rlq run-script install --blueprint freedos
```

After preflight, `run-script` resolves its machine
(creating one when `--blueprint` names a
blueprint with no machine yet), brings it to the state the script's
[`machine` header](#header) expects — starting a stopped machine
when the script expects `running`, failing when the script expects
`stopped` but the machine is running — then executes the script. The
machine stays in whatever state the last executed step left it.
Failure likewise leaves the machine in its observed state for
diagnosis; no command implicitly tears it down. The embedding
API's twin is `run_script`, taking the same identifiers under
CLI–API parity.

Scripts are authored documents: Reliquary reads but never rewrites
them — with one named exception: the authoring recorder's opt-in
fragment apply (U6; [recorder.md](../../planning/proposed/design/recorder.md)) inserts a captured
fragment at its playback anchor
and touches no other byte. They belong in version control beside
the machine blueprints (media components and all) on which they
depend.

## Primary language goals

Every language decision is judged against these. They are numbered
so later decisions, reviews, and spec sections can cite them, and
so a proposed feature can be rejected by naming the goal it costs.

- **G1 — Agentless at the guest seam.** The guest is a black box
  that cannot be configured, only watched and typed at. No feature
  may depend on guest cooperation. This is a permanent requirement
  ([AGENTS.md](../../AGENTS.md)), not a current limitation.
- **G2 — Non-computational.** No expressions, variables,
  arithmetic, functions, or general-purpose loops. Anything
  computational belongs in Python via the embedding API, which
  remains a first-class surface.
- **G3 — Statically inspectable before the machine starts.**
  Parsing, binding, control-flow analysis, and whole-script
  capability preflight all complete before the first guest input.
  The authored graph is explicit and finite even when a run cycles.
- **G4 — Legible in real time.** A run is usually long, unattended,
  and watched by someone who wants to know where it is. The
  language's own structure — named phases, the pending observation,
  declared budgets — must be sufficient to answer "where am I, what
  is it waiting for, how long has it got" without extra syntax.
- **G5 — Backend- and control-plane-agnostic at the surface.** A
  script says "wait for this text"; the machine's backend and
  selected control plane decide how that is observed. Verbs stay
  intent-level, above portable input events.
- **G6 — Small and unambiguous.** Brevity, succinctness, structure,
  clarity. One concept, one spelling. Surface area is the scarce
  resource; deletion is the preferred remedy.
- **G7 — Grows coherently.** New capabilities extend observation and
  action without adding a second control-flow model or a second
  syntax. Growth stays explicit and preflightable.

## The procedural–declarative seam

The language is deliberately a hybrid, and the seam between its two
halves is the most load-bearing decision in the design. Naming the
seam early is what keeps later decisions consistent; most of the
language's prohibitions exist to keep it clean. The rule itself is
stated with the language model below; this section is the argument
behind it.

Everything knowable before the run starts is declared — the
platform, the machine state the script expects, which phases exist,
their timing budgets, the media it needs, the inputs it binds.
Everything the guest dictates is procedural — which key to send,
what text to wait for, the order its own installer screens arrive
in. The seam falls where our knowledge ends:

| concern | paradigm | why |
|---|---|---|
| machine shape | declarative (the blueprint) | ours, and knowable |
| which phases exist, their budgets | declarative | ours, and knowable |
| media and property references | declarative | ours, and knowable |
| keystrokes and observations within a phase | procedural | the guest's installer dictates the order |
| which route the run takes | procedural choice over a declarative graph | the guest chooses at run time |

**Why not fully declarative.** OS installation has a mature
declarative form — Kickstart, preseed, AutoYaST, Windows
`unattend.xml` — in which the author states what the installed
system should be and the installer does the rest. Where those
exist they are strictly better: Reliquary does not invent a
competing declarative install language. For guests that accept
them, it serves the answer file the way Packer does today — a
local HTTP server the installer fetches from
([http-serve.md](http-serve.md)).
Procedural keystroke scripting remains for the guests where
answer files do not exist: DOS, Win9x, and similar. G1's
agentless requirement is about the control plane — no dependence
on a guest agent or other cooperating software for observation
and input — not a ban on an installer's native answer-file
path. Using Kickstart (or its kin) is that path; it is not a
substitute for agentless scripting on guests that lack one.

**Why not fully procedural.** A plain imperative script — the
AutoHotkey or Expect shape — would be shorter to specify and would
need no phase concept at all. It is rejected because it forfeits
G3 and G4 together: a straight-line script with ad-hoc loops has
no statically knowable shape to analyze, and no named units to
report progress against. The declarative half is what makes a run
checkable before it starts and legible while it runs.

**The tensions this creates, which we accept.** These are real and
should not be papered over; several are already catalogued as
residual problems in [`script-examples/`](../../planning/design/script-examples/):

- `phase` is a declarative construct whose body is procedural. The
  hybrid is not hidden; it is the point.
- A sequential phase is procedural, a reactive phase is
  declarative, and both are spelled `phase`. The two are forbidden
  to mix rather than given a combined semantics — a prohibition,
  not a definition.
- The paradigm boundary shows in the handler keywords: `on` is a
  case in a branching `wait`, `always` a standing rule in a
  reactive phase — one shape, two named lifetimes, which the
  keyword split resolved.
- Declarative timing scopes annotate procedural statements, so an
  observation's effective bound is not locally readable
  (`script-examples/03`, open).
- Procedural `insert`/`eject`/`set-boot` mutate declarative
  machine state that outlives the run, deliberately diverging a
  machine from its blueprint until restored — the `set-` prefix
  naming the persistence is what settled the spelling.

**The prohibitions that keep the seam clean.** Each exists to stop
the procedural half from eroding the declarative half:

- no author-side conditionals — the only decisions that matter are
  the guest's, expressed as observations of what it actually
  showed, never as the script author's logic (G2);
- inputs supply data and may never select a branch, a phase, or a
  path, so the graph stays static (G3, P19);
- no fallthrough and no anonymous phases, so every route is named
  and searchable (G3, G4);
- no `sleep` or `delay`, so every pause is justified by an
  observation rather than a guess about guest speed (G1, G5);
- no implicit machine teardown, so a failed run leaves state to
  diagnose rather than a tidied crime scene.

OS installation automation is expressed as install and verify scripts
attached to machine blueprints. Media acquisition (download, hash-verify,
cache under `cache/media/`) stays a host-side capability the language can
invoke, with pinned hashes kept in shared definitions or directly inside
the script.

## The language model

The language is a deliberately constrained, domain-specific
programming language. It has sequencing, branching, named phases,
and explicit phase transitions, but no expressions, mutable
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
- **Actions** deliver intent-level input or perform supporting host
  operations: `enter`, `type`, `press`, `select`, `insert`,
  `eject`, `set-boot`, `set`, `screenshot`, `start`, and `stop`.

Intent-level verbs remain above portable input events. `select`
means choosing a visible menu entry, not sending a guessed number
of Down keys. The selected control plane composes the necessary
key press and release events and owns their pacing (G5). Pointer actions
will follow the same model when GUI automation arrives.

Three design rules govern the whole surface:

- **One shape.** Every line of a script is a *node*: a name,
  positional arguments, `name=value` properties, and optionally a
  block. The entire structural grammar is that one production.
- **Spelling reveals role.** Every token class has exactly one
  spelling and every punctuation mark exactly one role; a reader
  can classify any token without context. See
  [lexical rules](#lexical-rules).
- **Nouns declare, verbs act.** Declarative nodes (headers,
  `property`, `phase`) begin with a noun; imperative nodes begin with
  a verb. The declarative zone precedes the imperative zone, and
  the grammar enforces the boundary.

That third rule reflects a deliberate split: **a script is
declarative about everything Reliquary owns, and procedural at the
seam with the guest.** What is knowable before the run starts is
declared — the platform, the expected machine state, which phases
exist, their budgets, the properties it binds. What the guest dictates
is procedural — which key to send, what text to wait for, the order
its own installer screens arrive in. The guest is a black box that
cannot be configured, only watched and typed at, so interaction
with it is necessarily a sequence of acts; everything else is a
description. Several rules below exist to keep that seam intact —
notably that a phase is either sequential or reactive but never
both, that properties may supply data but never select a branch or a
phase, and that there are no author-side conditionals, because the
only decisions that matter are the guest's. The reasoning is
recorded above, under "The procedural–declarative seam".

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

A script passes through a fixed pipeline: **lex → parse →
desugar → validate → bind → preflight → execute**. Tokens form
nodes ([lexical rules](#lexical-rules)); nodes parse under the
typed grammar; [derived forms](#derived-forms) rewrite to the
core language; validation and binding check what follows; and
the [execution model](#execution-model) gives the result its
run-time meaning.

Every rule in this spec belongs to one of three enforcement
tiers:

- **Legality rules** — checkable from the script text alone: the
  lexical rules, the grammar, and the
  [syntactic restrictions](#syntactic-restrictions) (S-ids).
  Violations are STATIC ERRORs.
- **Machine rules** — need something beyond the text in scope:
  the media namespace, the filesystem, a machine or
  blueprint, explicit property values. Capability preflight, slot
  and drive existence, property binding, and media reconciliation
  live here ([validation and preflight](#validation-and-preflight)).
  Violations are PREFLIGHT ERRORs, raised before any guest
  input.
- **Dynamic semantics** — the meaning of execution itself
  ([the execution model](#execution-model)). What goes wrong
  here is a RUN FAILURE.

`check-script` has exactly two modes, one per checkable tier:
without a machine it applies every legality rule; with
`--machine`/`--blueprint` (and optionally
explicit property values) it adds the machine rules. Dynamic semantics are
exercised only by a run. See
[error classes](#error-classes-and-exit-codes) for how the tiers
surface to callers.

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
- Exactly two adjacencies are load-bearing and admit no
  surrounding space: `name=value` and `key+key` are each one
  token. `timeout = 5m` is not a modifier — `timeout` would read
  as a positional argument — and is a parse error, as is
  `ctrl + c`.
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
content is text and only text: keys never travel inside a string —
they are `press`'s job.

There is no raw-string form. Backslashes are already literal, so a
raw form would only save the `\${` escape — one token
class is too high a price for that, and it would break the rule
that a token is classified by its first character.

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
dialect is Python's `re` syntax — named deliberately as the
language's contract rather than inherited as an implementation
detail: an implementation in another language must provide this
dialect, not substitute its host's. A regex is a screen condition;
`machine=` accepts only a machine-state word. Property references are
never expanded inside a regex.

### References

`@name` references a media by name; it resolves through the
blueprint namespace — the `media` specs across the `.rlqb`
files in the active source, never carried in the script. A media
name is a `media-name` token, not a `name`: it may lead with a
digit (`@86Box`), because the `@` sigil has already classified the
token where a bare word could not be. A property key may not — it
also appears bare at its `property` declaration, where a leading
digit lexes as a duration. That is the whole of the difference
(D24). `$key`
references a declared
[property](#properties) and must stand alone
as a whole argument; inside strings the braced form `${key}` is
used instead, and dotted keys are valid in both forms. The
`property` key is a bare name at its declaration site; the
sigils mark use sites.

## Core grammar

Every line of every script is one structural shape:

```text
node = name , { argument } , { modifier } , [ block ] ;   (* informative *)
```

This is the shape a parser recognizes before typing; conformance
is defined solely by the typed grammar below together with the
static-validation rules that follow it. The core view is
structural — what a line looks like; the typed view is normative
for admissibility.

Every block holds nodes. Milestone 5's HTTP `content` declaration
does not use a block: it attaches either a raw triple-quoted body
or a `from=` source file whose lines are served as an installer
answer file
([http-serve.md](http-serve.md)). A script carries no JSON: media
travel as `media` components in the blueprint and landmark
declarations are authored files of their own, resolved from the
active source (docs/spec/asset-resolution.md),
and answer files are `content` entries with inline or file-backed
bodies.

A typing layer over the node shape supplies the rest of the
language definition:

- **Ordering.** Header nodes come first, then `property`
  declarations, then planned `http` declarations, then either
  top-level statements (a linear script) or `phase` nodes (a phased
  script). Mixing the two body kinds is a parse error.
- **Signatures.** Each node name fixes its argument types, allowed
  modifiers, and whether it takes a block. The complete signature
  tables follow; an argument or modifier outside a node's
  signature is a parse error. The tables are informative
  summaries — the typed grammar and the
  [syntactic restrictions](#syntactic-restrictions) govern.

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

Declarations:

| node | arguments | modifiers | block |
|---|---|---|---|
| `property` | optional `text`/`media`/`secret`, key | `prompt` | — |
| `http` | — | `port-min`, `port-max` | `content` entries |
| `content` | name, string URL path, optional `"""` opener | `indent`, `from` | text body, or — with `from` |

Statements:

| node | arguments | modifiers | block |
|---|---|---|---|
| `wait` | one condition (string/regex, or `machine=` state) | `timeout`, `stable` | — |
| `wait` | — (no condition; its handlers carry them) | `timeout` | `on` handlers |
| `on` | one condition | `stable` | statements |
| `always` | one condition | `stable` | statements |
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

And the phase declaration:

| node | arguments | modifiers | block |
|---|---|---|---|
| `phase` | name | `timeout`, `deadline`, `pacing` | statements, or `always` handlers |

### Grammar (normative)

The signature tables above expand into this complete EBNF. Every
production is an instance of the node shape. A parser may parse
structurally and then type-check, but
this grammar and the static rules below decide what is legal:

```text
script          = { header } , { property-def } , { http-def } ,
                  ( linear-body | phased-body ) ;

header          = "description" , string , eol
                | "platform" , name , eol
                | "machine" , ( "running" | "stopped" ) , eol
                | "entry" , name , eol
                | "timeout" , duration , eol
                | "deadline" , duration , eol
                | "pacing" , duration , eol ;

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

linear-body     = statement-list ;
phased-body     = phase , { phase } ;
phase           = "phase" , name , { timing-mod } , block-open ,
                  ( sequential-body | reactive-body ) ,
                  block-close ;
timing-mod      = ( "timeout" | "deadline" | "pacing" ) , "=" ,
                  duration ;

sequential-body = statement-list ;
reactive-body   = always-handler , { always-handler } ;
always-handler  = "always" , condition ,
                  [ "stable" , "=" , duration ] , block-open ,
                  statement-list , block-close ;
statement-list  = { statement } ;

statement       = observation | action | transfer ;
transfer        = "goto" , name , eol | "finish" , eol ;
observation     = "wait" , condition , { watch-mod } , eol
                | "wait" , [ "timeout" , "=" , duration ] ,
                  block-open , handler , handler , { handler } ,
                  block-close ;
handler         = "on" , condition ,
                  [ "stable" , "=" , duration ] , block-open ,
                  statement-list , block-close ;
watch-mod       = ( "timeout" | "stable" ) , "=" , duration ;
pacing-mod      = "pacing" , "=" , duration ;

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
                | "screenshot" , [ name ] , eol
                | "insert" , slot , ( media-ref | property-ref ) ,
                  eol
                | "eject" , slot , eol
                | "set-boot" , slot , { slot } , eol
                | "set" , variable-key , string , eol
                | "start" , eol
                | "stop" , eol ;

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
segment starting with a letter) is likewise validation's rule.

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

- **S1** — syntax is well formed: no unknown node names, no
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

- **S2** — every argument, modifier, and block fits its node's
  signature, including each timing modifier's placement per the
  [placement matrix](#timing).
  Ids: `node.modifier-not-allowed`, `node.timing-placement`,
  `node.modifier-not-a-duration`, `node.modifier-not-a-string`.

- **S3** — each header appears at most once; `entry` appears
  exactly in phased scripts.
  Ids: `flow.entry-in-linear`, `flow.entry-missing`,
  `syn.duplicate-header`.

- **S4** — no node carries the same modifier name twice; a
  repeat is an error, never a last-wins override.
  Id: `node.duplicate-modifier`.

- **S5** — names are valid and unique in their namespaces:
  reserved node names are not identifiers, property keys are
  declared once per script and are not spelled `text`, `media`,
  or `secret`, user-declared property keys do not use the
  reserved `rlq` or `reliquary` namespaces, durations are
  positive.
  Ids: `name.reserved-node`, `name.duplicate-phase`,
  `name.duplicate-property`, `name.property-is-a-kind`,
  `name.property-reserved-namespace`,
  `name.variable-reserved-namespace`, `time.non-positive`,
  `prop.secret-default`, `prop.dead-default`, `prop.unknown-kind`.

- **S6** — every `$` reference names a declared property or a
  Reliquary-owned run property in a reserved namespace made
  available by the script's declarations.
  Ids: `prop.undefined-reference`, `prop.secret-reference`,
  `prop.derivation-cycle`, `prop.http-without-block`. The
  `${key}`-in-a-statement half is unenforced (see below).

- **S7** — an observation carries **exactly one** condition — a
  bare string/regex beside a `machine=` modifier, or two
  `machine=` modifiers, are errors — the condition precedes any
  timing modifier, the channel is known, and its value is of the
  right kind (a state word for `machine=`, never a string).
  Ids: `obs.missing-condition`, `obs.two-channels`,
  `obs.not-a-condition`, `obs.unknown-channel`,
  `obs.screen-named`, `obs.wrong-kind`.

- **S8** — a branching `wait` carries no condition of its own,
  has at least two handlers, and appears nowhere inside a
  handler body. The recursion `handler → statement →
  observation` is deliberate: the grammar stays context-free and
  the depth limit is a static rule, not a parse rule.
  Ids: `wait.branching-in-handler`, `wait.too-few-handlers`, and
  `wait.branching-condition` — the last unreachable today, the
  grammar rejecting that shape first.

- **S9** — `on` appears only inside a branching `wait`, `always`
  only directly inside a reactive phase, and a phase is
  sequential or reactive, never mixed.
  Ids: `handler.mixed-phase`, `handler.on-outside-branching-wait`,
  `handler.always-outside-reactive-phase`.

- **S10** — the two script shapes never mix; `goto` and `finish`
  are invalid in a linear script; every `goto` names a declared
  phase; `entry` names exactly one.
  Ids: `flow.transfer-in-linear`, `flow.goto-undeclared`,
  `flow.entry-undeclared`.

- **S11** — the [terminating-statements rules](#terminating-statements):
  nothing follows a terminating statement, and a sequential
  phase's statement list terminates.
  Ids: `flow.unreachable-statement`, `flow.phase-falls-through`.

- **S12** — a phased script whose transition graph contains a
  cycle declares a header `deadline`.
  Id: `flow.cycle-without-deadline`.

- **S13** — watch patterns are non-empty and regexes compile.
  Ids: `obs.empty-pattern`, `obs.uncompilable-regex`.

- **S14** — closed vocabularies hold by name: key names are from
  the portable set, `insert`/`eject` name removable
  (floppy/cdrom) slots, `set-boot` names drive slots, and
  interpolation appears only where the argument accepts it.
  Id: `key.not-portable` (the `press` vocabulary; the
  insert/eject and set-boot vocabularies are preflight's).

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
  authored linear surface (S10).

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
  declares `machine stopped`. There is deliberately no undiverged
  variant of the precondition: whether a diverged machine matters
  is the operator's call, and `apply` is the documented recovery —
  divergence policy never lives in a script header.
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

Each header may appear at most once. The file name supplies the
script name. There is no format-version field before 1.0 because
the planned format carries no compatibility promise yet.

## Script shapes

A script uses one of two shapes. Mixing them is a parse error.

### Linear script

A linear script has top-level statements, executed in order. It is
the normal form for a known sequence:

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
phase. Top-level executable statements are not allowed:

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

A script declares the properties it consumes; references supply
their bound values to statements while control flow stays fixed.
The declared name *is* the property key every
[source](script-properties.md) speaks — there is no separate input namespace
(owner, 2026-07-21 — the property-construct round): a dotted key
joins the shared personal vocabulary, an undotted key is
script-scoped by convention, and every supply source speaks the
same keys.

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

`default=` declares the key's *derivation* — the script's own
answer when no outer source supplies one. Its value is a quoted
string in the reference grammar below: literal text, `${key}`
references to other declared keys, and the `rlq.*` system
facts ([script
properties](script-properties.md#property-sources)). A
derivation is not an expression — no transforms, no
conditionals — and it binds statically: references among
defaults form a static dependency graph, a cycle is a static
error, and a reference to an undeclared, non-system key is a
static error. At binding time a derivation whose references all
bind answers the key — a literal default always answers, so
`default="paul"` simply stops resolution at the derivation —
while one touching an empty or unavailable fact does not
answer, and the key falls to the ask. `default=` may repeat:
the candidates are tried in declaration order and the first
that answers supplies the key — alternation on availability,
never on a value test — so a curated fact prefers itself over
a raw fallback (`default="${rlq.host.full-name}"
default="${rlq.env.FULLNAME}"`). A literal candidate anywhere
but last is a static error — the candidates below it are dead.
A `secret` declaration
may not carry `default=`, and no derivation may reference a
secret key. `prompt=` and `default=` compose: the prompt is
simply never shown unless the derivation fails to answer.

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

That prohibition also bounds what any source can
customize: no property — whatever supplies it — can retarget a
script at a different-language installer, whose every screen
differs. Locale-class customization is a *composition* seam owned
by the machine blueprint, which selects the media/script pair;
value seams supply
data only, and each script stands alone against the guest it was
written for (U5; see [customization
seams](../blueprint-guide.md#customization-seams)).

### The property sources

Before the machine starts, Reliquary binds each declared property
from the first source that answers. Everything that can answer is
a property source, in one flattened order; each source answers
for a different owner (owner, 2026-07-21 — the property-construct
round). This list is normative; other documents summarize it and
link here:

1. **An explicit CLI value** — *the caller's* answer for this
   invocation: a repeatable `--property <key>=<value>`; the API
   twins take the same values as their in-memory `properties=`
   mapping under parity. It beats everything, the design
   included. A key given twice is an error, and every explicitly
   supplied key must be declared by the running script — an
   unknown key is a preflight error, never a silent ignore.
2. **A [blueprint
   parameter](../blueprint-reference.md#parameters)** —
   *the design's* answer, for every machine of the blueprint: a
   direct value, or a *redirect* (`{"property": "<key>"}`) that
   resolves another key through the remaining sources below.
   Parameters never chain through other parameters, and a
   redirect replaces resolution of the declared key entirely —
   never falling back to it.
3. **The environment** — `RELIQUARY_PROPERTY_*` ([spelling and
   mangling](script-properties.md#property-sources)): *the
   session's* standing values, the CI injection path. An ambient
   variable never overrides a designed value; the explicit flag
   above is the override path.
4. **The user properties file** — `user.properties`, or the file
   selected by `--properties <path>`: *the person's* durable
   values and secret markers
   ([script properties](script-properties.md)).
5. **The declared derivation** — *the script's* computed
   answer: the declaration's `default=` candidates, tried in
   declaration order, each resolved in the reference grammar
   over literal text, other declared keys, and the `rlq.*`
   system facts ([Properties](#properties)). The first
   candidate whose references all bind answers the key — a
   literal always answers, so declaring one is opting to stop
   here — while a candidate touching an empty or unavailable
   fact does not, and a key no candidate answers falls
   through.
6. **The interactive ask** — one ask per unresolved key,
   presented with the declaration's `prompt=` text; the answer
   serves every reference to the key and is invocation-local,
   never written back.

Nothing binds uninvited (owner, 2026-07-21, restated by this
round): no value reaches a script unless a declaration names its
key, and the one environment channel is the declared
`RELIQUARY_PROPERTY_*` spelling, sitting below the design.

The order itself is closed at this surface — it is semantics,
each rank encoding an adjudicated argument, never
configuration. How the model grows without opening it — new
tiers at design-decided ranks, provider plurality inside a
tier, programmatic injection through the embedding API with
mandatory provenance — is recorded with the operator-side
mechanics ([script
properties](script-properties.md#growth-the-order-is-closed-the-seams-are-named);
planning/DECISIONS.md, 2026-07-23).

Asking requires an interactive context: stdin and stderr both
ttys — prompt text writes to stderr, the answer reads from
stdin (the CLI output discipline, docs/spec/cli.md) — under the
interactive progress renderings (`auto`/`pretty`). Without one — no
terminal, or an explicit `plain`/`jsonl` progress selection — a
still-unbound property fails before
execution, so a program can never hang on a hidden prompt. A
blueprint's designed values override personal standing defaults —
a blueprint that fixes its user name as
"testuser" keeps it fixed on every machine of it — while an
explicit `--property` overrides even the design for one run
(U5). A media value is resolved after binding, and a
media ask lists the media names valid
for that property.

Ordinary properties are strings. Secret properties keep only a
marker in the properties file; their values live in the host
credential store. `text` and `media` declarations require
ordinary stored values, while `secret` requires a secret
property. Kind
mismatches fail rather than silently downgrading protected data.
Blueprint parameters follow the same kind rules, and a `secret`
declaration never takes a direct blueprint value — the [field
reference](../blueprint-reference.md#parameters) states the
blueprint-side rules. A secret never travels through
`--property` — argv leaks into process listings and shell
history, exactly the `set-property` rule; the environment may
supply one (the warned plaintext class), the API mapping may (an
in-memory value), and the ask enters one without echo.
See the [script-properties specification](script-properties.md) for
the file format, maintenance commands, precise failure rules, and
security boundary.

The transcript records property keys, redirect targets, and
supplying sources (flag, parameter, environment, file, or ask) —
never values. For a `secret`, it also omits the entire expanded
argument, redacts the value from textual diagnostics, and
suppresses later automatic failure screenshots. An explicitly
requested screenshot and the guest's own display, logs, or command
history remain capable of exposing guest-entered data.

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

Five clocks exist. Each is checked at **boundaries** — dispatch
samples and statement starts — never mid-delivery:

| clock | starts | satisfied / expires |
|---|---|---|
| observation `timeout` | when its observation arms | expires at the first boundary past the duration with no success |
| `stable` hold | at each episode's first sample | satisfied at the first sample where the episode's age reaches the duration |
| reactive interval (`timeout` on a reactive phase) | at phase entry, and again each time dispatch resumes after a handler action | expires when the duration passes with no handler firing |
| phase `deadline` | at each activation (each entry to the phase) | expires when the activation's wall clock exceeds the budget |
| run `deadline` | at run start | expires when the run's wall clock exceeds the budget |

Expiry produces the failure the [timing section](#timing)
promises: the diagnostic names the expired clock and the scope
that supplied it.

**Severability follows the guest seam.** Input delivery is
atomic: once a verb begins composing events — a `type` string, a
`press` sequence, a `select` traversal step — the delivery
completes even if a deadline passes meanwhile; the expiry is
declared at the next boundary. A torn half-typed command would
leave the guest in a state no observation could account for.
Host-side operations are the opposite: a media fetch crosses no
guest seam and aborts cleanly at deadline, however long it had
run.

### The run event stream

Every run emits one normative event stream — JSON Lines, each
event carrying a sequence number, timestamp, elapsed time, and
kind — as **live output** to the run's driver, never a stored
file (owner, 2026-07-24; D36: the run returns its output and
stores nothing; the persisted `run-events.jsonl` and the run
directory are async-backlog work, proposed/FEATURES.md "Asynchronous
runs"). Under `--progress jsonl` / `run_script`'s event
iterator the stream *is* the machine-readable output; the pretty
and plain displays and the transcript a caller keeps are
*renderers* of it — no surface reports anything the stream does
not carry.

Spans in the stream mirror the activation tree the clocks above
define — a run span (the run deadline's scope), a span per phase
activation (the phase deadline's scope), a span per observation
(its timeout's scope). The minimum vocabulary the runtime emits:

- preflight identification: the selected backend, and the
  control plane serving each operation;
- run and phase-activation span starts and ends, and `goto` /
  `finish` transitions;
- observation arm, match (with the matched row and elapsed
  time), and timeout;
- handler fires, and each action's start and completion — input
  deliveries, `insert` / `eject` / `set-boot`, `start` / `stop`,
  `screenshot`. An `insert` names the media it actually mounted,
  so a `$property` argument reports the **resolved** name and not
  the property's: the two sigils are equally definite on the
  page — `@` fixed, `$` deferred to the run — and the stream is
  where that difference becomes visible;
- transfer progress only where an honest total exists — media
  fetch bytes, `select` traversal
  steps — never invented denominators: renderers show phases and
  observations as "elapsed / limit" pairs, not progress bars;
- on failure: the pending condition or action, the expired clock
  and its source scope, the route taken with phase revisit
  counts, the nearest-miss screen row, the automatic screenshot
  reference, and the suggested next command;
- reserved, designed but not emitted: `screen`'s CLI-only read
  kind, which waits on the guest-console commands carrying a
  stream at all (only `run-script` and `fetch-media` do today);
  and, with the backlogged record model (D36), interaction runs'
  neutral `ended` terminal event and the authoring recorder's
  (U6) handover kinds — control passing from script to human and
  back, a capture session as one record with mixed drivers. A
  reserved kind has no constant in the implementation: the
  vocabulary the code declares is the vocabulary it emits.

Events carry their originating statement's source line and
number wherever one exists (owner, 2026-07-22) — action,
observation, and transition events name the line they execute —
so a transcript line can always cite its source.
Events carry property keys and supplying sources, never
bound values; the secret contract applies to the stream
exactly as it applies to transcripts.

The stream is a contracted machine surface (owner, 2026-07-22):
from 1.0 it grows additively only — new event kinds and new
fields may appear in any release, an existing field never
changes type or meaning, and a removal or rename is a breaking
change — and consumers must ignore unknown event kinds and
unknown fields. Pre-1.0 the shapes track this spec with no
stability promise. The human renderings (`pretty`/`plain`) are
deliberately uncontracted; the machine surfaces are this
stream (as live output), `--json` documents, and exit codes
(docs/spec/cli.md; run-record files dropped with
persistence, D36).

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
wait machine=stopped     # the machine: non-default, always named
```

| channel | observes | condition spelling |
|---|---|---|
| the screen (default) | the guest's visible display | string or regex, unprefixed |
| `machine=` | machine state reported by the backend | `stopped` |

Machine state has exactly one spelling, `machine=stopped`; there
is no bare `stopped` condition. This split is deliberate twice
over: a bare word and a quoted string in the same argument
position must never mean two different observation domains, so
the non-default domain is always named — and the default domain
is *only* unprefixed, because two spellings of one observation
would be two dialects in miniature.

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
`pacing` sets the gap before guest input, and there is no
`delay`.** When each clock starts, where it is
checked, and how expiry is declared are defined by the
[execution model's clock table](#clocks).

The three families scope differently, and placement is the law:

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
  family, and applies to the four guest-input verbs:

  ```text
  statement > phase > header > built-in 0.1s
  ```

  There is no branching-`wait` rung: an observation container
  cannot carry `pacing`, because pacing paces the actor and a
  `wait` acts on nothing. A guest-input verb inside a handler
  therefore inherits from its phase or the header, skipping the
  `wait` that contains it.

Where each word may appear, and what it means there — any other
placement is a parse error:

| written on | `timeout` | `deadline` | `stable` | `pacing` |
|---|---|---|---|---|
| header | default for all observations | budget for the run | error | default for all guest input |
| `phase` | default within the phase | budget per phase entry | error | default within the phase |
| single-condition `wait` | bound on this observation | error | hold requirement on this match | error — it delivers no input |
| branching `wait` | bound on reaching the first match | error | error — put it on the `on` | error — it delivers no input |
| `on` / `always` | error — the container owns the waiting | error | hold requirement on this condition | error — put it on the input verb |
| `enter` / `type` / `press` / `select` | error | error | error | gap before this delivery |
| every other statement | error | error | error | error — it delivers no input |

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

Because per-observation and pacing resolution are fully lexical,
the effective timeout of every observation and the effective gap
before every guest input are computable at parse time (G3, G4):
`check-script` reports the resolved timing plan — including a
`guest input` section naming each verb's pacing and the scope that
supplied it — and a timing
failure names which clock expired and the scope that supplied it —
an observation timeout from a statement, a phase deadline from its
declaration, or the run deadline from the header.

`stable` requires a watch condition to remain matched for the
stated duration before succeeding:

```rlqs
wait "Formatting" stable=2s
```

There is no generic sleep or delay verb, on principle (G1, G5): a
blind
pause encodes a guess about guest speed that will be wrong on
another host. Every pause must be justified by an observation;
`stable` strengthens one rather than blindly pausing after it.

**`pacing` is not that verb, and the prohibition stands.** The
distinction is between a pause an author *sequences* and a pause
that is a property of *delivering input*. A `delay` verb would be
the first: a step in the script, standing between two others,
encoding a guess about how long something takes. `pacing` is the
second — the control plane's own gap before it starts typing,
which it takes whether or not anyone writes the word. What the
language adds is the ability to tune that gap, not to insert one.

The gap exists because agentlessly a guest's *input* readiness is
unobservable where its output is not (G1): an installer paints its
welcome screen before it begins reading the keyboard, so a control
plane that types the instant a screen appears asserts something it
cannot know. `send_keys` already paces *between* key events; this
is the missing pause before the first. Screen polling remains
control-plane-owned and untunable; input-event pacing is
control-plane-owned and tunable, on the ladder above.

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
key event, and each accepts `pacing=` to tune it
([Timing](#timing)). The four are `enter`, `type`, `press` and
`select`; the supporting operations below are not guest input and
pay nothing. `select` is both — it delivers keys *and* observes
between them — so it carries a `timeout` for its feedback and a
`pacing` for its delivery, and appears twice in the resolved plan.

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
ends by explicitly restoring it, conventionally with `eject` as
its final step. A script that fails or is interrupted leaves its
media changes in place for diagnosis and resumption; `apply` is the
one-command recovery when a diverged machine should return to its
blueprint shape.

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
the new order takes effect on the next `start`. Like
`insert`/`eject`, the change diverges the machine from its
blueprint until a later `set-boot`, or
[`apply`](../blueprint-guide.md#applying-blueprint-edits), restores
it.

Most install scripts never need this: a blueprint that boots
`["hdd0", "cdrom0"]` with a blank hard disk falls through to an
attached installer CD, then boots the installed disk once it is
populated. The verb exists for scripts that genuinely need a
different order than the blueprint's default.

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

Variables are **cleared at each `start`**, so one always reports
what the current boot produced rather than what a previous boot
left behind. They are the consumer's names for the consumer's
values: reliquary stores them and reads no meaning into either
(G2, P18).

**Readiness rides this channel.** reliquary ships no readiness
script of any kind — what "ready" means belongs to the workflow
being built, not to reliquary (P18). A consumer's own ready script
`set`s a variable as its last step, and the driving program polls
`get-machine-var` until it appears. An unset variable and a machine
that never ran read alike, which is what keeps the poll a plain
loop.

### File exchange — a named omission

The language deliberately has no file-exchange verbs (owner,
2026-07-22). Moving files across the host/guest boundary is the
caller's side of the seam, like every interpretation of what a
run produced (G2): while a machine is stopped on every control
plane, its drives are plain host state — a
[directory-source media](media-spec.md#the-media-component)
*is* its directory, and drive images are readable and
writable with the user's own tools — so exchange is ordinary
out-of-band host work against the machine directory
(`get-machine-dir` reports it; contract in
[the instance model](instance-model.md)). The omission also
keeps every quoted string in a script on one side of one
boundary: string content is guest-facing text, never a host
path.

In-band file operations **are a CLI/API capability, not a
language one**: `put-file` / `get-file` (milestone 9), and
`put-files` / `get-files` / `list-files` for whole trees and
listings (D62) — twins `put_file` / `get_file` / `put_files` /
`get_files` / `list_files`. All five address their target the way
the guest names it — `A:\TEST.EXE`, or `A:\OUT` and `A:\` for a
directory, per **P17**, in force since D47, and not
the `<drive-key>:<path>` form D5 had roughed — over a
directory-source drive — or, for the three read verbs, a drive
image read at rest — stopped-only, with a write to an image
failing closed naming the gap (P11). The
letter map is built from the machine's declared platform and
reliquary's own drive assignment, never by inspecting a guest
(P10), and places every drive on the one-volume-per-disk assumption
(D71). Future live guest-agent transfer would get its own
distinct capability with an explicitly stronger guarantee. None of
this lands in the *language*: the omission above stands, and
reopening it is a language decision under the growth goals.

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
[syntactic restrictions](#syntactic-restrictions) S1–S14 — from
the script text alone, before the machine starts. With more in
scope, preflight further rejects, naming what it needed:

- media references (`@name`) naming no media the namespace
  defines (the media namespace);
- `insert`/`eject` slots and `set-boot` drives the target
  machine does not declare (a machine);
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
rlq check-script <script_name>
    [--machine <id> | --blueprint <name>]
    [--property <key>=<value>]... [--properties <path>]
```

performs parsing and static
analysis — including the resolved timing plan, each observation's
effective timeout, and its source scope — without executing the
script, changing the user's properties, accessing secret
values, or writing any file. Supplying a machine (and any
explicit values) also performs typed binding — reporting each
declared property's supplying
source (flag, blueprint parameter — direct or redirect —
environment, file, or ask) — and
capability preflight.
Source-aware checking reports property presence, kind, and
supplying source; it
never reveals a property value. Its two modes are the two
checkable tiers of the [processing model](#processing-model);
the embedding API's twins are `run_script` and `check_script` —
`start_script` joins them as `run-script --detach`'s twin,
returning the run handle whose operations the CLI `run` family
mirrors, and `attach_run` reopens that handle from a fresh
process — taking the same identifiers under CLI–API parity.

### Error classes and exit codes

Every failure this surface can produce belongs to one of three
classes, matching the enforcement tiers — which are not this
surface's alone, as the generalization below sets out:

| class | tier | exit code |
|---|---|---|
| STATIC ERROR | legality rules (S-ids) | 2 |
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

**The classes are not this surface's alone** (D58). They are named
for a run's enforcement tiers and hold unchanged on every
interface, because the questions that decide them never mention a
script: is it settled by the authored input alone, does the world
satisfy that input, did the work itself fail. So a malformed
blueprint is a STATIC ERROR exactly as a malformed script is,
naming a machine that does not exist is a PREFLIGHT ERROR exactly
as an undeclared drive slot is, and a failed image transfer is a
RUN FAILURE with no run in sight. A capability Reliquary declares
but has not implemented is a PREFLIGHT ERROR: the request is
legal, and the world — which includes what this build
implements — does not satisfy it.

Exit `1` therefore means a **fault**, never a user's mistake, and
has two populations that are both Reliquary's own: a deliberate
`InternalError` (Python), which is an invariant Reliquary detected
in its own state and carries no user input to correct, and a
genuine accident that never was a `ReliquaryError`. A deliberate
raise always lands in the hierarchy, so `except ReliquaryError`
stays the catch-all it is documented to be; a bare builtin is left
to the invariants the language itself enforces.

Every diagnostic
carries a stable dotted identifier naming its rule
(`obs.two-channels` style); identifiers share one namespace
across the classes, and the full id index is deferred to beta.

**Ids are finer than the S-numbered rules.** An S-number names a
restriction; an id names one diagnostic under it — S7 is one rule
and `obs.two-channels` is one of the six ways to break it. The
two are not competing schemes and a message carries only the id;
the [syntactic restrictions](#syntactic-restrictions) list the
ids that enforce each rule, which is where a reader goes from one
to the other. The prefix is the subject, never the error class or
the surface, because the namespace is shared across both: `obs.`,
`wait.`, `handler.`, `flow.`, `name.`, `prop.`, `time.`, `key.`,
`node.`, `http.`, `media.`, `machine.`, `platform.`, `progress.`,
`store.`, `lex.`, `syn.`, `ref.`, `value.`, `field.`, `drive.`,
`blueprint.`, `image.`, `screen.`, `script.`, `dir.`.

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
`progress.`, `store.`.

Two families the blueprint document could have taken new subjects
for took existing ones instead: its name-charter rules are `name.`
and its media semantics are `media.`, those being the same rules
already named elsewhere.

**This list is closed and enforced.** A diagnostic whose subject
is not on it does not get a new prefix invented for it in passing;
the list grows by an edit here, and a test holds the code and this
list to each other in both directions — an id with an unlisted
subject fails, and a listed subject nothing raises fails too.

The subject rule is what lets **one rule keep one id across
surfaces**, which is its whole purpose. `media.unknown` is raised
where the resolution namespace defines no such media *and* where a
script's `insert` names one: one condition, one answer for a
caller asking what went wrong. `name.duplicate-property` covers a
script declaring a property twice and a properties file defining a
key twice. `machine.not-running` covers the CLI, the script runner
and the machine verbs. Had the prefix named the tier or the
surface, each of those would have carried two or three ids for one
rule, and a consumer would have had to know which layer noticed
before it could tell what happened.

An id is a **contract**: it is what a consumer switches on, so it
is stable where the message text is not. The message wording,
like every human rendering, is uncontracted and free to improve.

Coverage on this surface is complete: the lexer, the grammar, the
node signatures, the static rules, and — since the error classes
generalized to every surface (D58) — the preflight and runtime
tiers too, property binding and media resolution included. The
script conformance corpus
(`reliquary_tests/fixtures/conformance/script/`) holds it there by
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

**The blueprint surface is located too** (D70). A script
diagnostic cites a line and column, or the statement it came from;
a blueprint diagnostic cites its field breadcrumb *and* the line
and column that field was written at, rendered by the same
skeleton — `<path>:<line>:<column>: error: <message> (<id>)`, with
the source line and a caret beneath it. The breadcrumb did not
move into the rendering: it stays in the message, because it says
which field and the position says where, and the two answer
different questions.

Position is **optional and its absence is not a defect**. It comes
from the document's text, so a blueprint loaded from a path has
one and a value handed straight to the API does not — there is
nothing to point into, and citing nothing is the honest answer.
Other surfaces stand where they stood: a preflight diagnostic
about the media namespace has no document position to cite and
carries an id alone.

The grammar's own rejections are the coarsest ids in the scheme:
`syn.unexpected-token` and `syn.unexpected-end` name a token, not
a rule, because that is all a parser knows. That is the cost this
spec accepts by keeping the S-rules above the CFG, and it is
visible where it bites — a construct the grammar refuses cannot
carry the id of the rule it violates.

## The run's output and failure

A run drives the machine and **returns its output** to whoever
started it; it stores nothing (owner, 2026-07-24; D36). The
output is the [event stream](#the-run-event-stream) — rendered
live to the run's driver (pretty for a person, jsonl for a
program) and gone when the run ends. There is no run directory,
no persisted `run-events.jsonl` or `transcript.txt`, no
retention, and no `run` management family: persistence is the
substrate a cross-process follower would read, and following a
run from a process that did not start it is asynchronous work in
the backlog (proposed/FEATURES.md "Asynchronous runs", D35/D36) —
which is where the whole record model now lives (the `runs/<n>/`
archive, monotonic numbering, retention, `list-runs` / `run
status` / `run delete`, and interaction runs). Milestone 9
stores nothing; each run returns to its own caller, which is what
keeps the multithreaded case free of a shared store.

The stream ends with a **terminal event** stating the outcome:
success, a failure class, or cancelled — Ctrl-C on a foreground
run emits a `cancelled` terminal event, exits `5`, and leaves
the machine as-is. Under `jsonl` the last line is the
machine-readable result; there is no separate result mode. On
the API, `run_script` / `exec` return a typed result and raise
by error class ([error classes and exit
codes](#error-classes-and-exit-codes)).

On failure the returned output carries the pending condition or
action, the clock that expired and the scope that supplied it
(statement timeout, phase deadline, or run deadline), final
observed screen text, machine state, and an automatic screenshot
when available.

A run's **product is the consumer's**, never a record Reliquary
keeps: the value returned, a file the caller retrieves in-band
(guest-terms addressing), a small value read from a machine
variable, or a whole disk image swapped out. Reliquary attaches
no meaning to any of it and has no test-result vocabulary — no
pass/fail schema, no result parsing (G2). A primitive-driven
loop needs no bracket to be recorded: the caller's own driving
code, collecting each call's returned output, is its record.
Per-run selection travels as ordinary script properties;
granular results come out as the caller's own files and values.
The consumer keeps, organizes, and discards on its own side of
the seam (P4, P18).

There is no automatic retry. Re-running an installation against a
partially modified disk is not generally safe and is not described
as a retry. The caller deliberately resumes, recreates the machine,
or runs again according to that workflow's documented recovery
semantics.

### Interaction runs — the recording bracket

A primitive-driven loop needs no recording bracket in milestone 9:
each command returns its output, and the caller's own driving code
collecting those outputs is its record (D36). The `begin-run` /
`end-run` bracket that records such a loop into one persisted run
record is part of the record model, which moved to the
asynchronous-runs backlog with the rest of persistence (proposed/FEATURES.md
"Asynchronous runs", D35/D36); it returns if that work
schedules.

U14's unit-test loop is served without it: per-run test selection
travels as ordinary script properties (`--property` / the
`properties=` mapping, interpolated by property references);
granular results are a caller-authored artifact (JUnit XML, TAP)
the caller takes directly — retrieved in-band by guest-terms
address (U14), swapped out as a disk image (U20), read from a
directory-source results drive at rest, or captured as text through
`exec` — and keeps on its own side of the seam. Reliquary has
deliberately no test-result vocabulary — no pass/fail schema, no
result parsing (G2). Granularity comes from run structure: one
iteration is one returned output.

## How the vocabulary grows

The text-mode vocabulary is a foundation, not a promise that every
future feature must fit an already frozen grammar before the first
implementation has validated it. Before beta, empirical use may
still reshape the language coherently.

The intended post-beta growth discipline is (G7):

- existing observation forms keep their meanings;
- **a new channel names a new non-default observable surface; a
  new value spelling names a new matcher over the default
  surface.** A serial stream becomes `wait console="login:"` — a
  new prefixed channel, because it is a different observable.
  Image matching becomes a landmark reference, `wait @setup-page`
  — a new value spelling, because it is a different matcher over
  the same screen. Neither is a new construct or a positional
  keyword;
- new action kinds use explicit sibling forms following the same
  node shape, as future pointer verbs will;
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
    press  enter

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
    select "Yes"
    goto hd-boot
}

phase hd-boot {
    wait   "Load FreeDOS"
    select "Load FreeDOS with JEMMEX (more compatible)"
    wait   "C:\>"
    screenshot installed
    goto shutdown
}

phase shutdown {
    enter "fdapm poweroff"
    wait  machine=stopped timeout=2m
    eject cdrom0
    finish
}
```

The blueprint declares `cdrom0` empty and boots
`["hdd0", "cdrom0"]`; the script supplies the installer medium. A
blank hard disk fails to boot, so the opening `insert` makes the
machine fall through to the LiveCD, and the closing `eject`
returns the machine to its default shape — the same boot order
thereafter boots the installed hard disk. No `set-boot` verb is
needed.
The second visit to `cd-boot` reaches the other branch of its
closing `wait` because the disk has been partitioned. The
guest-driven reboot is expressed by the installer selection and the
resulting screen, not by a Reliquary reboot command.

Verification is a separate script needing no machine
reconfiguration at all: after the install script's final `eject`,
the machine is back in its blueprint shape and simply boots the
installed hard disk. The verify script declares
`machine stopped` too and issues a plain `start`. If an
interrupted install run left the CD attached, `apply` restores the
blueprint shape (or the HD-first order boots the installed disk
anyway while the CD remains attached).

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
