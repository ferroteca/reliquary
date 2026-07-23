<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# DECISIONS

The adjudicated design-decision record: the July 2026 design
rounds and gap queues, moved out of [TASKS.md](TASKS.md)
(2026-07-22) so the task list stays a task list. Each entry
records what was decided, by whom and when, what was weighed and
declined, and where it folded. The specs, planning/ROADMAP.md, and
planning/INTERFACES.md / planning/USE-CASES.md remain the
normative homes — this file is the adjudication trail, and the
guard against re-litigating: anything recorded here as killed,
declined, or superseded is not revisited without new evidence,
argued through the interface-change rule
(planning/INTERFACES.md). Entries keep the spellings of their
time; mentions of "TASKS" records inside entries refer to
entries now in this file.

Decisions are numbered in the order first recorded — D1 the
earliest — and a number is never reused; the list reads
newest-first, so the top entry carries the highest number and
a new entry prepends with the next free one. The D-number is
the decision's citation handle everywhere: a decision
generally supports use cases (U-numbers), governing principles
([PRINCIPLES.md](../PRINCIPLES.md), P-numbers), or language goals
(G-numbers), and names what it supports; and it is citable
downstream — design docs, specs, and code commits justify
choices by citing D-numbers. New entries carry their supports;
retrofitting the older ones is a queued sweep (TASKS.md). An
overruled or no-longer-relevant decision moves, number and
text intact, to the Retired decisions section at the bottom,
its note naming what overruled it — a retired decision binds
nothing but remains the record.

