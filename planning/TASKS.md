<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# TASKS

Small to-do tasks.  Large tasks belong in the roadmap.

- ABSOLUTE PRIORITY #1: realign the implementation with the redesigned script language
  - the July 2026 redesign is decided; planning/design/script-spec.md is the source of truth
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
  - work items:
    - retarget script.py to the node grammar (parser should shrink: colon,
      comma, expect, ->, and regex-keyword handling all disappear)
    - retarget script_runner.py; failure diagnostics name the expired clock
      and its source scope; check-script reports the resolved timing plan
    - convert builtin scripts and planning/examples/ scripts to the new surface
    - update every doc that quotes script syntax (README, planning/examples/README)
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
      ./ROADMAP.md before proposing fixes, and judge any fix against the goals
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
    drag deferred; landmarks live only in the catalog, never embedded —
    AMENDED (owner, 2026-07-21, the wrinkle round below): embedded
    landmark blocks resolve in place; the catalog remains the only
    shared/refresh form and reliquary never rewrites a script
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
- GUIDING-PRINCIPLES GAP QUEUE (planning/INTERFACES.md necessity/sufficiency panel,
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
    collected caller artifacts out, no test vocabulary — G2); the
    unit-test loop is now IN U3 itself (amended 2026-07-21: the
    canonical journey uses reliquary twice — define and build the test
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
    in ./ROADMAP.md "Authored-asset resolution"): every invocation
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
    surface (G4 during the run — ties to run-events; the USE-CASES
    feedback split, 2026-07-21, now names the demand); GUI/landmark
    assets forming a new authored artifact class (hardened 2026-07-21:
    .rlql is the fourth authored extension — the INTERFACES listing is
    due at the asset-spec/realignment pass); published JSON Schemas
    elevating reliquary-machine.json into a public contract (the
    blueprint and media-definition schemas are AUTHORED 2026-07-21 —
    see the JSON-SCHEMA entry below; the state schema and its
    public-contract elevation stay with milestone 3); the adapter
    API becoming world-facing (planning/design/backend-adapter.md
    is INTERNAL by decision, owner 2026-07-21 — a real third-party
    adapter story elevates it into the INTERFACES inventory
    through the interface-change rule, never by drift)
  - RESOLVED (July 2026): hand-placed proprietary payloads vs the "cache is
    not an interface" doctrine — local-path (item- or archive-level) is now
    the only hand-supply path; the cache is never hand-fed; a sourceless
    definition pins hashes but fails resolution naming the definition to
    edit (specced in media-spec.md + codex.md)
