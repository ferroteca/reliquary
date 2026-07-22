<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# TASKS

Small to-do tasks. Large tasks belong in the roadmap; the
adjudicated design-decision records live in
[DECISIONS.md](DECISIONS.md).

## Implementation realignment (ROADMAP milestone 4 — the next work)

Realign the implementation with the redesigned script language
and the July 2026 decisions (DECISIONS.md).
planning/design/script-spec.md is the source of truth (full
typed EBNF) with
reliquary/builtins/scripts/freedos-1.4-plain-install.rlqs the
reference script; ROADMAP milestone 4 owns this work, and no
later milestone starts before it lands. No backward
compatibility: the old surface is deleted entirely, not
bridged.

Numbered tasks, in dependency order — the spine is 1 → 2 →
3/4 → 5 → 6; task 9 runs parallel to the spine; 7/8 start once
the parser stack validates scripts; 10–12 close out:

1. Parser retarget, node grammar: rebuild script.py on the
   typed EBNF's three-production skeleton — every line a node
   of name, positional arguments, name=value properties, and
   an optional brace block; the lexer's five spellings
   ("..." guest text, /.../ regex, @name media references,
   $key / ${key} property references, bare words) plus #
   comments. Colon, comma, expect, ->, and regex-keyword
   handling all deleted — the parser should shrink.
2. Parser retarget, vocabulary and node signatures: phase
   (was state), goto (was ->), finish (was done), expect
   folded into the branching wait { on ... }, always for
   reactive handlers (on only in branching waits), set-boot
   (was boot), no <key> tokens (key names only after press);
   the colon-free noun-first headers with entry and the
   run-level deadline; per-node signature validation.
   LANDED as own-lexer + lark parser (owner, 2026-07-22 —
   DECISIONS.md): script_grammar.lark mirrors the normative
   EBNF, reliquary's tokenizer feeds it through a custom lark
   lexer so the lexical diagnostics stay authored, and
   script_parser.py's transformer checks per-node modifier
   signatures and builds the typed tree. The grammar stays
   permissive where an S-rule owns the diagnostic (S8's
   two-handler minimum, S9's phase purity, S11's terminators),
   so tasks 3-4 can cite ids and name the problem.
3. Static validation, shapes and observation channels: the
   two non-mixing script shapes; phases sequential or
   reactive, never hybrid; every sequential phase ends in
   goto/finish; the two-handler minimum in branching waits;
   the screen-default conditions (a bare string or regex the
   only screen spelling — screen= does not exist;
   machine=stopped the only machine spelling — no bare
   stopped); one condition per observation; unknown or
   wrong-kind channels are validation errors.
   LANDED as script_validation.py (owner, 2026-07-22): the
   rules the grammar deliberately does not carry, checked over
   the typed tree, each diagnostic naming the construct and
   citing its id — S3/S10 (the shapes, entry, goto targets), S5
   (unique phase names), S7 (one condition, known channel, right
   kind), S8 (the branching wait's shape and its one-level depth
   limit), S9 (sequential or reactive, on vs always), S11 (the
   terminating-statement rules). Two grammar consequences: a
   handler's condition became optional so `on machine=stopped`
   parses (the normative EBNF always allowed it — the channel is
   part of `condition`, not a modifier) and a bare word is
   admitted as a condition so S7 can name it (`wait stopped`).
   Non-timing modifiers on an observation are channels, not
   signature errors; the timing set stays the node's own.
4. Static validation, timing model: lexically scoped
   timeout/stable defaults (innermost wins), per-activation
   deadline budgets (fresh per phase entry; the header
   deadline backstops the run, and S12 requires one of a
   cyclable phase graph), and the placement matrix enforced as
   parse errors.
   LANDED as script_timing.py (owner, 2026-07-22): resolve()
   computes the plan up front — each observation's effective
   timeout with the scope that supplied it (innermost-wins:
   statement > branching wait > phase > header > built-in 60s),
   each phase's budget, the run's — so the runner is handed its
   bounds and check-script can report them without running
   anything. A branching wait is a real scope level: the
   observations inside its handler bodies inherit its timeout.
   Budgets resolve trivially because they are never inherited.
   The placement matrix stays in the node signatures (a parse
   error, per the task), but each timing rejection now gives its
   reason and cites S2; S5's positive durations and S12's cycle
   check (reachable phases only, naming the route) are in
   script_validation.py with the other S-rules.