- D27 — THE INPUT MODEL, AND D26'S CLOSURE TEST CORRECTED —
  DECIDED (owner, 2026-07-23, the same round continued).
  Supports P8; AMENDS D26 (part D) and ADDS P15 to the standing
  list. Three findings, one of them a defect in D26 as written.

  A — THE CLOSURE TEST WAS MIS-STATED. D26 called the character
  class `[A-Za-z0-9._:/-]` "the whole closure, and the only test
  needed", on the claim that EVERY operator needs a character
  outside it. THAT CLAIM IS FALSE, and the counter-example is the
  likeliest request of all: `${mem:-512M}` is built entirely from
  legal characters, because `:` is the qualifier separator and
  `-` is a media-name character. It is still refused — the
  qualifier is the text before the first colon, `mem` is not a
  known qualifier, and unknown qualifiers fail closed (D24) — so
  THE CLOSURE HOLDS AND ONLY ITS STATEMENT WAS WRONG.
  THE CORRECTED FORMULATION: the closure is that THE BODY IS ONE
  OF D24'S TWO PRODUCTIONS — qualified
  `qualifier:media-name[/path]`, or a dotted property key — AND
  NEITHER HAS A POSITION AN OPERATOR COULD OCCUPY. The character
  class is a FIRST SCREEN, catching `|`, `(`, `[`, `?`, `=`, and
  whitespace; the productions catch everything assembled from
  already-legal characters. Both are needed, neither alone is the
  test. Found by working the examples the principle asked for —
  recorded because a closure whose stated test is wrong invites
  exactly the feature it exists to refuse.

  B — P15, THE CLOSED INPUT MODEL, JOINS THE STANDING LIST.
  Everything reaches Reliquary through FOUR CHANNELS: three
  AUTHORED — specs (`.rlqb`, `.rlql`) carry the data, scripts
  (`.rlqs`) carry the logic, properties carry the values — and
  one INVOCATION, the CLI/API twins, carrying the command. It
  goes to the standing list rather than the proposals doc because
  it is honored as the code stands: the sweep found only
  `RELIQUARY_HOME` / `RELIQUARY_CACHE_DIR` / `RELIQUARY_QEMU_HOME`,
  each an invocation knob twinned with a flag, and no
  config-file reading of any kind. THE SET IS CLOSED AGAINST
  ACCRETION, NOT AGAINST DECISION (owner — "I wouldn't rule out
  an rc file at some point, but it needs justification"): a new
  input is ASSIGNED to an existing channel, and a new channel is
  ARGUED AND RECORDED under the interface-change rule before it
  exists — NEVER ARRIVED AT BY NAIVELY IMPLEMENTING A SMALL
  REQUEST ACROSS A STATED BOUNDARY (owner's framing, and the
  operative form of the whole round). The scoping is what makes
  it usable: not every small request is suspect, only one that
  crosses a written line, which turns the check mechanical —
  does this cross a stated ceiling or channel edge? If so it is
  a DECISION, not an implementation. The implementation is not
  unskilled; it is LOCALLY CORRECT, which is exactly why nothing
  stops it, and naive only about the line it crosses. And it is
  why the lines are written down at all: a boundary nobody
  stated cannot be checked against. This is the kernel P14 shares: both principles
  are ANTI-ACCRETION, NOT ANTI-GROWTH, because the precedents
  they guard against never failed by decision. Nobody at Helm
  decided to build a template engine; each feature landed
  individually justified. The principles exist to manufacture the
  moment where the big thing is visibly being decided.
  WORKED, NOT DECIDED: an rc file is most likely NOT a fifth
  channel but PERSISTENCE FOR THE FOURTH — invocation defaults,
  a memory the CLI channel does not have — and the argument it
  would have to win is already visible from the model: P4 (home
  convenience is unobjectionable; a project-tree rc silently
  changing `rlq` behavior breaks the runnable-in-place property
  U4 depends on, so "home only, never discovered upward" is the
  shape that survives), P6/P7 (a default that changes what a
  command does makes the CLI harder to drive from a program —
  mitigable by explicit flags always winning and the effective
  configuration being visible, but argued, not assumed), and P12
  (where it would live). Nothing here adopts one.

  C — P14 RESTATED OVER THREE AUTHORED CHANNELS, NOT TWO. The
  owner's challenge — the two-pillar language was hard to anchor,
  and properties is a third — is upheld, and the evidence was
  already normative: script-properties.md has "transforms in
  derivation syntax are permanently out — normalization lives in
  a fact's definition, arbitrary computation in the embedding
  API's provider seam", which is P14 written for the property
  pillar and never recognized as the same rule. THREE CHANNELS,
  THREE CEILINGS, ONE ESCAPE. The invocation channel is governed
  OPPOSITELY and stays with P6/P7: the authored channels are
  CAPPED (no more than this), the invocation channel is FLOORED
  (no less than this, and no cleverer) — which is why one
  principle could never cover all four.
  AND THE ESCAPE IS RESTATED: "computation's designated home is
  the embedding API" was imprecise and manufactured a P6 tension,
  since P6 forbids capability reachable from the API but not the
  CLI. COMPUTATION IS NOT A RELIQUARY CAPABILITY AT ALL — it
  lives OUTSIDE the pillars, in the caller's own language, and
  the API and CLI are two doors to it. The CLI user's host
  language is the shell, which P7 already guarantees is easy to
  drive Reliquary from. WHAT THIS SHARPENS: the evaluation
  layer's constituency is the HOME CLI USER (U1, U5) who has no
  project and no language — not the automating user (U4), who
  has both and for whom generation above is natural. The
  residency split (P4) predicts it.

  FOLDED: this entry; PRINCIPLES.md (P15 added, and the
  four-channel chart into the cross-cutting prose);
  PRINCIPLE-PROPOSALS.md (P14 restated over three channels, its
  architecture preamble moved out to P15); machine-blueprint.md
  ("Format stability" — the corrected closure test, and the
  worked standing answer and adoption test); ROADMAP milestone 7
  deliverable 1 (the corrected test). D26 keeps its text; this
  entry is the amendment of record.

- D26 — THE REACH TRIM AND THE STRING-GRAMMAR CLOSURE — DECIDED
  (owner, 2026-07-23, the format re-examination round). Supports
  U4, U5; P7, P10. AMENDS D18 (its HCL2 decline and its growth
  rule) and D24 (its reach rule). The owner re-opened the
  blueprint format one round after D18 affirmed it — "getting
  this decision wrong will be very expensive." THE FORMAT STANDS
  AGAIN, but the re-examination found the premise misdirected and
  the real exposure somewhere else, and this entry moves the
  hardening to where it belongs.

  A — THE FORMAT CHOICE IS THE CHEAP DECISION; THE STRING
  SUBLANGUAGE IS THE EXPENSIVE ONE. Swapping the format is
  near-free here and stays that way: three authored blueprints
  plus a one-line fixture corpus, D25 having just removed every
  compatibility promise before 1.0, and a logic-free tree
  converting mechanically in BOTH directions (Packer ran exactly
  the JSON→HCL2 migration and survived it — D18 read that as
  evidence for JSON, and it is equally evidence that the mistake
  is cheap to unwind). What does not unwind is a language living
  inside JSON strings: Helm's `{{ }}` and CloudFormation's
  `Fn::`/`!Sub` are unremovable not because the host format was
  wrong but because, once authors depend on the sublanguage, it
  must be carried alongside whatever replaces it. THE ROUND'S
  GOVERNING FIND: the irreversible decision was never JSON vs
  HCL2 — it is HOW MUCH LANGUAGE IS ALLOWED INSIDE THE STRINGS,
  and D18's growth rule governed only tree extensions, which is
  why D24 could widen the string surface without tripping any
  recorded rule.

  B — HCL2 DECLINED STRUCTURALLY, NOT "NOT YET". D18 declined
  "HCL2 NOW" on evaluator cost — a timing argument, which
  guarantees the question returns every time the cost estimate
  moves. The permanent objection is P7 with P6: blueprints are
  documents the embedding API emits as well as reads, and an HCL2
  WRITER outside Go effectively does not exist (`hclwrite` is
  Go-only; `python-hcl2` parses without round-tripping). Adopting
  HCL2 gives every non-Go binding a lossy, read-only relationship
  with the project's primary authoring format — a P7 violation on
  day one, not a deferred bill. Scale seconds it: real blueprints
  are 34–43 lines, and the one live growth pressure (member
  itemization) is the one place D22 forbids a language from
  helping — names must be static, the catalog can never depend on
  a download. HCL2 moves from the deferred column to the closed
  one. YAML, TOML, and KDL are unchanged and stay declined on
  D18's reasoning.

  C — THE REACH TRIM: CLOSED VOCABULARIES STAY STATIC. D24 widened
  `${…}` to any value not participating in identity or resolution
  structure, arguing from surface symmetry with the script
  language (G6) rather than from named cases. Reach is
  ASYMMETRIC — widening it later is backward-compatible,
  narrowing it is not — so the burden of proof belongs on the
  widening, and the symmetry argument does not discharge it.
  Tested against demand, the positions separate: `location`,
  `parameters` values, and `description` have named cases (D22's
  supply seam; prose), and the open numerics `memory` / `cpus` /
  `size` are plausible and cheap. THE CLOSED VOCABULARIES HAVE NO
  NAMED CASE AND CARRY THE WHOLE COST: `platform`, `backend`,
  `materialize`, `controller`, and `control-planes` items are
  where a published schema's completion is most valuable and
  where a reference destroys it. THE RULE, ONE CLAUSE ADDED TO
  D24'S: A REFERENCE MAY NOT SUPPLY A CLOSED-VOCABULARY VALUE.
  `platform` is the sharpest instance — P10 has it never inferred
  and always from the blueprint, and a `${…}` platform is a
  runtime-decided platform in all but name. This trades a measure
  of G6 symmetry for U4/U5 editor completion knowingly: the
  blueprint's enums are a fixed catalog the script language has
  no counterpart to, so the surfaces are not actually divergent
  where authors feel it.
  `sha256` IS KEPT INTERPOLABLE (weighed and declined for
  exclusion): a hash is not a closed vocabulary, so excluding it
  would cost the rule its one-clause shape; and it would NOT buy
  back parse-time validation, since what forces the
  `sha256`-required-once-remote check to resolution time is a
  REFERENCED LOCATION RUNG, not the hash field. D24's two-phase
  validation stands unchanged.

  D — THE STRING-GRAMMAR CLOSURE: OPERATIONS ARE CLOSED,
  NAMESPACES ARE OPEN. The `${…}` body is CLOSED at D24's shape
  and does not grow. Stated as the character class it already
  is — the whole closure, and the only test needed:

      ^\$\{[A-Za-z0-9._:/-]+\}$

  Every character is load-bearing today: `:` separates the
  qualifier (the text before the first colon), `/` separates the
  containment path (exactly one), `.` carries the property
  dot-path and is legal in a media name, `_` and `-` are
  media-name charter characters. CLOSED PERMANENTLY: every
  operator — defaults (`${key:-x}`), pipes and filters, calls,
  indexing, arithmetic, comparison, ternaries, nesting
  (`${${a}}`), and any second escape. They share one property
  that makes the closure mechanical rather than a matter of
  judgment: EVERY ONE OF THEM NEEDS A CHARACTER OUTSIDE THE
  CLASS. A proposal that does not fit the regex is a LAYER-SWITCH
  SIGNAL, never a grammar extension — which is the point of
  deciding now, because each such feature will arrive with a
  real user and a good case, and unanimous individual
  justification is exactly how the Helm shape is reached.
  OPEN: new QUALIFIERS — `env:`, `file:`, `machine:`, `script:`,
  `landmark:`, `secret:` already reserved by D24 — because a
  qualifier names a NAMESPACE TO LOOK IN, never an OPERATION TO
  PERFORM, and adding one costs no new character. UNAFFECTED: the
  script language's `${key}` is the narrower unqualified form
  (script-spec.md, `interpolation = "${" , name , "}"`) and is
  already inside the class; the closure is not a reason to
  harmonize it upward.

  E — THE LAYER SWITCH IS A SEPARATE KIND, NEVER A WIDENING OF
  `.rlqb`. D18 named Jsonnet the leading evaluation layer on the
  ground that JSONC is already valid Jsonnet — VERIFIED and it
  holds (Jsonnet takes `//`, `/* */`, `#`, and trailing commas;
  the JSON escape set is identical; `${…}` has no meaning in a
  Jsonnet string and passes through literally, escape included),
  so every existing blueprint would carry over byte-identical.
  But the free migration belongs to the DOCUMENTS, not to the
  DECISION: the day `.rlqb` means "evaluate as Jsonnet" the
  format can never narrow back, and schema validation and
  completion die for every file in the format, including the
  large majority that never wanted computation — the exact cost
  D18 bought JSON to avoid. THEREFORE, WHENEVER IT COMES: the
  evaluation layer is a DISTINCT FILE KIND or an EXPLICIT STEP (a
  `.rlqb.jsonnet` evaluated to a `.rlqb`, or an evaluate flag),
  so plain `.rlqb` keeps its schema, completion, and strictness
  permanently and the power user opts in per file. Recorded
  against the day, not scheduled; the packaging cost (Python
  Jsonnet means native bindings and Windows wheel availability)
  is a known input to that decision, not a blocker to this one.

  WEIGHED AND DECLINED: migrating to HCL2 (B); reverting D24's
  reach wholesale to D22's whole-value-only rule (the named cases
  are real and D24's argument for them stands — only the
  unnamed closed-vocabulary positions are trimmed); excluding
  `sha256` from reach (C); harmonizing the script `${…}` upward
  to the qualified form (nothing asks for it); gating the grammar
  closure on evidence (the inversion this entry exists to
  prevent — evidence-gating is right for reach, where the change
  is cheap in the safe direction, and wrong for grammar, where it
  is not).
  FOLDED: this entry; machine-blueprint.md ("Format stability" —
  the growth rule gains the string-grammar closure and the
  separate-kind rule); ROADMAP milestone 7 (the decide-first
  block and deliverable 1's reference-grammar paragraph — the
  reach exclusion lands with the parser, and deliverable 5's
  schema keeps its enums unpolluted). No landed code changes:
  the reference grammar is unimplemented, and
  blueprint-schema-v1.json is the milestone-6 schema deliverable
  5 replaces.

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
  U5; P11; G3, G6, G7. Triage under the interface-change rule: no
  use-case impact — an unlanded format hardened before its parser
  is written. D22 settled the `${…}` grammar fast at the close of
  the revision round; the scenario battery run against it here
  holds the shape and sharpens it, with one amendment (the escape)
  and one widening (the reach).
  THE REACH RULE, the battery's governing find: A REFERENCE MAY
  SUPPLY ANY VALUE THAT DOES NOT PARTICIPATE IN IDENTITY OR
  RESOLUTION STRUCTURE. The exclusions are `name`, `type`,
  `children` paths, and object keys (drive slots) — the catalog
  and the authored graph stay static (G3), which is D22's own
  ground for killing the `children` glob; everything else a scalar
  position accepts may be referenced.
  FULL INTERPOLATION (owner — "a general `${...}` should be viable
  almost anywhere a scalar/string/enum is provided"): an
  unqualified `${key}` interpolates ANYWHERE A STRING VALUE IS
  ACCEPTED, exactly as the script language already does
  (script-spec.md "Strings"; reliquary/script_parser.py) — the
  blueprint refusing what scripts allow was the surface divergence
  the battery could not justify (G6). Object field values
  interpolate too. THE ESCAPE IS `\${` — identical to the script
  spelling, written `"\\${"` in JSON — AMENDING D22's "the object
  form escapes out-of-band": prose fields (`description`) and
  direct `parameters` values have no object form, and a parameter
  carrying a literal `${HOME}` into a guest config file is an
  ordinary case, not a corner. The object form remains what D22
  made it — the canonical/state form and the option point — it is
  simply no longer the escape. RESOLUTION ORDER: interpolate, then
  scheme-dispatch the result; RESOLVED TEXT IS NEVER RE-SCANNED,
  which is D22's no-chaining rule made precise — a property whose
  value reads `${media:X}/p` stays literal text and fails the
  scheme check.
  QUALIFIED REFERENCES STAY STRUCTURAL: `${media:<name>}` is
  whole-value only (it desugars to an object; a media reference
  inside prose is meaningless), the `/<path>` suffix its second
  component as D22 has it. A BARE `${media:X}` IS LEGAL as a whole
  location, desugaring to `{"parent": "X"}` WITH NO `path` — the
  parent's own bytes — which is how `materialize: difference` puts
  an overlay over another media, the one case D22 left with no
  spelling. Declined: a new `{"media": …}` object form (a second
  object spelling for what `parent` already says).
  THE MEDIA-NAME CHARTER, SPLIT FROM THE PROPERTY-KEY CHARTER
  (owner challenge — "I am surprised 86Box.zip would cause any
  issue, and what's the downside to `[()\[\]]`"): the battery had
  inherited the script `name` production for media names without
  testing whether it was load-bearing, AND IT IS NOT. The lexer
  dispatches on the `@`/`$` sigil BEFORE the digit branch
  (reliquary/script_nodes.py), so the sigil is what classifies the
  token and a leading digit is unambiguous behind it; the
  letter-initial rule is load-bearing ONLY FOR PROPERTY KEYS,
  which also appear BARE at a `property` declaration, where a
  leading digit lexes as a duration. Media names have no bare site
  in any surface — `@name` in scripts, JSON strings in
  blueprints. Nor do `(`/`)`/`[`/`]` cost anything grammatically:
  a token ends at whitespace, brace, or comment
  (`_DELIMITERS = " \t{}#"`), so brackets scan straight through.
  THE CHARTER THEREFORE SPLITS, by one clause: `media-name =
  (letter | digit) , { letter | digit | "." | "_" | "-" }`, while
  `property-key` keeps its letter-initial `name`. The wider
  grammar-forced-only charter (excluding just whitespace, `{`,
  `}`, `#`, `/`, and control characters, admitting `FD(1)` and
  `FD[SE]`) was WEIGHED AND DECLINED: parens and brackets are
  equally shell metacharacters — `rlq fetch-media FD(1)` is a bash
  syntax error exactly as `FD[1]` is — and every media name is
  argv at `fetch-media` / `add-media` / `clean-media`, so a name
  needing per-shell quoting is a permanent papercut against P7;
  brackets add a glob hazard over `cache/media/` on top. What is
  mechanically forced out of a name regardless: whitespace, `{`,
  `}`, `#`, `/` (the containment separator — `${media:C:/x}` is
  otherwise ambiguous), and control characters.
  NAME DERIVATION — SANITIZE WITH A WARNING (owner), read as: THE
  SANITIZER REPAIRS THE CHARACTER SET, NEVER INVENTS A NAME. A
  stem outside the charter is repaired and warned, naming both the
  derived name and the source it came from (`FD 1.4 (final).zip` →
  `FD-1.4-final`); where repair cannot yield a legal name — the
  stem is empty, or repairs to nothing — or where there is no stem
  to derive from at all (a `${…}` location, a reference-bearing
  path suffix, a mirror list whose first rung is a reference), it
  FAILS CLOSED demanding an explicit `name`. A leading digit is
  NOT such a case under the split charter: `86Box.zip` derives
  `86Box` cleanly, no warning. Two sources
  sanitizing to one name still meet the standing duplicate-name
  collision error naming both, so the repair can hide nothing.
  Media names have never been charter-checked at all
  (the regex lives only in the script layer); deliverable 1 is
  where the check starts.
  CASE: names MATCH CASE-SENSITIVELY, COLLIDE CASE-INSENSITIVELY
  (owner) — `cache/media/` is name-keyed on filesystems that are
  not, so `FDBOOT` and `fdboot` in one source are a collision
  error naming both, while references still bind exactly.
  THE PATH SUFFIX: exactly one `/` separates reference from path,
  member paths are `/`-separated always (the container formats'
  own convention), and the path normalizes — `..`, absolute paths,
  and empty segments REFUSED as containment escapes. A backslash
  after `}` is an error naming the `/` rule (the Windows author's
  first guess); trailing and doubled slashes are errors.
  DISPATCH AND DEGENERATES: the qualifier is the text before the
  FIRST colon, so a property key never contains one (the charter
  already agrees); unqualified `${media}` is rejected with a
  did-you-mean rather than read as a property of that name;
  unknown qualifiers fail closed naming themselves (P11), with
  `property:` reserved-and-rejected under a nudge to drop the
  qualifier and `env:` / `file:` / `machine:` / `script:` /
  `landmark:` / `secret:` reserved; qualifiers are lowercase-only;
  `${}`, `${media:}`, `${:x}`, an unterminated `${`, and
  whitespace inside the braces are all parse errors naming the
  malformed reference. Scheme dispatch is unchanged, drive-letter
  exemption included.
  CYCLES AND ORDER: containment cycles and a self-parent fail
  closed naming the cycle; forward references stay legal —
  resolution reads the whole source and is order-independent.
  LISTS: a one-element mirror list is the scalar (no special
  case), an empty list is an error, nested lists are illegal.
  TWO-PHASE VALIDATION, the widening's one real cost and the same
  work `location` already demanded: shape at parse, value at
  resolution (`create`/`apply`). THE `sha256`-REQUIRED-ONCE-REMOTE
  RULE MOVES TO RESOLUTION TIME — a `${key}` rung may resolve to a
  URL, so parse-time cannot know. Coercion at non-string positions
  is the field's own parser run over the resolved string, failing
  closed naming field, value, and source. Failures before
  milestone 8 name properties, never a milestone number.
  RECORDED, NOT A DEFECT: scripts reference media as `@name` and
  blueprints as `${media:<name>}` — deliberate divergence, since
  JSON has no token classes and a reference must live inside a
  string; the property spelling is identical across both surfaces,
  which is what D22's "one reference syntax" was buying.
  WEIGHED AND DECLINED: whole-value-only reach (D22 as written —
  it left the blueprint refusing what scripts allow, and left a
  property-built path unexpressible); the two-rule split
  (interpolation in free text, whole-value in typed fields — a
  second rule bought nothing, G6); the `{"media": …}` object form;
  silent sanitization (the derived catalog key must be visible to
  the author who will type `@name`); fully case-insensitive names
  (it would make the blueprint catalog case-blind while the script
  token is not); case-sensitivity throughout (two media differing
  only in case silently share one cache file on Windows and
  macOS).
  FOLDED: this entry; ROADMAP milestone 7 — the decide-first block
  retired, deliverable 1 restated to the hardened grammar,
  INTERFACES.md added to deliverable 6's realignment list (it
  still describes the retired four-component shape); script-spec.md
  — the `media-name` production and the References prose, the one
  place this round touches a landed surface — and its shipped
  check (reliquary/script_nodes.py), which now accepts `@86Box`.
  media-spec.md
  and blueprint-model.md stay superseded pending deliverable 6, as
  D22 left them; this entry and D22 are normative meanwhile.

- D23 — USE-CASE LIFECYCLE: THE CURRENT LIST + THE PROPOSALS DOC —
  DECIDED (owner, 2026-07-23). The use-case surface
  splits in two: planning/USE-CASES.md is the CURRENT STATE —
  every numbered use case in force — and the new
  planning/USE-CASE-PROPOSALS.md tracks proposed changes (new
  use cases being drafted, proposed retirements and
  supersessions) until adopted under the interface-change rule.
  THE LIFECYCLE (owner): a use case in force is never changed
  in nature — it may be CLARIFIED (an in-place wording edit no
  past citation would read differently under — clarify, never
  change; needs no argument; an undelivered clarification may
  park in the proposals doc against its use case's number until
  applied — owner follow-up, same day) or RETIRED:
  dropped without replacement, or SUPERSEDED by one or more new
  use cases carrying the need forward in a changed shape. ONE
  NAMESPACE (owner): proposed and in-force use cases number
  from the same global U-sequence; a proposal keeps its number
  for life and moves over verbatim on adoption; numbers are
  never reused — a dead proposal retires its number, and a
  superseded use case leaves the list stubless (amended by the
  no-placeholder follow-up below): DECISIONS.md records it and
  successors name it, so citations always resolve. DEAD-PROPOSAL SWEEP (owner): a
  proposal declined, withdrawn, or lapsed unimplemented is
  removed, and its removal triggers a planning-doc sweep —
  downstream design docs, ROADMAP items, and TASKS entries
  predicated on it fall out in the same pass; the death is
  recorded here with its reason. TRACEABILITY (owner): every
  ROADMAP item cites the use case — in force or proposed — that
  demands it, so a dead proposal's U-number is the sweep's
  search key (the citation-retrofit sweep is an open issue).
  THE PLANNING FLOW (owner, same-day follow-ups): use cases
  drive the roadmap; a roadmap milestone item is picked up by
  translating it into a sprint tasklist; tasks flow from the
  roadmap and from issues, and a task is either scheduled for
  the sprint or backlogged. Small one-offs really just are
  issues; issues live on the GitHub tracker, and TASKS.md's
  backlog — the section formerly named Wishlist: small,
  obvious, just hasn't met the bar for scheduling — is the
  parking place for non-GitHub issues; a small, obvious,
  needed fix goes directly to tasks. In theory every issue
  points to the use case it serves, small ones may simply be
  deemed obvious; an issue can easily trigger a use-case
  proposal (triage through the interface-change rule). A
  separate planning/ISSUES.md was weighed and REVERTED
  in-round (owner steer: tasks is the parking place — one
  local doc, GitHub the tracker). TASKS' Language / Watches /
  Design sections stay put pending their own sprint/backlog
  sort [agent's boundary call, veto cheap]. NAMING (owner):
  "primary use cases" is just "use cases" — the qualifier
  drops across the living docs (historical entries here keep
  their spellings; the primary interfaces and the primary
  language goals keep their names). MOVE TRIGGER — DELIVERY
  (owner, 2026-07-23, vetoing the agent's adoption-time
  encoding): "moved over when implemented" means what it says.
  ACCEPTANCE (the argument won) authorizes work and makes a
  proposal citable; DELIVERY makes it current and moves it
  over. The current list is not an implementation claim: a use
  case is current while its delivery is landed or SCHEDULED on
  the numbered arc ("I'm sure we don't meet most of the use
  cases as the code stands today" — owner); UNSCHEDULED
  delivery is the relocation trigger, and the door swings both
  ways. First instance: U5 moved back as
  accepted-awaiting-delivery (owner — its customized-Windows
  scenario waits on the unscheduled GUI era). NO STUB (owner
  follow-up, same day, rejecting the agent's stub): an
  undelivered case lives ONLY in the proposals doc — the
  shared U-namespace keeps its citations valid. U6 followed
  the same day (owner, confirming the flag: the recorder — its
  whole delivery — is unscheduled Horizon work; only milestone
  9's reserved handover kinds touch it). U2 joined the same
  position when milestone 12 demoted — still flagged, owner's
  call pending.
  THE MAPPING + SWEEP DIRECTIVES (owner, 2026-07-23): the
  roadmap–use-case mapping found three gaps — the
  multi-backend pillar demand-free, U5/U6
  delivery-unscheduled, the multi-language binding expectation
  unscheduled — and the owner directed: gap 1 addressed by a
  drafted proposal (U7); gap 2 by U5's relocation (above);
  gap 3 by a proposed use case and NO roadmap item (U9 — the
  CLI fallback carries unbound languages until a second
  binding earns scheduling on its own). GENERAL DIRECTIVE
  (owner): the use cases break down into much smaller chunks
  where possible — calibrating example: "a user at the
  keyboard should be able to easily find a codex blueprint …
  and seed it into their library" — and people read them, so
  each must be succinct, digestible, and justified. Drafts
  U7–U17 and the pending U1/U2 condensations sit in
  USE-CASE-PROPOSALS.md awaiting adjudication — drafting is
  not acceptance; nothing folded into the current list.
  DECISIONS NUMBERED + THE RETIRED LIST + ITEMIZED PRINCIPLES
  (owner, 2026-07-23, same-day follow-ups): decisions carry
  permanent D-numbers — D1 the earliest, this entry D23 — and
  generally support use cases or governing principles, naming
  them; the D-number is citation currency beyond planning —
  design choices and code commits justify themselves by citing
  it (owner). Overruled or no-longer-relevant decisions move,
  number and text intact, to the Retired list at the bottom of
  this file: D2 (overruled by D16) and D17 (superseded by D22)
  open it. The governing principles are itemized in the new
  PRINCIPLES.md (P1–P12, each indexed at its
  normative home), feeding use cases and decisions; the
  supports retrofit for D1–D22 is queued in TASKS.md.
  ACCEPTANCE IS SCHEDULING (owner, 2026-07-23, closing the
  acceptance semantics): a proposal is accepted when the
  roadmap schedules the work its use case demands — the citing
  roadmap item is the acceptance record; no separate
  acceptance stamp exists. A chunk whose demanded work already
  landed is accepted and delivered in one act. U5's acceptance
  rides milestone 8 (scheduled, citing it); its unscheduled
  canonical scenario is why it is not current.
  MILESTONE 12 DEMOTED TO HORIZON (owner, 2026-07-23): machine
  mobility — clone, export, import — leaves the numbered arc
  for lack of use-case backing (clone has none; export stands
  only on the U8 draft; import's U2 loses its scheduled
  delivery — the U2 relocation question is flagged alongside
  U6's). Guest agents renumber 13 → 12; historical entries
  keep the milestone numbers of their time, forward-looking
  pointers move (the renumber rule, D14). The remaining
  unjustified Horizon items — fork-blueprint, the media verbs
  beyond fetch, pytest-reliquary — are flagged "currently
  unjustified" in place (owner).
  IMPLEMENTED-ONLY, RESTATED (owner, 2026-07-23, correcting
  the agent's landed-or-scheduled softening): the current list
  carries NO unimplemented use case and no placeholder — it is
  an implementation claim, every entry met by the code today;
  the placeholder is the proposals doc. Applied: U1 (the
  export clause is unimplemented Horizon work), U2 (import
  unimplemented), and U3 (granular results and selective
  re-run ride milestones 8–9) moved to
  accepted-awaiting-delivery; U4 alone is met as written (its
  proprietary-OS mention read as example, not demand — agent's
  judgment, veto cheap). THE PRINCIPLES PROSE MOVES (owner:
  seams, axes, models, and concepts are not use cases): the
  cross-cutting prose — ephemeral machine, the control-plane
  arc, the artifact-residency split, the feedback split —
  leaves USE-CASES.md for PRINCIPLES.md, now its normative
  home (P1/P3/P4/P5); PRINCIPLES.md over a new
  ARCHITECTURE.md was the agent's choice (veto cheap), and
  citations across ROADMAP, INTERFACES, TASKS, media-spec,
  machine-blueprint, guest-communication, and codex re-point
  to P-numbers. PRINCIPLES DRIVE WORK (owner, 2026-07-23,
  closing the round): principles drive tasks and roadmap items
  just as use cases do — the traceability rule accepts a
  P-number as the demanding citation, and the ROADMAP citation
  sweep covers both. AND PROPOSED PRINCIPLES (owner, same
  message thread): principles get the same proposals
  machinery — planning/PRINCIPLE-PROPOSALS.md (new), the same
  global P-namespace, lifecycle, no-placeholder rule, and
  sweep; the ROADMAP design-principle absorption candidates
  move there as its first tracked entry. SAME EVOLUTION MODEL
  (owner): clarify yes, retire yes, add yes, change no — for
  STANDING principles and use cases; a proposed U or P may be
  reshaped freely until it enters force (number kept; work
  scheduled against an accepted one is re-checked in the same
  edit). THE P1–P12 DELIVERY PASS (owner-prompted, 2026-07-23,
  verified against the code, not the docs): P1–P4 and P6–P12
  are real — evidence: create/destroy/recreate and the
  machine-is-its-cache-dir model (P1); no guest-cooperation
  dependency anywhere (P2); no guest agent built or shipped
  (P3); assets.py's fail-closed no-default source and the two
  modes (P4); the landed twin renames, omissions named never
  drifted (P6); --json printing the twin's return (P7); this
  round itself (P8); the deletions throughout (P9); explicit
  platform gates and no guest probing — probe_image_format
  reads host image formats, not guests (P10);
  NotImplementedError discipline naming gaps — controller,
  exec platform, import-vm (P11); home.py containment with its
  tests (P12). P5 FAILED the bar: the feedback split is
  run-scoped and the machine-readable run rendering does not
  exist — no run-events stream, no --progress renderers (the
  flag lives only in an error message) — moved to
  PRINCIPLE-PROPOSALS.md as accepted (milestone 9, scheduled,
  cites it). One P11 LEAK found and filed to the TASKS
  backlog: declared control-planes are vocabulary-checked but
  never refused at materialization — an unimplemented plane is
  accepted silently. STANDING PRINCIPLES LIVE AT ROOT (owner):
  PRINCIPLES.md moves from planning/ to the repository root —
  it describes current reality, the placement rule's own
  test; references re-pointed. P13 DRAFTED (owner, 2026-07-23,
  naming it "property sources" — the house noun): the
  custody-and-introspection kernel of the property source
  model drafted into PRINCIPLE-PROPOSALS.md; the tier list
  stays design in script-properties.md, and milestone 8's
  citation, when made, is its acceptance.
  TERMINOLOGY (agent's proposal, veto cheap): the owner's
  candidate "obsolete" set aside for the two words already in
  house usage — RETIRED (removed, no successor; "the source
  type retires") and SUPERSEDED (replaced, successors named;
  this file's own preamble vocabulary) — "deprecated" rejected
  outright (implies still-usable-but-discouraged, clashing
  with the no-BC rule). SEEDED: the break-out expectations U3
  and U6 carried in-line ("dense, will likely be broken out")
  move to the proposals doc as tracked proposals; removing the
  sentences is a clarification (meta-commentary, not nature).
  Today nothing hangs on a proposal: every design doc, ROADMAP
  item, and TASKS entry cites in-force use cases or
  principles, so nothing downstream falls out if the two
  tracked break-outs die. (Amended same day: with U5 relocated,
  milestone 8 and the GUI-era backlog hang on an accepted
  proposal — by design; acceptance authorizes the work.) FOLDED: USE-CASES.md (status +
  lifecycle preamble; the two sentences removed),
  USE-CASE-PROPOSALS.md (new), INTERFACES.md (triage bullets,
  the strict workflow, Record-it, the use-cases
  section, the qualifier drop), ROADMAP preamble (the
  traceability rule + the flow), TASKS.md (preamble — the
  flow, sprint/backlog, the
  milestone-tasklist translation; Wishlist renamed Backlog;
  the citation-sweep one-off added), PRINCIPLES.md (new), this
  file (preamble, the D-numbers, the Retired list), AGENTS.md
  (layout bullets), .agents/skills/documentation-rules.md
  (planning/ inventory).

- D22 — THE BLUEPRINT REVISION ROUND — DECIDED (owner, 2026-07-23, the
  second same-day round; supersedes the four-component shape of
  the media/composition round below, before any of it was
  implemented — ROADMAP milestone 7 is the retargeted
  implementation). The composed model collapses further. TWO SPEC
  TYPES: `machine` and `media` — the archive/media distinction was
  never a property of the artifact, only of the use, so ARCHIVE IS
  ABSORBED INTO MEDIA, and the containment vocabulary is
  PARENT/CHILDREN (owner — "archive" and "members" exit the format
  language): any media may declare `children` (batch, recursive),
  and any media may declare its `parent` from the child side — a
  `${media:<name>}/<path>` location string, or the
  `{"parent": …, "path": …}` object (`parent` taking a media name
  or an inline media spec). `children` IS PURE SUGAR: every
  containment edge resolves to child-declares-parent; a `children`
  entry is a media spec declared in place (path-form only, no
  `location` key; a bare string is the path), desugaring to a
  standalone spec with a parent location — one semantic, two
  spellings, zero new rules (the identity dedup/collision rules
  are position-independent). BARE-STRING SPECS: a root array
  element that is a string is a media, desugaring to
  `{"location": <string>}` — invalid where the location kind
  demands a pin (a bare url string fails closed naming the object
  form). THE STRING-POSITION TABLE: at a drive → a media name; at
  a spec position → a location; in `children` → a path — each
  position with exactly one object desugaring. The mount-vs-
  container READING is decided at each reference site (a drive or
  script `insert` mounts; a parent location or `children` walk
  extracts). Dual roles are legal — one ISO mounted at `cdrom0`
  and container-read for its boot floppy. Container reading is
  ROSTER-GATED by format (zip at milestone 7; ISO9660 incl.
  `[BOOT]` El Torito virtual paths the recorded follow-on;
  filesystem-image reading out pre-beta).
  THE ROOT is a flat array of specs — the plural component
  sections retire; a lone spec OBJECT is kept as PURE SUGAR for
  the array of one (owner — minimalism convenience), same rules
  as any element, so the historical bare-root-machine reading
  (object ⟹ machine, no announcement) retires: an untyped lone
  object is a media. `type` is OPTIONAL, DEFAULTS
  TO `media`; a machine declares `"type": "machine"`
  (mandatory-everywhere argued hard and DECLINED by owner:
  blueprints are small, loose typing wins on convenience at this
  scale; the codex and examples always write `type` — model good
  code, don't enforce; the media-branch error carries a
  did-you-mean hint when machine vocabulary appears). An optional
  `type` anywhere nested is a checked echo — mismatch is an error.
  INLINE + ANONYMOUS: a media is definable inline at its drive
  (full spec, or the `{ "size": … }` blank — `size` implies
  `new`); the NAME IS THE MEMBERSHIP BIT — named (explicit, or
  stem-derived from content-intrinsic material: url/path stems,
  never the slot) → the one global catalog; the content-free
  blank is the SOLE ANONYMOUS citizen — in no namespace, site
  identity only, slot-named file at materialization,
  unreferenceable from scripts. THE SOURCE TYPE RETIRES; ONE
  `location` FIELD on media: strings interpreted by scheme —
  bare path (relative from the referencing file), `https:`/
  `http:`, `${media:<name>}/<path>`, `${<key>}` — and
  OBJECTS EXPLICIT (`url` / `local` / `parent`+`path` incl. an
  inline parent spec / `property`), under the format-wide law
  STRINGS ARE INTERPRETED, OBJECTS ARE EXPLICIT: every
  interpreted string has exactly one object desugaring (the
  canonical/state form), the object is the escape and the option
  point. Unrecognized scheme-shaped strings are parse errors
  (single-char drive-letter exemption). Mirror lists are lists of
  locations, mixed schemes allowed, `sha256` required once any
  remote rung is present; a property reference is
  whole-field-only, no
  chaining, resolved at `create`/`apply` into the state (never at
  `start`), binding through the property sources at milestone 8
  (grammar lands at 7, resolution fails closed naming 8 until
  then). THE UNIVERSAL REFERENCE: `${…}` is the one reference
  syntax everywhere — unqualified `${a.b.c}` ≡
  `{"property": "a.b.c"}` (one spelling across locations,
  `parameters` values, and the milestone-8 derivation grammar's
  `${key}` cross-references); qualified `${media:<name>}` reads
  the catalog, and `${media:<name>}/<path>` is the containment
  location, desugaring to `{"parent": "<name>", "path": …}` —
  the path suffix is the second component of one location, never
  string interpolation (property references take no suffix;
  other qualifiers reserved, fail closed). THE MEDIA LOCATOR:
  one shared parser (Spring-style dispatch) turns every accepted
  string into its typed object desugaring — locations,
  bare-string specs, `children` paths, `${…}` references — so
  shorthand intelligence lives in exactly one component. COMPOSITION DECLINED (fragment merge worked through and
  killed — it was a second personal-values mechanism in
  disguise): same-`(name, type)` canonically identical specs
  DEDUP (self-contained blueprints coexist); differing specs
  collide naming both; in-file duplicates always error. The
  supply seam is edit-your-seeded-copy (home) or a
  property-valued location (project/CI). THE CACHE: one
  name-keyed `cache/media/` (`cache/archives/` retires) with an
  IDENTITY LEDGER — recorded sha256, derivation keys
  `(parent-sha, path)`, provenance
  refetchable/derived/supplied, source lineage — giving a
  deterministic preflight identity check before any fetch,
  feeding the standing on-mismatch contract with
  lineage-informed messages (version bump vs cross-project
  collision distinguishable at a glance). CONTENT ADDRESSING
  RE-WEIGHED AND RE-DECLINED (the ledger closes the detection
  gap name-keying had; CAS stays the recorded escalation if
  collision friction proves real). Command family: `clean-media`
  (blunt; spares `supplied`; skips running-machine attachments),
  `clean-media <name>` (targeted eviction), `prune-media`
  (attachment-closure prune; scope-relative; `--dry-run`),
  `add-media <name> <file>` (the guarded door — a pinned
  unlocated media resolves by cache hit). WEIGHED AND DECLINED
  along the way: wrapper-key root discrimination (self-describing
  `type` travels with pasted fragments); document-scoped
  anonymous names (a middle scoping tier — anonymous means
  absent, not private); the `literal:` escape scheme (the object
  form escapes out-of-band); `file://` (bare paths carry relative
  resolution; RFC file: is absolute-only); union-of-channels via
  composition (a single author's mixed mirror list serves the
  case); child-side-only containment (dropping the batch
  `children` form — declined: sugar over the one semantic, not a
  rival spelling); the path glob in `children` (names must be
  static — the catalog can never depend on a download); the
  `property:` and `parent:` scheme spellings (superseded before
  landing by the universal `${…}` reference — `${key}` for
  properties, `${media:<name>}/<path>` for containment);
  mandatory root `type` (above).
  FOLDED: this entry;
  ROADMAP milestone 7 retargeted + the milestone-8
  property-binding deliverable; TASKS.md design/wishlist entries;
  blueprint-model.md banner marked superseded pending its
  milestone-7 rewrite (this entry is normative for the revised
  model until then).

- D21 — CODEX NAMING: A LAUNCHING POINT, NEVER A VERSION LIBRARY —
  DECIDED (owner, 2026-07-23, closing the open point from the
  generic-blueprint walkthrough): no versioned items in the
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

- D20 — THE DECLARED DERIVATION RANK (HOST-DERIVED DEFAULTS LANDED) —
  DECIDED (owner, 2026-07-23, same-day follow-up settling the
  forks the source-model governance entry below left pending;
  supersedes that entry's closed-@host-token sketch). The use
  case: a guest user created at install time defaults from the
  host — login name, descriptive full name — overridable by any
  explicit source. THE SHAPE: the chain's tail is DERIVATION →
  ASK. A declaration takes an optional `default=` beside
  `prompt=` (they compose — the prompt shows only when the
  derivation cannot answer): its value is a string in the
  EXISTING reference grammar — literal text, `${key}`
  references to other declared keys, and `rlq.*` SYSTEM
  FACTS — so the reserved namespace earns its keep and no new
  token syntax exists. NAMESPACE (owner): the canonical facts
  live under the short `rlq.*` — the name users type, brevity
  in interpolations — while `reliquary.*` stays reserved and
  empty, never an alias. "A script literally declaring
  default="paul" is just opting to stop at derivation" (owner).
  Derivations are not expressions: no transforms, no
  conditionals; cross-key references form a static dependency
  graph, cycles and references to undeclared non-system keys
  are static errors, system facts are leaves. A derivation
  answers when its references all bind (a literal always
  answers); an empty or unavailable fact makes it unanswerable
  and the key falls to the ask — noninteractively, the standing
  unanswered-key preflight failure. ALTERNATION (owner, via the
  fallback framing): `default=` may repeat — ordered
  candidates, the first that answers wins; the predicate is
  always availability (did every reference bind), never a value
  test — the mirror-list / first-source-that-answers house
  shape; a literal candidate anywhere but last is a static
  error (dead candidates below it); provenance names the
  winning candidate. THE ENV FACT FAMILY: rlq.env.<NAME> reads
  the named host environment variable, verbatim — the raw
  escape hatch beside the curated facts (the backend-settings
  precedent: host-specific by construction, visible on its
  face); platform case rules apply; unset or empty is
  unanswerable; ordinary text only — secrets keep their own
  channels; distinct in custody from the RELIQUARY_PROPERTY_*
  tier (the tier pushes at any declared key; the fact is
  pulled, by name, from a declaration). The curated fact stays
  preferred — rlq.host.username is the os-neutral value,
  rlq.env.USERNAME the always-there fallback (owner). SECRETS:
  no `default=` on a secret declaration, no secret key
  referenced in a derivation.
  PROVENANCE OVER PROHIBITION: check-script and transcripts
  name the derivation as supplying source like any tier; no
  hermetic ban — a project wanting determinism pins the key in
  its committed properties file. INITIAL FACT CATALOG:
  rlq.host.username (login name, login-safe normalization
  documented with the implementation), rlq.host.full-name
  (display name / GECOS; frequently empty — unanswerable by
  design). WEIGHED AND DECLINED: the closed @host token
  vocabulary (a second reference syntax duplicating `${}`);
  terminal exclusivity (prompt= XOR default= — proposed by the
  owner, reversed on second thought: derivation-then-ask
  degrades gracefully where a hard default-terminal failure
  served no one); transform pipelines in derivation syntax
  (normalization belongs in a fact's definition, arbitrary
  computation in the embedding API provider seam — the openQA
  conditional_schedule lesson at declaration scale); a bare
  top-level env.* fact namespace (unreserved — it would invade
  user space; every system fact stays under the one rlq.*
  root). PARKED:
  rlq.host.hostname; a raw unnormalized username fact;
  blueprint parameters redirecting to system facts (the
  designed-binding route). FOLDED: script-spec.md (Properties —
  the `default=` grammar; The property sources — rank 5, the
  declared derivation, ask renumbered 6), script-properties.md
  (order summary, the derivation bullet, the system-fact
  catalog, the binding short form, check-script's source list).

- D19 — PROPERTY SOURCE MODEL: THE ORDER IS CLOSED, THE SEAMS ARE
  NAMED; BESPOKE IMPLEMENTATION — DECIDED (owner, 2026-07-23,
  the source-model governance round). The owner probed the
  chain's extensibility — injectable custom providers, end-user
  control of the layer hierarchy — and the round adjudicated
  with the Spring lens (the owner's ten-plus Spring years:
  MutablePropertySources / EnvironmentPostProcessor reward
  vastly outweighed risk). The distinction that predicts
  outcomes is not fixed-vs-reorderable but CUSTODY AND
  INTROSPECTION: Spring's rank control lives in code, versioned
  with the application, its chain enumerable with per-key
  provenance (Actuator /env); PAM / nsswitch.conf put
  reordering in per-machine operator files with no provenance —
  that custody without introspection, not reordering itself, is
  the hazard class.

  THE GOVERNANCE RULE (the property chain's growth rule — the
  same shape as the blueprint computational-growth rule): the
  flattened order is semantics, never configuration, at the
  artifact/CLI surface. Three designed expansion routes: (1)
  NEW TIERS land by design decision at fixed ranks (the
  host-derived-defaults tier is the worked candidate —
  declaration `default=` with a closed @host token vocabulary,
  silent with recorded provenance, never on secrets — its forks
  pending their own round; nothing folded yet); (2) PROVIDER
  PLURALITY lives inside a tier behind a capability contract
  (the credential store is the precedent; a corporate-secrets
  provider joins there, invisible to the order); (3)
  PROGRAMMATIC INJECTION belongs to the embedding API — a
  future register_property_source(name, provider,
  before=/after=<rank>): custody in code, provenance mandatory
  (check-script and transcripts name the injected source like
  any built-in tier), protocol Reliquary-defined and FLAT under
  the INTERFACES binding rule — no third-party types in the
  public seam.

  PRIOR ART RECORDED (the order matches independent
  convergence): Spring PropertySource (same noun; a fixed
  documented precedence for file-side users plus programmatic
  mutability for code), Viper (explicit > flag > env > file >
  remote store > default — near-isomorphic, defaults tier
  included), .NET configuration providers (user-secrets ≈
  user.properties + credential store; the Key Vault provider ≈
  the provider route), pydantic-settings / Dynaconf; Ansible's
  twenty-two precedence levels as the accretion bound.

  WEIGHED AND DECLINED: pydantic-settings as implementation
  base (model-centric — fields fixed at class definition where
  Reliquary's keys are script-declared per run; typed coercion
  inapplicable — values are text by spec, declarations carry
  the type; env mangling and collision rules differ; the file
  tier is bespoke-load-bearing — surgical comment-preserving
  edits are why the line format exists; pydantic-core
  dependency weight and major-version churn; diagnostics need
  translation to the named-key house style; and the public
  provider protocol must be flat and Reliquary-shaped, so the
  library could only ever scaffold the internal for-loop);
  Dynaconf (global settings object, its own environment
  semantics, format zoo, a Vault loader that serves its layout,
  looser maintenance). REVISIT CONDITION: typed value coercion,
  multi-format settings files, or out-of-box Vault/Redis
  loaders as product features flip the math toward
  pydantic-settings, whose source protocol is good design to
  steal shapes from. EXTRACTION AS A STANDALONE LIBRARY
  DECLINED: the extractable resolution loop is commodity —
  several pip installs exist; the differentiators are entangled
  with Reliquary (the designed blueprint tier, the interactive
  ask tier, secret kinds bound to the credential store and the
  run engine's redaction contract); and the library market
  wants exactly the reorderable surface this rule closes. The
  exportable form, if ever wanted, is the written pattern, not
  code. FOLDED: script-properties.md (Property sources —
  "Growth: the order is closed, the seams are named"),
  script-spec.md (The property sources — closure note).

- D18 — BLUEPRINT FORMAT: JSONC AFFIRMED + THE COMPUTATIONAL-GROWTH
  RULE — DECIDED (owner, 2026-07-23, the format-review round).
  The owner re-opened "blueprints are authored source, not data —
  is JSON right?" and separately flagged computational/
  programmatic expansion as a likely growth area. Both resolved
  together: the JSONC choice STANDS, and the growth rule is
  recorded ahead of the growth so logic is never smuggled into
  the tree one convenient field at a time.

  A — THE FORMAT STANDS. The dichotomy that governs format
  choice is not authored-vs-machine-written but logic-bearing vs
  declarative, and the project already applies it consistently:
  scripts (sequencing, branching) got a purpose-built DSL; the
  user-properties file (machine-rewritten key=value) left JSON
  for the line format (recorded below); blueprints are logic-free
  declarative components — the profile where JSON's weaknesses
  are mildest and its payoff largest (the published schema's
  editor completion/validation, load-bearing for U4/U5 seeded
  customization; trivially emitted by import/init; parsed
  natively by every embedding language). JSONC's comments and
  trailing commas are the authored-source concessions, already
  in; the authored/machine asymmetry (JSONC for yours, strict
  canonical JSON for everything Reliquary writes) is the
  source-vs-data distinction, already built in. WEIGHED AND
  DECLINED: YAML (the format's values are its footgun shapes —
  sizes, hashes, bare names silently retyped unless quoted —
  plus whitespace-significant nesting on the recursive archive
  tree; the standing no-YAML call holds); TOML (recursive member
  trees are its pathological case; declined once already for
  nesting, the properties entry below); KDL (the aesthetic
  best fit, but it costs the entire tooling story — no
  editor-schema ecosystem comparable to JSON Schema, immature
  parsers in the embedding languages); HCL2 NOW (python-hcl2
  parses but does not evaluate — adopting the expression
  language today means writing an evaluator, paying immediately
  for capability at a scale not yet visible); A FULL LANGUAGE
  (Vagrant's Ruby Vagrantfile: unparseable outside its own
  runtime, unschemable, arbitrary execution at load — a choice
  its own vendor never repeated). Prior art read as the natural
  experiment: Packer's strict-JSON era failed on exactly two
  forces — no comments (JSONC already concedes) and wanted
  logic (deliberately excluded here) — before migrating to HCL2.

  B — THE COMPUTATIONAL-GROWTH RULE. Growth pressure is
  anticipated (the owner's read) at three seams: variant/matrix
  expansion (the localization composition seam at scale), member
  itemization (the parked extraction short-circuit), and derived
  values. The governing line: A CONSTRUCT THAT ENRICHES VALUES
  MAY LAND AS DATA; COMPUTATION THAT DECIDES STRUCTURE NEVER
  ENTERS THE TREE. Bounded, purpose-built declarative constructs
  (a member glob; possibly a variant matrix, the
  GitHub-Actions-matrix shape) may be added one at a time, each
  argued on its own, expanded by Reliquary, never author-side.
  General expressions — arithmetic, conditionals, string
  interpolation, user logic of any kind — trigger a LAYER
  SWITCH, never a tree extension, and both designated routes
  keep plain JSON as the substrate: GENERATION ABOVE (the
  embedding API is computation's designated home — the G2
  principle extended to the blueprint surface), or a
  JSON-SUPERSET EVALUATION LAYER producing the plain format
  (Jsonnet the leading candidate: JSONC is already valid
  Jsonnet, so every existing blueprint carries over
  byte-identical, and evaluation output feeds the existing
  schema/validation/resolution pipeline unchanged). PERMANENTLY
  REJECTED: in-tree function objects (the CloudFormation `Fn::`
  shape) and string templating (the Helm shape) — the two
  documented ways JSON formats die. FOLDED:
  machine-blueprint.md ("Format stability" — the growth rule),
  ROADMAP "Decisions still needed" (Blueprint computational
  constructs).

- D16 — BLUEPRINT `name` FIELD REINSTATED — DECIDED (owner, 2026-07-22),
  reversing the 2026-07-21 drop. `name` returns as an optional
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
  the three "Decide first" questions ROADMAP milestone 6 gated its
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
  FILES — DECIDED (owner, 2026-07-22). A new ROADMAP milestone 5
  lands Packer's ephemeral local HTTP server for Kickstart /
  preseed / AutoYaST / `unattend.xml` and kin
  (planning/design/http-serve.md). Former milestones 5–12 renumber
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
  planning/design/http-serve.md (new), TASKS forward refs,
  backend-adapter / guest-communication / landmarks status
  banners.

- D13 — PARSER: OWN LEXER + LARK PARSER — DECIDED (owner,
  2026-07-22), following the no-JSON-in-scripts round that made it
  possible. The grammar lives in Reliquary/script_grammar.lark,
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

- D12 — NO JSON IN SCRIPTS — DECIDED (owner, 2026-07-22): a script
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

- D11 — THE JULY 2026 SCRIPT-LANGUAGE REDESIGN — DECIDED;
  planning/design/script-spec.md is the source of truth (full typed
  EBNF included) and planning/design/script-examples/design-install.rlqs
  the reference script. Realigning the implementation is ROADMAP
  milestone 4, the arc's next work. The round records:
  - the redesign resolves the old "clunky/awkward" critiques: one node shape
    (name, args, name=value props, optional block), spelling-reveals-role tokens
    ("text", /regex/, @media-ref, $input-ref, bare internal names), no commas or
    colons anywhere, phase/goto/finish (was state/->/done), expect folded into
    the branching wait { on ... }, colon-free noun-first headers with entry and
    a run-level deadline, and screen-default observation channels (bare
    string/regex is the screen observation, its only spelling; machine=stopped
    the only machine-state spelling; console= later as a new channel,
    @landmark later as a new matcher spelling)
  - MILESTONE ZERO — DECIDED (owner, 2026-07-21), folded into the spec
    (see ./ROADMAP.md "Milestone zero — settle the surface"; evidence in
    workflow journals wf_ac5f89b4-402 / wf_1a266a6b-ff8):
    1. enter/key-tokens: (b) — <key> tokens DELETED, enter/press kept;
       keys live only after press, the \< escape is gone, enter stays a
       derived form (type + press enter)
    2. on's two lifecycles: (a) keyword split — `always` for reactive
       handlers, `on` only inside branching waits; a container mismatch
       is a validation error (lifetime readable from the first word)
    3. cyclic-deadline: ACCEPTED — header deadline required when the
       phase graph cycles; design-install.rlqs and the spec example now
       carry deadline 45m
    4. terminating details: BOTH — finish banned in linear scripts (EOF
       is the one ending); branching wait requires >=2 handlers
    5. bless-as-batch: APPLIED to the spec (insert/eject occupancy run
       errors; empty-pattern + regex-compile checks; fixed-string-regex
       warning; stage-source existence; input delivery contract;
       select's clocks named; prompt-echo note)
    6. sequencing rule: ADOPTED — the execution model (sample / episode /
       clock table) with the minimum run-events vocabulary is written
       into the spec before script_runner.py is retargeted
    - namings DECIDED: boot renamed set-boot; machine=running deferred
      (no waitable transition exists — the growth rule admits it later);
      undiverged header option deferred (divergence policy belongs to
      apply, never a script header); response files accept JSONC
    - NOT urgent, deliberately open: landmark namespace scoping, GUI asset
      format details (asset SHAPE settled 2026-07-21 by the wrinkle round;
      the .rlql JSON schema + similarity metric remain with the asset spec
      work), error-id index (beta), full spec document restructure
      (editorial, may trail realignment)
  - timing model: timeout/stable are lexically scoped defaults (innermost wins),
    deadline is a per-activation budget (fresh per phase entry; header deadline
    backstops the run); the placement matrix is enforced as parse errors
  - APPLIED (July 2026 spec review, adversarially adjudicated): one normative
    grammar (typed EBNF; node shape demoted to informative); terminating-
    statements model replacing the terminal production (the old grammar
    rejected the reference script); completed lexical rules (whitespace,
    name=/key+key adjacency, maximal munch, eol); honest LL(1) claim via the
    property-key lexical rule; string/regex productions defined; JSON island
    given a real production + nested-brace close rule; duplicate properties
    banned; branching-wait nesting banned in ALL handler bodies; raw strings
    DELETED; portable key vocabulary published as a closed set (esc only, no
    escape alias); slot vocabulary deduplicated to blueprint reference
  - DECIDED (owner, July 2026): image-match assets are "landmarks";
    Option B for observations — the screen is the unprefixed DEFAULT
    channel (bare string/regex/@landmark are its only spellings; screen=
    deleted from the language); non-default channels always prefixed
    (machine=stopped, future console=); growth rule: new channel = new
    observable surface, new value spelling = new matcher over the screen;
    @ namespace: media and landmark names share one collision-checked
    pool; landmark namespace scoping (flat vs per-platform) marked OPEN
  - remaining GUI detail from review, to spec with the landmark work:
    image-match assets named "landmark" (four-lens panel; cue is
    domain-fatal: .cue sheets beside disc images); matched via bare @ref
    under the amended growth rule "a new channel names a new observable
    surface; a new value spelling names a new matcher over an existing
    surface" (replaces the image= growth example, which named a matcher);
    click owns its search as an observation-bearing action (needs a timing-
    matrix row); store whole source screenshots with pinned dimensions/mode;
    variant invariants (identical spot sets, declared order, per-variant
    failure reporting); no count= (bare number), no read/OCR areas initially,
    drag deferred; landmarks live only in the catalog, never embedded —
    AMENDED (owner, 2026-07-21, the wrinkle round below): embedded
    landmark blocks resolve in place; the catalog remains the only
    shared/refresh form and Reliquary never rewrites a script
  - OWNER WRINKLE SMOOTHED — DECIDED (owner, 2026-07-21, design round;
    folded into ROADMAP "Landmarks" + "Authored-asset resolution" +
    "Cross-script reuse" + the GUI open decision, and USE-CASES U6):
    - per-region strictness: whole-screen exact match by default;
      regions are MODIFIERS only — `fuzzy` (explicit similarity=NN%,
      unit spelled, no implicit default) and `ignore`; selecting/
      confining regions deferred as additive growth (G7 — the safe
      failure asymmetry: over-match times out visibly, under-match
      would click the wrong screen); geometry (regions + named spots,
      pinned dimensions/mode) declared ONCE at landmark level,
      variants are renderings sharing it by construction — the
      identical-spot-sets invariant becomes structural; a layout
      change is a new landmark, never a variant
    - bundling: "never embedded" AMENDED — `landmark <name> {}` blocks
      are first-class script content (same schema as the catalog form,
      no second schema, + inline base64 variants) and RESOLVE IN
      PLACE: nothing installs, no files sprout (embedded media
      installs for consumers outside the script; landmarks have none);
      script-scoped, sharing uses the catalog form; refresh writes
      <name>.<n>.png beside the script, never rewriting it; duplicate
      names error, never coalesce. Catalog form: <name>.rlql (JSONC,
      FOURTH authored extension, same resolution rules, landmarks/
      optional dressing) + <name>.<n>.png numbered-adjacency variants,
      provenance in PNG text chunks (no sidecar files); recorder
      drafts self-contained by default, catalog form on request;
      block placement in a script (header zone vs trailing assets
      zone) left to the asset spec work
    - multi-file half: asset FACTORING through one asset root is
      already served by authored-asset resolution; the include
      question STAYS OPEN with the named desire recorded as evidence
      under ROADMAP "Cross-script reuse" (any future design preserves
      G2/G3 + transcript provenance; still gated on real scripts)
    - cursor stripping: the normalization contract — pointer verbs
      always end parked (fixed per-platform park position, never
      script surface; parking IS the strip for guest-composited
      cursors); park zone permanently masked from matching (region
      overlap = preflight warning); cursor-free framebuffer capture
      (RFB cursor pseudo-encoding) used where the control plane
      offers it; the recorder masks the known live-cursor
      neighborhood in proposed assets (generated-comment flagged);
      diagnostics exempt — explicit screenshot and failure
      screenshots capture unmodified reality (cursor-clean in script
      runs anyway: every pointer action already ended parked)
  - RUN FEEDBACK, DECIDED SHAPE (five designers, zero new syntax needed):
    one normative run-events.jsonl per run (append-only JSONL; seq/t/elapsed/
    kind; spans mirror the timing-scope tree: run=header deadline,
    phase#visit=phase activation, wait=observation timeout); every surface —
    live tty display, plain/CI output, transcript.txt, Python embedding API,
    rawjson — is a RENDERER of that stream (BuildKit --progress vocabulary);
    no denominators on phases/observations (systemd-style "elapsed / limit"
    text pair, never a bar); transfer events only where an honest total
    exists (media fetch bytes, stage/collect, select traversal); failure
    report includes route+revisits, expired clock + source scope, nearest-
    miss row, screenshot, and the suggested next command; use-case backing
    recorded (owner, 2026-07-21): the USE-CASES feedback split — human CLI
    sessions get pretty, timely progress, automated sessions get
    machine-readable output just as timely, two renderings of one run,
    neither scraped from the other — the renderer model's demand-side
    anchor
  - ASYNC RUNS, DECIDED SHAPE (owner, 2026-07-21, design round —
    ROADMAP "Asynchronous runs"; all three forks settled on the
    recommendations):
    - the stream is written LIVE — append + flush per event, first
      preflight event to a terminal event stating the outcome; writer
      death without one = crashed run; the live-write clause and run
      identity are now NORMATIVE in script-spec.md "Failure, runs, and
      transcripts" (run dir renamed runs/<n>/, was <timestamp>-<run_id>)
    - sync script = start + attach (one code path; Ctrl-C on a
      foreground run cancels the run, Ctrl-C on a reattach only stops
      tailing); script --detach preflights in the foreground (G3,
      failures on the invoker's exit code) then hands off at the
      machine boundary and prints the run id
    - the detached runner is an owned child under the vm.json identity
      doctrine: writer pid + start time in the run record, identity
      verified before any command targets the run, stale records fail
      closed
    - run cancel ends at an event boundary (severability per the
      execution model), machine left as-is (no implicit teardown),
      --stop opts into power-off; exit code 5 = cancelled (spec
      error-classes updated; neither success nor RUN FAILURE 4)
    - run identity machine-scoped: monotonic per machine, never
      reused, <machine-id>/<n>; run ops take the number positionally,
      defaulting to latest, machine via the ordinary selectors
    - CLI: script --detach + run (status|tail|wait|cancel) + list
      runs; API: run_script stays blocking, start_script returns the
      pull-only handle (status / events iterator / wait / cancel) +
      attach by id — no callbacks (the C/Java binding constraint)
    - SYNC PROGRAMMATIC (owner, 2026-07-21, follow-up round): the
      CLI/API divergence is BLESSED as a named decision, not drift —
      run_script returns a typed result / raises by class, the
      foreground script command speaks stream + exit code; --progress
      (auto|tty|plain|rawjson) on script and run tail (the decided
      BuildKit vocabulary); rawjson stdout is pure event JSON, last
      line = terminal event = the result (no separate result mode);
      plain/rawjson are noninteractive — prompting needs a tty under
      auto/tty, missing values fail preflight (spec inputs section
      updated, cli.md updated)
    - implementation at the run-records milestone, behind the
      realignment like everything else (script_runner.py still writes
      the superseded runs/<timestamp>-<run_id>/ layout until then)
  - SPEC-CRAFT QUEUE, FULLY ADJUDICATED (18 of 24 proposals survive, each
    with a refined right-sized form recorded in the review output —
    workflow wf_ac5f89b4-402 journal):
    - execution model: LANDED in the spec (owner-adjudicated,
      2026-07-21) — sample / condition-holds-at-a-sample / episode
      defined, dispatch and stable restated over them, the five-clock
      table, and the minimum run-events vocabulary designed in.
      Decisions: severability follows the guest seam (input delivery
      atomic, host transfers abort at deadline); sampling guarantees
      are freshness + at-least-one, cadence deliberately unspecified;
      a fired handler re-arms only after an OBSERVED non-holding
      sample (episodes exist over dispatch samples only)
    - SPEC-CRAFT REORG LANDED (2026-07-21): §Processing model with the
      three enforcement tiers (legality / machine rules / dynamic
      semantics) and check-script's two modes defined in tier terms;
      §Error classes and exit codes (STATIC ERROR 2 / PREFLIGHT ERROR 3
      / RUN FAILURE 4, 0 success, 1 reserved — exit-code values are the
      agent's proposal, veto cheap; dotted id namespace obs.two-channels
      style, id INDEX deferred to beta; static-conformance fixture
      corpus queued to the parser retarget); §Derived forms over parsed
      nodes (enter => type + press enter; bare condition => screen
      channel; linear script => implicit entry phase + EOF => finish —
      the recorded press=>key-tokens rewrite was voided by milestone
      zero's token deletion; desugaring is definitional, diagnostics
      name the authored surface); §Syntactic restrictions S1-S14
      merging the context-sensitive list with the static half of the
      validation list, preflight list rewritten per tier naming what it
      needed; signature tables marked informative, the example marked
      non-normative; G-citations threaded at load-bearing spots;
      run_script / check_script named as the API parity twins. The full
      Reason-blockquote editorial sweep remains deliberately open (may
      trail realignment)
    - killed by adjudication (do not revisit without new evidence): ISO
      terms clause, five-subheading per-construct template, four-table
      vocabulary appendix, separate image= channel restructure,
      conformance-files-as-spec-content, paragraph numbering
  - AHK/Python failure catalogs captured (studies complete; spec audits hit
    session limit — resume workflow wf_1a266a6b-ff8 after reset); sharpest
    imports: container-determined semantics rule (hits [04] — a construct's
    lifetime should be recoverable from its own text), reserve future
    keyword space now, naming freeze is free before v1 and never after
- D10 — GUIDING-PRINCIPLES GAP QUEUE (planning/INTERFACES.md necessity/sufficiency panel,
  adversarially walked per use case; evidence in workflow journal
  wf_92864b8e-623) — verdict: the five primary interfaces are necessary and
  minimal; every gap below is a spec lagging the principles, and this queue
  is the realignment pass's work list:
  - CLI programmatic contract (U3 via CLI; the whole unbound-language path
    rests on it): exit codes, stdout/stderr discipline, output stability, a
    machine-readable mode — error classes + exit codes are now homed in
    script-spec.md "Error classes and exit codes" and the run-events
    minimum in its execution model (2026-07-21); --progress renderer
    selection, rawjson stdout purity (pure event JSON, terminal event =
    the result), and the plain/rawjson no-prompt rule are settled for
    the stream-bearing commands (2026-07-21, ROADMAP "Asynchronous
    runs") — now script, run tail, AND fetch, with the implicit-fetch
    phases of bare machine ops rendering the same events (2026-07-21,
    blueprint-spec queue item 3); query output is homed (2026-07-21,
    CLI queue item 4: global --json prints the API twin's return as
    one JSON document — the twin's-return rule); the discipline and
    stability halves CLOSED (2026-07-22, gap-closure queue item 1:
    the result-is-stdout doctrine + the four contract surfaces) —
    every half of this entry is now homed
    (the machine-readable mode is now demanded directly by the USE-CASES
    feedback split, 2026-07-21);
    the interaction command family is now IN the settled CLI list
    (2026-07-21, CLI DESIGN GAP QUEUE items 1-3: the script
    language's vocabulary — type/enter/press/select/wait/screenshot
    — plus CLI-only screen and exec, and the insert/eject/set-boot
    state ops); the query-output half remains open as CLI queue
    item 4
  - U2 import: RESOLVED (owner, 2026-07-21, design round — see the
    blueprint-spec queue item 2): import never copies; captured disks
    stay in place as local-path definitions, and the presented choice
    is materialization — --hdd-images (duplicate | difference)
    selecting base.type, prompted on a tty, required
    noninteractively; U2 amended to match
  - U3 run records: only `script` invocations produce a run record — a
    programmatic API/CLI-primitives loop leaves nothing, yet U3 says the
    run record is the product; align with the decided run-events.jsonl
    normative-stream model (every surface a renderer of it) — the
    minimum vocabulary is now normative in script-spec.md's execution
    model (2026-07-21); async consumption settled (2026-07-21, ROADMAP
    "Asynchronous runs": live-write, script --detach, the run family,
    start_script/attach handles); record durability/custody settled
    (2026-07-21, blueprint-spec queue item 1: machine-bounded
    retention, run delete, copy-out survival);
    remaining halves CLOSED (2026-07-22, gap-closure queue item 2:
    interaction runs — the begin-run/end-run opt-in bracket — give
    primitive loops the same records; transcript.txt respecified a
    pure renderer of the stream; per-test results = properties in,
    collected caller artifacts out, no test vocabulary — G2; the
    collected-artifacts half later superseded by the run-collection
    drop, 2026-07-22 below — artifacts are read out-of-band, records
    carry no output/); the
    unit-test loop is now IN U3 itself (amended 2026-07-21: the
    canonical journey uses Reliquary twice — define and build the test
    VM, then automate testing inside it; detailed per-test results,
    update a test object, re-run one test or the whole suite; granular
    results and selective re-run are first-class demands) — so the
    run-records design serves a primary use case directly: per-run
    test selection is property data (inputs-as-data holds), and the
    iterate loop needs per-iteration run records plus collected
    results the automator can parse
  - U3 stage/collect: the "declared exchange drive" cannot be declared —
    CLOSED (2026-07-22, gap-closure queue item 3): the results
    directory is a script-declared drive-key+path (coupled to the
    instruction stream, never a blueprint item) reached by the
    adapter's at-rest access with record custody; the CLI gains
    stage-files/collect-files; and hostdir joins the drive
    vocabulary as the writable vvfat-served fourth content source
    — then SUPERSEDED IN PART (owner, 2026-07-22, the run-collection
    drop below): the file-exchange half (results directory,
    stage/collect, stage-files/collect-files, record custody) is
    dropped; the hostdir half stands
  - U5 blueprint parameterization — CLOSED (2026-07-22, gap-closure
    queue item 5): the design below was recorded 2026-07-21 with
    owner adjudication pending, then overtaken and fully adjudicated
    by the property-construct rounds — every element survived into
    the settled shape or was superseded by an owner decision (the
    closure trace is in the queue item). Recorded design was:
    blueprint `parameters` field (direct value |
    {"property": ...} reference; binding order response > blueprint >
    input property= > prompt; a reference REPLACES the input's own
    property= binding, never chains; secret inputs never take direct
    values — U4; read at invocation like the scripts map, no
    state/apply/digest involvement) plus the seam doctrine: value
    seams = parameters, locale-class customization = composition seam
    (the blueprint selects the media/script pair; the watch-condition
    ban stands, G2/G3). Landed: machine-blueprint-reference.md
    #parameters, machine-blueprint.md #customization-seams, cookbook
    #9, script-spec.md inputs + validation + check-script, ROADMAP
    (blueprint fields, inputs paragraph, literal-defaults open
    decision resolved). Original gap text: no parameter field, no
    seam vocabulary, no channel by which a blueprint-held value
    reaches a script; inputs cannot parameterize watch conditions, so
    a value seam never covers a different-language installer UI
  - U1 export journey: CLOSED (2026-07-22, gap-closure queue item
    4): export-drive/export-machine with exporters decoupled from
    backends — install on QEMU, export-machine --to virtualbox; the
    invented QEMU artifact is deleted (libvirt is that ecosystem's
    answer), and cross-backend rides the blueprint shape plus the
    adapters' raw interchange
  - ARTIFACT RESIDENCY (use-case amendment 2026-07-21, the split in
    USE-CASES.md; resolution model DECIDED owner 2026-07-21, recorded
    in ./ROADMAP.md "Authored-asset resolution"): every invocation
    names where authored assets live — the asset root — defaulting to
    the current directory (blueprints/ media/ scripts/ subdirs, the
    home's own layout), falling back to the Reliquary home unless an
    explicit no-home option disables it. Automation runs with the
    fallback OFF: strictly project-scoped resolution, so neither home
    assets nor the codex behind them can reach the run
    (answers the former open question — home exclusion is the
    opt-out, not automatic). The codex remains NEVER a
    resolution tier for automation; at most copied from, the copy
    committed. DETAILS DECIDED (owner, 2026-07-21) and folded:
    --assets <dir> + --assets-only (API assets= / assets_only=,
    global, under parity); root shadows home (identical descriptors
    coalesce, within-root duplicates stay errors, provenance in run
    records); machine state records the blueprint's absolute source
    path (state-only blueprint-source) and --blueprint selection is
    scoped to the invocation's resolution — apply can never adopt
    another project's same-named blueprint; embedded blocks install
    into the resolving root's media/ (idempotent by identity —
    commit once, CI trees stay clean); U6 drafts emit into the
    session's asset root. Folded into ROADMAP "Authored-asset
    resolution" + "The CLI", media-spec, script-spec, blueprint
    guide + reference (blueprint-source), instance-model. EXTENSIONS
    DECIDED (owner, 2026-07-21): blueprints are *.rlqb, media
    definitions *.rlqm (scripts *.rlqs) — assets identified by
    extension, discovery walks the root, subdirs are optional
    organizational dressing (home convention included); within-root
    same-kind stem collisions are errors; Reliquary reads by
    extension and writes by convention (home media/ for home-resolved
    installs, beside the script in a project); folded across the same
    docs plus cli.md, builtin-library, README, CLAUDE.md, examples.
    Remaining:
    implementation only (resolution module, extension rename plus the
    builtins/ → codex/ package-dir rename and the codex index, state
    field, selection scoping,
    install targeting), at the residency milestone
  - ARTIFACT RESIDENCY — REDESIGNED AT IMPLEMENTATION (owner, milestone-6
    T6, 2026-07-22, superseding the 2026-07-21 shadow/fallback model
    above): building the resolution module surfaced a simpler, safer
    shape and it was adopted through the interface-change rule (strong
    alignment with the U3/U4 automation-hermeticity use cases — an easy
    approval). Changes from the 2026-07-21 record:
    - ONE flag, `--assets` (API `assets=`); `--assets-only` /
      `assets_only=` are DROPPED. The knob is single-tier: naming a root
      makes it the SOLE source. Root REPLACES home — the shadow/coalesce
      and the root→home fallback are gone (a project that references an
      asset only in the home no longer resolves it; hermetic by
      construction).
    - Two modes. HOME MODE (the CLI default, no `--assets`): resolve from
      the home's canonical `blueprints/` / `media/` / `scripts/` folders,
      seeding missing names from the codex — a human-CLI convenience.
      DIR MODE (`--assets <dir>`, and every API call): walk that dir
      recursively by extension as the sole source, no home, no codex, no
      seeding. list/search follow the same split (canonical folders vs
      recursive walk).
    - The embedding API has NO default source: a bare call that resolves
      a name with nothing configured fails closed ("no asset source
      configured"), so automation can never silently pick up user (home)
      assets or a stray CWD. CWD is NOT an asset default anywhere (the
      2026-07-21 "defaults to the current directory" is dropped — CWD is
      arbitrary for a programmatic agent). Home mode is reachable only via
      the explicit `HOME_ASSETS` marker (`set_assets`, `Context(assets=…)`),
      which the CLI sets by default; it is never the API default.
    - Asset identity is the file's `name` field when declared, else its
      filename stem; two files of one kind resolving to one effective name
      is an error (the conflict guard). This makes blueprint `name` the
      id-safe IDENTITY (selection key / machine-id segment), REVERSING the
      2026-07-22 "name is a display name" reinstatement — human prose lives
      in `description`. Media items already self-identify by their `name`s;
      scripts carry no `name` and stay stem-identified. The codex FreeDOS
      blueprint dropped its spaces-bearing `name` (falls back to the stem).
    - Resolution flows through an asset-source seam (HomeSource / DirSource).
      A third source — OBJECTSOURCE, JSON-imported objects supplied by an
      embedding caller with no files at all, self-identifying by `name` —
      is the settled fast-follow (its own SC after T6): the API source is
      polymorphic (a dir, or a set of objects). Scripts, lacking a `name`,
      would be a name→source map under ObjectSource — a detail for that SC.
    - Two design threads SHORTLISTED (TASKS.md "Design"): media definitions
      are now residency-scoped but payloads still cache home-side by item
      name (cross-project collision / hermeticity tension); and whether the
      machine hardware spec, a machine's media usage, and media
      locators/archives are separable fragments composable under one
      blueprint schema.
    - Folded: ROADMAP "Authored-asset resolution" + "The CLI", AGENTS.md,
      cli.md, api.md, instance-model, machine-blueprint-reference, README,
      docs (cli-/api-reference, blueprint-guide), CHANGELOG. Blueprint-source
      selection scoping (state field from T2) landed as specified.
  - RESOLVED (July 2026): hand-placed proprietary payloads vs the "cache is
    not an interface" doctrine — local-path (item- or archive-level) is now
    the only hand-supply path; the cache is never hand-fed; a sourceless
    definition pins hashes but fails resolution naming the definition to
    edit (specced in media-spec.md + codex.md)
- D9 — BLUEPRINT-SPEC GAP QUEUE (owner-requested review, 2026-07-21: the media
  and blueprint specs walked against planning/INTERFACES.md / planning/USE-CASES.md; the
  media spec tracks the principles closely — the gaps cluster in the
  blueprint spec: machine-blueprint.md + -reference.md + -cookbook.md):
  1. RESOLVED (owner, 2026-07-21, design round) — run records vs
     disposability, settled as the CUSTODY MODEL: disposable and
     reconstructible are distinct properties — everything under cache/
     is disposable, run records are the named exception to
     reconstructible (evidence, never regenerable); retention is part
     of the recorded-outputs contract (append-only, never rewritten,
     never implicitly pruned, machine-bounded: destroy/recreate and
     the explicit `run delete` are the only deleters — a run-family
     verb, NOT clean, whose own invariant is nothing-irreplaceable-
     is-cleanable; run delete takes explicit numbers, never defaults
     to latest, refuses live runs, frees no number; API twin
     delete_run under parity); survival is the custody handoff —
     contents are delivered live (the feedback split), the record
     directory is self-contained/self-identifying (stands alone
     across recreate id reuse), copying it out is the sanctioned
     path, deliberately no export verb (named decision). Folded:
     USE-CASES residency split, INTERFACES recorded outputs,
     script-spec "Failure, runs, and transcripts" (contract home),
     blueprint guide (ownership prose + tree gains runs/ — the tree
     half of item 6), ROADMAP (both layout claims + "Asynchronous
     runs" retention paragraph + run delete in the family),
     instance-model, cli.md
  2. RESOLVED (owner, 2026-07-21, design round) — U2 import
     disk-location choice, settled by REFRAMING THE CHOICE: import
     never copies — every captured disk stays in place, its generated
     definition an absolute local-path at the native file (computed
     hash, no URL); relocating an image is the user's own copy/move
     plus a definition edit (the definition is theirs). The presented
     choice is materialization: --hdd-images (duplicate | difference)
     selects the generated drives' base.type, spelled explicitly in
     the blueprint — prompt with the tradeoff on a tty, error when
     absent noninteractively, never defaulted; API twin hdd_images=
     required under parity (named --hdd-images, owner: hdd is the
     blueprint's own medium token, and the choice covers the hard
     disks that become base drives, not captured floppy/CD media).
     Snapshot targeting (point the definition
     at a named native snapshot in the disk chain) recorded as an
     open import-scope question in ROADMAP. U2 amended to match (the
     disk stays put; the decision point is duplicate-vs-difference).
     Open wrinkle noted, not decided: whether per-start media
     verification covers a materialized drive's base that is no
     longer needed (a duplicate machine's) — reconciliation step 2's
     "every media item the state references" is ambiguous there.
     Folded: USE-CASES U2, blueprint guide import, ROADMAP import
     bullet + CLI grammar + import-scope open question, cli.md
     import section, media-spec local-path cross-link;
     guiding-principles queue U2 entry closed.
     FOLLOW-UP ROUND (owner, 2026-07-21): import reads only a source
     at rest — running or suspended sources fail closed naming the VM
     and its state (powered off only: a saved VM's disk is mid-flight
     guest state — the ill-defined machine again), state per backend
     reporting with image-lock detection the bare-image fallback; and
     import modifies the source VM only with consent — the --snapshot
     / --no-snapshot pair (prompted on a tty, required
     noninteractively, API snapshot= required under parity):
     snapshot pins the definitions to the frozen extent and leaves
     the source VM free to keep running natively (Reliquary-named
     snapshot, provenance in the generated definitions' notes, its
     later fate the user's — verification reports a lost extent);
     no-snapshot touches nothing but running the source again breaks
     verification until re-import. Never-modifies became
     never-modifies-unasked, scoped to the VM's snapshot chain — the
     captured images themselves are still never copied, moved, or
     modified. Folded into the same documents; disks that are
     already snapshot chains remain with the open import-scope
     question
  3. RESOLVED (owner, 2026-07-21, design round) — the feedback split
     now reaches media fetching, with no new machinery: one event
     vocabulary, every surface a renderer. Media movement (download,
     extraction, verification) emits the run-event stream's
     transfer/verification event kinds wherever it happens: inside a
     script run it rides the run's stream (already decided);
     standalone fetch renders it itself — --progress
     (auto|tty|plain|rawjson) with script's exact semantics, rawjson
     stdout purity, terminal event = the result; the implicit-fetch
     phases of bare machine ops (create/start/apply/recreate
     reconciliation) render the same events under the same defaults,
     their full output contract staying with the general
     CLI-discipline work. The fetch stream is EPHEMERAL: media has
     no state document, there is no fetch record, nothing
     reattaches — run records remain the only recorded outputs.
     Honesty rules carry over (byte totals only where the source
     names them; hashing/extraction elapsed-only; each mirror
     attempt its own event); plain/rawjson never prompt — the
     mismatched-file checkpoint maps to "prompt" under auto/tty and
     fails fast otherwise. API (owner chose build-now over defer):
     fetch_media() stays blocking (typed result, errors by class);
     start_fetch() returns a pull-only handle — status() /
     events(follow=) / wait(timeout=) / cancel() (event-boundary
     abort, partial download deleted) — process-local, no
     attach-by-id (reattachment is what run records provide), and
     rejects on_mismatch="prompt". Folded: media-spec (#fetch-
     progress + API twins), cli.md fetch, ROADMAP "Asynchronous
     runs" (fetch joins the stream-bearing commands + the settled
     fetch-progress paragraph); guiding-principles CLI-contract
     entry updated
  4. RESOLVED (owner, 2026-07-21, design round) — the lifecycle twins
     are named: flat verb-noun functions completing the
     fetch_media/run_script family — create_machine, start_machine,
     stop_machine, apply_blueprint, destroy_machine,
     recreate_machine, clone_machine, delete_blueprint, import_vm (a
     bare import is a Python keyword) — taking the CLI's selectors
     (machine id or blueprint/number pair; resolve_machine() the
     shared resolution seam) and the mirrored globals
     (home=/assets=/assets_only=), returning what the CLI prints
     (create_machine/clone_machine return the new id), raising by
     class where the CLI exits by code; export's twin is a NAMED
     omission — it lands with export's still-open CLI shape. Folded:
     blueprint guide (verb table gains an API-twin column +
     conventions paragraph; import passage names import_vm), ROADMAP
     ("The CLI" twins paragraph; import bullet names import_vm),
     cli.md (Machines-section parity note — and its stale
     everything-regenerates claim corrected to item 1's doctrine in
     passing). Implementation realignment: rename
     create_from_blueprint → create_machine and the package surface
     machines.start/stop/destroy → start_machine / stop_machine /
     destroy_machine; lifecycle.py's legacy start_machine(config)
     name collision dies with the root-home model. FOLLOW-UP (owner,
     2026-07-21): the API now has its own documents — the design is
     consolidated in planning/design/api.md (principles, conventions,
     the CLI↔API surface index, the two handles, realignment
     renames) and the implemented binding is documented in
     docs/api-reference.md; INTERFACES' embedding-API section and
     spec-homes row point at both, AGENTS "The runner surface"
     narrows to the engineering contract, README links the reference
  QUEUE COMPLETE (2026-07-21): all nine items resolved — items 1-4
  above; items 5-9 were editorial sweeps, fully landed and not
  retained here (git history keeps their records)
- D8 — CLI DESIGN GAP QUEUE (owner-requested review, 2026-07-21: the complete
  CLI design — cli.md + ROADMAP "The CLI" + api.md's parity table —
  walked against planning/INTERFACES.md / planning/USE-CASES.md and
  modern CLI practice; verdict: the two-layer lifecycle vocabulary, the
  parity doctrine, the selection failure modes, run-record custody,
  import's consent points, and the no-prompt/--detach discipline are
  sound — the gaps cluster in vocabulary collisions, cross-surface
  naming drift, and the machine-readable query contract):
  1. RESOLVED (owner, 2026-07-21, design round — all six forks on
     the recommendations): the `run` collision dissolves through
     item 2's alignment — guest execution renames to
     `exec <command> [--timeout]`, the composite convenience
     (`enter` + the platform workflow's completion detection,
     which scripts spell as explicit observation; a CLI/API
     capability above the language, not a language concept) — and
     `run` names run records exclusively. The settled run family
     stays as decided (rename-to-`runs` weighed and declined: no
     remaining problem argues for reopening the async round)
  2. RESOLVED (owner, 2026-07-21, same round): the CLI interaction
     family adopts the script language's vocabulary verbatim, each
     verb defined once in script-spec.md and referenced, never
     redefined, by the CLI — `type` raw (implicit Enter dropped),
     `enter` added, `keys` → `press` (the closed portable key set,
     `+` chords), `menu` → `select`, `wait` adopts the condition
     grammar ("..." normalized literal / /.../ regex /
     machine=stopped) and normalized matching, and `text` →
     `screen`, the CLI-only read of the language's default
     observation channel. API twins DEFERRED with precedent
     (export/property) to the control-plane design — a named
     omission in api.md; the capability stays reachable through
     today's Machine functions until then. Folded: cli.md
     (Interaction section rewritten + Global options verb list),
     ROADMAP "The CLI" (synopsis gains the interaction family —
     and the settled `run delete` line it was missing — plus the
     settled-vocabulary paragraph), api.md interaction row;
     docs/cli-reference.md follows at implementation realignment
  3. RESOLVED (owner, 2026-07-21, same round, the rider):
     `insert <slot> <media>`, `eject <slot>`, and
     `set-boot <key>...` join the CLI design with the script
     verbs' spellings and rules by reference — removable slots
     only and running-or-stopped for insert/eject (occupancy is a
     run error, a missing/non-removable slot fails preflight),
     stopped-only ordered drive keys for set-boot,
     state-not-blueprint persistence with `apply` the
     reconciliation. One named divergence: the CLI's media
     argument is a bare name — `@` marks references only inside
     script text. stage/collect stay out: their exchange-drive
     model remains the guiding-principles U3 gap
  4. RESOLVED (owner, 2026-07-21, design round — all three forks
     on the recommendations): machine-readable query output is
     `--json`, a global flag, defined by parity rather than
     enumeration — under `--json` a command prints exactly what
     its API twin returns, serialized as one JSON document
     (object, array, or scalar) on stdout, nothing else there,
     diagnostics on stderr, exit codes unchanged: the twin's
     return contract IS the command's --json contract, so the
     two presentations cannot drift and future commands are
     covered by definition. Void twins print {} on success (a
     program passes --json unconditionally); stream-bearing
     commands (script, run tail, fetch) reject it naming
     --progress rawjson (document flag vs stream flag, one
     meaning each); secrets serialize as their marker, never
     their value; --verbose stays pretty-only. --format weighed
     and declined (YAGNI — a pre-beta conversion stays free if a
     second format ever earns its way in). Field names land with
     each twin's return contract; the output-stability promise
     stays with the general programmatic-contract work. Folded:
     cli.md (global synopsis + the Machine-readable output
     section), ROADMAP "The CLI" (globals sentence + settled
     paragraph), api.md (returns-mirror convention closed into
     the rule; sync-divergence bullet), guiding-principles
     CLI-contract entry
  5. RESOLVED (owner, 2026-07-21, batch round; folded with item
     14): codex extraction renames `pull` → `seed` — the
     doctrine's own word (seed-not-a-resolution-tier, the `seeded`
     provenance column, the implemented library.seed_blueprint),
     killing the git false-friend (git/docker pull = network
     acquisition; ours was local extraction while `fetch`
     downloads). API twins named under parity: seed_blueprint(name,
     only=) / seed_media / seed_script — the family was absent from
     api.md's table entirely. Item 14's dash rule spells the
     commands seed-blueprint / seed-media / seed-script; landed
     in 14's fold
  6. RESOLVED (owner, 2026-07-21, batch round; folded with item
     14): the scaffolder renames `create blueprint` →
     `new blueprint` (cargo/dotnet/rails-new precedent; `create`
     becomes machine-lifecycle vocabulary only; twin
     new_blueprint()), and import's destination flag renames
     `--blueprint` → `--name` (mirrors as name= in every binding
     language — `--as` declined, as= is a Python keyword; the
     import→import_vm precedent designs keyword collisions away),
     making --blueprint selector-only everywhere. Under item 14
     these spell new-blueprint and import-vm --name
  7. RESOLVED (owner, 2026-07-21, batch round; folded with item
     14): `check-script <name>` becomes the check family
     with `script`'s label resolution — with a --blueprint/
     --machine selector the argument resolves label-first then
     bare name, exactly as `script`; without one, bare script name
     only. Twin check_script() unchanged; a future check
     blueprint/media validation family stays open. (The batch
     chose the spelling `check script`; item 14's dash rule
     respells it check-script — the original hyphen, now derived
     from the twin's name rather than an outlier)
  8. RESOLVED (owner, 2026-07-21 — auto-detect on the
     recommendation): `set-property <key> --secret` uses the
     house tty-detection pattern — a no-echo prompt on a tty,
     otherwise the value is read from stdin (to EOF, one trailing
     newline stripped, empty is an error), so
     `echo $key | rlq set-property k --secret` is the
     programmatic path and the CLI stays a complete binding;
     never an argv value (process listings, shell history). The
     explicit --stdin flag and the hybrid were weighed and
     declined (one spelling, zero new surface; the forgot-to-pipe
     block is standard Unix stdin behavior). Folded:
     property-registry.md "Maintaining properties" (the
     fails-with-guidance clause replaced), cli.md Properties,
     ROADMAP (property bullet + milestone 4 deliverable 2)
  9. RESOLVED (owner, 2026-07-21, follow-up round — id-only on
     the recommendation): `--machine` takes the full machine id,
     exactly; prefix matching AND the bare-number pair form
     (`-b NAME -m N`) are deleted, closing the freedos-1
     ambiguity structurally — nothing is left to disambiguate.
     The id is the (blueprint, number) pair composed, so each
     selector carries one honest type and the mirror is clean:
     resolve_machine(machine=, blueprint=), no stringly union
     reaching any binding (the suffix trio
     --blueprint-name/--machine-number/--machine-id was weighed
     and declined: deletion beat addition — the decomposed form
     was redundant with the id, and blueprint/machine need no
     disambiguating suffixes once each has a single referent).
     Folded: cli.md (Selection bullets, create-machine prose,
     Selection rules — pair examples and the ambiguous-prefix
     block deleted, error text names --machine <id>),
     ROADMAP (machine-model selection sentence + "The CLI"
     selection paragraph), api.md Selectors convention,
     instance-model, machine-blueprint guide
  10. RESOLVED (owner, 2026-07-21, by item 14's flag-position
      fork): flags may appear before or after the command word,
      uniformly — position carries no meaning, the north star's
      two spellings are identical, synopses canonically show
      flags after the command; the cli.py SUPPRESS workaround
      retires at implementation realignment
  11. RESOLVED (owner, 2026-07-21 — rename both, on the
      recommendation; a settled spelling knowingly reopened
      pre-implementation): the progress modes are
      `--progress (auto | pretty | plain | jsonl)` — `jsonl`
      names the JSON-Lines stream honestly (and self-distinguishes
      from the `--json` single-document flag), `pretty` names the
      forced live rendering by what it emits rather than the tty
      whose absence is the reason to force it. Folded: cli.md,
      ROADMAP "Asynchronous runs" + --json paragraph, media-spec
      #fetch-progress, script-spec noninteractive clauses
      (historical decision records in TASKS keep the old names)
  13. RESOLVED (owner, 2026-07-21, one sweep): `--timeout`
      accepts the language's duration literals (500ms/30s/20m;
      bare integer = seconds; API twins keep numeric seconds — a
      named presentation divergence); `fetch-media`'s
      <media_name> is always required, exactly the twin
      fetch_media(name, script=) — --script supplies definitions,
      never selects what to fetch (the no-name example was the
      error; fetch-all-for-a-script stays possible future
      growth); `export --drive` requires <destination>, nothing
      guessed, whole-machine export defaulting to the backend's
      native location (the rest of export stays open); `hmp`'s
      backend-scoped rehoming was already recorded at items 1-3
      (pending the control-plane design); the media noun overload
      is NAMED, not renamed — `clean-` names the cache directory
      it reclaims, never an artifact class (the settled
      clean_media twin and the clean-<cache-dir> symmetry both
      kept; rename weighed and declined)
  QUEUE COMPLETE (2026-07-21): all fourteen items resolved — 1-3
  (interaction vocabulary), 4 (--json), 5-7 (seed / new-blueprint /
  import-vm --name / check-script), 8 (secret stdin), 9 (id-only
  selectors), 10 (uniform flag position), 11 (progress-mode
  names), 12 (staleness), 13 (the underspecification sweep), 14
  (the twin-name identity rule). Implementation follows at the
  realignment milestone; docs/ and README follow with it
  14. TWIN-NAME IDENTITY — RESOLVED (owner, 2026-07-21; agreed in
      principle, then the design round settled both remaining
      forks on the recommendations and the fold landed): a CLI
      command IS its API twin's name, dash-separated where the
      twin has underscores, and its --flags mirror the function's
      parameters — what the surface pays in succinctness it reaps
      in cohesiveness, and the parity invariant becomes
      self-enforcing (naming the twin names the command; drift
      becomes impossible; several queue items above — 1, 6a — were
      hand-fixed instances of what this rule prevents by
      construction). The identity is already ~80% latent
      (delete blueprint ↔ delete_blueprint, check_script,
      list_machines, clean_downloads, seed_blueprint,
      new_blueprint); the rule completes it: create-machine,
      start-machine, stop-machine, apply-blueprint,
      destroy-machine, recreate-machine, clone-machine,
      delete-blueprint, import-vm, run-script, check-script,
      fetch-media, clean-downloads, clean-media, list-machines,
      list-blueprints, search-media, seed-blueprint... — and the
      property noun-first outlier dies (get-property,
      set-property, unset-property, list-properties, twins named
      in the same act, closing api.md's pending row). TWO NAMED
      EXCEPTIONS, each an identity with a different home surface:
      the interaction family (type/enter/press/select/wait/screen/
      screenshot/exec) keeps identity with the SCRIPT LANGUAGE —
      its home surface, settled at items 1-3 — and its deferred
      API twins adopt the script names when the control-plane
      round lands; the run family (run status|tail|wait|cancel|
      delete) maps to HANDLE METHODS per the blessed divergence
      (dash keeps run-script a distinct single token beside it).
      Selectors become per-command flags (rlq start-machine -b
      freedos), resolving item 10 toward flags-after-verb and
      retiring the SUPPRESS hack. North star becomes `rlq
      run-script install -b freedos-1.4-plain` (+4 chars, paid
      knowingly). ROUND OUTCOMES: the state ops sit on the
      management side — `insert-media` / `eject-media` /
      `set-boot-order` (twin identity; the crisp boundary is
      live-console vs durable-state, and the script verbs
      insert/eject/set-boot remain the in-script spellings of the
      same operations); flag position is UNIFORM — a flag may
      appear before or after the command word, position carries
      no meaning (the north star's two spellings are identical),
      synopses canonically show flags after — resolving item 10
      and retiring the SUPPRESS hack. Items 5-7's spellings
      landed dash-formed (seed-blueprint/-media/-script,
      new-blueprint, import-vm --name, check-script with label
      resolution). FOLDED: cli.md (intro doctrine, every synopsis
      and example, Flags-and-options rewrite), ROADMAP "The CLI"
      (identity paragraph, two-layer + interaction + globals +
      --json paragraphs, full synopsis block, lifecycle bullets,
      import/export bullets, scaffolder, future milestones 3/4/
      7/8 — completed milestones keep their historical spellings;
      the realignment milestone owns the implementation rename),
      api.md (identity convention; table collapsed to the
      mechanical transform, seed family and property twins added,
      property "pending naming" row closed), INTERFACES.md (CLI
      section), USE-CASES U1, codex.md, machine-blueprint.md
      (verb table gains the CLI/twin column), -reference,
      -cookbook, instance-model, media-spec, property-registry.
      docs/ and README follow at implementation realignment
- D7 — API DESIGN GAP QUEUE (owner-requested review, 2026-07-21:
  planning/design/api.md walked against planning/INTERFACES.md /
  planning/USE-CASES.md, the CLI design, and Python practice; verdict:
  the twin-name identity rule, the --json twin's-return rule, pull-only
  handles, and the named-omission discipline are sound — the gaps were
  unnamed conventions and unnamed twins):
  1. RESOLVED (owner, 2026-07-21): the async starters are a NAMED
     convention — start_script / start_fetch are the blocking twins'
     starters, presenting on the CLI as --detach on the blocking
     command, never a third command; start_fetch deliberately has NO
     CLI form (a fetch handle is process-local — a CLI driver
     backgrounds fetch-media itself, the process being the handle;
     run records provide reattachment). Folded: api.md (conventions +
     handles), media-spec fetching, ROADMAP "Asynchronous runs".
     DESIGN ROUND (owner, 2026-07-21, both forks on the
     recommendations): the convention now DERIVES from the async
     round's sync-is-async-plus-attach doctrine — the CLI composes
     start+attach (--detach = start without attach), the API
     separates them, and the identity rule binds the capability
     pair, not each function alone (api.md bullet rewritten; a
     mechanical mirror was weighed and declined: detach= is a
     union return type, a start-script command duplicates the
     capability); start_fetch's no-CLI-form CONFIRMED
     (process-is-the-handle; fetch records weighed and declined —
     reopening ephemerality for a cache-warming convenience)
  2. RESOLVED (owner, 2026-07-21): attach-by-id is NAMED —
     attach_run(machine=, blueprint=, run=None), the run number
     defaulting to the machine's latest exactly as the CLI run
     operations; the last unnamed twin. Folded: api.md (table +
     handles), cli.md run family, script-spec twins sentence (its
     stale `script --detach` spelling fixed to run-script in
     passing), ROADMAP "Asynchronous runs".
     DESIGN ROUND (owner, 2026-07-21, both forks on the
     recommendations): attach_run CONFIRMED (the doctrine's own
     verb — sync is async plus attach; open_run/get_run weighed
     and declined) and the latest-run default CONFIRMED (mirrors
     the settled CLI default; delete's required-number rule stays
     deletion's alone — attach is read-only observation). One
     handle type: attach_run returns what start_script returns;
     a crashed run attaches and reports crashed. No doc change —
     the committed shape stands
  3. RESOLVED (owner, 2026-07-21): the exception taxonomy is NAMED —
     ReliquaryError the root every deliberate error subclasses;
     StaticError(2) / PreflightError(3) / RunFailure(4) /
     RunCancelled(5) the one exit-code mapping under parity; exit 1
     is precisely an error outside the taxonomy; other bindings
     spell the same classes natively. Folded: api.md conventions,
     script-spec "Error classes and exit codes", ROADMAP "The CLI".
     DESIGN ROUND (owner, 2026-07-21, both forks on the
     recommendations): SCOPE settled — the root is universal, the
     four named classes are the RUN SURFACE's exit-code mapping;
     deliberate errors outside the run surface subclass the root
     directly until the general programmatic-contract work names
     finer classes (growth additive, never a break; a full domain
     tree now was weighed and declined as speculation ahead of
     the queued contract); NAMING confirmed as spec-term identity
     (RunFailure / RunCancelled unsuffixed — RunCancelled an
     outcome, subclassing the root, never RunFailure; strict
     Error-suffixing declined). api.md Errors bullet rewritten
  4. RESOLVED (owner, 2026-07-21): flag↔parameter mirror drift
     closed — --refetch-mismatched respelled --on-mismatch
     (fail | refetch), the mechanical mirror of on_mismatch=
     (interactive runs without the flag still map to "prompt";
     milestone 2 and released CHANGELOG keep historical
     spellings). Folded: media-spec mismatched-files, cli.md
     (fetch synopsis + prose, run family), api.md naming
     convention.
     DESIGN ROUND (owner, 2026-07-21): --on-mismatch CONFIRMED
     (enum-flag house style per --hdd-images; explicit fail also
     forces noninteractive failure on a tty); the PROMPT RULE
     named — "prompt" is selected, never inferred: a library
     never prompts by default, on_mismatch="prompt" is the
     caller explicitly delegating the checkpoint to the tty
     (folded into media-spec; CLI-owned checkpoint weighed and
     declined — the mismatch error names one file while refetch
     pre-approves all, so the loop changes semantics or the
     veneer starts owning them); and AGAINST the recommendation,
     --stop respelled --stop-machine — the exceptions cover
     command names only, flags mirror their function's or
     method's parameters everywhere, exception families included
     (api.md naming bullet flipped; cli.md run family + synopsis
     + example; ROADMAP cancel paragraph + synopsis; TASKS async
     record keeps its historical spelling)
  5. RESOLVED (2026-07-21): api.md contract homes no longer point
     at the short-lived cli.md — list/search → ROADMAP "The CLI";
     guest-console → script-spec (verbs) + the control-plane
     design (twins).
     DESIGN ROUND (owner, 2026-07-21): list/search refined to the
     HYBRID — family semantics (ANDed terms, CODEX column,
     --verbose pretty-only) stay in ROADMAP "The CLI"; each
     noun's return shape lands with that noun's own spec as it
     lands (machines → instance model, blueprints → blueprint
     guide, media → media spec, scripts/runs → script spec) —
     the table's each-family-with-its-spec principle applied
     (api.md row updated); guest-console home CONFIRMED (verbs
     in script-spec, twins with the deferred control-plane
     design — the named-omission pattern; screen/exec durably
     defined in ROADMAP "The CLI")
  6. RESOLVED (owner, 2026-07-21): the property twins' signatures
     are settled — list_properties(prefix=None), get_property(key),
     set_property(key, value, secret=False), unset_property(key);
     named divergence: the API takes a secret's value as an
     ordinary in-memory parameter (argv/process-listing concerns
     are CLI-side; a library never prompts or reads stdin);
     get_property returns the marker for a secret, never the
     value; the kind-change rule applies unchanged. Folded:
     property-registry.md "Maintaining properties".
     DESIGN ROUND (owner, 2026-07-21, both forks on the
     recommendations): set_property's single-twin shape CONFIRMED
     (one command, one twin — set_secret would name a command the
     CLI doesn't have); the VALUE-UNION PRINCIPLE recorded in
     api.md's returns convention — returns are plain JSON-shaped
     values, a union of document shapes is ordinary JSON (forced
     by the --json marker rule), a value-or-handle union is never
     allowed (a handle is not a value — why detach= died);
     list_properties returns the registry projection (key →
     value-or-marker), the pretty listing a rendering of it
     (property-registry updated)
  7. RESOLVED (owner, 2026-07-21, follow-up — the deferred
     semantics settled on the recommendations): wait(timeout=)
     completes exactly as the blocking twin (same result, same
     raises) and expiry raises OUTSIDE the taxonomy (Python: the
     builtin TimeoutError) — nothing failed, the handle stays
     valid, the call repeats; a handle is a follower, never the
     owner — dropping one never affects its operation (GC timing
     carries no semantics in any binding; cancel() is the only
     cancellation, a dropped fetch runs to completion);
     resolve_machine is an IMPLEMENTATION SEAM, not a public twin
     (no command — selection is a property of every machine-scoped
     call, the query form is list_machines(blueprint=)); per-twin
     return-shape contracts stay with the queued output-stability
     work, the wait-mirrors-the-blocking-twin rule settled now.
     Folded: api.md (selectors + pull-only conventions),
     media-spec fetch handle, ROADMAP ("Asynchronous runs" handle
     paragraph + "The CLI" selection sentence), cli.md Selection.
     DESIGN ROUND (owner, 2026-07-21, all three forks on the
     recommendations): wait expiry CONFIRMED outside the taxonomy
     (builtin TimeoutError; interlocks with item 3's scope — the
     catch-all deliberately does not catch expiry, "still
     running" is not an error; a ReliquaryError subclass and a
     sentinel return weighed and declined; api.md pull-only
     bullet gains the catch-all sentence); drop semantics
     CONFIRMED (follower-never-owner, cancel() the only
     cancellation; cancel-on-drop declined — GC timing carries
     no semantics in any binding; Python with-sugar cancel
     declined as the same trap opted into; named cost: an
     abandoned fetch runs to completion); resolve_machine
     CONFIRMED internal (a resolve-machine command would
     duplicate the list family's query). Return shapes stay
     queued, landing per item 5's hybrid homes
  8. RESOLVED (owner, 2026-07-21, design session — all four forks
     on the recommendations): the backend-adapter design output is
     AUTHORED — planning/design/backend-adapter.md, the provider
     seam's doctrine: the three-layer split (machine model above
     the seam unmoved, adapter, control planes composing
     carriers), the seam inventory with extraction sources
     (discover / capability report / materialize-dispose /
     start-stop-liveness / carriers / ownership), capability
     honesty (reported, never emulated), the generalized vm.json
     identity record, endpoint two-phase, non-goals, extraction
     map. Forks: doctrine now, SIGNATURES AT THE MILESTONE-6
     EXTRACTION (defined-by-working-code holds — the doc records
     them when they land); INTERNAL, not world-facing (watch
     below — third-party adapters would elevate it through the
     interface-change rule); text readback = adapter CARRIERS +
     one shared fixed-font recognizer composed by the
     agentless-display control plane (snapshot contract: character
     rows + opaque equality-comparable per-cell attribute tokens —
     the menu algorithm compares, never interprets); drive
     materialization belongs to the ADAPTER (native formats +
     native differencing; qemu-img becomes QEMU-adapter
     internals). Folded: backend-adapter.md (new), ROADMAP
     ("Backend adapters" doctrine paragraph, agentless-display
     recognizer sentence, milestone 6 intro), the
     guiding-principles watch list
- D6 — GAP-CLOSURE DESIGN QUEUE (owner-requested, 2026-07-21: the five gaps
  left standing in the guiding-principles queue above once the
  blueprint-spec, CLI, API, and property queues closed — itemized for
  design rounds, in leverage order; everything else open is
  deliberately parked in ROADMAP "Decisions still needed"):
  1. RESOLVED (owner, 2026-07-22, design round — all five forks on
     the recommendations): THE OUTPUT DISCIPLINE — the result is
     stdout, everything else is stderr: a result-bearing command's
     pretty stdout is exactly the human rendering of what its twin
     returns (the same value --json serializes — the parity rule
     extended to channel placement); progress, narration, warnings,
     prompt text, and error reports live on stderr, so tables and
     printed ids pipe clean and announcement lines never pollute a
     pipe. Stream-bearing commands' human modes (pretty/plain)
     render EVERYTHING to stderr — stdout stays empty (the outcome
     travels by exit code, run record, and jsonl, whose stdout
     events remain the settled exception; an outcome line on stdout
     was declined as scraper bait); --detach's printed run id stays
     a result. --progress auto resolves by stderr-is-a-tty (the
     stream progress renders on); prompting requires stdin AND
     stderr ttys — prompt text on stderr, answer from stdin
     (console-device direct access declined: a platform seam, and
     unsuppressable by redirection). Diagnostics codified:
     rlq: <message> / rlq: warning: <message>, detail indented,
     errors name the next command. Color per-stream tty only,
     NO_COLOR honored, no --color flag (YAGNI as --format). THE
     STABILITY CONTRACT: the contract surfaces are exactly four —
     exit codes, --json documents, the jsonl event stream,
     run-record files; pretty/plain are explicitly uncontracted
     (the named refusal that keeps scrapers off); growth from beta
     is additive-only (new kinds/fields may appear; an existing
     field never changes type or meaning; removal/rename breaks)
     with consumers ignoring unknown kinds and fields (the
     BuildKit/LSP lesson); pre-beta no promise, CHANGELOG records
     shape changes; the version-field spelling stays with the beta
     format-versioning decision. Folded: ROADMAP "The CLI" (the
     discipline + stability paragraphs), script-spec (event-stream
     stability + the precise interactive-context tty definition),
     api.md returns convention (return-shape stability), cli.md
     (Output discipline section, --progress prose, --json
     stability paragraph), media-spec fetch-progress (stderr
     rendering; its stale "as on `script`" spelling fixed to
     run-script in passing); per-noun field contracts stay with
     each noun's spec (api-queue item 5 hybrid). The
     guiding-principles CLI-contract entry is CLOSED — all four
     halves homed
  2. RESOLVED (owner, 2026-07-22, design round — all four forks on
     the recommendations): INTERACTION RUNS, the opt-in bracket —
     begin-run / end-run (flat twins begin_run/end_run; begin
     returns the run number) open and close an ordinary run record
     whose driver is the caller; while open, EVERY machine-targeting
     command on that machine appends the event kinds the execution
     model defines (interaction family with screen's CLI-only read
     kind, state ops, lifecycle — interaction-only scope declined
     as lying by omission); with none open, primitives record
     nothing (always-record and never-record both declined). One
     open run per machine — a second begin-run or a run-script
     fails closed naming it (mixed-driver records stay U6's growth
     path via the reserved handover kinds); end-run writes the
     neutral `ended` terminal (no outcome — G2); no resident
     writer: appends ride the machine lock, the crashed-run rule is
     script-run-scoped, openness is visible never inferred (run
     status shows last-event time; run cancel refuses naming
     end-run; run delete refuses while open); followers indifferent
     (run tail / attach_run / list-runs; records self-identify
     their driver). THE RENDERER CONTRACT — transcript.txt stays in
     every record, written live (on-demand rendering declined: the
     copied-out record must stand alone), respecified as a PURE
     renderer: every line derives from an event, adds nothing,
     one-way stream→transcript, format uncontracted per item 1; the
     old transcript bullet list promoted to stream content
     requirements, adding the missing kinds — backend/control-plane
     selection at preflight, statement provenance on events
     generally (was embedded-installs only), collected-file landed
     paths. PER-TEST RESULTS — two channels and a named refusal:
     selection IN as script properties (--property / properties=,
     interpolated by ordinary references — supersedes the stale
     "response data" phrasing; responses died in the
     property-construct round); results OUT as caller-authored
     artifacts (JUnit XML, TAP) via collect/exec-capture into the
     record's output/, path reported live in events; NO test-result
     vocabulary in Reliquary (G2) — granularity comes from run
     structure: one iteration = one run record. The
     collect-into-runs/<n>/output/ demand is recorded as input to
     queue item 3. (The custody half — collect and output/ — was
     later dropped: see the run-collection drop, 2026-07-22.) Folded: script-spec "Failure, runs, and
     transcripts" (transcript respec, crashed-rule scoping, the
     Interaction runs section) + "The run event stream" (preflight
     and interaction kinds, collected paths, statement provenance),
     ROADMAP "Asynchronous runs" (interaction-runs paragraph) +
     "The CLI" (synopsis + interaction paragraph), cli.md (Recorded
     interaction runs section, intro sentence, machine-scoped
     list), api.md (table row, attach_run driver-indifference);
     guiding-principles U3 run-records entry CLOSED (its stale
     response-data phrasing fixed to properties)
  3. RESOLVED (owner, 2026-07-22, design round — an extended
     owner-driven walk-through that reshaped the design four
     times; each intermediate shape was killed by an owner
     challenge): THE RESULTS DIRECTORY IS A SCRIPT DECLARATION —
     `results <drive-key> ["<path>"]` (header node, S15; path
     defaults to the drive root; renamed from `exchange`
     in-round, owner: name it by what earns it — U3's results
     out; stage-into-results the named cost; resultsdir and
     workdir weighed and declined, workdir a docker false
     friend): the def is coupled to the
     instruction stream — the script that tells the guest to
     write to D:\RESULTS is the file that declares results hdd1
     "/results" — so it is NOT a blueprint item (blueprint stays
     pure topology; the letter↔key agreement is the author's
     ordinary guest-boundary duty, Reliquary never maps guest
     letters). stage/collect are IN-BAND COPIES resolving within
     the point (bounded host reach; no absolutes, no ..), machine
     stopped on every control plane, via the adapter's at-rest
     filesystem access (native formats + chains, capability
     honesty, FAT first; no-filesystem fails by name — a blank
     size drive has none until the installer makes one);
     preflight verifies the drive (size/base/hostdir content —
     never media, never an empty slot); directory arguments
     recursive, collect "/" sweeps the point (also the
     crash-forensics read — the drive at rest is authoritative);
     stage creates the dir; capacity errors name file and free
     space; collect lands in runs/<n>/output/ (item 2's demand,
     served). CLI: stage-files <path>... --to <drive:path> /
     collect-files <drive:path>... [--to <dir>] (twins
     stage_files / collect_files; durable-state side per the
     insert-media precedent), --to defaulting to the open
     interaction run's output/, required with none open. HOSTDIR
     REINSTATED (owner: "vvfat is too useful to ignore") as the
     FOURTH drive content source beside media/size/base: a host
     directory presented to the guest as a READABLE, WRITABLE FAT
     drive — no modes, no flags; the directory reflects the
     guest's writes at the latest by machine stop (QEMU vvfat may
     show them live; the floor is the contract); while stopped
     the directory IS the drive's content (out-of-band
     preparation with any host tool is legitimate;
     stage-files/collect-files are the in-band form);
     latest-state-only (history is what run records are for) and
     no sharing across concurrently running machines, both
     documented; hdd/floppy only (never cdrom — no ISO9660);
     relative paths asset-root-resolved (U4-portable), absolute
     allowed (the local-path class); unverified by design (media
     stays the pinned path); apply-absorbable; adapter-served
     under capability honesty (QEMU = vvfat, proven for DOS-era
     write patterns; others serve the contract their own way or
     report unsupported — owner: backend nonuniformity accepted
     here, vvfat too useful to ignore). Division of labor:
     hostdir = the standing working surface (the design's half),
     stage = per-run injection (the instruction stream's half),
     the results directory + collect = bounded reach and
     evidence custody.
     DECLINED along the walk-through: a dedicated size-valued
     exchange drive (topology/drive-letter churn); folder-as-
     custody and the boundary folder MIRROR (last-stop-wins vs
     one-iteration-one-record; parked — the CLI pair covers the
     folder workflow explicitly); the blueprint drive:path
     exchange def (the instruction-stream coupling killed it);
     READ-ONLY HOSTDIR and any writable/readonly flag (an agent
     invention the owner never asked for, declined explicitly
     after discussion-to-understanding — hostdir is writable,
     period; QEMU's live vvfat-rw caveats concern modern guests,
     not this domain, and imposed no constraint). Growth notes:
     agent-era live transfer stays DISTINCT VERBS (guest-file-*
     needs no results directory); multiple results directories =
     an optional drive argument, additive. Folded: script-spec (header
     table/grammar/prose, S15 + S1-S15 citation, stage/collect
     rewrite, preflight list), blueprint reference (four-field
     exactly-one-of, #hostdir, no-image-paths scoping, validation
     summary), machine-blueprint.schema.json (hostdir def +
     floppy/hdd oneOf), ROADMAP (offline-exchange paragraph, CLI
     synopsis + state-ops paragraph, horizon vvfat note), cli.md
     (File exchange section, machine-scoped list), api.md (table
     row, realignment note); guiding-principles U3 stage/collect
     entry CLOSED. SUPERSEDED IN PART (owner, 2026-07-22, the
     run-collection drop below): the file-exchange half — results
     directory, stage/collect, stage-files/collect-files, record
     output/ custody — is dropped; hostdir, the at-rest access
     doctrine, and distinct-verbs-for-live-transfer stand
  4. RESOLVED (owner, 2026-07-22, design round — all four forks on
     the recommendations, the targets fork revised mid-round by the
     owner's decoupling insight): EXPORT IS TWO COMMANDS —
     export-drive <key> <destination> / export-machine --to
     <exporter> [<destination>] (twins export_drive /
     export_machine; the --drive mode flag dies; api.md's named
     omission closes), both stopped-only and STREAM-BEARING
     (transfer events, --progress, --json rejected naming
     --progress jsonl, terminal event = the result), the artifact
     independent and outside purview, the machine untouched.
     EXPORTERS ARE THEIR OWN VOCABULARY, decoupled from backends
     (owner: export may target kvm/virt-manager or others — never
     limit import/export to the backend list): --to names an
     exporter — virtualbox, vmware, hyperv, libvirt, ... — probed
     on the host independently; presented, never defaulted (tty
     prompt listing available exporters, required noninteractively;
     to= required under parity — the --hdd-images pattern); the
     exporter builds the native VM from the machine's resolved
     blueprint shape (capability-checked like create) with drives
     through the adapters' RAW INTERCHANGE (each adapter reads a
     drive out as raw and materializes one from raw — the one new
     adapter obligation; exporters are their own seam family
     beside the adapters); libvirt recorded as the QEMU-ecosystem
     answer, so the Reliquary-invented bare-image-plus-launch-
     config artifact is DELETED, never specced — U1's journey
     lands as install on QEMU, export-machine --to virtualbox.
     MEDIA DRIVES MATERIALIZE AS COPIES in whole-machine export
     (state-inserted media too): the export stands alone, never
     referencing the disposable cache; blocking declined.
     EXPORT-DRIVE lands the drive's native format or raw by
     destination extension (.img/.raw); other conversions declined
     as growth (cross-backend wants are export-machine's job); an
     exported installed disk + a local-path definition = an
     installed base for other blueprints. Import mirrors the
     decoupling in vocabulary only (importers read native VM
     sources, no same-named backend required; the settled import
     mechanics untouched). Taxonomy recorded: accelerators
     (KVM/WHPX/HVF/TCG) are adapter-internal capability of the
     qemu backend — never backend identity, never blueprint
     vocabulary; libvirt is an exporter now, a possible distinct
     future backend later, the roles independent. Folded: cli.md
     (Exporting rewrite, twins paragraph, machine-scoped list,
     import-vm importer wording), ROADMAP ("The CLI" export
     bullet + twins sentence + synopsis + import bullet, milestone
     8 intro + deliverable 2, the Decisions-still-needed export
     entry REMOVED), api.md (table row, omission closed),
     backend-adapter.md (raw-interchange seam entry,
     exporter-family placement, accelerators-are-not-backends
     non-goal); guiding-principles U1 export entry CLOSED
  5. RESOLVED (2026-07-22, verification closeout — bookkeeping as
     expected, plus one residue fix): the U5 recorded design's
     pending adjudication was OVERTAKEN AND COMPLETED by the
     owner-adjudicated property-construct rounds — every element
     traced: the `parameters` field with its two bindings SURVIVED
     (direct value | redirect); the reference form became the
     REDIRECT, replaces-entirely and never-chains surviving
     verbatim; the recorded binding order "response > blueprint >
     input property= > prompt" was SUPERSEDED by the flattened
     property sources (--property > parameter > env > file > ask:
     responses deleted, input property= dissolved into the
     one-namespace property declaration, the prompt became the
     once-per-key ask); the secret-parameter rules and the seam
     doctrine (value seams = parameters, locale-class =
     composition; the watch-condition ban, G2/G3) survived
     untouched; invocation-read, no state/apply/digest involvement
     survived. Landed docs verified in the settled shape:
     machine-blueprint-reference #parameters (re-keyed, redirect,
     the flattened source order), cookbook #9, guide
     #customization-seams, ROADMAP's literal-defaults note.
     Residue fixed in passing: cookbook #9's intro declared
     "owner-name and install-key inputs" — the dead concept name
     AND pre-one-namespace keys that didn't match its own
     example — now "the identity.full-name and os.install-key
     properties". The guiding-principles U5 entry is CLOSED
  QUEUE COMPLETE (2026-07-22): all five items resolved — 1 (the
  output discipline + the stability contracts), 2 (interaction
  runs + the renderer contract + per-test results), 3 (the results
  directory, stage/collect, hostdir), 4 (export mechanics + the
  exporter vocabulary), 5 (the U5 closeout). Every gap entry in
  the guiding-principles queue is now closed (its watch list
  stands, as watches); everything still open anywhere is parked in
  ROADMAP "Decisions still needed" by design, with implementation
  work owned by the realignment and later milestones
- D5 — THE RUN-COLLECTION DROP — DECIDED (owner, 2026-07-22, the
  out-of-band round; an owner revisit of gap-closure items 2 and 3
  settled through "what use case cannot be met without it?" —
  answer: none; the mechanism was custody and ergonomics, never
  capability; U6 verified untouched — console capture in, authored
  files out). DROPPED wholesale: the `results` header,
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
  backend. Named cost accepted: per-iteration artifact history
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
- D4 — THE USER-PROPERTIES DESIGN ROUND — DECIDED (owner, 2026-07-21,
  the docker-comparison round; all three forks on the
  recommendations). The docker model largely CONFIRMS the design
  (marker-file + host credential store = credential helpers;
  stdin secret entry = docker secret create -; secrets as a
  separate channel with different physics = the build-arg-leak
  lesson; reject-unknown response keys stricter than docker's
  warn); the round's changes:
  1. RENAMED: "the property registry" → USER PROPERTIES — the
     concept name only; properties.json and the property command
     family are untouched. "Registry" reads as a remote
     artifact-distribution service (docker/npm/OCI) and stays
     free for any future sharing service; the settled command
     vocabulary already says properties. property-registry.md →
     user-properties.md (git mv). Folded: INTERFACES (supporting
     contract + spec homes), AGENTS, ROADMAP (home layout, assets
     rule, property bullet, script section, milestone ordering +
     milestone 4 heading, milestone 5 deliverable 4), USE-CASES
     (spelling only — no use-case change), script-spec, blueprint
     guide + reference + schema descriptions, api.md contract
     home, cli.md Properties. Historical records (released
     CHANGELOG, closed TASKS items) keep the old name per the
     documentation rules
  2. INLINE RESPONSES: run-script/check-script gain a repeatable
     `--respond <name>=<value>` beside `--responses <path>`
     (docker -e / helm --set / terraform -var precedent — a
     one-value override no longer requires authoring JSON: U1
     ease, and argv-clean quoting for CLI-driving programs,
     U3/U4). File + inline build ONE responses mapping — the
     twins' `responses=` parameter, so CLI–API parity is the
     identity, not a translation; inline overrides the file for
     its name (the more explicit spelling), a name repeated
     inline is an error, and a `secret` input never binds from
     `--respond` (argv is not a credential store — the
     set-property rule) while the response file's warned
     plaintext allowance stands (the API's in-memory mapping
     legitimately carries secret values — the set_property
     precedent, and refusing only the CLI file would break
     parity). Folded: script-spec (responses paragraphs +
     check-script synopsis), cli.md (synopses, prose, example),
     ROADMAP (both synopses, script section, milestone 5)
  3. WIRING LOCUS CONFIRMED: the script may suggest a key
     (input property=) and a blueprint parameter REPLACES it —
     the compose-style blueprint-only wiring was weighed and
     declined (every blueprint would re-wire universal keys like
     identity.full-name, and a bare codex script run would lose
     personal defaults and fall to prompting — U1; scripts stand
     alone, the embedded-media precedent). No doc change — the
     committed shape stands
  4. THE OWNERSHIP FRAMING recorded and the binding order
     CONSOLIDATED: each source answers for a different owner —
     the caller (this invocation), the design (every machine of
     the blueprint), the person (durable), then the prompt —
     and precedence follows ownership, specific-and-short-lived
     first. script-spec "Inputs, properties, and response files"
     is the chain's one normative home; user-properties.md and
     the blueprint reference now summarize and link instead of
     restating (the docker-compose precedence-table lesson:
     drift-prone restatement is what made docker's env story
     confusing)
  5. NO AMBIENT CHANNEL named: an input value never binds from a
     process environment variable — a caller interpolates one
     into a response explicitly; recorded in script-spec so a
     future env-channel proposal argues against a decision, not
     a gap (docker's silent -e NAME inheritance and .env
     interpolation are the counterexample)
  - fixed in passing: user-properties.md's stale "property set"
    command spelling → set-property; script-spec's stale
    "rlq script" example spelling → run-script
  FOLLOW-UP ROUND (owner, 2026-07-21, the layering round; all
  four forks on the recommendations):
  6. HOME PROPERTIES CONFIRMED FOR AUTOMATION — the
     uncontrolled-source worry resolves: unlike the codex (banned
     from automation because artifacts changing outside source
     control break a project), properties carry exactly what MUST
     NOT be checked in (U4's license, U5's mechanism), reach a
     run only where a source-controlled artifact names the key
     (input property= / blueprint reference), and fail preflight
     loudly when absent — the control is versioned, only the
     values are personal
  7. THE LAYERED PROPERTY STACK — the property step of the
     binding order resolves through layered sources, nearest
     first: --property <key>=<value> (repeatable; API
     properties=) > RELIQUARY_PROPERTY_* environment > the
     selected properties file. The stack lives INSIDE binding
     step 3: a response or blueprint parameter beats every layer,
     so a stray env var never overrides a designed value (the
     docker -e footgun stays dead); env satisfies blueprint
     property references too — CI injects a license key with no
     pre-provisioned home. Normative home: user-properties.md
     "Property sources"
  8. ENV SPELLING: prefix form RELIQUARY_PROPERTY_<KEY> (the
     TF_VAR_/NPM_CONFIG_ convention; suffix form
     RELIQUARY_<KEY>_PROPERTY weighed and declined — grep-able
     common prefix, self-evident reserved namespace); mangling
     uppercases and folds `.`/`-`/`_` to `_`; a mangle collision
     between two CONSULTED keys is a fail-closed preflight error
     naming both
  9. --properties <path> SELECTS the properties file, REPLACING
     the home's for the invocation (layer-above-home weighed and
     declined — project defaults are blueprint parameters' job;
     replacement is the hermeticity tool: a project-controlled
     file means nothing personal reaches the run, the
     --assets-only instinct applied to values). Env
     RELIQUARY_PROPERTIES; API properties_file=. Property
     commands maintain the selected file (so project-file secret
     markers are provisioned normally) — the settled property
     twins gain properties_file= ADDITIVELY (item 6 of the api
     gap queue stands otherwise); credential scoping GENERALIZED
     from absolute-home to absolute properties-file path (the
     home's file is <home>/properties.json — a strict
     generalization)
  10. SECRET RULES PER LAYER: --property never satisfies a
     secret-bound key (argv — the set-property rule, as
     --respond); env MAY (the CI secret-injection path, named
     the same warned plaintext class as a response-file secret;
     ordinary-only env weighed and declined as a refusal that
     gets worked around); the file layer alone holds markers and
     kinds. Item 5's no-ambient refusal NARROWED (superseded in
     place — this round is uncommitted): nothing binds by INPUT
     NAME from the environment and nothing reaches an input
     without a source-controlled artifact naming its key; the
     declared RELIQUARY_PROPERTY_* layer is the one environment
     channel, inside step 3. Transcripts/check-script name the
     supplying layer (flag/environment/file), never values.
     Folded: user-properties.md (Property sources — normative —
     + maintaining/secret-storage/checking), script-spec
     (binding step 3, the narrowed uninvited rule, transcript
     provenance, check-script), cli.md (synopses, run-script
     prose, Properties), ROADMAP (synopses, property bullet,
     script section, milestone 4 deliverable 4, milestone 5),
     blueprint reference (property-reference bullet)
  SECOND FOLLOW-UP ROUND (owner, 2026-07-21, the format round):
  11. ASK IS THE FINAL LAYER — interactively the property stack
     ends by asking the user: flag > env > file > ask. One ask
     per unresolved key per run (presented with the first
     requesting input's prompt text), its answer satisfying
     every input bound to that key — the
     duplicate-prompt-inconsistent-answers hole closes; answers
     stay invocation-local, never written back. The input
     chain's own prompt step remains only for propertyless
     inputs; noninteractive behavior unchanged (the stack
     exhausts, preflight fails). Blueprint property references
     resolve through the full stack, ask included — never a
     different key
  12. THE FILE FORMAT — strict JSON → the Reliquary line format
     (fork on the recommendation): one key = value per line,
     # full-line comments and blank lines PRESERVED through
     property commands (surgical line edits — the
     canonical-rewrite rationale for the comment ban dies with
     the canonical rewrite), values verbatim-trimmed with no
     quoting/escapes/continuations, @-prefixed value-kind
     tokens (@secret the first; @@ spells a literal leading @;
     the deliberate seam for future kinds), duplicate keys and
     bad lines fail closed naming file and line, UTF-8, atomic
     writes. Keeping JSON weighed and declined (the file was
     already the JSON family's odd member, and since the
     layering round every other property layer speaks
     key=value); TOML declined (dotted keys nest, rewrite
     fidelity needs a dependency). The API/--json marker
     spelling {"secret": true} STANDS — returns stay JSON-shaped
     under the value-union rule; @secret is file syntax only
  13. FILENAME (owner — AGAINST the recommendation):
     user.properties, the Java-association name for instant
     editor key=value recognition; properties.rlqp (the format
     family) and bare "properties" (git-config style) weighed
     and declined. The spec NAMES the caveat: the format is not
     Java properties — no unicode escapes, no continuations.
     Folded: user-properties.md (names-and-values rewritten,
     sources layer 4, filename throughout), script-spec (chain
     steps 3/4 + prompting paragraph + marker sentence), cli.md
     (Properties, --json marker rule, run-script prose), ROADMAP
     (home layout, property bullet, script section, milestone 4
     deliverables 1-2 — scoping fixed to file path — and
     milestone 5), blueprint reference (reference resolution),
     the realignment JSONC work item (user properties leave the
     strict-JSON set)
  THIRD FOLLOW-UP ROUND (owner, 2026-07-21, the property-construct
  round — "design this well"; the namespace and caller-flag forks
  settled by the owner, the flag fork with a corrected mental
  picture: "blueprint is a property source, CLI overrides it"):
  14. THE PROPERTY DECLARATION — `input` is replaced by the
     `property` node: `property [text|media|secret] <key>
     [prompt="..."]`, type optional defaulting to text, the three
     type words reserved in type position (a key so spelled is
     rejected), prompt= feeding the interactive ask, one
     declaration per key per script (a duplicate is a static
     error; the multi-inputs-share-a-key machinery and round 3's
     first-requester tie-break die — reference the key instead).
     References $key / ${key} accept dotted keys (the `name`
     token already did); grammar input-def → property-def,
     input-ref → property-ref, S5/S6 updated
  15. ONE NAMESPACE (fork on the recommendation): the declared
     name IS the user-property key — the input-name keyspace, the
     property= bridge, and round 1 item 3's script-suggests
     wiring spelling are superseded (the semantic — the script
     names a key, the blueprint may re-wire — survives as
     declaration + redirect). Short undotted keys are legal,
     script-scoped by convention; dotted keys join the shared
     vocabulary. Blueprint parameters re-key by property key;
     their reference form is renamed the REDIRECT: resolves the
     target key through the NON-blueprint sources (parameters
     never chain), never falling back to the redirected key
  16. THE FLATTENED SOURCE ORDER (the owner's picture): everything
     is a property source, one normative list in script-spec "The
     property sources" — explicit --property value (caller) >
     blueprint parameter (design) > RELIQUARY_PROPERTY_* env
     (session) > the selected properties file (person) > the
     once-per-key interactive ask. The binding-chain-plus-stack
     two-axis model dies; U5's guarantee survives as
     design-beats-standing (env/file), explicit-CLI-beats-design;
     env stays below the blueprint (round 2's named refusal — an
     ambient variable never silently overrides a designed value;
     the flag is the override path). The input-level prompt step
     is gone: every declaration is property-keyed, the ask IS the
     prompt
  17. THE RESPONSE CONCEPT DELETED: --respond/--responses, the
     JSONC response file, and the responses= mapping are removed
     (rounds 1-2's inline-responses additions superseded, same
     working tree). The caller channel is --property (repeatable;
     twice is an error; keys must be declared by the running
     script — stores may hold extras, explicit answers may not) +
     the API properties= mapping; --properties <path> and
     properties_file= keep the round-2 store-selection semantics.
     The per-run plaintext-secret FILE channel dies with response
     files: secrets per run travel via env (warned class), the
     in-memory API mapping, or the no-echo ask — argv never. A
     tier-1 bulk values file was weighed and declined (repeatable
     flags and the API mapping cover it; growth stays additive)
  18. NODE-SYNTAX RENAME: the construct collision (a `property`
     node in a grammar whose name=value tokens were also called
     "properties") is cleared by renaming the syntactic concept
     MODIFIERS throughout the spec (tables' column, S2/S4/S7,
     timing/watch productions -prop → -mod, the LL(1)
     modifier-name token, "timing modifier"). Folded: script-spec
     (Properties section rewritten as the normative home, node
     tables, grammar, S-rules, lexical rules, references,
     transcript/event provenance, check-script, sharing,
     validation lists), user-properties.md (intro, Property
     sources flattened, Binding script properties, Secret
     properties at runtime, checking, sharing), cli.md (synopses,
     run-script prose, examples, selector note), ROADMAP (both
     synopses, script section, principles bullet, milestones 4-5,
     milestone-zero JSONC note marked dissolved, decisions-still-
     needed), blueprint guide + reference (parameters re-keyed,
     redirect) + cookbook + schema descriptions, the realignment
     JSONC work item, planning/design/script-examples/06 (input → property)
  FOURTH FOLLOW-UP ROUND (owner, 2026-07-21, the naming round):
  19. THE MECHANISM IS NAMED SCRIPT PROPERTIES; "user properties"
     names one source — the person's durable file,
     user.properties. The owner's read: the property-construct
     round had already moved the mechanism's normative home into
     script-spec, leaving a doc called "User properties"
     documenting mostly non-user sources. user-properties.md →
     script-properties.md (git mv, second rename in this
     uncommitted set), titled "Script properties"; INTERFACES
     supporting contract renamed (its authored world-facing
     surfaces named: the user.properties file and the
     RELIQUARY_PROPERTY_* spelling), AGENTS contract mentions,
     ROADMAP (property bullet, script section, milestone list +
     ordering, milestone 4 heading), api.md contract home,
     cli.md, blueprint guide companion list, script-spec links,
     USE-CASES spelling ("the personal user-properties file")
  20. ONE PACKED ENV VAR weighed and DECLINED (owner floated and
     retracted in the same message): a single RELIQUARY_PROPERTIES
     holding name-value pairs would need a quoting grammar for
     pair packing, collides with the settled RELIQUARY_PROPERTIES
     file-selection variable, loses one-secret-one-var CI
     injection, and sits inside platform environment-block size
     limits; per-key RELIQUARY_PROPERTY_<KEY> stands
- D3 — JSON SCHEMAS FOR THE AUTHORED FORMATS — DECIDED (owner, 2026-07-21,
  design round; all three forks settled on the recommendations):
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
- D1 — RESOLVED (owner, 2026-07-21): the built-in library is named THE
  CODEX (was "change 'builtin library' concept to 'template
  library' ??"; "canon" was weighed and rejected — codex is the
  artifact, a bound volume copied from, where canon is the
  abstract authority/list) — folded across INTERFACES, USE-CASES, ROADMAP,
  AGENTS, CONTRIBUTING, cli.md, README, and docs
  (builtin-library.md renamed codex.md); Reliquary/builtins/
  package dir renames to codex/ at implementation realignment

## Retired decisions

Overruled or no-longer-relevant decisions, moved out of the
active list with numbers and text intact (entries keep the
spellings of their time); each retirement note names what
overruled it. A retired decision binds nothing but remains the
record — and the guard against re-litigating still applies:
reopening one is argued through the interface-change rule.

- D17 — RETIRED (superseded by D22, the blueprint revision
  round, before any of it was implemented) — COMPOSED BLUEPRINT
  MODEL + MEDIA-RESIDENCY CACHE — DECIDED
  (owner, 2026-07-23, the media/composition design round). Full
  worked design: planning/design/blueprint-model.md (the source of
  truth, normative until the specs realign to it). Interface triage
  (planning/INTERFACES.md): the machine blueprint and the media
  definition are both world-facing interfaces, so this is a MAJOR
  interface change, landed under the interface-change rule and
  use-case-aligned (U1 lazy install, U3/U4 hermetic automation and
  artifact residency, U5 customization) — no use-case amendment
  needed. Two threads settled together.

  A — MEDIA RESIDENCY vs THE DOWNLOAD CACHE (the SHORTLISTED
  topic). Payload and archive caches stay NAME-KEYED and home-side
  (`cache/media/<name>.<ext>`, `cache/archives/<name>.<ext>` —
  `downloads/` renamed `archives/`), independent of `--assets`; the
  cached filename tracks the component `name`, not the source
  basename. CONTENT ADDRESSING WEIGHED AND DECLINED: an opaque
  hash-named cache cuts against "the cache is not an interface", and
  the residual clash it would close (two same-named components
  across projects aliasing one slot) is rare, already guarded by
  per-use hash verification, isolable via the orthogonal
  `--cache`/`RELIQUARY_CACHE_DIR` knob, and resolvable by naming one
  component explicitly — never blocking. Accepted because Reliquary
  users target a handful of systems, not vast libraries.
  Hermeticity of a `--assets` run = committed hashes determine
  inputs; cache-location isolation is the existing `--cache` knob,
  decoupled from `--assets` (dir-mode-implies-project-cache
  declined: couples orthogonal axes, loses cross-project dedup).

  B — THE COMPOSED BLUEPRINT MODEL (topic B, expanded well past
  "compose now or defer"). Reliquary's two authored JSON formats
  fold into ONE — the blueprint (`.rlqb`); `.rlqm` retires. A
  `.rlqb` root is polymorphic: plural component sections
  (`machines`/`media`/`sources`/`archives`), mixed and matched
  across files, a bare-root lone machine still valid. Four component
  types, identity `(name, type)`; NAMES DEFAULT TO THE SOURCE/PATH
  STEM (portable — the payload filename travels with the source; the
  `.rlqb`-file stem stays forbidden as identity), explicit only
  where there is no filename-bearing source. MEDIA OWNS
  MATERIALIZATION (`materialize` = new/difference/copy/use, default
  use; the machine drive shrinks to a media name or `null`, losing
  `size`/`base`/`hostdir`); `sha256` required on a `url` source,
  optional on local/from-archive (the "evolving drive" liveness
  case); `read-only` default true on cdrom; hostdir folds in as a
  `use` payload shape. SOURCES are named locators (mirror lists
  live here); ARCHIVES are RECURSIVE TREES — a node with `members`
  is an archive, a leaf is a media, the tree is the extraction, so
  nested archives need no special chaining. Machine directory
  reorganizes: `drives/` → `media/` (materializations named by
  media item, not slot, so removable-slot swaps never clobber),
  backend files into a backend-named subdir (`qemu/`/`virtualbox/`
  /…), `reliquary-machine.json` → `machine.json` with `vm.json`
  folded in as a while-running state section.

  WEIGHED AND DECLINED / PARKED: content addressing (A); the
  globbed media-set auto-expander (dropped — members are itemized
  explicitly under a shared archive tree; a succinct extraction
  short-circuit PARKED as a wish); create-at-destination media
  (fuses source with destination, duplicates `export-drive`);
  keeping `.rlqm` a separate kind (superseding the round's own
  earlier "model now, defer mechanism" lean — the owner drove the
  full unification); mandatory-name-without-derivation (relaxed to
  stem defaults). FOLDED: blueprint-model.md (new); TASKS.md (the
  two Design items retired here); ROADMAP pointer. REALIGNMENT
  AHEAD (implementation, milestone-scale, landed coherently per the
  no-BC rule): machine-blueprint.md + reference + cookbook,
  media-spec.md, the two published `*.schema.json` + conformance
  corpus (collapse to one blueprint schema), instance-model.md +
  the ROADMAP home-layout, AGENTS.md, machines.py / lifecycle.py /
  media.py, the codex, planning/examples.

- D2 — RETIRED (overruled by D16, the `name` reinstatement) —
  BLUEPRINT `name` FIELD DROPPED — DECIDED (owner, 2026-07-21,
  digression round during the CLI queue): the blueprint's one name
  is its file stem; `description` is the single discovery-prose
  field, uniform across the authored formats (scripts already had
  no name header; media's item `name` is a different, load-bearing
  concept — the identifier drives reference — and is untouched).
  Rationale: a display name is never an identifier, drifts from
  the stem unvalidated, and adds nothing over the description;
  listings become STEM | DESCRIPTION (truncated) and search
  matches stem/description/platform. Folded: blueprint reference
  (§description), guide + reference + cookbook status notes,
  machine-blueprint.schema.json, cli.md (named-scripts example,
  index prose, all three list/search sections — including fixing
  the stale claim that script search matches a `name` scripts
  never had), codex.md (index prose), ROADMAP (blueprint fields,
  codex index). This supersedes the old wishlist ask for a NAME
  column in 'list blueprints'; its other half survives in
  TASKS.md (the list-blueprints top-line announcement)
