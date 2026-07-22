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
    one JSON document — the twin's-return rule); still unhomed: the
    general stdout/stderr discipline for pretty output across every
    command, and the stability contracts for the rawjson event
    schema and the --json shapes
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
    remaining: records for API/CLI-primitive runs,
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
    public-contract elevation stay with milestone 3)
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
