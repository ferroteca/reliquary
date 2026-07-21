<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The script spec

> **Status:** This document is the source of truth for the redesigned
> script surface adopted in July 2026. It supersedes the earlier
> milestone-one syntax (`state`, `->`, `done`, `expect`, `regex`
> strings, colon headers, comma-separated modifiers, bare media
> names, and the bare `stopped` condition) completely; pre-beta,
> there is no compatibility between the two surfaces and none is
> planned. The implemented parser and runtime (`script.py`,
> `script_runner.py`) and the shipped built-in and example scripts
> still speak the earlier surface and will be retargeted wholesale.
> `script-examples/design-install.rlqs` is the reference script, and
> the other files there catalog known residual rough edges in this
> surface. Embedded media blocks, inputs and property binding,
> reactive phases, and the full transcript contract remain later
> milestones; details may still change before first release.

A reliquary script automates a guest: it watches observable guest
and machine state, supplies input, swaps media, and moves files
across the VM seam. Scripts live in
`<reliquary_home>/scripts`, one `<name>.rlqs` file per script, and
run against a machine selected with `--machine <id>` or, when the
blueprint has exactly one machine, `--blueprint <name>`:

```powershell
rlq script install --blueprint freedos-1.4-plain
```

After preflight, `script` installs embedded media definitions,
resolves its machine (creating one when `--blueprint` names a
blueprint with no machine yet), brings it to the state the script's
[`machine` header](#header) expects — starting a stopped machine
when the script expects `running`, failing when the script expects
`stopped` but the machine is running — then executes the script. The
machine stays in whatever state the last executed step left it.
Failure likewise leaves the machine in its observed state for
diagnosis; no command implicitly tears it down.

Scripts are authored documents: reliquary reads but never rewrites
them. They belong in version control beside the machine blueprints
and media definitions on which they depend.

## The language model

The language is a deliberately constrained, domain-specific
programming language. It has sequencing, branching, named phases,
and explicit phase transitions, but no expressions, mutable
variables, arithmetic, user-defined functions, or general-purpose
loops. Its job is guest automation, not computation.

The basic rhythm is **observe, then act**:

```rlqs
wait   "What is your preferred language"
select "English (United States)"
```

- **Observations** establish that the guest or machine has reached
  a known state: `wait`, in its single-condition and branching
  forms, and reactive `on` handlers.
- **Actions** deliver intent-level input or perform supporting host
  operations: `enter`, `type`, `press`, `select`, `insert`,
  `eject`, `boot`, `stage`, `collect`, `screenshot`, `start`, and
  `stop`.

Intent-level verbs remain above portable input events. `select`
means choosing a visible menu entry, not sending a guessed number
of Down keys. The selected control plane composes the necessary
key press and release events and owns their pacing. Pointer actions
will follow the same model when GUI automation arrives.

Three design rules govern the whole surface:

- **One shape.** Every line of a script is a *node*: a name,
  positional arguments, `name=value` properties, and optionally a
  block. The entire structural grammar is that one production.
- **Spelling reveals role.** Every token class has exactly one
  spelling and every punctuation mark exactly one role; a reader
  can classify any token without context. See
  [lexical rules](#lexical-rules).
- **Nouns declare, verbs act.** Declarative nodes (headers, `media`,
  `input`, `phase`) begin with a noun; imperative nodes begin with
  a verb. The declarative zone precedes the imperative zone, and
  the grammar enforces the boundary.

That third rule reflects a deliberate split: **a script is
declarative about everything reliquary owns, and procedural at the
seam with the guest.** What is knowable before the run starts is
declared — the platform, the expected machine state, which phases
exist, their budgets, the media and inputs. What the guest dictates
is procedural — which key to send, what text to wait for, the order
its own installer screens arrive in. The guest is a black box that
cannot be configured, only watched and typed at, so interaction
with it is necessarily a sequence of acts; everything else is a
description. Several rules below exist to keep that seam intact —
notably that a phase is either sequential or reactive but never
both, that inputs may supply data but never select a branch or a
phase, and that there are no author-side conditionals, because the
only decisions that matter are the guest's. The reasoning is
recorded under "Procedural and declarative" in
[ROADMAP.md](../ROADMAP.md).

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

## Lexical rules

- Files are UTF-8 text. A UTF-8 BOM is accepted but not required;
  LF and CRLF line endings are equivalent.
- One node occupies one line. A `{` at the end of a line opens a
  block; a `}` alone on a line closes it.
- `#` begins a comment outside a quoted string or regex.
- Identifiers use ASCII letters, digits, `.`, `_`, and `-`, must
  start with a letter, and are case-sensitive. Reserved node names
  (headers, declarations, and verbs) cannot name phases, inputs,
  or media labels.
- Properties are written `name=value`, space-separated, after the
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
  token. `timeout = 5m` is not a property — `timeout` would read
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
| `"..."` | literal text crossing the guest boundary, or a host path | `wait "C:\>"`, `enter "fdapm poweroff"`, `stage "payloads/AUTOTEST.EXE"` |
| `/.../` | regex match | `wait /[0-9]+ files copied/` |
| `@name` | external reference, resolved from the library | `insert cdrom0 @freedos-1.4-livecd` |
| `$name` | run-supplied input value | `insert floppy1 $supplemental-disk` |
| `name=value` | property of the node it follows | `timeout=5m`, `machine=stopped`, `exclude="with sources"` |
| `5m`, `500ms` | duration | `wait machine=stopped timeout=2m` |
| `<key>` in typed strings | key token | `type "<down><down><enter>"` |

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

Any other backslash is literal. Inside a string, an input reference
is written `${name}` and is expanded only where the containing
argument accepts it; a `$` not followed by `{` is literal. In
`enter` and `type`, recognized `<key>` tokens produce key input.

There is no raw-string form. Backslashes are already literal, so a
raw form would only save the `\<` and `\${` escapes — one token
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
backslashes, passes through to Python's regular-expression syntax
unchanged. A regex is a screen condition; `machine=` accepts
only a machine-state word. Input references are never expanded
inside a regex.

### References

`@name` references a media item by its catalog name; it resolves
through the shared media library (including definitions the script
itself embeds). `$name` references a declared
[input](#inputs-properties-and-response-files) and must stand alone
as a whole argument; inside strings the braced form `${name}` is
used instead. Definition sites — the `media` label, the `input`
name — are bare identifiers; the sigils mark use sites.

## Core grammar

Every line of every script — outside a `media` island — is one
structural shape:

```text
node = name , { argument } , { property } , [ block ] ;   (* informative *)
```

This is the shape a parser recognizes before typing; conformance
is defined solely by the typed grammar below together with the
static-validation rules that follow it. The core view is
structural — what a line looks like; the typed view is normative
for admissibility.

One declared island: a `media` node's block contains a JSON object
(RFC 8259) rather than nodes. It is the sole place where the block
rule in [lexical rules](#lexical-rules) does not apply: the island
closes at the `}` that closes its JSON object, so a nested `}`
alone on a line — which the archive form always contains — does
not close it, and neither does a `}` inside a JSON string. Script
tokenization is suspended for the interior; comments and input
references have no meaning there.

A typing layer over the node shape supplies the rest of the
language definition:

- **Ordering.** Header nodes come first, then `media` and `input`
  declarations, then either top-level statements (a linear script)
  or `phase` nodes (a phased script). Mixing the two body kinds is
  a parse error.
- **Signatures.** Each node name fixes its argument types, allowed
  properties, and whether it takes a block. The complete signature
  tables follow; an argument or property outside a node's
  signature is a parse error.

Header nodes:

| node | argument | notes |
|---|---|---|
| `description` | string | optional human-facing text |
| `platform` | name | required |
| `machine` | `running` or `stopped` | expected starting machine state |
| `entry` | phase name | required in a phased script, forbidden in a linear one |
| `timeout` | duration | script-wide observation default |
| `deadline` | duration | wall-clock budget for the whole run |

Declarations:

| node | arguments | properties | block |
|---|---|---|---|
| `media` | label | — | JSON media definition |
| `input` | `text`/`media`/`secret`, name | `property`, `prompt` | — |

Statements:

| node | arguments | properties | block |
|---|---|---|---|
| `wait` | one condition (string/regex, or `machine=` state) | `timeout`, `stable` | — |
| `wait` | — (no condition; its handlers carry them) | `timeout` | `on` handlers |
| `on` | one condition | `stable` | statements |
| `goto` | phase name | — | — |
| `finish` | — | — | — |
| `enter` | string | — | — |
| `type` | string | — | — |
| `press` | key names | — | — |
| `select` | string | `exclude` | — |
| `screenshot` | optional name | — | — |
| `insert` | slot, `@media` or `$input` | — | — |
| `eject` | slot | — | — |
| `boot` | drive keys | — | — |
| `start` | — | — | — |
| `stop` | — | — | — |
| `stage` | path string | — | — |
| `collect` | path string | `to` | — |

And the phase declaration:

| node | arguments | properties | block |
|---|---|---|---|
| `phase` | name | `timeout`, `deadline` | statements, or `on` handlers |

### Grammar (normative)

The signature tables above expand into this complete EBNF. Every
production but `media-def`'s island is an instance of the node
shape. A parser may parse structurally and then type-check, but
this grammar and the static rules below decide what is legal:

```text
script          = { header } , { media-def } , { input-def } ,
                  ( linear-body | phased-body ) ;

header          = "description" , string , eol
                | "platform" , name , eol
                | "machine" , ( "running" | "stopped" ) , eol
                | "entry" , name , eol
                | "timeout" , duration , eol
                | "deadline" , duration , eol ;

media-def       = "media" , name , json-island ;
json-island     = "{" , eol , { json-line } , "}" , eol ;
input-def       = "input" , ( "text" | "media" | "secret" ) ,
                  name , { input-prop } , eol ;
input-prop      = ( "property" | "prompt" ) , "=" , string ;

linear-body     = statement-list ;
phased-body     = phase , { phase } ;
phase           = "phase" , name , { timing-prop } , block-open ,
                  ( sequential-body | reactive-body ) ,
                  block-close ;
timing-prop     = ( "timeout" | "deadline" ) , "=" , duration ;

sequential-body = statement-list ;
reactive-body   = handler , { handler } ;
statement-list  = { statement } ;

statement       = observation | action | transfer ;
transfer        = "goto" , name , eol | "finish" , eol ;
observation     = "wait" , condition , { watch-prop } , eol
                | "wait" , [ "timeout" , "=" , duration ] ,
                  block-open , handler , { handler } ,
                  block-close ;
handler         = "on" , condition ,
                  [ "stable" , "=" , duration ] , block-open ,
                  statement-list , block-close ;
watch-prop      = ( "timeout" | "stable" ) , "=" , duration ;

condition       = string | regex
                | "machine" , "=" , machine-state ;
machine-state   = "stopped" ;

action          = "enter" , string , eol
                | "type" , string , eol
                | "press" , key , { key } , eol
                | "select" , string ,
                  [ "exclude" , "=" , string ] , eol
                | "screenshot" , [ name ] , eol
                | "insert" , slot , ( media-ref | input-ref ) ,
                  eol
                | "eject" , slot , eol
                | "boot" , slot , { slot } , eol
                | "start" , eol
                | "stop" , eol
                | "stage" , string , eol
                | "collect" , string ,
                  [ "to" , "=" , string ] , eol ;

block-open      = "{" , eol ;
block-close     = "}" , eol ;
media-ref       = "@" , name ;
input-ref       = "$" , name ;
key             = key-name , { "+" , key-name } ;

name            = letter , { letter | digit | "." | "_" | "-" } ;
duration        = number , ( "ms" | "s" | "m" | "h" ) ;
number          = digit , { digit } ,
                  [ "." , digit , { digit } ]
                | "." , digit , { digit } ;
string          = '"' , { str-char | escape | interpolation
                        | key-token } , '"' ;
escape          = "\" , ? any character except a line
                        terminator ? ;
interpolation   = "${" , name , "}" ;
key-token       = "<" , key , ">" ;
regex           = "/" , { regex-char | regex-escape } , "/" ;
regex-char      = ? any character except "/", "\", and a line
                    terminator ? ;
regex-escape    = "\" , ? any character except a line
                        terminator ? ;
```

`json-line` is any line of the JSON island, tokenized by RFC 8259
rather than by this grammar; the island closes at the `}` closing
its object, as described above. `interpolation` and `key-token`
are recognized only where the argument accepts them — never in a
regex, `key-token` only in `enter` and `type`. `slot`, `key-name`,
and `machine-state` values are `name` tokens whose closed
vocabularies (drive slots, the portable key set, machine states)
are checked by validation, not the grammar.

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
  script's does not have to: reaching end of file completes the
  run, and a trailing `finish` states that explicitly. `goto`
  remains invalid in a linear script.

A small set of constraints is deliberately context-sensitive —
enforced by static validation over the parse tree rather than
encoded in the CFG:

- each header appears at most once; `entry` appears exactly in
  phased scripts;
- no node carries the same property name twice; a repeat is a
  static error, never a last-wins override;
- an observation carries **exactly one** condition — a bare
  string/regex condition beside a `machine=` property, or two
  `machine=` properties, are errors — and the condition precedes
  any timing property on the same observation;
- a branching `wait` carries no condition of its own; its
  handlers do;
- no handler body contains a branching `wait`. The recursion
  `handler → statement → observation` is deliberate: the grammar
  stays context-free and the depth limit is a static rule, not a
  parse rule;
- the [terminating-statements rules](#terminating-statements);
- the [timing placement matrix](#timing): each timing property is
  legal only where the matrix allows it;
- `goto` names a declared phase and never appears in a linear
  script; media labels are unique; reserved node names are not
  identifiers; durations are positive.

The grammar is line-oriented and LL(1) over the token stream in
[lexical rules](#lexical-rules), given one lexical rule: a bare
word immediately followed by `=` is a property-key token. Without
it the node shape is not LL(1) — an argument and a property key
are the same token until the `=` is seen, as in
`phase formatting timeout=5m`. All static validation —
terminating-statement checking, transition targets, capability
preflight, timing resolution — runs over the typed tree before any
machine starts.

## Header

Header nodes precede embedded media definitions, input
declarations, and executable content:

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
  starts. The default is `running`: the `script` command starts a
  stopped machine before executing. `stopped` requires a stopped
  machine — a running machine fails preflight rather than being
  implicitly powered off — and the script performs its own explicit
  `start`, typically after inserting the media it needs. An install
  script that must insert its installer medium before first boot
  declares `machine stopped`.
- `entry` names the phase where a phased script begins. It is
  required in a phased script and forbidden in a linear one.
- `timeout` optionally changes the script-wide observation default
  from `60s`. See [timing](#timing).
- `deadline` optionally bounds the whole run's wall clock. It is
  the backstop for legitimate transition cycles — a reboot loop
  that never converges fails here rather than running forever.

Each header may appear at most once. The file name supplies the
script name. There is no format-version field before beta because
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
completes it, equivalently to an explicit `finish`. `goto` is
invalid in a linear script — there are no phases to name.

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
  or `finish`. It cannot contain direct `on` handlers.
- A reactive phase contains only `on` handlers. Every handler is
  active from phase entry. A handler may transition, finish the
  script, or complete its action and return to the same reactive
  phase. It cannot contain an interleaved ordered body.

If a handler should only become relevant later, the script enters a
smaller phase at that point. Handler activation is therefore
visible in the phase graph rather than hidden in statement
position.

There are no anonymous phases and no implicit phase entry.

## Embedded media definitions

A script may carry media definitions needed by that workflow, but
never has to: a script's media references resolve through the
ordinary shared catalog, so definitions that live as separate
library documents — as the built-in library keeps its own — work
identically. Embedding suits a script distributed as a single
self-contained file. Each block has a definition label followed by
the ordinary media-definition JSON object; the outer opening brace
becomes the node's block:

```rlqs
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
the definition, not an item; an archive definition may still
contain several independently named items, each referenced by
`@<item-name>`.

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
   temp-and-replace. Installation is transactional across the
   blocks: an I/O failure removes files created by that attempt
   before the script proceeds.
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

Inputs externalize run-specific data while keeping control flow
fixed. Three input types exist initially:

```rlqs
input text owner-name property="identity.full-name" prompt="Registered owner"
input media supplemental-disk prompt="Supplemental disk"
input secret product-key property="products.windows-98.install-key"
```

- `text` is immutable text supplied to action arguments such as
  `enter`, `type`, and `select`. It cannot parameterize watch
  conditions, phase names, paths, or control flow.
- `media` is the name of a defined media item. It is valid only
  where a media argument is expected, such as `insert`.
- `secret` is protected immutable text. It may be expanded only in
  `enter` and `type`; its value and expanded argument are omitted
  from transcripts and diagnostics.
- `property` optionally binds the input to a key in the
  [user property registry](property-registry.md). The quoted key is
  literal and cannot contain an input reference.
- `prompt` is optional user-facing text; the input name is used
  when it is omitted.

References use `$name` as a whole argument and `${name}` inside
strings:

```rlqs
enter "setup /owner=${owner-name}"
insert floppy1 $supplemental-disk
type "${product-key}"
```

A `media` input must occupy the whole media argument; it cannot be
interpolated into text. A `text` input may appear more than once in
an ordinary quoted input string. Input references are not
expressions and cannot control watch conditions, transitions, or
phase selection. A `secret` input follows the text interpolation
rules only inside `enter` and `type`.

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
2. the property named by `property=`; or
3. an interactive prompt.

Without an interactive terminal, a still-missing value fails before
execution. Response files therefore override personal registry
defaults for one invocation. Prompted values are not written back
to the registry. A media value is resolved after binding, and a
media prompt lists the embedded and existing library names valid
for that response.

Ordinary properties are strings. Secret properties keep only a
marker in `properties.json`; their values live in the host
credential store. `text` and `media` inputs require ordinary
properties, while `secret` requires a secret property. Kind
mismatches fail rather than silently downgrading protected data.
See the [property-registry specification](property-registry.md) for
its file format, maintenance commands, precise failure rules, and
security boundary.

The transcript records input references and source kinds, never
expanded values. For a `secret`, it also omits the entire expanded
input argument, redacts the value from textual diagnostics, and
suppresses later automatic failure screenshots. An explicitly
requested screenshot and the guest's own display, logs, or command
history remain capable of exposing guest-entered data.

Response files may contain sensitive text and should not be assumed
safe to commit. A response-file string may override a `secret`
input, but it is still plaintext in that file; the property
registry is the normal reusable source for protected values.

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

When several `on` handlers could match the same screen snapshot,
the first declaration wins. Validation warns about obvious literal
shadowing; regex overlap cannot generally be proven.

### Machine state

`machine=stopped` is the initial machine-state condition:

```rlqs
wait machine=stopped
```

It means that the backend reports the machine no longer running. It
does not by itself prove that shutdown was graceful; the preceding
guest action supplies that intent:

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
The single-condition form succeeds when its condition matches and
fails when its timeout expires:

```rlqs
wait "C:\>"
wait /[0-9]+ files copied/ timeout=5m
wait machine=stopped
```

A script that needs to know a console command completed waits for
output uniquely produced by that command or for the resulting guest
state; `enter` itself makes no completion claim.

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
`wait` requires at least one handler. An empty handler body is the
explicit no-action branch.

### `on` and reactive phases

`on <condition> { ... }` binds a condition to an action, using the
same condition spellings as `wait` — an unprefixed string or
regex for the screen, or a named non-default channel such as
`machine=stopped`. Its lifecycle belongs
to its container: inside a branching `wait` the first match ends
the wait; directly inside a reactive phase every handler stays
active until the phase transitions. The syntax is identical in
both places — the language has exactly one branch form.

A handler body — in a branching `wait` or in a reactive phase —
contains ordered statements and single-condition `wait`s, and may
end in `goto` or `finish`. It may not contain a branching `wait`.
Branch nesting stops at one level on purpose: further structure
belongs in the phase graph, where `goto <phase>` and
`phase <phase>` find it, rather than in indentation depth.

A reactive phase is a set of handlers, all armed from phase entry:

```rlqs
phase copying timeout=5m deadline=30m {
    on "Please insert disk 2" {
        insert floppy1 $supplemental-disk
        press enter
    }
    on "Installation complete" {
        select "Reboot"
        goto first-boot
    }
}
```

Handlers are evaluated in declaration order. Dispatch is
single-threaded and run-to-completion:

1. The first matching, armed handler is selected.
2. That handler is consumed for the current matching episode.
3. Its action completes without interruption from other handlers.
4. A `goto` or `finish` takes effect; otherwise dispatch resumes
   in the same phase.
5. The handler cannot fire again until its condition has first
   become unmatched and later matches again.

This edge/episode rule prevents a persistent confirmation screen
from generating repeated input on every poll. A handler action may
contain ordered statements, including single-condition `wait`, but
no handler is dispatched recursively while the action runs.

Handler conditions accept the same channels as `wait`. A `stable`
property strengthens the condition:

```rlqs
on "Installation complete" stable=1s {
    goto first-boot
}
```

## Timing

The timing model in one sentence: **`timeout` bounds the time to
the next observed event, `deadline` bounds the total wall clock of
the construct it annotates, `stable` strengthens one observation,
and there is no `delay`.**

The two families scope differently, and placement is the law:

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

Where each word may appear, and what it means there — any other
placement is a parse error:

| written on | `timeout` | `deadline` | `stable` |
|---|---|---|---|
| header | default for all observations | budget for the run | error |
| `phase` | default within the phase | budget per phase entry | error |
| single-condition `wait` | bound on this observation | error | hold requirement on this match |
| branching `wait` | bound on reaching the first match | error | error — put it on the `on` |
| `on` | error — the container owns the waiting | error | hold requirement on this condition |

Two placements are rejected deliberately rather than tolerated:
`deadline` on a single observation would be an exact synonym for
`timeout` (a scope containing one observation has identical bound
and budget), and a language should refuse two spellings for one
meaning; `stable` on a container is meaningless because only a
match can be required to hold.

Because per-observation resolution is fully lexical, the effective
timeout of every observation is computable at parse time:
`check-script` reports the resolved timing plan, and a timing
failure names which clock expired and the scope that supplied it —
an observation timeout from a statement, a phase deadline from its
declaration, or the run deadline from the header.

`stable` requires a watch condition to remain matched for the
stated duration before succeeding:

```rlqs
wait "Formatting" stable=2s
```

There is no generic sleep or delay verb, on principle: a blind
pause encodes a guess about guest speed that will be wrong on
another host. Every pause must be justified by an observation;
`stable` strengthens one rather than blindly pausing after it.
Screen polling and input-event pacing remain control-plane-owned;
the script does not tune them.

## Input verbs

### `enter`

```rlqs
enter "fdapm poweroff"
enter "setup /owner=${owner-name}"
```

Types the expanded string and presses Enter. It sends input only;
it does not assert that a command started, completed, or succeeded.
Completion is an explicit subsequent observation.

`enter "..."` is equivalent to `type "...<enter>"`.

### `type`

```rlqs
type "A:"
type "<down><down><enter>"
```

Types text and recognized `<key>` tokens with no implicit ending.
Use it for input containing both text and keys. An unrecognized key
token is a static validation error.

### `press`

```rlqs
press enter
press down down enter
press ctrl+c
```

Presses a sequence of keys. Names joined by `+` form a chord.

The portable key vocabulary is one closed set, owned by the
language and shared between `press` and `<key>` tokens:

```text
enter esc tab space backspace
up down left right
insert delete home end pageup pagedown
f1 f2 f3 f4 f5 f6 f7 f8 f9 f10 f11 f12
ctrl alt shift
```

Single printable characters are not key names — they reach the
guest as text through `type` or `enter`, except as the
non-modifier member of a chord (`ctrl+c`). The chord production
`key = key-name , { "+" , key-name }` holds identically inside
`<...>` in a typed string, so `type "<ctrl+c>"` is legal and means
the same as `press ctrl+c`. A control plane that cannot deliver a
listed key is a named capability failure at preflight; the
vocabulary is never per-platform.

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
verb never guesses.

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

Captures the screen in the current run directory. The default name
contains the step number. Repeated explicit names receive an
occurrence suffix rather than overwriting an earlier capture.
Failing observations capture a screenshot automatically.

### `insert` and `eject`

```rlqs
insert cdrom0 @freedos-1.4-livecd
insert floppy1 $supplemental-disk
eject cdrom0
```

These change what medium occupies a declared **floppy or CD-ROM**
slot and record the change in the machine's state document, not
its blueprint. Hard-disk slots are never targets: `insert` and
`eject` address removable slots only. Slot names, ranges, and the
alias/canonical rule are defined once, in the
[blueprint field reference](machine-blueprint-reference.md); `boot`
keys use the same vocabulary. The verbs never create or remove
the drive itself: drives are guest-visible hardware the blueprint
declares — an installer-driven blueprint declares the slot empty
(`"cdrom0": null`) — and an `insert` or `eject` naming a missing
or non-removable slot fails static preflight, before any guest
input. `insert` accepts a media reference (`@name`) or a `media`
input (`$name`); bare media names are not valid. By execution time
every embedded definition has been installed, so resolution uses
the ordinary shared catalog, then fetches and hash-verifies the
item as needed. Both verbs work on a running machine (a media
change the guest observes) and on a stopped one (the medium present
at the next `start`).

**Insertions are definitive machine state.** An `insert` persists
across `stop`/`start` exactly like an installer's writes to a hard
disk: the machine has diverged from its blueprint, and stays
diverged until a later `insert`/`eject` changes the slot again or
[`apply`](machine-blueprint.md#applying-blueprint-edits) returns
the machine to its blueprint. A script that changes machine state
it should not leave behind — an install script's installer CD —
ends by explicitly restoring it, conventionally with `eject` as
its final step. A script that fails or is interrupted leaves its
media changes in place for diagnosis and resumption; `apply` is the
one-command recovery when a diverged machine should return to its
blueprint shape.

### `boot`

```rlqs
boot hdd0 cdrom0
boot cdrom0
```

`boot` replaces the machine's boot order with the listed drive
keys (canonical or alias form), persisted in the machine's state
document. Every key must name a drive the machine already
declares; duplicates are rejected. The machine must be stopped —
the new order takes effect on the next `start`. Like
`insert`/`eject`, the change diverges the machine from its
blueprint until a later `boot`, or
[`apply`](machine-blueprint.md#applying-blueprint-edits), restores
it.

Most install scripts never need this: a blueprint that boots
`["hdd0", "cdrom0"]` with a blank hard disk falls through to an
attached installer CD, then boots the installed disk once it is
populated. The verb exists for scripts that genuinely need a
different order than the blueprint's default.

### `stage` and `collect`

```rlqs
stop
stage "payloads/AUTOTEST.EXE"
start

# guest runs and shuts down
collect "RESULTS.LOG" to="results/"
```

`stage` places a host file on the declared exchange drive;
`collect` copies a guest-produced file from it. Both require the
machine to be stopped on every control plane. This uniform contract
preserves agentless virtual-FAT snapshot and write-back semantics.
Future live guest-agent transfer, if added, will use different
verbs with an explicitly stronger capability rather than silently
changing these verbs' lifecycle behavior.

Stage sources resolve relative to the script directory. Collection
destinations resolve beneath the run's output directory, never the
process working directory. The CLI may select another output root;
script paths cannot escape it.

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

Parsing and static validation finish before the machine starts.
They reject:

- malformed syntax, unknown node names, and unbalanced blocks;
- arguments, properties, or blocks outside a node's signature,
  including every illegal timing placement in the
  [placement table](#timing);
- duplicate or invalid names, reserved words used as names, and
  unknown `$` input references;
- conflicting embedded or shared media definitions and definition
  labels whose target files already contain different content;
- a missing or invalid `entry` phase;
- `goto` targets naming undeclared phases, and `goto` in a linear
  script;
- mixed linear/phased shapes;
- mixed sequential/reactive phase contents;
- a sequential phase whose statement list does not terminate, and
  any statement written after a terminating statement;
- a branching `wait` with no handlers, or a branching `wait`
  anywhere inside a handler body;
- any property name repeated on one node;
- unknown channel names, an observation carrying no condition or
  more than one, a condition on a branching `wait` itself, and
  channel values of the wrong kind (a string for `machine=`, or an
  unknown machine state);
- invalid key tokens and invalid typed argument positions;
- `insert`/`eject` targets that are not floppy or cdrom slots and
  (with a machine in scope) slots the target machine does not
  declare;
- `boot` keys that are not drive slots or (with a machine in
  scope) drives the target machine does not declare;
- unknown response keys, missing noninteractive responses, and
  response values of the wrong type;
- malformed property bindings, input/property kind mismatches,
  and required secret credentials unavailable from a secure host
  store.

Static analysis warns about unreachable phases, reactive phases
with no possible exit, obvious shadowed literal conditions, and
inputs that are declared but unused.

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
analysis — including the resolved timing plan, each observation's
effective timeout, and its source scope — without executing the
script, changing the user property registry, accessing secret
values, or writing to `media/`. Supplying a machine and response
file also performs typed binding and capability preflight.
Registry-aware checking reports property presence and kind; it
never reveals a property value.

## Failure, runs, and transcripts

Every invocation creates a unique run directory under:

```text
cache/machines/<machine_id>/runs/<timestamp>-<run_id>/
├── transcript.txt
├── screenshots/
└── output/
```

The CLI may redirect the output root, but transcript paths are
always reported explicitly. A transcript records:

- each executed source line and line number;
- phase entries, handler firings, branches, and transitions;
- observations with their channel, normalized matches, and elapsed
  time;
- input names and whether each came from a response, named user
  property, or prompt, but never expanded input values;
- each media definition installed or found identical, its source
  script line and shared-library path, and verified hashes;
- the selected backend and control plane for each operation; and
- every produced screenshot or collected-file path.

On failure it adds the pending condition or action, the clock that
expired and the scope that supplied it (statement timeout, phase
deadline, or run deadline), final observed screen text, machine
state, and an automatic screenshot when available.

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
  property; and
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

## Complete FreeDOS install example

```rlqs
description "FreeDOS 1.4 plain install from LiveCD"
platform    dos
machine     stopped
entry       startup
timeout     30s

phase startup {
    insert cdrom0 @freedos-1.4-livecd
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
thereafter boots the installed hard disk. No `boot` verb is needed.
The second visit to `cd-boot` reaches the other branch of its
closing `wait` because the disk has been partitioned. The
guest-driven reboot is expressed by the installer selection and the
resulting screen, not by a reliquary reboot command.

Verification is a separate script needing no machine
reconfiguration at all: after the install script's final `eject`,
the machine is back in its blueprint shape and simply boots the
installed hard disk. The verify script declares
`machine stopped` too and issues a plain `start`. If an
interrupted install run left the CD attached, `apply` restores the
blueprint shape (or the HD-first order boots the installed disk
anyway while the CD remains attached).

## Sharing

A shareable blueprint/script bundle consists of its script, machine
blueprint, any separate shared media definitions, and an example
response file containing only non-sensitive illustrative values.
Media definitions embedded in a script are installed into the
recipient's shared library on first run. Definitions already reused
by several scripts may be distributed directly under `media/`
instead. The user property registry, personal or secret response
files, and staged payloads stay out of the bundle and version
control. A script may recommend property keys, but every recipient
supplies their own values. Media remains hash-pinned and
independently fetched.