5. Runner retarget: rebuild script_runner.py on the new
   graph — phase transitions, branching-wait dispatch,
   reactive run-to-completion dispatch with the
   once-per-episode rearm rule, the timing runtime honoring
   task 4's scoping. Run records keep the superseded
   <timestamp>-<run_id>/ layout (the runs/<n>/ move is
   milestone 7's, run records).
   LANDED (owner, 2026-07-22): script_runner.py rebuilt on the
   typed tree — the phase graph, branching-wait dispatch,
   reactive run-to-completion with the once-per-episode rearm,
   and the clocks read from the parse-time plan, so failures
   already name the expired clock and its source scope (task 6's
   first half falls out of the model). Consequences:
   - script.py is deleted, not bridged; parse_script and
     load_script moved onto the new stack in script_parser.py
     and the exports follow (State/ExpectBranch out,
     Phase/Handler/Property in). test_script.py went with it.
   - a sample reads every channel together, so a branching wait
     can mix screen and machine=stopped handlers; a sample whose
     session is gone IS the stopped observation, and it
     reconciles the machine phase.
   - sessions go through Machine.qmp(), so the runtime verifies
     VM identity (the old runner opened a raw Qmp(port)) and
     never holds a session while a statement list runs.
   - the engine takes an injected clock/sleep: the dispatch
     tests are deterministic and the suite no longer sleeps.
   - properties parse but do not bind: ${key} and insert $key
     raise a named runtime error until the property family
     (milestone 6).
   - NOT YET: the shipped builtins and planning/examples scripts
     are old-surface and no longer parse — task 7.
6. Diagnostics and check-script: failure diagnostics name
   the expired clock and its source scope; check-script
   grows to report the resolved timing plan (each
   observation's effective timeout and source scope).
   LANDED (owner, 2026-07-22): the runner already named clocks
   (task 5); `check_script()` / `rlq check-script` now resolve a
   script read-only (home or builtin, no seeding), print
   `format_plan()` (defaults, phase budgets, every observation's
   timeout and source scope), and with a machine selector also
   run media-slot preflight. Static errors exit 2.
7. Convert the shipped scripts: the builtins
   (freedos-1.4-plain-install, freedos-1.4-verify) and
   planning/examples/scripts/ move to the new surface;
   planning/design/script-examples/design-install.rlqs
   retires into the converted builtins.
   LANDED (owner, 2026-07-22): all four scripts converted and
   parsing; design-install.rlqs deleted, and
   freedos-1.4-plain-install.rlqs IS the reference script now
   (spec status note, ROADMAP, the script-examples README).
   Two things the conversion caught:
   - library.py's insert-media text scan still expected the
     bare media name and captured `@name` with its sigil, so a
     seeded script no longer brought its definition. Fixed to
     match the `@` form only ($key names no static item), with
     a test.
   - the reference-script tests read design-install.rlqs from
     planning/, which is not packaged; they now resolve the
     builtin through reliquary.__file__, so they pass against an
     installed artifact too.
   The examples' install script needed a header deadline it
   never had: its cd-boot <-> partitioning cycle is exactly what
   S12 requires one for.
8. Confirm the portable key vocabulary (the one in-milestone
   confirmation — ROADMAP milestone 4): check the spec's
   closed press key-name set against what the converted
   scripts actually need; adjudicate any gap.
   LANDED (owner, 2026-07-22): the converted scripts need only
   `enter`, already in the published set, so no vocabulary
   change was needed. The confirmation exposed an enforcement
   gap instead: S14 said the set was checked statically, while
   the runner rejected unknown names only after execution began.
   `script_validation.py` now owns the portable set and rejects
   unknown names, bare printable characters, and malformed chords
   during parsing; chords retain their one-character member
   (`ctrl+c`). The QEMU runner now only translates the validated
   language names to backend spellings.
9. CLI/API renames under the twin-name identity rule
   (DECISIONS.md, CLI queue item 14): run-script,
   fetch-media, the seed- family, new-blueprint, import-vm
   --name, check-script, the dashed list-/search- forms, the
   property family noun-last; create_from_blueprint →
   create_machine; machines.start/stop/destroy →
   start_machine / stop_machine / destroy_machine
   (lifecycle.py's legacy start_machine(config) collision
   dies with the root-home model); id-only --machine
   selectors; uniform flag position (the cli.py SUPPRESS
   workaround retires).
10. Documentation sweep: every doc that quotes script syntax
    (README, planning/examples/README); docs/ and
    docs/cli-reference.md follow the CLI renames.
11. Test realignment and the old-surface purge: the test
    suite retargeted to the new parser, runner, and command
    names, then a whole-tree sweep for surviving old-surface
    spellings (state, ->, done, expect, bare stopped, <key>
    tokens, boot, superseded command names) — none survive
    anywhere.
12. Milestone gate: the FreeDOS install and verify scripts
    run end to end on the new surface and check-script
    reports the timing plan (ROADMAP milestone 4's "Done
    when").

Realignment items riding later milestones (kept here so the
umbrella list stays complete; not milestone 4):

- the static-conformance fixture corpus (ROADMAP milestone 5,
  deliverable 6): valid and invalid documents, run against
  both the parsers and the authored JSON Schemas
  (DECISIONS.md, the schema round)
- the error taxonomy under parity (ROADMAP milestone 7):
  ReliquaryError the root; StaticError(2) / PreflightError(3) /
  RunFailure(4) / RunCancelled(5)
- authored-asset residency (ROADMAP milestone 5): the resolution
  module (--assets / --assets-only), the extension renames
  (.rlqb / .rlqm), the builtins/ → codex/ package-dir rename and
  the codex index, the state blueprint-source field, and
  selection scoping
- shared JSONC reader for authored documents (ROADMAP
  milestone 5) — blueprints, standalone media definitions:
  RFC 8259 + // and /* */
  comments + trailing commas, nothing more (no JSON5 features);
  string-aware tokenizer, comments replaced by spaces so error
  line/col survive; every machine-written file stays strict JSON
  (user properties speak their own line format); survey PyPI first, but the published
  JSONC/JSON5 readers looked either too permissive (JSON5
  features the spec excludes) or position-losing, and the
  comments-become-spaces rule that keeps error line/col exact is
  the unusual requirement to check them against
- new media definition surface (ROADMAP milestone 5):
  definition-level description /
  notes / redistributable-under (the built-in URL
  licensing-assertion field), archive-level local-path;
  sourceless definitions fail resolution with the
  edit-the-definition error
- CLI fetch/clean commands + API parity (ROADMAP milestone 5):
  fetch_media(), clean_downloads(), clean_media()
- codex: teaching comments at blueprint seams once the JSONC
  reader lands (ROADMAP milestone 5)
- the hostdir drive content source (vvfat on the QEMU
  adapter — ROADMAP milestone 5)
- user.properties and the property command family (ROADMAP
  milestone 6) — use the `keyring` package for the protected host
  credential store rather than hand-rolling Windows Credential
  Manager / macOS Keychain / Secret Service backends; its
  (service, username) model takes the spec's scoping directly,
  with the properties-file path as the service and the property
  name as the username

## Language

- residual language problems catalogued in
  planning/design/script-examples/*.rlqs (see its README) —
  best-guess priority, fix-cost order, NOT validated against
  real authoring pain; reorder freely once we've actually
  written/debugged scripts under this surface:
  1. [08] reserve the small closed vocabularies (key names,
     drive slots) globally so they can't shadow phase/artifact
     names — mechanical, no spec redesign, also closes most of
     [01]'s asymmetry
  2. [06]'s remaining half: warn when an `@`-reference matches no
     known item (the label/item split itself is gone with the
     media block — DECISIONS.md, no JSON in scripts)
  - [03], [05], [07] — provisionally leave as documented
    tradeoffs, not bugs: boundary tax (guest-text escaping) or
    placement-equals-scope consequences, where a "fix" mostly
    just relocates the mush rather than removing it
  - [01], [02], [04], [09] are resolved (DECISIONS.md: milestone
    zero and the observation-channel decisions); their files are
    regression notes
  - note: several of these are the procedural/declarative seam
    showing through the syntax — see "Primary language goals"
    (G1–G7) and "Procedural and declarative" in ./ROADMAP.md
    before proposing fixes, and judge any fix against the goals
    it costs rather than in isolation
- the full Reason-blockquote editorial sweep of script-spec.md
  remains deliberately open (may trail realignment); the
  error-id INDEX is deferred to beta
- resume the spec-audit workflow (wf_1a266a6b-ff8): the
  AHK/Python failure-catalog studies are complete — imports
  recorded in DECISIONS.md — but their spec audits hit the
  session limit

## U6 authoring recorder

Use case in planning/USE-CASES.md; design in
planning/design/recorder.md. Work items, in rough
dependency order:

- reliquary-owned console viewer over the vnc control plane
  (recording prerequisite: backend display-window input is
  invisible to reliquary)
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
  round; planning/design/landmarks.md) — implementation rides
  the asset spec work
- run-events: handover event kinds (script/human control
  passing); a capture session is one run record with mixed
  drivers
- CLI record command family + API twins land together (parity)

## Watches (re-ask as these harden)

- live-run progress surface (G4 during the run — ties to
  run-events; the USE-CASES feedback split, 2026-07-21, names
  the demand)
- GUI/landmark assets forming a new authored artifact class
  (hardened 2026-07-21: .rlql is the fourth authored extension —
  the INTERFACES listing is due at the asset-spec/realignment
  pass)
- published JSON Schemas elevating reliquary-machine.json into a
  public contract (the blueprint and media-definition schemas
  are authored — DECISIONS.md; the state schema and its
  public-contract elevation stay with milestone 5)
- the adapter API becoming world-facing
  (planning/design/backend-adapter.md is INTERNAL by decision,
  owner 2026-07-21 — a real third-party adapter story elevates
  it into the INTERFACES inventory through the interface-change
  rule, never by drift)

## Wishlist

- allow specifying the cache location outside the home dir
- 'list-blueprints' should announce the blueprints directory on
  its top line (instead of the home-dir announcement)
- new command diff-blueprint <name>: diff the user blueprint
  against the codex blueprint of the same name
- CLI, from cli help: --version should be `version` with an
  undocumented --version/-v alias; -h should be `help` with
  undocumented -h/--help aliases
- 'reliquary -h' should reflect the command as "reliquary",
  'rlq -h' otherwise
- --qemu → --qemu-home
- CLI help: run-script's text says little more than "runs a
  script on a machine"
- an 'inventory' report: every item in the home and cache dirs
  itemized in one way or another (backend implementation files
  ignored — just the presence of a machine is noticed):
  - orphaned listed first (because either you *really* want to
    keep it, or you really *should* delete it): media
    (definitions, not cached payloads), scripts
  - blueprints: materialized (online machines, offline
    machines), unmaterialized
  - media: referenced
  - scripts: orphaned (listed first??), referenced
- README, blueprints and machines: give several clear examples
  to illustrate the concepts — e.g. a 1 MB MS-DOS blueprint;
  QEMU machine #0; QEMU machine #1; QEMU machine #3 with a
  specific floppy image mounted; QEMU machine #4 with 16 MB of
  memory and a specific cdrom mounted
- CLI clean, beyond the settled clean-downloads / clean-media
  invariants: delete completely unreferenced media? all
  downloads? unreferenced only? (machine-cache cleaning is an
  open decision in ROADMAP "Decisions still needed")