- BLUEPRINT-SPEC GAP QUEUE (owner-requested review, 2026-07-21: the media
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
     the source VM free to keep running natively (reliquary-named
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
  5. RESOLVED (2026-07-21): the codex-automation caveat now sits at
     both points of use — the guide's seeding sentence (seeding is
     the human-convenience half of the residency split; automation
     runs --assets-only where the codex is never a resolution tier;
     a project pulls a copy once and commits it) and the media
     spec's home-fallback paragraph (same statement for definitions)
  6. RESOLVED (2026-07-21): all stale machine ids replaced with the
     settled <blueprint>-<n> scheme — the guide's mermaid diagram
     (freedos-0/-1) and state example (msdos-0,
     backend-id reliquary-msdos-0), the cookbook's state example,
     instance-model's state example (freedos-0), and cli.md's two
     hex-id examples (delete refusal now names
     freedos-1.4-plain-0/-1; the ambiguous-prefix example now shows
     'freedos' matching freedos-0 vs freedos-1.4-plain-0). The tree
     half had already RESOLVED with item 1's fold
  7. RESOLVED (2026-07-21): the reference's claim is scoped — a
     media name is the only cross-boundary reference the MACHINE
     SHAPE may make (the drive inventory reaches the media catalog
     and nothing else, U4); the scripts map and parameters property
     references are named as invocation wiring, never machine shape
  8. RESOLVED (2026-07-21): the guide's ownership bullet now carries
     the qualification in place — reliquary reads it and never
     writes it; import/init author one once at the user's request
     and never touch it again, delete (equally at request) removes
     it; ROADMAP's parallel phrase reads "reads it and — once
     authored — never writes it"
  9. RESOLVED (2026-07-21): cookbook example 2's media note
     reanchored to the empty-slot convention — the installer medium
     never appears in the blueprint; the install script inserts
     @freedos-1.4-livecd and ejects it last; the definition/media
     block explanation retained
  QUEUE COMPLETE (2026-07-21): all nine items resolved. Also fixed
  in the 5-9 sweep: the suffix-drop rename had missed the -design.md
  cross-links INSIDE the nine renamed design docs (they were
  untracked when the tracked-files-only sed ran) — now zero remain;
  and the design docs' relative planning-path citations normalized
  to the prose convention (planning/ROADMAP.md, ...)
- CLI DESIGN GAP QUEUE (owner-requested review, 2026-07-21: the complete
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
  12. RESOLVED (2026-07-21): the naming-conventions table now
      shows `.rlqb` / `.rlqm`; the stray hex ids and the
      rlq/reliquary synopsis alternation had already fallen to
      the item-14 fold's rewrites
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
- API DESIGN GAP QUEUE (owner-requested review, 2026-07-21:
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
- GAP-CLOSURE DESIGN QUEUE (owner-requested, 2026-07-21: the five gaps
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
     vocabulary in reliquary (G2) — granularity comes from run
     structure: one iteration = one run record. The
     collect-into-runs/<n>/output/ demand is recorded as input to
     queue item 3. Folded: script-spec "Failure, runs, and
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
     ordinary guest-boundary duty, reliquary never maps guest
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
     entry CLOSED
  4. EXPORT MECHANICS (parent: the U1 export entry + the ROADMAP open
     decision): the two targets (single-drive media image vs
     whole-machine native registration), the exact CLI shape and
     command name, format conversion or not, whether a
     media-referenced drive blocks whole-machine export or
     materializes into it, the cross-backend story for U1's
     install-once-export-to-VirtualBox journey, and the API twin
     (api.md's named omission — name and twin land together)
  5. U5 STATUS CLOSEOUT (parent: the U5 blueprint-parameterization
     entry, "owner adjudication pending"): the recorded design
     predates the property-construct rounds (parameters re-keyed by
     property key, references renamed redirects, the response concept
     deleted); verify the landed shape covers the original gap text
     and close the entry — expected bookkeeping, not new design
- THE USER-PROPERTIES DESIGN ROUND — DECIDED (owner, 2026-07-21,
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
  12. THE FILE FORMAT — strict JSON → the reliquary line format
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
     JSONC work item, script-examples/06 (input → property)
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
- JSON SCHEMAS FOR THE AUTHORED FORMATS — DECIDED (owner, 2026-07-21,
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
    by file association, which tracks the installed reliquary;
    $schema-as-versioned-URL recorded as the leading candidate
    spelling of the version field at beta (ROADMAP "Decisions
    still needed")
  - validator: the parser stays reliquary's validator (fail-closed
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
  - open find, not decided: whether size/base are valid on cdrom
    drives — the reference says size is "meaningful for hdd and
    floppy" without prohibiting it elsewhere; the schemas encode
    only the stated rules (size/base allowed on every drive object)
- SPEC REALIGNMENT LANDED (July 2026), docs ahead of implementation — the
  media/blueprint specs now describe these; implementation work items:
  - shared JSONC reader for authored documents (blueprints, standalone
    media definitions): RFC 8259 + // and /* */ comments + trailing commas,
    nothing more (no JSON5 features); string-aware tokenizer, comments
    replaced by spaces so error line/col survive; JSON islands in scripts
    and every machine-written file stay strict JSON (the user properties
    left the JSON family for their own line format, and response files
    were deleted outright — the format and property-construct rounds)
  - new media definition surface: definition-level description / notes /
    redistributable-under (the built-in URL licensing-assertion field),
    archive-level local-path; sourceless definitions fail resolution with
    the edit-the-definition error
  - CLI fetch/clean commands + API parity: fetch_media(script=),
    clean_downloads(), clean_media()
  - codex: teaching comments at blueprint seams once the JSONC
    reader lands
- U6 AUTHORING RECORDER (use case in planning/USE-CASES.md; design in
  ./ROADMAP.md "Script authoring by recording") — work items, in rough
  dependency order:
  - reliquary-owned console viewer over the vnc control plane (recording
    prerequisite: backend display-window input is invisible to reliquary)
  - text-mode recorder first (no new language surface: waits from VGA
    scrapes, type/press actions, generated-comment uncertainty flags)
  - runner run-to-point / breakpoint / human-takeover machinery (also the
    failure report's "take over from here" suggested next command)
  - round-trip: fragment emission anchored by playback position; opt-in
    surgical apply at the anchor (never regenerate, never text-merge)
  - landmark catalog shape: DECIDED (owner, 2026-07-21, the wrinkle
    round — ROADMAP "Landmarks"): <name>.rlql declaration +
    <name>.<n>.png numbered-adjacency variants, provenance in PNG text
    chunks; refresh stays file-creation-only for embedded landmarks
    too (variants land beside the script); GUI capture rides
    landmark/click, a click's position seeds its landmark's spot
  - run-events: handover event kinds (script/human control passing);
    a capture session is one run record with mixed drivers
  - CLI record command family + API twins land together (parity)
- install script output currently is UGLY, it needs to be BEAUTFIUL, TIMELY, and INFORMATIVE
  - this is the human half of the USE-CASES feedback split (2026-07-21);
    render it from the run-events stream per the decided shape above
- "rlq run-script install --blueprint freedos-1.4-plain" is our north star
  - "rlq --blueprint freedos-1.4-plain run-script install" is identical
    (settled: uniform flag position, CLI queue items 10/14)
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
- BLUEPRINT `name` FIELD DROPPED — DECIDED (owner, 2026-07-21,
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
  column in 'list blueprints'; its other half survives below
- 'list-blueprints' should announce the blueprints directory on its
  top line (instead of the home-dir announcement)
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
