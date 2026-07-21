<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# TASKS

Small to-do tasks.  Large tasks belong in the roadmap.

- ABSOLUTE PRIORITY #1: realign the implementation with the redesigned script language
  - the July 2026 redesign is decided; docs/script-spec.md is the source of truth
    (full typed EBNF included) and script-examples/design-install.rlqs is the
    reference script
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
    (see ROADMAP.md "Milestone zero — settle the surface"; evidence in
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
      format details, error-id index (beta), full spec document restructure
      (editorial, may trail realignment)
  - timing model: timeout/stable are lexically scoped defaults (innermost wins),
    deadline is a per-activation budget (fresh per phase entry; header deadline
    backstops the run); the placement matrix is enforced as parse errors
  - work items:
    - retarget script.py to the node grammar (parser should shrink: colon,
      comma, expect, ->, and regex-keyword handling all disappear)
    - retarget script_runner.py; failure diagnostics name the expired clock
      and its source scope; check-script reports the resolved timing plan
    - convert builtin scripts and examples/ scripts to the new surface
    - update every doc that quotes script syntax (README, examples/README)
    - no backward compatibility: delete the old surface entirely
  - residual language problems catalogued in script-examples/*.rlqs (see its
    README) — best-guess priority, fix-cost order, NOT validated against real
    authoring pain, reorder freely once we've actually written/debugged
    scripts under this surface:
    1. [08] reserve the small closed vocabularies (key names, drive slots)
       globally so they can't shadow phase/artifact names — mechanical, no
       spec redesign, also closes most of [01]'s asymmetry
    2. [06] default a single-item media block's label to its item name;
       warn when an @-reference doesn't match any known item
    3. [01] RESOLVED (milestone zero): <key> tokens deleted, enter kept
       as a derived form — its file is a regression note
    4. [04] RESOLVED (milestone zero): the on/always keyword split —
       its file is a regression note
    5. [03], [05], [07] — provisionally leave as documented
       tradeoffs, not bugs: boundary tax (guest-text/host-path, string/regex
       escaping) or placement-equals-scope consequences, where a "fix"
       mostly just relocates the mush rather than removing it
    - [09] RESOLVED (milestone zero): boot renamed set-boot — its file
      is a regression note
    - [02] RESOLVED by named observation channels (wait machine=stopped,
      bare string = the screen, its only spelling); its file is a regression note
    - note: several of these are the procedural/declarative seam showing
      through the syntax ([04] especially, [03] and [09] partly) — see
      "Primary language goals" (G1-G7) and "Procedural and declarative" in
      ROADMAP.md before proposing fixes, and judge any fix against the goals
      it costs rather than in isolation
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
    drag deferred; landmarks live only in the catalog, never embedded
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
    miss row, screenshot, and the suggested next command
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
    - three enforcement tiers named once: Legality Rules (script text
      alone) / Machine Rules (needs machine in scope) / Dynamic Semantics;
      short §Processing model (lex - parse - desugar - validate);
      check-script's two modes defined in those terms
    - error classes now, id INDEX deferred to beta: STATIC ERROR /
      PREFLIGHT ERROR / RUN FAILURE (+ exit codes); one id namespace
      (obs.two-channels style) landing WITH the reorg, plus a
      static-conformance fixture corpus
    - derived forms section after the grammar, rewrites over PARSED NODES:
      screen shorthand, enter=>type+<enter>, press=>type tokens, linear
      script => entry + one phase, EOF => finish ("the spec already IS a
      desugaring-based language")
    - normative/informative marked at point of use ("This section is
      non-normative." + Reason blockquotes); signature tables marked
      informative with the grammar named as governor
    - constraint list renamed "Syntactic restrictions" with stable ids
      (S1..Sn) folded together with the static half of the validation list
    - killed by adjudication (do not revisit without new evidence): ISO
      terms clause, five-subheading per-construct template, four-table
      vocabulary appendix, separate image= channel restructure,
      conformance-files-as-spec-content, paragraph numbering
  - AHK/Python failure catalogs captured (studies complete; spec audits hit
    session limit — resume workflow wf_1a266a6b-ff8 after reset); sharpest
    imports: container-determined semantics rule (hits [04] — a construct's
    lifetime should be recoverable from its own text), reserve future
    keyword space now, naming freeze is free before v1 and never after
- GUIDING-PRINCIPLES GAP QUEUE (INTERFACES.md necessity/sufficiency panel,
  adversarially walked per use case; evidence in workflow journal
  wf_92864b8e-623) — verdict: the five primary interfaces are necessary and
  minimal; every gap below is a spec lagging the principles, and this queue
  is the realignment pass's work list:
  - CLI programmatic contract (U3 via CLI; the whole unbound-language path
    rests on it): exit codes, stdout/stderr discipline, output stability, a
    machine-readable mode — pieces already decided piecemeal (error classes
    + exit codes, rawjson renderer, run-events.jsonl) but no contracted
    home; also the interaction command family (type/keys/run/text/wait/
    screenshot/menu/hmp) is absent from the settled CLI list though a
    CLI-driving U3 agent lives on it
  - U2 import: the disk-location choice (leave-in-place vs copy-to-durable-
    base) is the use case's named key decision point but every settled spec
    admits only unconditional copy; `local-path` in the media spec is the
    natural leave-in-place spelling; the CLI shape carries no flag for it
  - U3 run records: only `script` invocations produce a run record — a
    programmatic API/CLI-primitives loop leaves nothing, yet U3 says the
    run record is the product; align with the decided run-events.jsonl
    normative-stream model (every surface a renderer of it) — the
    minimum vocabulary is now normative in script-spec.md's execution
    model (2026-07-21); remaining: records for API/CLI-primitive runs,
    the full renderer contract (transcript rewrite), per-test result
    collection; the
    unit-test loop is now IN U3 itself (amended 2026-07-21: the
    canonical journey uses reliquary twice — define and build the test
    VM, then automate testing inside it; detailed per-test results,
    update a test object, re-run one test or the whole suite; granular
    results and selective re-run are first-class demands) — so the
    run-records design serves a primary use case directly: per-run
    test selection is response data (inputs-as-data holds), and the
    iterate loop needs per-iteration run records plus collected
    results the automator can parse
  - U3 stage/collect: the "declared exchange drive" cannot be declared in
    the decided blueprint drive vocabulary (no directory/vvfat kind), the
    CLI has no file-exchange commands, and only the superseded legacy
    Runner/root-home surface serves injection today
  - U5 blueprint parameterization — DESIGN RECORDED 2026-07-21, owner
    adjudication pending: blueprint `parameters` field (direct value |
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
  - U1 export journey: the easy path lands on QEMU, export targets the
    machine's own backend, cross-backend conversion is open, and QEMU's
    export artifact ("bare image + launch config") is a reliquary-invented
    format with no spec — the default-install-to-VirtualBox journey is
    unresolved
  - ARTIFACT RESIDENCY (use-case amendment 2026-07-21, the split in
    USE-CASES.md; resolution model DECIDED owner 2026-07-21, recorded
    in ROADMAP.md "Authored-asset resolution"): every invocation
    names where authored assets live — the asset root — defaulting to
    the current directory (blueprints/ media/ scripts/ subdirs, the
    home's own layout), falling back to the reliquary home unless an
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
    same-kind stem collisions are errors; reliquary reads by
    extension and writes by convention (home media/ for home-resolved
    installs, beside the script in a project); folded across the same
    docs plus cli.md, builtin-library, README, CLAUDE.md, examples.
    Remaining:
    implementation only (resolution module, extension rename plus the
    builtins/ → codex/ package-dir rename and the codex index, state
    field, selection scoping,
    install targeting), at the residency milestone
  - watches (served but strained; re-ask as they harden): live-run progress
    surface (G4 during the run — ties to run-events); GUI/landmark
    assets forming a new authored artifact class; published JSON Schemas
    elevating reliquary-machine.json into a public contract
  - RESOLVED (July 2026): hand-placed proprietary payloads vs the "cache is
    not an interface" doctrine — local-path (item- or archive-level) is now
    the only hand-supply path; the cache is never hand-fed; a sourceless
    definition pins hashes but fails resolution naming the definition to
    edit (specced in media-spec.md + codex.md)
- SPEC REALIGNMENT LANDED (July 2026), docs ahead of implementation — the
  media/blueprint specs now describe these; implementation work items:
  - shared JSONC reader for authored documents (blueprints, standalone
    media definitions, response files): RFC 8259 + // and /* */ comments + trailing commas,
    nothing more (no JSON5 features); string-aware tokenizer, comments
    replaced by spaces so error line/col survive; JSON islands in scripts,
    the property registry, and every machine-written file stay strict JSON
  - new media definition surface: definition-level description / notes /
    redistributable-under (the built-in URL licensing-assertion field),
    archive-level local-path; sourceless definitions fail resolution with
    the edit-the-definition error
  - CLI fetch/clean commands + API parity: fetch_media(script=),
    clean_downloads(), clean_media()
  - codex: teaching comments at blueprint seams once the JSONC
    reader lands
- U6 AUTHORING RECORDER (use case in USE-CASES.md; design in
  ROADMAP.md "Script authoring by recording") — work items, in rough
  dependency order:
  - reliquary-owned console viewer over the vnc control plane (recording
    prerequisite: backend display-window input is invisible to reliquary)
  - text-mode recorder first (no new language surface: waits from VGA
    scrapes, type/press actions, generated-comment uncertainty flags)
  - runner run-to-point / breakpoint / human-takeover machinery (also the
    failure report's "take over from here" suggested next command)
  - round-trip: fragment emission anchored by playback position; opt-in
    surgical apply at the anchor (never regenerate, never text-merge)
  - landmark catalog shape: variant-as-new-file + capture provenance (feed
    into the pending landmark spec work); GUI capture rides landmark/click,
    a click's position seeds its landmark's spot
  - run-events: handover event kinds (script/human control passing);
    a capture session is one run record with mixed drivers
  - CLI record command family + API twins land together (parity)
- install script output currently is UGLY, it needs to be BEAUTFIUL, TIMELY, and INFORMATIVE
- "rlq script install --blueprint freedos-1.4-plain" should be our north star
  - "rlq --blueprint freedos-1.4-plain script install" is identical 
- allow specifying cache location outside of home dir
- tension between 'media/download' that we need to resolve
  - see 'inventory'
  - we haven't quite nailed the model concepts and their relationships yet:
    - a downloadable (cached) object:
      - can be an item needed at runtime
      - can be an archive containing multiple:
        - item needed at runtime
    - a locally (non-cache) specified object:
      - can be an archive?
      - can be in item needed at runtime
    - when 'cleaning'
      - ?? 
- 'list blueprints' should have a 'NAME' column and announce that these are scripts in <home_script_dir> (top line 
  instead of home dir announcement)
- new command 'diff blueprint <name>' should diff the user blueprint to the built-in blueprint of the same name
- new 'delete <blueprint>' command
  - warn if there are active child machines (wait for confirm or block)
    - if confirmed, stop machines
      - block if can't stop
  - delete machines 
  - delete blueprint
  - check if there are linked scripts
  - if they would be orphaned
    - if they exist (by name) in the codex
      - if there is a script difference between user & codex
        - do not block, do not delete
        - clearly announce not delete script because it is different from the codex version
      - else
        - delete script
- RESOLVED (owner, 2026-07-21): the built-in library is named THE
  CODEX (was "change 'builtin library' concept to 'template
  library' ??"; "canon" was weighed and rejected — codex is the
  artifact, a bound volume copied from, where canon is the
  abstract authority/list) — folded across INTERFACES, USE-CASES, ROADMAP,
  AGENTS, CONTRIBUTING, cli.md, README, and docs
  (builtin-library.md renamed codex.md); reliquary/builtins/
  package dir renames to codex/ at implementation realignment
- CLI do we need these (from cli help)\
  - --platform
  - --version (should be version with undocumented --version -v alias)
  - -h (should be help with -h --help undocumented alias)
- 'reliquary -h' should reflect command as "reliquary", 'rlq -h' otherwise
- --qemu --> --qemu-home
- locks lifecyle I see cache\machines\.locks\<blueprint>.lock"
  - when deleting machines/blueprints, should these be cleaned up?
  - i.e. what is the lifecycle, is this the right location?
- cli help
  - script "runs a scipt on a machine" not much more than that
- we need an 'inventory' report:
  - every item in the home and cache dirs should be itemized in one way or another!
  -  backend implementation files ignored, just the presence of a machine is noticed
  - orphaned (listed first because, either you *really* want to keep it, or, you really *should* delete it)
    - media (specs not cached media)
    - scripts
  - blueprints
    - materialized
      - online machines
      - offline machines
    - unmaterialized
  - media
    - referenced
  - scripts
    - orphaned (should be listed first??)
    - referenced
- readme
  - blueprints and machines
    - give several clear examples to illustrate the concepts
      - e.g. 1mb ms-dos blueprint
        - QEMU machine #0
        - QEMU machine #1
        - QEMU machine #3 with a specific floppy image mounted
        - QEMU machine #4 with 16mb of memory and a specific cdrom mounted
- CLI 'clean', needs some serious thought
  - delete completely unreferenced media?
  - all downloads? unreferenced?
