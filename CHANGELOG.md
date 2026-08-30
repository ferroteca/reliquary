<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Changelog

All notable changes to Reliquary are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Fixed

- **A machine that was shut down some other way no longer gets stuck
  reporting `running`, and no longer gets stuck refusing
  `start-machine` because of it.** `machine.json` stores a `phase` field, and until
  now only reliquary's own `start`/`stop` commands ever updated it.
  If a guest powered itself off, or its QEMU process was killed, or
  the host crashed between runs, `phase` was left at a stale
  `running` and nothing noticed unless a script happened to run
  against that machine. Every other command — `list-machines`,
  `start-machine`, `apply-blueprint`, `set-boot-order`,
  `insert-media`/`eject-media`, `exec`/`wait-ready` — trusted that
  stored `running` value without checking it, so a machine that was
  actually down could not be started (it failed with
  `machine.already-running`), could not be reconfigured (it failed
  with `machine.must-be-stopped`), and crashed if you tried to change
  its media, because that tries to talk to a VM that isn't there. All
  of these commands now check a recorded `running` phase against the
  backend directly before doing anything else, using the same
  identity-verified session a script run already opens. If the
  backend confirms the VM is gone (`machine.vm-unreachable`), the
  phase is corrected to `ready` before the command proceeds.
  `list-machines` and the `exec`/`wait-ready` preflight check do this
  without holding a lock, reusing the reconciliation logic already in
  `mark_stopped`. The five commands that change machine state
  (`start-machine`, `apply-blueprint`, `set-boot-order`,
  `insert-media`, `eject-media`) already hold the per-machine lock
  when they run this check, so they can't call `mark_stopped` itself
  without deadlocking on their own lock — they do the same
  reconciliation directly instead. If the check can't confirm either
  way whether the VM is gone, the command reports the phase as
  originally recorded rather than guessing (P11).
- **The QEMU adapter now launches the system binary the guest's
  architecture actually needs** (F64's spike 0). Before this fix, it
  launched `qemu-system-i386` for every machine no matter what the
  blueprint's `platform` field said. For an amd64 guest, that meant
  the kernel triple-faulted on load and the machine reboot-looped
  through its firmware — it never booted, and nothing said why. The
  binary is now chosen from the machine's **declared** `platform`
  field (P10; the code never inspects the disk image to guess). DOS
  and win9x still use `i386` (DOS is tested specifically against that
  binary), while openbsd and winnt now use `x86_64`. If the schema
  allows a platform value that this binary-selection table doesn't
  recognize, the code raises an error instead of guessing, because
  silently picking the wrong binary is exactly what P11 forbids.
- **The start preflight now checks the same binary it is about to
  launch.** `BackendAdapter.discover()` now takes the machine's
  platform as an argument, so QEMU's availability check and its
  `using qemu: …` startup message report the binary for that guest's
  own platform. Previously they always named `qemu-system-i386` even
  when the launch itself used a different binary. VirtualBox, which
  only has one host tool, ignores this argument. This is an internal
  change with no effect on the CLI or API.

- **`rlq wait` now behaves like the script language's `wait` verb, as
  its name always claimed** (D116; T31). The command manifest already
  mapped `rlq wait` to `wait_text` as a documented exception to the
  usual command-name-matches-verb-name rule, but the CLI command
  actually did something different from the script verb: it always
  searched with a regex, across the whole screen joined into one
  string with newlines, without normalizing text, returning as soon
  as it found a match, with no way to wait on the machine's running
  state, and the reference docs described it as `rlq wait REGEX`
  instead of the script language's real syntax. Now the argument is
  parsed the same way the script language parses it: plain text
  (with the shell's quotes stripped) is matched as a normalized
  literal, `/regex/` is a regex, and `machine=stopped` waits on the
  machine's running state. `Machine.wait_text` matches one normalized
  screen row at a time and, once it finds a match, keeps waiting
  until the screen under it stops changing (D115) before returning.
  A timeout now raises `WaitExpired` (D90), same as the script
  language. A new `Machine.wait_stopped` method detects that the VM
  process is gone, so the CLI can wait for a guest power-off and
  update the recorded phase the same way a script does. A `${key}`
  placeholder in the text is rejected, since property substitution is
  a script-only feature.
- **Readiness checks now wait for the screen under the prompt to
  stop changing, not just for the prompt text to appear**
  (D115; T30). `wait_ready` used to return as soon as the bottom row
  of the screen matched a prompt. But `execute` treats a matching
  prompt only as a candidate, and waits until `screen_stability`
  confirms the screen under it has stopped changing, and the script
  language's `wait` verb applies that same rule to every observation.
  Boot screens are the ones most likely to still be changing when the
  prompt text first appears: if `AUTOEXEC.BAT` has `ECHO ON`, the
  prompt and the next command get printed on the same row, so a
  caller that proceeded as soon as it saw the prompt would read a
  command's output before it had finished painting. `wait_ready` now
  applies the same settle check as `execute`, on every control plane,
  and only polls frequently once a prompt is actually on screen. If
  it times out, the error message says whether it saw a prompt that
  then never settled, the same distinction `exec` already reports.

### Added

- **Landmarks: a new `.rlql` file kind, and a new `@name` screen
  condition for scripts** (F65, serving U5). A script could previously
  only wait on a screen it could read as text, so a GUI installer —
  which is exactly what use case U5 needs — was out of reach: the
  text recognizer produces garbage on a screen that was never in text
  mode, and there was no other way to wait on one. A landmark is
  declared once and can have several renderings: `<name>.rlql` is a
  JSON5 file that records the screen's pixel dimensions and can
  include named regions and named spots. Its variant screenshots are
  plain `<name>.<n>.png` files placed next to it, matched by their
  shared name and a number — so adding a new reference screenshot is
  just adding a file, never editing an existing one. Landmark files
  resolve from a `<home>/landmarks` directory, a fixed subdirectory
  like `fonts`, not a new user-configurable root. Landmark names share
  the same collision-checked `@` namespace that media and font names
  already use. Every mistake is caught before a machine even starts:
  a region or spot outside the screen's pinned dimensions, a
  `similarity` value set on an `ignore` region or missing from a
  `fuzzy` region, a percent value outside the allowed `(0%, 100%)`
  range, an unrecognized field, a landmark with no variant screenshot
  at all, and a variant screenshot whose dimensions don't match the
  pinned ones. A JSON schema for the file ships at
  `src/reliquary/schemas/landmark-schema-v1.json`, alongside the
  blueprint schema; `docs/spec/landmarks.md` documents everything a
  JSON schema can't express.
- **A landmark match compares pixels exactly, region by region.**
  Every pixel in a captured screenshot falls into exactly one
  category: an `ignore` region excludes it (and takes priority where
  regions overlap), a `fuzzy` region is judged against its own
  declared percent threshold, and any pixel left over must match
  exactly — this last rule is just what applies to a landmark with no
  regions at all. A variant screenshot matches when all its leftover
  pixels match exactly and every fuzzy region clears its threshold;
  the landmark as a whole matches when any one of its variants
  matches. There's deliberately no single combined score for the
  whole screen: a small mismatched region would get averaged away by
  a large matching area, which would report success against the
  wrong screen and hide exactly where it failed. When nothing
  matches, the failure report names the closest variant by filename,
  lists which of its regions failed, and gives the percentage each
  region achieved, in a new `landmark-miss` field. The reference
  screenshot is converted to the capture plane's own pixel format
  before comparing — a conversion step that is a no-op on every plane
  built so far, but will matter once one uses a different pixel
  format.
- **`@name` can be used anywhere a screen condition is allowed** — a
  plain `wait`, an `on` arm, an `always` handler — and it accepts
  `stable=` and `timeout` like any other screen condition. This is a
  new way of writing the existing, unprefixed screen condition,
  rather than a new kind of condition or new syntax — the language's
  existing extension mechanism is what makes that possible. The kind
  of `@` name is checked wherever it's used: the `@` namespace holds
  three kinds of things (landmarks, media, fonts), so each usage site
  now checks that the name it references is the right kind, and
  reports both the name and the mismatch if not. This adds
  `landmark.wrong-kind`, and also adds the same check in the other
  direction as `media.wrong-kind` and `font.wrong-kind` — previously,
  a landmark name used in an `insert` or `font` statement was
  reported as an undeclared name instead of a kind mismatch.
  `--dry-run`'s timing plan now names the specific landmark each
  observation is watching.
- **Whether a machine can support a landmark condition is now
  checked per-condition, before it runs.** A landmark condition needs
  to capture the framebuffer, so the backend-adapter interface gained
  a new method, `capture_format(plane)`, which reports the pixel
  format a given control plane's screen carrier captures in, or
  `None` if that plane doesn't capture a framebuffer at all (the
  default, so a backend has to opt in rather than accidentally claim
  support). A session on a plane that reports a format gains a
  `framebuffer()` carrier alongside the existing `text_screen()`
  carrier. QEMU's agentless-display plane reads characters the guest
  has already resolved out of VGA text memory, not pixels, so it
  reports no format, and a landmark condition on that plane is
  refused before any input reaches the guest, with the error
  `machine.plane-no-framebuffer`. QEMU's VNC plane and VirtualBox's
  display plane both capture an actual framebuffer and report `rgb`.
  A script that never uses a landmark condition is unaffected — the
  plane is never asked. The `screenshot` verb and the automatic
  screenshot taken on failure use a separate mechanism and keep
  working on every plane.
- **The screen-settling check (`screen_stability`) now works on
  pixels as well as text cells.** A landmark comparison works on
  captured pixels, which have no text cells, so `screen_stability`
  now also accepts a captured frame and measures the proportion of
  *pixels* that stayed the same — using the same time window, the
  same default threshold, and the same repeated-change mask as the
  text-cell version. Its `Reading` result now records which unit it
  counted, so a timeout message says "pixel" when it was counting
  pixels. A wait that only checks a landmark condition skips the text
  recognizer entirely, since matching glyphs would be wasted work on
  a screen it's not going to read as text.
- **What this change deliberately leaves out.** There is no `click`
  command and no pointer input yet. Named spots are parsed and
  validated because the file format needs to be settled and a
  recorder already writes them, but nothing reads a spot's value yet.
  Since no command can move the guest's cursor yet, a captured
  screenshot and a keyboard-only run always agree by construction; the
  rule for where to park the cursor before a screenshot will be added
  along with pointer support, and is only described in the docs for
  now, not enforced in code. Selecting regions on screen is also
  deferred. A recorded transcript stores character rows and attribute
  data, not pixels, so a landmark wait recorded in a transcript can't
  be replayed, and replay reports that by name instead of fabricating
  a screen to match against.
- **Pointer input: a new `pointer_event` carrier, a `tablet` pointing
  device, and a new `click` script verb** (F66, split out of F5,
  serving U5). The backend-adapter interface gained one new method,
  `pointer_event(x, y, buttons)`, which sends RFB's own `PointerEvent`
  message on the VNC plane's wire, alongside the existing `KeyEvent`,
  with no translation needed. Everything built on top of it reuses
  existing pieces: `click @landmark` and
  `click @landmark spot="name"` find a landmark using F65's matcher,
  send a left click at one of its declared spots, and park the
  cursor afterward. Coordinates are always framebuffer pixels, the
  same coordinate space a landmark is defined in, so no separate
  scaling is needed.
- **`pointing-device` is now a machine field**, set to `tablet` or
  `mouse`, checked against backend capability at assignment time the
  same way `drives` already is — if a blueprint declares `tablet` and
  the assigned backend can't supply it, assignment fails, naming both
  the backend and the missing device. Every platform still defaults
  to `mouse`, the standard relative pointing device every machine
  already has. QEMU renders `tablet` as
  `-usb -device usb-tablet,id=pointer0` and reports both device types
  in its capability report. `click` refuses to run, before doing
  anything, on a machine whose `pointing-device` is `mouse`, naming
  the reason: an absolute click position needs an absolute pointing
  device, and reliquary won't guess a calibration against a relative
  one (P10).
- **`click` gets the same before-it-runs capability check landmark
  conditions do, plus one more.** `click` needs everything a landmark
  condition needs (framebuffer capture) plus the ability to deliver a
  pointer event on the control plane driving the machine. This is a
  separate question from framebuffer capture, since a plane can have
  one without the other — VirtualBox's display plane captures a
  framebuffer today but has no pointer delivery wired up. This is
  reported by a new adapter method, `pointer_capable(plane)`, which
  defaults to `False`. `click`'s own `spot=` argument is checked too:
  if the landmark declares exactly one spot, `spot=` isn't needed; if
  it declares more than one, `spot=` is required; and naming a spot
  the landmark doesn't declare is refused, naming the missing spot.
  All of this is checked before the machine starts.
- **`click` searches for its target using the same machinery as
  `wait`, not the same machinery as `select`.** `select` searches by
  scanning text inside a single console call; `click` instead does a
  real landmark pixel match, using the same settle-gated polling that
  `wait @landmark` already uses. So a `click` on a landmark that
  never appears times out with the statement's own timeout, and no
  pointer event is ever sent. Like `select`, `click` is timed in two
  parts: an `Observation` for the search and an `Input` for the click
  itself, and it appears as two separate steps in the resolved
  execution plan.
- **Every pointer verb parks the cursor in the bottom-right corner
  after use**, and that parking spot is always excluded from landmark
  matching as a built-in `ignore` region — scaled to each landmark's
  own screen size rather than a single fixed pixel position, since
  most content is anchored top-left and a fixed position could land
  on real content at a different resolution. This exclusion happens
  on the host side, by masking that region out of the comparison;
  reliquary does not negotiate an RFB option to keep the cursor out
  of the framebuffer capture itself.
- **This first version supports only a single left click.** Adding a
  `button=` argument, a `count=` argument, or a separate drag verb
  are all possible future additions with no concrete need for them
  yet; the underlying `pointer_event` method already accepts any
  button mask and could support any click sequence, so none of that
  future work would require touching a backend adapter. The recorder,
  VNC support on the other backends, and relative-mouse input are all
  out of scope for this change.
- **Per-drive QEMU options can now be set through the existing
  machine-level `backend-settings` escape hatch** (D118). A separate,
  drive-scoped `backend-settings` section was considered and rejected:
  QEMU's own `-set drive.<slot>.<option>=<value>` syntax can already
  target one specific drive using the section that already exists.
  Every drive the adapter renders now includes `id=<slot>` (hard
  disks previously did not), and the existing overlap check now
  understands `-set`: a `-set` targeting a property that `drives`
  already renders — `file`, `if`, `index`, `media`, `id`, `format`,
  `bus`, or `unit` — is refused, naming `drives`, the same as setting
  `-drive` directly would be. Options like `cache`, `aio`, `discard`,
  and `serial` remain free for the caller to set. The blueprint
  reference documentation now shows this pattern.
- **New CLI command `rlq wait-ready`, matching `Session.wait_ready`
  in Python** (D114; T29). `AgentlessGuestExec.wait_ready` was only
  callable from Python, which violates P6's rule that nothing should
  be reachable from Python but not from the CLI. The closest existing
  CLI equivalent, `rlq wait "C:\\\\>"`, is actually a weaker check: it
  matches that pattern anywhere on screen, not the same readiness
  check `wait_ready` performs. `rlq wait-ready` is the same
  precondition `exec` already requires, exposed as its own command —
  meant to be run once, between `start-machine` and the first `exec`
  call. Its `--timeout` and `--prompt` options mirror the Python
  method's parameters, and it runs the same preflight checks `exec`
  does (guest is DOS, machine is running, identity is on record).
  It's declared in the command manifest, so the test suite checks
  that the CLI command and the Python method behave the same way. A
  readiness timeout is now raised as `WaitExpired` (D90) everywhere:
  as a `RunFailure` with exit code `4` from the CLI, and as Python's
  `TimeoutError` too, since the boot might still finish later. The
  README and `docs/dos-automation.md` now teach `wait-ready` in the
  places that used to teach the regex-based wait.
- **`wait_ready` now accepts a `prompt=` argument, for guests with a
  customized prompt** (D113; T28). `AgentlessGuestExec.wait_ready`
  only recognized the standard DOS prompt. D112 made `execute` work
  with a guest whose prompt is customized, but the documented
  readiness pattern — call `wait_ready`, then `execute` — still
  failed on the very first call for that same guest. The caller can
  now say exactly what the ready prompt looks like — the literal text
  the guest draws on its bottom row, e.g.
  `wait_ready(prompt="[C:\\]>")` — mirroring how the script
  language's own `wait "C:\>"` works. `None` keeps checking for the
  standard prompt shape, and a timeout now names which prompt text it
  was waiting for. A blueprint field for this, treating "screen
  stopped changing" as readiness on its own, a regex-based version,
  and retiring `wait_ready` in favor of `wait_text` were all
  considered and rejected. The README and `docs/dos-automation.md`
  show this new argument and point to `wait_text` as the general
  authored wait.
- **A `share` device can now be served over virtio-9p, and that is
  what a share with no stated `model` gets on QEMU** (F69). A share
  presents a host directory to the guest for as long as the machine
  runs; until now the only mechanism behind it was `model: vvfat`,
  QEMU's synthesized FAT volume, which takes a snapshot of the
  directory when the machine starts — so a change on either side only
  became visible across a stop/start. A `9p` share is live in both
  directions instead, at the cost of a 9P driver loaded in the guest
  (virtio-dos ships `VIO9P` for DOS; loading it is the user's job, the
  same as a packet driver). It renders as `-fsdev local` plus a
  `virtio-9p-pci` device, with the slot key as the guest-visible mount
  tag, and it is not a disk, so adding one never shifts a guest's
  drive letters. Leaving `model` out means the backend's own live
  mechanism, never silently the snapshot one, so an unstated-model
  share — which had no live default to resolve to and so was refused
  on every backend — now works on QEMU.
- **QEMU's share capability is probed on the installed binary rather
  than claimed** (F69). fsdev/9p is a QEMU compile-time option, and
  the official Windows binaries are built without it, so an adapter
  claiming 9p on the strength of its own code would be promising
  something a given install cannot deliver. The adapter asks the
  binary — one `-device help`, looking for `virtio-9p-pci` — and
  reports what it found. On a QEMU without it, a `9p` share and an
  unstated-model share are both refused by name at assignment, naming
  the missing capability, the same way any other capability failure
  reads; `model: vvfat` is unaffected, since vvfat is in every build.
  Because QEMU installs a separate system binary per guest
  architecture, the probe is run against the binary the machine's
  `platform` will actually launch: the capability report and the
  requirements check both now carry that platform, the same way
  backend discovery already did.
- **A share's `read-only` media flag is now honored.** It maps onto
  each mechanism's own option — QEMU's `fat:` prefix without `rw:`
  for a `vvfat` share, `readonly=on` for a `9p` one — so a share
  declared read-only protects the host directory from the guest
  instead of being silently ignored. The flag is recorded on the
  machine's resolved share entry, since a backend renders from that
  and never sees the media.

### Fixed

- **`exec` now finds a command's echo even when it wraps onto more
  than one screen row.** A command longer than the screen is wide —
  85 columns, easy to reach with a path plus arguments — would run on
  the guest but `exec` refused it with `screen.no-echo`. This
  happened because the echoed text wraps at column 80, so no single
  screen row ends with the full command text, and the old scan only
  looked for a row ending with the whole command. The scan now
  reconstructs the line the guest actually wrapped: it matches the
  end of the command against the row it thinks is the last line, and
  checks that each row above it holds exactly a screen-width's worth
  of the command's text. A row only counts as a continuation of the
  command when its content really is the command's own text. If a
  wrap happened to fall on a space character (which trailing-space
  stripping would otherwise hide), the missing space is restored from
  the original command text rather than read off the screen. Row
  width is read from the frame's own attribute data, which every
  current backend provides one token per cell; a frame that doesn't
  provide attribute data can still only find an unwrapped echo, and
  says so instead of guessing (P11). The
  `freedos-exec-wrapped-echo.rlqt` transcript, which had recorded the
  refusal, has been re-recorded against the fixed code, and is
  removed from the transcript corpus README's list of known gaps
  (issue #8).

- **`exec` now identifies a command's echo by its position on
  screen, not by matching its text** (D111; issue #7). If a file's
  last line happens to look like the echo of the command that
  printed it — for example `C:\>TYPE C:\ECHOLIKE.TXT`, where that
  exact text is also printed by `TYPE`'s own output — the old
  backward scan, which just looked for a row ending in the command
  text with a `>` in it, matched that output line instead of the
  real echo. `exec` then returned an empty result with no error at
  all, which is exactly the kind of silent wrong answer P11 forbids.
  The fix: a command is typed at the prompt the guest was sitting at,
  so its echo is that same prompt row with the command text appended,
  and it sits at the same screen position the prompt was at. The rows
  above the echo are recognized as whatever was above that prompt
  before, minus anything that scrolled off since. A row that merely
  contains matching text, with the command's own output printed above
  it, is never mistaken for the echo. Running the same command twice
  correctly finds the second echo, for the same reason. The
  echo-lookalike transcript has been re-recorded against the fixed
  code and now correctly returns the file's three lines.

- **`exec` now also recognizes completion at the prompt the guest was
  already sitting at, in addition to the standard prompt shape**
  (D112; issue #9). Before this fix, `exec` only recognized the
  standard prompt pattern `X:\path>`, so a guest whose `AUTOEXEC.BAT`
  sets `PROMPT [$P]$G` never matched, and every command waited out
  its full timeout — the guest was unusable from the first command.
  Now, whatever prompt the guest was showing when the command was
  sent counts as valid completion evidence on its own, whatever its
  shape — this is the guest's own statement of what its prompt looks
  like, so it needs no pattern to be declared. The standard prompt
  shape is still also recognized, because that's what lets a command
  like `CD` complete even when it changes the prompt's text. **There
  is one known limit**: a command that changes a customized prompt —
  `PROMPT` itself, or `CD` while a customized prompt is active —
  returns to text that `exec` has no prior evidence for, so it times
  out. The timeout message now names both prompt shapes it was
  waiting for, so this can be diagnosed without inspecting the guest.
  A blueprint field to declare the prompt pattern up front was
  considered and rejected, since nothing currently needs it. A new
  transcript, `freedos-exec-at-custom-prompt.rlqt`, records `VER`
  succeeding at the `[C:\]>` prompt; the existing `PROMPT [$P]$G`
  transcript still records the timeout as the documented limit.
  `wait_ready` — the readiness wait in the Python API, which the
  guides recommend calling before `execute` — still only recognizes
  the standard prompt shape, since it has no earlier screen to read a
  customized prompt from. That remaining gap in the public API is
  tracked as **T28**.

### Changed

- **`destroy-machine` now stops a running machine first, instead of
  refusing to run** (S1, S2). Previously, running `destroy-machine`
  on a running machine failed with `machine.must-be-stopped`, telling
  the caller to run `stop-machine` first — but `destroy` can just as
  well do that itself, the same way `restart-machine` already starts
  a machine that's stopped. The per-machine lock is now held across
  both the stop and the destroy, the same way `restart-machine` holds
  it across its own stop and start, so nothing else can touch the
  machine in between. If the stop itself fails closed — for example,
  an identity mismatch — the machine is left `running` and the error
  is raised rather than destroying anything. As always, the CLI
  command and the Python API change together (P26).

## 0.1.0a3 - 2026-08-22

### Added

- **A new VNC control plane on QEMU, handling the screen and
  keyboard** (F63; D110), serving **U5**. Setting
  `control-planes: ["vnc"]` in a blueprint now works end to end on a
  QEMU machine: starting the machine adds a loopback-only VNC server
  on an allocated display (`-vnc 127.0.0.1:<display>`, with no
  authentication, since the endpoint only accepts local connections
  and identity checking is handled separately by the management
  interface). The VNC port is recorded in the VM's identity record
  alongside the QMP port, and is probed under the same startup
  deadline as everything else. A session on a machine using this
  plane reads the screen from the RFB framebuffer through the same
  fixed-font recognizer the VirtualBox display plane already uses,
  and sends keystrokes as RFB key events, translated from QEMU's
  qcode key names to X11 keysyms. Media changes still go over QMP,
  and identity is still verified over the QMP session before the RFB
  socket is even opened — `query-vnc` cross-checks the VNC port QMP
  reports against the one that was recorded. Nothing changes inside
  the guest, so this plane stays as agentless as the default plane
  (P2). The VNC wire protocol is implemented as a small in-tree RFB
  3.8 client (`src/reliquary/rfb.py`): it uses security type None
  (no auth), forces a 32-bit true-colour pixel format, only supports
  Raw framebuffer updates (no compression), and sends `KeyEvent`
  messages. This needs no new dependency, and does not yet send
  `PointerEvent` messages — that arrives with the pointer feature.

- **The `control-planes` list in a blueprint is now an ordered list
  of preferences, not just a set of requirements** (F63; blueprint
  surface S4,
  [docs/spec/blueprint-model.md](docs/spec/blueprint-model.md)).
  The requirement check is unchanged: every plane listed must still
  appear in the assigned backend's capability report, or assignment
  fails, naming the plane and the backend. What's new is that the
  **first** entry in the list is now the one actually used: the
  session's screen and keyboard access come from whichever plane is
  listed first. The default list is still `["agentless-display"]`,
  so existing blueprints behave the same as before. QEMU's capability
  report now includes `vnc`; on every other backend, declaring `vnc`
  still fails assignment, since they don't support it.

- **A new codex script can pull the character font a DOS guest has
  actually loaded** (F62; D109), completing use case **U25** —
  promoted to the root [USE-CASES.md](USE-CASES.md) list in this
  change (D34); F61 already delivered the other half of it. The BIOS
  call `INT 10h AH=11h AL=30h` with `BH=03h` returns a pointer to the
  *live* 8x16 character table the guest currently has loaded, not a
  fixed address in ROM — all 256 glyphs, 4096 bytes total. Because
  the result depends on what a particular guest loaded, this dump is
  a codex script (`freedos-dump-font.rlqs`) rather than something any
  one author's script should have to reimplement. It works by typing
  a short stub into `DEBUG`, which is already on the `PATH` of every
  codex FreeDOS install: the stub makes the BIOS call, copies the
  character table to a fixed offset in its own memory segment, and
  writes it out. Nothing is staged into the guest ahead of time, and
  nothing is left behind once the stub has run and the machine is
  shut down (P2, P3).

  **The dumped bytes are written out through a drive the blueprint's
  author supplies.** The codex blueprint itself declares no such
  drive (P16, D108) — pointing to a host directory is a decision each
  author makes for their own blueprint — so the script writes the
  output through the `floppy0` slot, whose DOS drive letter (`A:`) is
  fixed regardless of whatever else is attached to the machine. If a
  blueprint never added that drive, the script doesn't silently
  succeed by writing into thin air — the write fails the same way
  writing to an empty floppy drive always fails in DOS, and the run
  stops there with that error (P11). A drive backed by a host
  directory has no image file for a live insert or eject to check
  against, so there's no cheaper way to detect the missing drive than
  letting the guest's own DOS report the failure.

- **A guest's own font can now be declared as an asset, and a script
  can tell reliquary to read the screen with it instead of the
  host's** (F61; D109). The agentless display plane used to read
  every screen using only the *host's* hypervisor fonts
  (`text_recognize.banks_from_binary`). If a guest loaded a font of
  its own — for example, a localized installer drawing text in a
  codepage the host doesn't offer — the recognizer read the screen
  using fonts that didn't include those characters, and a `wait` on
  that screen would time out. The fix is a new file kind, `<name>.rlqf`:
  a JSON5 file placed next to its matching `<name>.bin` binary font
  dump, resolved from a `fonts/` directory under the home directory
  (`docs/spec/asset-resolution.md`), and sharing the same
  collision-checked `@` namespace that media names already use. The
  `.rlqf` file records what the raw 4096 bytes alone can't say: the
  character cell layout (256 glyphs of 16 rows, or 512 glyphs of 8
  rows — both are 4096 bytes, so the byte count alone can't tell them
  apart) and which codepage its character indices mean, decoded using
  Python's own codec registry. `font @guest` is a new script
  statement: from that point in the script forward, that font is used
  first; a second `font` statement replaces the first rather than
  adding to it; and it's deliberately not a `with`-scoped block, since
  choosing a font doesn't change anything on the machine and so there
  is nothing to undo when the scope ends.

  **Which font wins a match is now a real priority order, not just a
  tie-breaker.** The recognizer used to pool every font's glyph shapes
  together and pick whichever single shape, from any font, was
  nearest to what's on screen — with declaration order only breaking
  ties. Under that scheme, naming a font could only ever add one more
  candidate that might beat the correct glyph from another font. Now
  the recognizer tries each font bank in order and stops at the first
  one whose best match is within the matching distance threshold.
  That's what makes naming a font actually narrow down the answer,
  and makes it well-defined which codepage applies to a given font.
  The host's own built-in fonts keep exactly the same matching
  behavior as before, so no existing recorded transcript, test
  fixture, or corpus entry had to change for this. When the wrong
  font is used, the failure report now says so: its count of unread
  cells now also lists which fonts the last read attempt was matched
  against, in the order they were tried (P11).

  This change is the whole delivery of use case **U27** — promoted to
  the root [USE-CASES.md](USE-CASES.md) list in this change (D34) —
  and half of **U25**, which stays open until F62's DOS-side font dump
  (above) lands alongside it.

## 0.1.0a2 - 2026-08-19

### Added

- **The interpretation layer has a conformance corpus** (F43), and
  it is the first one built from fixtures nobody hand-wrote: seven
  `.rlqt` captures of real FreeDOS runs against QEMU — the three
  codex scripts and four ordinary commands — replayed in the default
  suite through the shipped `control_display`, `interaction_agentless`
  and script dispatch, with no hypervisor needed. Each fixture checks
  itself by replay: a call the capture never saw counts as an error,
  every call the capture recorded must actually happen, and the
  replay must reach the same conclusion the capture recorded.

  **This is also how a captured wrong answer becomes a fixture**, and
  three of the four command captures do exactly that — they record
  bugs `rlq exec` currently has. Today, `rlq exec`: refuses a command
  longer than 80 columns (`screen.no-echo`, because the echoed
  command text wraps onto more than one row, so no row *ends* with
  it); returns an **empty result with no error** when the command's
  own output happens to end with a line that looks like the echoed
  command — a file whose last line reads `C:\>TYPE C:\ECHOLIKE.TXT`
  is enough to trigger this, which breaks the spec's promise of "the
  command's own output or a failure"; and never completes against a
  guest whose `PROMPT` has been customized, because the
  prompt-matching pattern does not allow for a custom suffix. None of
  these three bugs is fixed here — deciding what counts as a DOS
  prompt, or as an echo, is a design decision, not something a test
  fixture should settle on its own — and each fixture is written to
  fail loudly, flagging itself for an update, once the underlying bug
  is fixed.

- **A script that calls a stopped-only verb while the machine is
  running is now rejected before it runs at all** (T27; V17).
  `set-boot`, and F54's scoped `boot` head, write the firmware's boot
  order, which can only be changed while the machine is stopped.
  Before this change, calling one of these verbs while the machine
  was running failed at **run** time, with the machine's own error —
  and for the typical shape that triggers this (change the boot
  device, start the machine, install, stop it, change the boot device
  back), run time could mean five minutes into an install.

  **The script's own text already tells you this will fail.** The
  script's header declares the machine's starting state, and the
  language already knows which verbs start and stop the machine, so
  the check now runs at parse time instead, exiting with code `2`
  before anything reaches the guest. A `with` scope's **exit** is
  checked along with its entry — the exit is the half an author is
  least likely to think about, since it is reached both when the
  script finishes normally and on every failure path — and this is
  the check F54 had left for this analysis to add.

  **This check only catches what a static pass can prove, and stays
  silent everywhere else.** Whether control reaches into a handler
  body depends on the guest, so nothing inside a handler is checked
  this way, and a phase reached only via a handler is not analyzed —
  that is the same boundary `reach` already draws elsewhere. Handler
  bodies are still walked to see what *effect* they have on the
  machine, and if two paths through the script disagree about the
  machine's state, the check gives no verdict at all. For example, a
  `wait machine=stopped` that completes means the machine has been
  observed stopped, so scripts that power the guest off from inside a
  handler and then wait for it still work correctly. Wrongly rejecting
  a valid script would be worse than the late failure this replaces,
  so the old run-time refusal is kept as a fallback for anything the
  static check cannot prove safe.

  The error reported is unchanged — it is still the machine layer's
  own `machine.must-be-stopped` — so code that checks for this error
  id does not need to know which layer caught the problem.

- **New `with` block: a machine-state change that undoes itself when
  the script leaves that part of the script** (F54; U24, U26, D104).
  A script's `insert`, `eject` and `set-boot` verbs change the
  machine and leave it changed; until now, the author had to write
  the code to undo them by hand, and any failure path that skipped
  that code left the change in place. A `with` block wraps a change
  in a scope, and **leaving the scope undoes the change**:

  ```rlqs
  with boot cdrom0 {
      phase startup { … }
      phase cd-boot { … }
  }
  ```

  Only three verbs can head a `with` block. `insert` and `eject` are
  written exactly as they would be as ordinary statements, and behave
  with their own signatures and their own preflight checks. The third
  is **`boot`, not `set-boot`, and it only states a prefix**: the
  drives named come first, followed by the machine's own existing
  boot order — so `with boot cdrom0` on a machine whose order is
  `["hdd0", "cdrom0"]` boots as `["cdrom0", "hdd0"]`, and the author
  never has to restate the part of the order they are not changing.
  `set-boot` itself is unchanged and still means full replacement.

  A `with` block wraps whatever unit the surrounding script is built
  from — phases in a phased script, statements in a linear one —
  which gives the language a way to mark off a *stage* of the script.
  **The scope tracks where control currently is, not where the text
  is written**: it is active while control is inside the block, is
  entered whenever control reaches any phase inside it (including via
  a `goto` from outside the block), and is left when control reaches
  a phase outside the block or the run ends; re-entering the block
  re-applies the change. Treating the block as purely lexical instead
  would have undone the change again at the very next phase
  transition, since every phase body ends by transitioning to another
  one — so this behavior is deliberate, not the naive alternative.

  **On exit, the target returns to the value it had on entry**, no
  matter how the runtime leaves — `finish`, a failure, or a
  cancellation at a boundary. **Restoring the boot order requires the
  machine to be stopped**, because the boot order can only be changed
  while stopped, and undoing it is not given an exception to that
  rule — so if the scope is exited while the machine is running, the
  run fails and names the change it could not undo. Restoring media
  has no such restriction. **A machine can only have one active scope
  per target** (boot order, or a given drive); scopes on different
  targets can nest freely. Entering and restoring a scope are recorded
  on the run's event stream (`scope.enter`, `scope.restore`), and a
  failure report lists every restore that was performed — information
  a diagnostician would otherwise have had to work out by hand.

  **The shipped FreeDOS blueprint and script were updated to use
  this.** `freedos.rlqb` now declares `boot: ["hdd0", "cdrom0"]` —
  reflecting what the machine actually is, a system that boots its
  own disk and only falls through to an empty optical drive — and
  `freedos-install.rlqs` wraps its phases in `with boot cdrom0`,
  keeping its mid-install `eject`. An interrupted install no longer
  leaves behind a machine that boots its installer disk forever.

  Not yet checked statically: if a boot-order restore is *provably*
  reached while the machine is running, that is currently still a
  run-time failure rather than something rejected when the script is
  authored. Moving that check to parse time depends on T27's
  reachability analysis, and will reuse it once it is available.

- **`.rlqb` blueprint files now use the standard JSON5 grammar**
  (F53; D102), replacing the project's own JSONC-like dialect. This
  means comments, trailing commas, unquoted keys, single-quoted
  strings, and hexadecimal and signed numbers are all allowed, along
  with the rest of the published JSON5 grammar. `NaN`, `Infinity`,
  and `-Infinity` are rejected so that parsed values stay ordinary
  JSON data. Diagnostics still point to the exact source location of
  the problem. Files Reliquary writes itself are still strict JSON.
  The reader is implemented in `json5reader`, built on the
  Apache-2.0-licensed `json5` package.

- **New `restart-machine` command** stops a machine if it is running,
  then starts it. This is the normal thing to do while iterating on a
  script, and until now took two separate commands. It runs as
  **one operation, not two**: the per-machine operation lock is held
  across both the stop and the start, so nothing else can start the
  machine, change its media, or apply a blueprint in between. This is
  not a new kind of lock — it is the same lock every command that
  changes the machine already takes, just not released partway
  through — and it is what stops a restart from finishing on a
  machine someone else has since started, which would otherwise fail
  with `machine.already-running`. If the machine is **already
  stopped, `restart-machine` just starts it** instead of refusing —
  the goal is to end up *running*, so the result does not depend on
  which phase the machine happened to be in, and a machine caught
  mid-`stopping` is settled into `stopped` first. `restart-machine`
  takes `--display` and a positional id, like the other machine
  commands; the `Session` method is `restart_machine`.

- **New `list-backends` command** reports which backends were found
  on the host and each one's installation home directory. It is
  CLI-only; `--json` returns the same `{backend, home}` records for
  scripts to consume.

- **VirtualBox now supports agentless display, and can run the
  FreeDOS scripts** (F52, split off from F3 along with F50/F51). The
  VirtualBox backend gained `keyboardputscancode` for keyboard input,
  `screenshotpng` for screen capture, the ability to change a mounted
  medium live, and `text_screen` (via F51's recognizer below) —
  after which it can claim the `agentless-display` capability. An
  opt-in integration test exercises it against a real FreeDOS guest:
  set `RELIQUARY_INTEGRATION=1` and run
  `tests.test_freedos_virtualbox_integration` (it pins
  `backend: virtualbox` on the seeded blueprint).

  **This was demonstrated against a live VirtualBox on 2026-08-13**:
  the unmodified codex script installs FreeDOS 1.4 from the LiveCD,
  partitions the disk, reboots, formats it, installs the system,
  boots the installed system through to a `C:\>` prompt, and powers
  the guest off — then the verify and ready scripts reboot it and
  hand it over. The bugs that first live run found are listed in this
  release's Fixed section.

- **New fixed-font text-screen recognizer** (F51, split off from F3
  along with F50/F52). `text_recognize` turns a PNG screenshot into
  the same `(rows, attribute tokens)` shape that the rest of the code
  expects from a text-mode screen, using Reliquary's own CP437-layout
  8x16 glyph bank. Fixtures under `tests/fixtures/text_recognize/`
  test it end-to-end with no hypervisor needed.

- **New VirtualBox lifecycle support and VDI disk creation** (F50,
  split off from F3 along with F51/F52). This is the first backend
  adapter besides QEMU: `backend_virtualbox.py` finds `VBoxManage` on
  the host, creates VDI disk images (as a `new` disk, a
  `difference` disk, or a `copy`), registers the VM under
  `cache/machines/<id>/virtualbox/` the first time it is started, and
  starts and stops it while checking the VM's UUID matches what
  Reliquary expects. The VMware and Hyper-V backends remain stubs.

- **New `delete-script` command removes a script.** It removes a
  script file from the home's `scripts/` directory, and refuses to
  do so while any blueprint still refers to that script, naming each
  blueprint that does. The error ids `script.unknown` and
  `script.has-blueprints` work the same way as the existing
  `blueprint.unknown` and `blueprint.has-machines`.

- **New command manifest lists every command in one place.** The
  package ships `schemas/command-manifest.toml`, which is the
  authoritative inventory of every command surface (P6): each
  capability is declared once, with the CLI command name and its
  `Session` method name derived from that single declaration, the
  command families and their documented exceptions to CLI/session
  parity recorded as data, and every public name classified. The
  test suite checks both the CLI and the `Session` API against this
  file in both directions (`tests/test_command_manifest.py`). The
  prose specs still describe behavior and design — `cli.md` and
  `api.md` remain the source of truth for that — but for the
  question of what commands exist, they defer to the manifest.

- **New `stability=` option makes `wait` conditions ignore a screen
  that is still changing** (F48, building on F47's stability
  measure). A condition can happen to match while the screen is
  still being drawn, and that is exactly the moment a `wait` should
  not act on. The existing `stable=` option only controls how long a
  *match* must hold before the wait is satisfied — it did nothing to
  guard the *individual frame* a condition was checked against. With
  `stability=` set, a frame that scores below the given threshold is
  now skipped entirely — none of its conditions are evaluated, and in
  a branching `wait` none of its handlers run. Unlike `stable=`,
  which is a duration, `stability=` is a proportion (0 to 1), and it
  is inherited the same way `timeout` is — a statement's own setting,
  else a branching `wait`'s, else the phase's, else the header's,
  else the built-in default of 0.99 — so **an ordinary script never
  needs to write it at all**. That default follows from the screen's
  geometry: one row of an 80x25 screen is 4% of the whole screen, so
  any threshold looser than 0.96 would treat a screen as settled
  while a line was still being drawn, while small moving elements
  like a 1-cell cursor or an 8-cell clock cost an order of magnitude
  less than that. Setting `stability=0` turns the check off for a
  single observation, at no cost.

  **This deliberately changes when existing `wait`s fire** (P8):
  every `wait` now behaves as if it had a clause its author never
  wrote. Two rules limit the effect. The check **never causes a
  wait to fail on its own** — if it was never able to measure
  stability at all, the condition is judged on whatever frame is
  available, so a wait with a short timeout still works, and the
  existing guarantee that "a timeout means samples were taken, not
  that nothing was ever checked" still holds. And when a wait times
  out because the screen it saw was still moving, the timeout
  message **says so**, naming the stability score it actually
  reached, instead of looking identical to an ordinary timeout. This
  does not replace `stable=` — the two check different things, and
  only `stable=` catches a screen that has gone quiet but is showing
  text that is about to be overwritten.

### Changed

- **The remaining test modules are converted to native pytest style**
  (F60, the last of these conversions; D106). The remaining twenty
  modules are converted — the CLI and documentation-example tests,
  the core helpers, the home and asset machinery, the media path, the
  guard checks, and the two modules that test the repository itself
  rather than the installed package. **No `unittest.TestCase` and no
  `subTest` remains anywhere in the suite**, so there is nothing left
  for the style policy to exempt, and `python -m unittest tests` no
  longer works as a way to run the suite: with nothing left for it to
  collect, it would report success while running nothing at all.

  **No test assertion changed.** The suite now reports **2,102 tests,
  up from 2,016** (2,140 before the drive and file commands were
  removed, see below). Most of that increase comes from the command
  manifest: its declared capabilities, family members, and exceptions
  are now each their own reported test case, where before one test
  method covered all of them — and likewise, every documentation
  example is now its own named test case, named for the document and
  position it comes from.

- **The machine and backend test modules are converted to native
  pytest style** (F59, building on F55; D106). Ten modules are
  converted — machines, the `Session` wrapper, events, properties,
  both backend adapters, the display/input seam, the drive layer,
  screen stability, and the recognizer. The setup code they shared is
  now pytest fixtures: one `rig` fixture builds the temporary home
  directory, the fake adapter, and the blueprint files that the
  machine layer's tests need, so each test states what it is testing
  rather than how its home directory was built. **No test assertion
  changed**, and the suite now reports **2,016 tests, up from
  1,901**.

  **The two backends are now tested against one shared contract**
  instead of by a separate, near-duplicate set of test methods for
  each (**P25**). Everything a backend adapter owes to the
  display/input seam — the backend name it answers to everywhere, its
  capability report, its image file extension, how it reports itself
  found or not found, the host font it reads and caches, and its
  refusal to control a VM whose recorded identity does not match — is
  written once and run against both backends, so a requirement can no
  longer be tested for QEMU while silently missing from VirtualBox's
  tests. Each backend supplies a **driver** to this shared contract —
  where its executable is found, where its font lives, how it detects
  a mismatched stop — and a third backend adapter would inherit the
  whole test contract just by supplying one.

- **The script-language test modules are converted to native pytest
  style** (F58, building on F55; D106). Its seven modules — the
  runner, the parser, the node layer, validation, timing, labeled
  wiring, and the dry run — now use plain `assert` statements, pytest
  fixtures in place of `setUp`, and `parametrize` in place of loops or
  `subTest`. **No test assertion changed**, and the suite now reports
  **1,901 tests, up from 1,825**: each of the 76 additional tests is a
  case that was already being checked, just inside a loop that
  previously reported as a single pass for all of them together.

  **The static-analysis rules are now checked from one table of
  cases** instead of one test method per rule. Each case names the
  rule it exercises and becomes its own named test node — for example
  `pytest -k V10-goto-undeclared` selects just that one case while
  it's being fixed — and a parametrized check walks the entire
  id-to-rule mapping, so a rule the language gains with no matching
  case now fails as a named missing case, instead of silently passing
  because nothing was counting it. This gives unit-level rule checks
  the same guarantee the conformance corpora already give fixtures.

- **The opt-in FreeDOS integration tests are now excluded by a pytest
  marker instead of skipped at run time** (F57, building on F55;
  D106). The two opt-in FreeDOS integration tests now carry
  `@pytest.mark.integration` and are **excluded from collection**
  unless `pytest --integration` is passed, so the default test run
  now reports **no skipped tests at all**, where it previously
  reported two. The `RELIQUARY_INTEGRATION` environment variable is
  retired as the gate for these tests; `RELIQUARY_INTEGRATION_HOME`
  is kept, and is now read by the `integration_home` fixture instead
  of at import time.

  A skipped test does not distinguish between "this was deliberately
  excluded" and "this failed to run" — which is why the suite used to
  assert a specific skip *count* just to guard this tier. The marker
  now records the reason directly, so that skip-count check is no
  longer needed, and any skipped test anywhere in the suite is now
  unambiguously a problem. Explicitly asking for the integration tier
  on a host without the right backend now fails with a message naming
  the missing backend, instead of silently passing — since asking for
  that tier means the tests were expected to actually run.

- **pytest is now the test runner** (F55; D106). The suite runs under
  `pytest`, which is added alongside `jsonschema` in the `dev`
  dependency group as a hard requirement, and `python -m unittest
  tests` is no longer the way to run it. **No test changed**: pytest
  collects the existing `unittest.TestCase` classes unchanged,
  `unittest.mock` is still the mocking library used, and the run
  covers the same tests, with the same two opt-in integration tests
  held out.

  This switch fixes a gap the standard library's `unittest` could not
  catch. A conformance corpus of 135 fixtures, run via `subTest`, once
  ran only against the parser and not against the schema, despite
  claiming to check that the two cannot drift apart — because a
  `subTest` loop reports the same single pass whether it checked all
  135 fixtures or silently ran only half of them. Once each fixture is
  a separate, parametrized pytest node, it is individually collected
  and its own pass or fail is the check. (Converting the actual test
  modules to this style is separate work, described below.)

  The project's `[tool.pytest.ini_options]` setting turns **plugin
  autoloading off**, and pins `testpaths`, strict config and marker
  handling, and a minimum pytest version. The suite ships inside the
  sdist (D105), so it needs to collect the same way in a packager's
  environment as it does here.

- **The conformance-fixture corpora are now parametrized pytest
  tests** (F56, building on F55; D106). Every fixture under
  `tests/fixtures/conformance/` is now its own collected test node,
  **named for its file**, in each check that runs against it, and the
  expected count of fixtures in each bucket is **pinned at the point
  where the fixtures are gathered up**. A corpus directory that fails
  to load is now reported as a collection error instead of a run that
  passes over nothing, and a single fixture being fixed can be run on
  its own by name, e.g. `pytest tests/test_script_corpus.py -k
  v7-no-condition`.

  This fixes the same kind of gap that motivated switching test
  runners. The blueprint corpus was, in practice, run only against
  the parser and not against the schema, despite claiming to check
  that the two cannot drift apart — because a loop over fixtures
  inside one `subTest` test reports a single pass whether it actually
  checked all of them or silently only half. A check that
  **partitions** a bucket of fixtures by a marker had the same failure
  mode on a smaller scale, so `// warns:` and `// schema: rejects` are
  now each asserted, in both directions, by one check that runs over
  the whole bucket rather than by two checks that each only see half
  of it.

  Both corpora are now read through one shared helper, `tests/corpus.py`,
  instead of each having its own file-globbing code — so this
  guarantee belongs to the shared test harness rather than to a
  particular fixture-file format, and a third corpus would get the
  same guarantee just by calling the same two functions. The suite
  now collects **1,827 tests, up from 1,310**: the checks being made
  are the same ones as before, but now the count of collected tests
  proves how many of them actually ran.

- **The source distribution (sdist) carries the test suite again**
  (D105). An sdist is the artifact a stranger builds *and verifies*
  from, and downstream packagers run the upstream test suite at
  package-build time — on platforms and interpreters this project
  never tests itself, which is the whole benefit of shipping it.
  Unpack `reliquary-<version>.tar.gz` outside the repository, put
  `src` on `PYTHONPATH`, and `pytest` runs **2,048 tests and deselects
  two** — the opt-in FreeDOS integration tests, one per backend,
  exactly as it does inside the repository.

  The suite is included **whole, not partially**. Setuptools' default
  sdist rules only pick up the top-level `tests/*.py` files and skip
  the fixture directories nested underneath them, which would ship a
  suite that looks complete but cannot actually verify anything.
  `tools/check_dist.py` now lists every fixture directory that must
  be included, and fails the release build if one of them goes
  missing.

- **Tests that read files from the repository itself are now kept
  separate from tests of the installed package, and only the second
  kind is shipped.** The new `tests/source_tree/` directory holds the
  documentation-example checks and the check for old, now-removed
  module paths: both of these read prose files, maintainer records,
  and the open-problem catalogue, none of which are part of a
  released package. If shipped as before, these tests would have
  found no `docs/` directory and no `AGENTS.md` in the installed
  package, checked only a fraction of what they were written to
  check, and still reported success — so they are kept somewhere they
  cannot run at all, rather than somewhere they would run without
  actually testing anything. Two `skipUnless` guards travel with
  them, and the total skip count is now the same two everywhere the
  suite runs.

- **`docs/` no longer ships inside the source distribution.** The
  prose documentation belongs to the repository, and what a consumer
  of the package needs already travels in the package's distribution
  metadata. The sdist now contains 257 files, down from 280 in the
  previous release, and carries a test suite that actually runs,
  instead of documentation nobody builds against.

  Unchanged in both directions: the **wheel** still carries no tests
  — 59 files, just the runtime code and its package data — and
  **`planning/` ships in neither the sdist nor the wheel**, since it
  is maintainer-facing project governance, not anything a consumer
  runs.

- **The machine layer and the CLI entry point are reorganized
  internally; nothing a user or embedder relies on moved.**
  `machines.py` used to hold two modules' worth of code plus shared
  groundwork: the drive layer — the drive report and the five
  in-band file commands, both since removed (see below) — is now
  `drives.py`, and the machine ids, directories, locks,
  `machine.json`, and selector resolution are now `machine_state.py`.
  `blueprint.py` and `script.py` are merged into `authoring.py`, which
  is the counterpart to `assets.py`. `machine.py` is renamed
  `machine_handle.py`, matching the package's convention of naming
  its core engine modules in the plural. `cli.py`'s `main()` now
  builds its commands through per-family builder functions, and the
  set of commands it recognizes is derived from the parser instead of
  being listed again separately.

  **Every documented surface is unchanged, and this was verified, not
  assumed**: the same 50 exports from the package root, the same
  `Session` methods, the same commands, flags, and exit codes, and
  `rlq --help` plus every subcommand's `--help` output is
  byte-for-byte identical to before. Machine state, error/rule ids,
  and the working-directory layout are unchanged, so no existing
  home, blueprint, or machine needs to be recreated. The one case
  this affects is an embedder that imports *past* the package root —
  importing `reliquary.machine`, `reliquary.blueprint`, or
  `reliquary.script` directly by module path. Those module paths no
  longer exist; the names they used to hold are available the same
  way they always were, from the package root and from `Session`
  (P26).

- **`--record` is now refused when combined with `--dry-run`**
  (S1, S2; P11), failing with exit code `2` and error id
  `progress.record-on-a-dry-run`. Previously it was accepted but did
  nothing: a dry run never starts a machine or reads a screen, so
  there was nothing for the recorder to capture, and it gave no
  indication that the flag had been ignored. This puts `--record` in
  the same category as `--display`, `--expect`, and a non-default
  `--progress`, which a dry run has always refused for the same
  reason — accepting a flag that has no effect is exactly the kind of
  misleading behavior P11 forbids. The check lives in `run_script`,
  so both the CLI's `--record` flag and the API's `record=` argument
  get it from the same place.

- **CLI list tables are now rendered with the Rich library**, giving
  consistent column alignment and text wrapping in the terminal. Long
  paths, addresses, property values, and other wide values now wrap
  onto multiple lines instead of being cut off. Machine listings now
  lead with the machine ID column; listings that include descriptions
  place them in a wrapping column on the same row. Terminals that
  support UTF-8 get rounded table borders; other encodings fall back
  to plain ASCII borders.

- **Disk images local to a machine now live in `disks/`** instead of
  `media/`, under each machine's own `cache/machines/<id>/` directory.
  The separate, shared cache of downloaded media is unaffected and
  stays at `cache/media/`.

- **`stop-machine` and `destroy-machine` now both accept an optional
  positional machine id** (`rlq stop-machine <id>` is a shorthand for
  `rlq stop-machine --machine <id>`; `destroy-machine` already worked
  this way). `--blueprint` and `--machine` still work as before.

- **`--backend` on `create-machine` now overrides the blueprint's
  `backend` field when the machine is created**, pinning the backend
  the same way declaring it in the blueprint does — the named backend
  must be installed and must support what the blueprint needs, or
  machine creation fails. It is no longer restricted to `--dry-run`
  only: under `--dry-run`, the question stays "would the blueprint
  work with this backend", so a missing or incapable backend is
  reported as a result rather than raised as an error. The old
  `machine.backend-outside-dry-run` guard, which used to reject
  `--backend` outside of `--dry-run`, is removed.

- **A blueprint's `scripts` map is now read each time a script is
  run, instead of being copied into the machine's saved state**
  (D101). This matches what `docs/spec/cli.md` always said — that a
  script label is looked up in *the blueprint's* map — and is the
  same assumption the blueprint-`parameters` design was already
  written on. Previously, the map was copied into `machine.json` when
  the machine was created, so a machine could not run a script label
  its blueprint gained later, until an `apply` was run — even though
  nothing about the machine's shape actually needed updating. Since a
  script label just names which instructions to run rather than
  describing what the machine is, `scripts` is now excluded from the
  "shape" that `apply` compares, exactly as `parameters` already was.

  **This has two visible effects.** `scripts` no longer appears in
  the published machine-state schema, and editing a blueprint's
  script map no longer marks machines built from it as diverged.
  Machines created before this change still carry a saved digest that
  was computed including the now-removed field, so the first `apply`
  run after upgrading will detect a difference that is not really
  there, reconcile it, and re-save the digest without that field —
  this is a one-time stale value of the kind already covered by the
  pre-1.0 compatibility rule, not a real migration.

- **The menu-selection code no longer has its own separate logic for
  detecting when a screen has settled** (F49). `_settled_screen`'s
  wait-for-two-matching-reads check and `_menu_baseline`'s learned
  mask of animated cells were both hand-tuned special cases of the
  general stability measure added in F47. Both are now replaced with
  calls to that shared measure, and the menu-specific copies are
  deleted, leaving one implementation used by all three call sites.
  Menu behavior is unchanged — the cursor-menu test suite is what
  this change was checked against, and it still passes unchanged —
  and two things get better as a side effect: the shared measure does
  not need a quiet moment on screen before it can learn which cells
  are animated, and decoration that *starts* partway through showing
  the menu is picked up within a few samples, where the old
  once-learned mask would never have picked it up at all. What is
  left in the menu-selection code is only what was never about
  settling in the first place: whether a keypress changed anything on
  screen, and which row the highlight moved to.

- **`exec` now waits for the screen to stop changing before reading
  it** (F45, building on F47's new stability measure). A DOS prompt
  can appear on screen mid-scroll, or the bottom row can briefly look
  like a prompt while output is still being drawn; the check for
  whether the command had finished used to accept the first frame
  that looked like a finished prompt, and return output cut off at a
  point that did not actually mark the end of the command's output —
  a result that looked plausible but was wrong. A prompt is now only
  treated as the command being done once the screen under it has
  stopped changing. **What `exec` returns is unchanged in the cases
  where it was already correct** — this only changes timing: it makes
  the spec's rule, "completion means the command finished, not just
  that a prompt is visible," actually hold, rather than changing what
  that rule means. This adds roughly 200ms per command to confirm the
  prompt is stable, and does not change the polling backoff — the
  extra time is spent confirming a prompt that already appeared,
  never waiting on one that has not appeared yet. If a wait times out
  after seeing a prompt that never stabilized, the timeout message now
  says so, naming the stability score it reached instead of stabilizing.

- **Listings now show each item's description** (D97, resolving the
  deferred item D88, tracked as T8). Wherever a listing's items have a
  `description` field — `list-codex`, both forms of `list-scripts`,
  and `list-blueprints` — the human-readable listing now prints it
  beneath the entry, indented and wrapped, rather than never showing
  it or showing it as a table column; an entry with no description
  contributes no extra line. `list-blueprints` rows in `--json` output
  now include `description` and `platform`, so the JSON record holds
  the same information the human-readable listing shows. This
  restores U11's promise that a user can read a description at the
  keyboard, not only by parsing `--json` output.

- **All embedding-API access now goes through `reliquary.Session`**
  (P26). A `Session` is opened on a home path or a `Context` — which
  now also carries the selected properties file — and refuses to be
  constructed without a home. **This is a breaking change for every
  embedder, with no aliases or compatibility shims** (the project
  makes no backward-compatibility promise before 1.0): the
  module-level functions (`create_machine`, `run_script`,
  `fetch_media`, the property functions, the listing functions, and so
  on) are removed from the package root and are now `Session` methods
  instead; the directory-selection global state, its `set_*_dir()`
  setter functions, and `adopt_environment()` are deleted; the
  per-call `context=` and `properties_file=` arguments are removed
  from every public function, since that is now fixed when the
  session is opened; and the library itself no longer reads any
  environment variables — the CLI reads `RELIQUARY_*_DIR` and
  `RELIQUARY_PROPERTIES` itself, when it constructs its own session,
  so other programs using the library must choose these explicitly.
  The old `dir.unassigned` error, previously raised the first time an
  unset directory was used, is retired in favor of failing when the
  session is constructed — the error id itself is unchanged. **The CLI
  itself is unchanged**: same flags, same environment variables
  honored, same default home directory, same exit codes. The types,
  the errors, `Context`, `default_home_dir()`, the standalone parser
  functions, and the guest-console family (`Machine` and its module
  functions, which are addressed by a machine's own directory rather
  than through a session) remain importable exactly as before.

### Removed

- **Reliquary no longer reads or writes files inside a machine's
  disk volumes, and the drive-letter mapping that supported it is
  removed** (D108). Seven commands, along with their `Session`
  method equivalents, are deleted outright rather than deprecated:
  `describe-drives`, `refresh-drives`, `put-file`, `get-file`,
  `put-files`, `get-files`, and `list-files`. Removed along with
  them: drive-letter-to-drive mapping, guest file-path parsing, the
  recorded drive report (the `volumes` and `geometry` fields in
  `machine.json`), the ability to read a disk image's filesystem
  while the machine is stopped, and the `at_rest` / `at_rest_write`
  backend capability flags. Reliquary still declares a machine's
  drives, creates their disk images, and swaps their media —
  **what is inside a disk volume is now up to the caller**, using
  the caller's own tools to reach it.

  **Three ways to move files across that boundary remain**, none of
  which requires Reliquary to understand a filesystem: attaching a
  host directory directly as a drive (directory-source media),
  `insert-media --file` to swap in a whole disk image live (U20,
  unchanged — its size-limit check only looks at the file's size, and
  never reads inside the volume), and `get-machine-dir`, which
  returns the machine's own directory on the host and is now the
  supported way to reach machine files rather than just a
  convenience.

  **The `remanence` dependency is removed** along with the code layer
  that wrapped it; it is also the tool a consumer should use directly
  if they need to read a file out of a disk image themselves. Outside
  of `qemu.qmp`, every remaining runtime dependency is now tier 1.

  The project's stated goals and specs are updated to match: **U14**
  no longer describes file access as a Reliquary feature, **P16** now
  explicitly carves out file content as outside Reliquary's scope
  rather than leaving it as a gap, and **P17** and **P27** are struck
  out. The previously pledged **F41** (which would have expanded file
  access) is withdrawn.

  **All seven of the affected `.rlqt` transcript fixtures were kept,
  and two of them had to be re-recorded against a live FreeDOS guest**
  to make that possible, since both relied on the removed file
  transport. `freedos-ready.rlqt` captures a codex script whose text
  had to change, and `freedos-exec-echo-lookalike.rlqt` used to be set
  up by having the host write a file directly onto the guest's disk;
  now the guest types that file in itself, using `COPY CON` (the only
  way to do it from inside the guest, since DOS command redirection
  cannot produce the `>` character that the last line of the file
  needs to contain). **The resulting screen is byte-for-byte
  identical**, so what the fixture checks is unchanged: `rlq exec`
  still returns an empty result with no error for a file whose last
  line looks like the echo of the command that printed it. Removing
  the file-access transport did not cost the corpus anything.

- **`Session.set_machine_var` is removed** — this is a bug fix, not
  a deprecation. Machine variables are meant to be a one-way channel
  for the guest to report information to the host: a script's `set`
  verb writes them, and the host only reads them, via
  `get-machine-var` / `wait-machine-var` — which is what the CLI spec
  has always said: "writing is the script verb's job, and the host
  side only reads." The removed session method let host-side code
  write into that channel too, which was wider than the verb it was
  meant to mirror: it could write a variable outside of any script
  run at all, and could be used to make it look like the guest had
  reported something it had not — and since no script can observe a
  machine variable being set, this could not trigger anything in a
  running script either, so it served no purpose. The engine still
  has its own internal writer, used by the script runner; there is no
  longer any public way to write a machine variable from outside a
  script.

### Fixed

- **`--record` now actually captures everything it is supposed to.**
  This fixes six bugs in the recorder, all of which could only be
  found by taking a real capture of a real FreeDOS install (F43). The
  **`screenshot` verb bypassed the recorder** by building its own
  machine handle instead of using the recorded one, so the one call
  both codex scripts make to capture the screen was missing from
  every recording. **The machine being powered off was never
  recorded**: the code that checks the machine's identity when a
  session is opened runs before the recording wrapper is set up, so
  when a guest powered itself off, opening the next session refused
  outright — meaning every recording stopped at the shutdown step
  every DOS install ends with. And **the recording pace setting had
  no effect at all** — the code took the larger of the recording pace
  and the normal polling interval, which meant it always used the
  normal two-second idle poll interval that the recording pace is
  meant to override. As a result, a five-and-a-half-minute install
  used to capture only 536 screens; it now captures 2,847. (The other
  three bugs — the recording wrapper being applied to a frozen
  dataclass, an inverted keyframe check, and a frame counter that
  collapsed to counting only one sample — were fixed as they were
  found.)

  A recorded run now genuinely behaves **differently** from an
  unrecorded one, and always did: each QEMU sample taken is a
  4000-byte memory dump, and taking one ten times a second, as
  recording now correctly does, makes an install run two to three
  times slower. This denser polling gives strictly more information,
  which is the tradeoff the recording feature was designed to make;
  the resulting transcript records the pace it was captured at.

- **A screen cell where nothing matched no longer looks the same as
  a cell that was actually read.** The recognizer only accepts the
  nearest glyph match when it is close enough to be trustworthy, and
  substitutes a blank space otherwise, since guessing the wrong
  character is worse for a `wait` condition than leaving it blank —
  but this substitution used to happen silently, so a screen drawn in
  a font the host did not have simply looked *sparse*, with no
  indication anything had gone wrong. A `wait` for a word on such a
  screen would time out with nothing useful to show, and the failure
  report's "nearest miss" row was being compared against text that
  had never actually been read. This silent behavior is also what let
  the font bug described below go unnoticed for as long as it did.

  `recognize` now returns a `Screen` that also carries `unreadable`,
  a list of the `(row, col)` position of every substituted cell. Code
  that unpacks or indexes the result as the existing
  `(text_rows, attribute_rows)` pair still works unchanged, so nothing
  that reads a screen needs to change — but the fact that some cells
  were unreadable now reaches callers that never touch pixels
  directly: `rlq screen` now reports when part of a screen could not
  be read, and a script's failure report now says how many cells were
  guesses. This turns "the text never appeared" into "the text may
  have been there but could not be read", which are different
  problems needing different fixes. Both stay silent when nothing was
  unreadable, and a backend that reads resolved characters straight
  out of guest text memory (rather than recognizing glyphs from
  pixels) never marks anything unreadable, since it has nothing to
  misrecognize. Reading a guest's screen is fundamentally a
  measurement, and a measurement that reports no confidence value
  cannot be told apart from an accurate one — but this new information
  is meant only as a signal to help diagnose problems, never as a pass
  or fail verdict on its own, since a BIOS splash screen is
  legitimately unreadable and is already a sample that `wait`
  conditions are expected to skip past.

- **The recognizer now checks every font a screen could have been
  drawn with, instead of assuming one.** It used to check against a
  single glyph bank chosen ahead of time, but there is no single
  correct choice: more than one font can be painted onto the screen
  during a run, and a screenshot does not say which font the VGA
  hardware was actually using at the time. A VGA BIOS installs its
  own glyph bank, with an override table applied, and draws its own
  messages using that; a DOS guest loads its own font and draws with
  that instead. The two fonts a stock VirtualBox install offers
  differ in 19 glyphs — including `W`, `m`, and `T` — so whichever one
  the recognizer assumed, roughly half of every run was misread:
  `Welcome` came out as `Uelcooe` through one font, and `Trying next
  boot device` came out as `Irying` through the other. This first
  looked like a difference between emulators, but it was not — both
  QEMU and VirtualBox install the identical font once VirtualBox's
  stored glyph bank is combined with its own patch; the two are byte
  for byte the same.

  `bank=` now accepts either one font or several (`as_banks`), and
  scores each screen cell against all of them. Since an override
  table only changes a glyph's shape and never what character it
  represents, the closest-matching glyph across all the fonts always
  gives the same recognized character no matter which font actually
  drew it — this needs no state, and makes no guess about which font
  is currently loaded. Glyph shapes shared between the fonts are
  merged rather than duplicated, so the added cost tracks how much
  the fonts actually differ: 275 glyphs to check instead of 256, about
  a 5% slowdown per read. `banks_from_binary` collects every glyph
  bank found in a backend's own installed binaries, **plus every
  variant that its override tables would produce**, by recognizing an
  override table purely from its shape — ascending character codes,
  no blank glyph, and terminated by a zero code byte, while skipping
  tables meant for other glyph heights — so an installation with a
  different set of fonts is still read correctly on its own terms.

  **Fonts are extracted from the installed backend on first use and
  cached, never bundled with Reliquary itself**, as
  `cache/support/<backend>/cp437-8x16-banks.bin`, holding however many
  fonts that particular installation provides. Like everything else
  under that cache directory, it can always be regenerated, so a
  truncated cache file is simply re-extracted rather than causing an
  error, and a cache hit never touches the installation again. The
  cache directory now reaches the backend adapter through
  `Machine(cache=)`, which passes it to `adapter.session(vm, cache=)`
  — a new, optional parameter on the adapter interface: passing `None`
  just means the fonts are re-extracted each time, which costs speed
  but never correctness. Not bundling the fonts is a licensing
  decision as much as an engineering one — these glyphs belong to
  whichever emulator the host has installed. A stock QEMU install
  yields just one font, with its glyph bank already including the
  overrides merged in.

- **The glyph bank Reliquary ships is the project's own font again,
  not an extracted copy of someone else's.** `fonts/cp437_8x16.bin`
  had become bytes copied directly out of a host's installed QEMU
  `vgabios`, while `REUSE.toml` recorded it as authored by Paul
  Galbraith under `GPL-3.0-only` — claiming authorship over bytes
  nobody on this project actually wrote, and content that fails
  D82's test for what can be included (*could this ship inside a
  proprietary product?*). The font is now produced again by
  `tools/gen_cp437_font.py`, which draws its own glyph shapes; the
  extraction script that had overwritten it is deleted. The original
  hand-authored font had a bug that likely motivated the switch to
  extraction in the first place — 62 character codes were never
  drawn, came out as blank cells, and were then indistinguishable
  from a space character, so they could never be recognized. Those
  undrawn codes are now filled in with a computed Reed-Muller
  codeword, sharing 64 of 128 pixels with every other glyph in the
  set: **all 256 codes are now visually distinct**, up from 254 in
  the extracted font it replaces. This font is `recognize`'s default,
  and what `render` uses to draw test fixtures — it is never what
  reads an actual running guest — and it no longer tries to pass as a
  real VGA font: it deliberately does not contain the classic VGA
  capital-A glyph shape (`CLASSIC_A`) that code elsewhere uses to
  locate a genuine VGA font bank inside a binary, so a test that
  specifically needs a real-VGA-like font says so explicitly and uses
  a different one (`tests/vga_bank.py`).

- **VirtualBox sessions now ask the hypervisor directly whether a VM
  is actually running, instead of finding out only when a command
  fails.** `showvminfo --machinereadable` reports a `VMState` field,
  which the session already fetched to check the VM's identity but
  then discarded — so a powered-off VM, which stays registered and
  responds to queries just as readily as a running one, would still
  let a session open successfully, and every subsequent command
  against it then failed with `machine.backend-failed`. This meant
  `wait machine=stopped` could never actually succeed on VirtualBox:
  the script runner treats `machine.vm-unreachable` as its signal
  that the machine has stopped, but nothing ever raised that specific
  error, so a script's normal ending — power the guest off, then wait
  for the machine to stop — aborted the whole run instead of
  finishing normally. A session now refuses to open at all for a VM
  VirtualBox reports as no longer running, and each command now
  re-checks the VM's state if it fails, closing the window where a
  guest could power itself off in the middle of a session. The check
  looks for the specific **stopped** states (`poweroff`, `aborted`,
  `aborted-saved`, `saved`, `teleported`) rather than checking for
  "not running", so a VM that is transitionally `starting` is never
  mistaken for powered off, and a machine that is still booting is
  never incorrectly marked as stopped.

  The same missing check also left machines stranded outside of a
  script run: `stop-machine` used to fail on a guest that had already
  powered itself off, `destroy-machine` would then refuse because the
  recorded phase still said `running`, and without `--force` the only
  way out was deleting the machine's directory by hand. An
  unreachable VM is now treated as a successful stop — since the
  adapter looked for the VM and could not find it running, which is
  exactly the state `stop-machine` is trying to produce — and this is
  handled at the shared backend layer so it works the same way for
  every backend, including QEMU's case of a dead QMP port. An
  identity mismatch, or a port that responds but with the wrong
  answer, is treated as a different, still-failing condition.

- **A boot menu with a countdown timer could time out before it was
  ever pressed.** `cursor_menu_select` used to spend
  `_BASELINE_READS` worth of reads learning which screen cells
  repaint on their own, before sending its first keypress — at
  roughly 2 seconds per read on a screenshot-based backend, this
  could take longer than a boot menu's own countdown timer, so the
  function would time out the very menu it was trying to control, and
  fail with "menu item is not on screen" while its failure screenshot
  showed a fully booted system. This was not simply a matter of being
  slow: those reads exist specifically because a screen cell that is
  changing (like a countdown number) can't be recognized as harmless
  decoration in fewer reads than that, so the function was spending
  exactly the time it had before the countdown ran out on learning
  about the very countdown that was running out. `select` now presses
  a key immediately if the item it wants is already visible on
  screen, and only takes the full set of baseline reads when it is
  not.

- **The shipped FreeDOS codex blueprint now boots from the installer
  medium first.** `boot` is now `["cdrom0", "hdd0"]`, and the install
  script now ejects the install CD at the completion dialog instead of
  at shutdown. The previous boot order relied on the firmware falling
  through to the next disk when the first one is not bootable, which
  turned out not to work the same way on every backend: both backends
  skip past a blank hard disk and an empty optical drive, but only
  SeaBIOS (QEMU's firmware) will also move past a disk that has been
  partitioned but has no active partition set — which is exactly the
  state every installer leaves the disk in right before its reboot.
  VirtualBox's firmware stops there instead, so the install looked
  like it worked but then hung on its second boot. **A blueprint
  already seeded into an existing home keeps the old, broken order**,
  because `seed-blueprint` never overwrites an existing file: delete
  `blueprints/freedos.rlqb` and re-run `seed-blueprint` to pick up
  this fix. [The blueprint reference](docs/blueprint-reference.md)
  now documents the actually-observed behavior under `boot`, and four
  other documents that taught the old order are updated to match: the
  script spec's FreeDOS example and its `set-boot` guidance, the
  blueprint model's `boot` rule, the CLI spec's installation-machine
  example, and the blueprint cookbook's install recipe.

- **The screen-stability check now adjusts itself to how often it is
  actually called, instead of assuming a fixed rate.** The stability
  check recognizes on-screen decoration (like a blinking cursor) by
  counting how many times a cell changes within a one-second window —
  three changes within that window marks it as decoration — but this
  was really a sample count disguised as a time window: a caller that
  only reads the screen once every 0.83 seconds only fits two samples
  into that one-second window, and can never reach the count of
  three, so no cell was ever recognized as decoration, a blinking
  status bar was counted as real content, and the screen was
  reported as never settling no matter how long a caller waited
  (measured stability scores of 0.98 against synthetic blinking
  content and a 0.99 threshold to pass, and 0.944 on a live guest).

  There is now an explicit, stated **minimum reading rate the check
  needs to work correctly** (`viable_cadence`, `viable_window`): one
  read every ~0.17 seconds, with a 100% safety margin built in. Since
  reading text directly out of VGA memory takes 16ms or less, while
  interpreting a screenshot through a glyph bank takes about 0.83
  seconds, the check's time window now **widens** to match whatever
  reading rate is actually being observed — using the *fastest* gap
  between reads seen so far, rather than the average, since using the
  average would let the runtime's normal 2-second idle backoff widen
  the window too far and hide exactly the kind of quick redraw this
  check exists to catch — after rounding the window up to a coarser
  value that matches how noisy each kind of reading is (1 second when
  screens are read by interpreting screenshots, 0.1 second when they
  are read directly from text memory). Past a configured maximum
  (`MAX_ANIMATION_WINDOW`) the window stops widening, and if the
  observed reading rate is still too slow to make the check work, it
  reports `Reading.blind` and the check **disables itself** rather
  than blocking — a check that cannot reach a verdict must not refuse
  to proceed, since that would cause a deadlock rather than add
  caution. This is reported once per run as `guard.cadence`, so a
  check that silently went inactive is not indistinguishable from one
  that ran and passed. This behavior is now part of the normative spec
  for `stability` in [the script spec](docs/spec/script-spec.md).

- **Menu selection now follows the highlighted item correctly when
  reading a recognized screenshot, not just when reading VGA text
  memory.** `select` used to find the menu's highlighted row by
  looking for the least common color/style attribute on screen, which
  assumes each row uses exactly one attribute — true when reading raw
  VGA bytes from text memory, but not true of a screen recognized from
  a screenshot, where a blank cell only shows a background color and
  so cannot carry the same style token as a cell with a letter in it,
  meaning a highlight bar drawn across a dialog box is read as two
  different tokens, one of which is indistinguishable from the
  ordinary backdrop. Picking by rarity therefore picked the wrong row,
  and a built-in sanity check then rejected that wrong answer, so
  every `select` call on VirtualBox failed with "no menu highlight
  responded to cursor keys". The highlight bar is now found by what a
  highlight bar actually does: it is the attribute confined to one row
  that then moves to a different row after a keypress — which also
  works correctly even when the FreeDOS language-selection menu
  redraws every row on every keypress. For a two-item menu, the
  highlighted row is determined from which direction the cursor key
  moved; anything still ambiguous after that falls back to the old
  rarity-based method, which continues to work correctly for screens
  read from text memory.

- **A guest running in a graphical video mode no longer aborts the
  whole script run.** The fixed-font screen recognizer used to reject
  any screenshot that was not an exact 80x25 text grid by raising a
  `StaticError` — the error class reserved for input that is invalid
  on its face, and which exits with code `2` — so on a screenshot-based
  backend, the very first sample taken by the first `wait` in a script
  would abort the entire run, and every VirtualBox boot passes through
  a 640x480 graphical BIOS splash screen on the way up. This rejection
  now raises `UnreadableScreen` instead (a `RunFailure`, and now an
  exported name), and a script run no longer lets that error escape:
  the sample is simply recorded as unreadable, and the `wait` keeps
  polling until the guest reaches a text mode, timing out on its own
  normal schedule if it never does. A failure report now names the
  actual screen shape that was captured, something the "nearest miss"
  row in the report could not previously do, since with no text rows
  recognized at any sample, nothing was ever close to a match. QEMU
  never ran into this problem, since it reads VGA text memory
  directly, which is always 80x25 text regardless of what video mode
  the guest thinks it is in.

- **`--record` and `run_script(record=)` are now documented.** D98
  decided that the `.rlqt` transcript file format is deliberately kept
  outside the documented application specs, but that *how you invoke*
  recording (S1, S2) should be documented — and yet that invocation
  was described in neither [the CLI spec](docs/spec/cli.md) nor
  [the API spec](docs/spec/api.md). Both specs now describe it,
  including the rule that recording stops if a bound secret value is
  about to reach the guest. The behavior itself is unchanged; it was
  simply never written down.

- **`--detach` no longer appears in the `run-script` command's
  documented usage summary.** This flag has never actually existed:
  a detach option and the ability to check on a detached run afterward
  are both still-unimplemented backlog items (D35/D36), and listing a
  flag in a normative usage summary that `argparse` would currently
  reject reads as a promise that it works. Documentation of that
  planned capability's naming is kept, but only in the passages that
  are explicitly scoped to describing the backlog item.

## 0.1.0a1 - 2026-07-31

### Removed

- **Released packages no longer include the test suite** (D96). The
  wheel never included it. The sdist did, and the suite made up
  two-thirds of it — 187 of 280 files. It shipped so a downstream
  packager could unpack the sdist and run the suite from it, which is
  reasonable to want but cost too much to keep. Completeness is now
  checked a different way: `uv build` builds the wheel *from* the
  sdist, so if the sdist is missing anything the build needs, the
  build fails. `planning/design/` is also removed from the sdist — it
  was only included so the suite could read the script-example
  catalogue from an unpacked sdist, which meant maintainer-only
  planning files were being shipped to everyone just to support a test
  run nobody actually did. `docs/` still ships. The sdist now has 74
  files, down from 280. **The already-published 0.1.0.dev6 sdist still
  contains the tests** and cannot be changed retroactively; this
  change applies starting with the next release.

### Changed

- **The minimum supported Python version is now 3.12** (D95), raised
  from `3.9`. This is a **breaking change for anyone on Python 3.9,
  3.10, or 3.11** — but those versions never actually worked with
  Reliquary; the `3.9` floor had been published without ever being
  tested. When the test suite was actually run on old versions, 3.9
  and 3.10 failed because `keyring` calls `platform.win32_ver()`,
  which shells out to a subprocess on those versions, and 3.11 failed
  because a `MappingProxyType` dataclass default is rejected as
  unhashable there — 39 errors in total. Python 3.12, 3.13, and 3.14
  all pass. The team considered fixing those two problems instead of
  raising the floor, and decided against it; both are cheap to fix
  later if anyone actually needs a lower floor. Running the test suite
  against the minimum Python version is now part of the required
  checks, so the claimed floor is now verified, not just asserted.

- **`uv` now sets up the development environment and publishes
  releases** (D94). `uv sync` replaces the old `venv` + `pip install`
  setup, and `uv.lock` is committed so the environment the test suite
  runs in is reproducible — this matters because there is no CI, so
  the local test suite is the only gate. `uv build` and `uv publish`
  replace `python -m build` and `twine`; both of the old tools
  required the development dependencies to be installed, and now the
  only one needed is `jsonschema`. `twine check` is also dropped: it
  checks RST rendering, but the readme is Markdown, not RST; the
  package index already validates and rejects bad metadata on its
  own; and `tools/check_dist.py` is still the real check on what gets
  published. This change (apart from the Python floor above) is
  maintainer-facing only — nothing users interact with changes.

### Fixed

- **A relative `local` media path is now resolved relative to the file
  that references it**, matching what the blueprint model has always
  specified. The old implementation instead resolved the path against
  the process's current working directory, so the same blueprint
  would find its file or not depending on where you happened to run
  the command from. The fix is in `load_document`: because it has the
  file's own path, every relative `local` location is made absolute
  against that file's directory as soon as the document is loaded,
  before any other document is combined with it. When a document is
  passed directly to `parse_document` as a value rather than loaded
  from a file, its paths are left as written, because there is no
  file path to resolve them against. One consequence is deliberate:
  two identically-named blueprints that both use the same relative
  path, but sit in two different directories, used to be treated as
  duplicates and deduplicated. Now that the paths are resolved to
  absolute paths, they point at different files, so they are treated
  as different blueprints and **no longer collide**. Deduplication
  still works for two blueprints in the same directory, and for
  blueprints that reference media by URL. This bug was found while
  wiring remanence-lib's FreeDOS setup to a local ISO file: the
  blueprint's documented relative path only worked because the caller
  had changed its working directory to the blueprints directory
  first.

## 0.1.0.dev6 - 2026-07-30

### Added

- **The QEMU adapter now actually applies `backend-settings`** (D92,
  delivering F28). The field was already parsed, its backend names
  validated, and it was saved into machine state — but no adapter
  actually read it. The docs described it as the escape hatch for
  backend-specific options, but the code that builds the QEMU launch
  command only used memory, drives, and boot order, so a blueprint's
  `qemu` section was saved faithfully and then silently ignored when
  the machine started. Now it is applied: QEMU's `machine` key becomes
  the `-machine` flag, its `args` list is appended to the launch
  command as written, and this section is rendered **last**, so in
  the command line Reliquary logs, your own arguments appear at the
  end.

  **Each adapter defines its own set of allowed keys, and an
  unrecognized key is refused** when the machine is created — for
  QEMU, the only allowed keys are `machine` and `args`. **Settings may
  not duplicate anything Reliquary already controls**: `-m`, `-smp`,
  `-boot`, the drive arguments, `-machine`/`-M`, and the
  identity/control-channel arguments are all refused, naming the
  blueprint field that already owns that setting — because having two
  places that could set the same thing is exactly what this feature
  must not allow. Two things are deliberately left available through
  this hatch anyway: `-device`, which is the documented way to add
  QEMU-specific hardware since backend-specific devices have no
  dedicated field in the blueprint (P25), and `-cpu`, which picks a
  CPU model (the `cpus` field only controls the count). Only the
  settings for the backend actually assigned to the machine are
  checked; a section for a different backend is kept as written and
  never inspected.

- **`backend-settings` can narrow which backend gets picked** (D92).
  If a blueprint doesn't declare a `backend` but has a
  `backend-settings` section for exactly one backend, that already
  tells Reliquary which backend the blueprint is written for, so
  machine creation assigns that backend directly instead of walking
  the usual priority order. If that backend isn't available or can't
  run the blueprint, creation fails, and the error says the choice was
  narrowed by `backend-settings` rather than claiming the blueprint
  pinned a backend it never named. If there are `backend-settings`
  sections for two or more backends, none of them narrows anything —
  each section just sits unused until its backend would have been
  picked anyway by the normal order. An explicit `backend` field in
  the blueprint always wins over this narrowing, either way.

- **A new example script shows how to hand off a running machine**
  (T9): `freedos-ready.rlqs`, which the `freedos` blueprint lists
  under its `ready` label, so it comes along automatically when you
  run `rlq seed-blueprint freedos`. The script boots the installed
  disk, waits for a DOS prompt, sets the machine variable `ready`, and
  then **leaves the machine running** — unlike the other two example
  scripts shipped with `freedos`, which both power the guest off when
  they finish, because they're done with it. This script instead hands
  off a live, running guest to whatever runs next.
  `rlq run-script ready --blueprint freedos --expect ready=yes` does
  the whole boot-and-handoff in one command.

  As with the other examples, you're expected to copy and adapt this:
  what "ready" should mean depends on the workflow you're building,
  and this example uses the simplest possible definition — the
  installed system has reached a prompt. A workflow that needs to wait
  for a TSR to be resident, or a driver to be bound, should wait for
  its own evidence of that before setting the variable.

- **`run-script --expect key=value` (and the `run_script(expect=)`
  twin)** (D90, delivering F30). Lets you check the machine variables
  a script run left behind, as part of running it: after the run
  completes, each `key` is read, and if it is unset or holds a
  different value, Reliquary raises `RunFailure` naming the key, the
  value you wanted, and the value it actually got. Before this,
  checking a run's result required two separate calls, with the
  caller responsible for comparing the values — and because an unset
  variable looks the same as a variable from a machine that never ran,
  a script that failed before reaching its `set` statement failed
  silently. This is a **check performed after the run completes, not
  something that waits for the value to appear** — `run-script`
  already blocks until the run finishes, so the variables are already
  final by the time `--expect` checks them. It is refused under
  `--dry-run`, since a dry run doesn't actually run anything.

- **`wait-machine-var` (and the `wait_machine_var()` twin)** (D90).
  This is the polling counterpart to `--expect`, for cases where
  `--expect` doesn't work: when **something else sets the variable**
  — a script run started from another thread, or a machine you're
  only observing rather than driving yourself. Leaving out the value
  to wait for makes it wait for the variable to be set to anything at
  all, which is what a readiness check typically wants. `--timeout`
  (default 120 seconds) and `--interval` (default 1 second) control
  how long and how often it polls.

  If the wait times out, the CLI exits with code `4`, and the Python
  twin raises **`WaitExpired`, which is deliberately both a
  `RunFailure` and Python's built-in `TimeoutError`**: the thing you
  were waiting for didn't happen, but nothing about the machine is
  actually broken, and the value might still show up later — so code
  that's already handling ordinary `TimeoutError`s in a retry loop
  will also catch this and can just wait again. This resolves a
  conflict between two design rules that had never come into contact
  before: the async design's rule that a timeout should raise
  something outside Reliquary's normal error hierarchy, and the
  standing rule that no deliberate error Reliquary raises is ever a
  bare built-in exception.

- **`exec --check` (and the `exec(check=True)` twin)** (D89,
  delivering F26). Checks whether a command actually succeeded, which
  its screen output alone can't tell you. A setup command — loading a
  driver or a TSR — usually produces nothing worth reading, and
  whether it worked is the only thing that matters, so without this
  flag, success and failure look identical, and a driver that failed
  to load shows up later only as every following command failing in
  confusing ways. With `--check`, a command that reports failure makes
  Reliquary raise `RunFailure` naming the command (CLI exit code `4`);
  the returned screen rows are unchanged either way.

  On DOS, the check works by running an `IF ERRORLEVEL 1` probe against
  a sentinel value that Reliquary itself writes and reads back — its
  own text, not the guest's, so this doesn't try to interpret anything
  the guest printed. It's opt-in because it costs one extra command at
  the DOS prompt, and **it only catches commands that ran and
  explicitly signalled failure**: `COMMAND.COM` leaves `ERRORLEVEL`
  unchanged when it can't find the program at all, so a mistyped
  command slips past the check and looks like success. That
  limitation is documented in the spec rather than worked around by
  matching specific error text, which would mean trying to account
  for every wording a localized copy of DOS might print — an
  open-ended list. If the probe's own result can't be read back, `exec`
  reports `command.outcome-unreadable` rather than claiming success.

- **`describe-drives` and `refresh-drives`, with the twins
  `describe_drives()` / `refresh_drives()`** (D83). These give you a
  single, machine-level report of what a machine's drives are and
  what they actually contain — the same information the drive-letter
  map and the file-transfer commands already use internally, now
  exposed directly. For each drive, the report shows the declared and
  resolved facts: key, medium, slot, media, and how it was
  materialized. For each hard disk, it also shows what was found
  reading the disk itself: the backing format (`qcow2`, `raw`, or a
  directory served as one FAT volume), the partition table as the
  disk declares it, and per volume the filesystem, its label if it
  has one, and the geometry from the volume's own boot sector (BPB)
  if it states one — `null` rather than a guess where it doesn't. It
  also shows the platform's drive-letter map built from those facts
  (letter to drive key and volume index), with any drive that
  couldn't be placed marked undetermined and given the same reason
  and disk id that the file-transfer commands already report for the
  same problem.

  **The report is always answered from Reliquary's own record and is
  never refused because of the machine's current state.** Every
  `start` reads the disks as its first step, before talking to the
  backend at all, so a running machine's report reflects that boot's
  starting state — `"recorded": true`, with each disk stamped with
  when it was read. `describe-drives` itself only reads a disk
  directly when the machine is stopped and that disk has no record
  yet (the window between `create-machine` and the first `start`). If
  the actual layout changes and the record goes stale, that gets
  picked up at the next `start`, or now on demand via
  `refresh-drives`, which re-reads while the machine is stopped and
  returns a fresh copy of the same report. Addressing a drive still
  never trusts a volume count taken before the current boot: the
  file-transfer commands' recorded volume counts are cleared at every
  `start`, and the re-read that restores them also refreshes this
  report. `--json` on either command prints exactly what its twin
  function returns.

### Changed

- **The codex commands are now CLI-only** (D87). `seed_blueprint()`
  and `seed_script()` are removed from the embedding API,
  `list-codex` is added with no Python twin at all, and
  `reliquary/__init__.py` no longer exports any of the three. The
  reasoning: the bundled codex content can change in a point release,
  and P18 says a program should never bind against something that can
  change like that — using the codex is meant to be a deliberate,
  human action. This is also **the first named exception to P6** (the
  rule that every CLI command has an equivalent Python function): it's
  stated as a rule you can test against — any command whose subject is
  the codex is CLI-only — rather than as a list of exceptions. Per
  D24, this asymmetry is intentional and used to settle any future
  disagreement: adding a Python twin later is harmless, but removing
  one after code has started depending on it is not something that
  can be undone cleanly.
- **A dry run now refuses a name that only exists in the library
  codex**, instead of reading the blueprint or script from there
  anyway. This narrows one clause of D80. There is no fallback path
  left for a dry run to read from, so a dry run and a real run now
  resolve names identically, which is what the rule was supposed to
  mean all along.

- **At-rest disk reading now only recognizes FAT12, FAT16, and
  FAT16B, on a standard MBR with primary/extended partitioning**
  (D83). FAT32 partition types (`0x0B`/`0x0C`) and FAT32-sized
  volumes are now refused by name, the same way any other
  unrecognized format is refused — 0.1.0.dev5 had actually read
  these. This matches the filesystems the DOS-workflow guests
  actually create; a FAT32 disk still boots and runs fine as a
  guest — only at-rest access (the file-transfer commands, the
  drive-letter map, and the drive report) refuses it, and the refusal
  names FAT32 as the reason.

- **The machine-state JSON schema now matches what the code actually
  writes**: the per-drive `volumes` count (read on the host and
  cleared at every `start`), the floppy `launch-size`, and the new
  `geometry` record are now all part of `machine-state.schema.json`.
  None of these three fields is included in the blueprint digest.

- **Script static-validation rule ids are renamed from `S1`–`S14` to
  `V1`–`V14`** (D84). Only the letter changes; the numbers stay the
  same, so `S6` is now `V6`. `S15`, which was already retired, stays
  retired, and no `V15` is issued. The rule ids in diagnostic
  messages, the normative rule list in `docs/spec/script-spec.md`,
  and the conformance test corpus (both the `# rule:` headers in
  fixture files and the fixture filenames) are all updated together —
  this is a clean break made before 1.0, with no old spelling kept as
  an alias. Anything that references a rule id by its old letter — a
  fixture header, a test, a note — needs to be updated to the new
  one.

- **Reliquary's user-facing boundaries are now named and numbered
  `S1`–`S8`**, called the "application surfaces" (D85). They are:
  `S1` the CLI, `S2` the embedding API, `S3` the scripting language,
  `S4` the machine blueprint format, `S5` the script properties, `S6`
  the codex, `S7` a run's returned output, and `S8` the
  working-directory layout. These are a fixed, permanent list of
  names, enumerated under "The application surfaces" in the
  top-level `ARCHITECTURE.md`. The rule governing how these are
  allowed to change — the **surface-change rule** — has moved from
  `planning/INTERFACES.md` to `planning/SURFACES.md`. Nothing about
  what the surfaces are, how they're specified, or how a proposed
  change to one is evaluated has actually changed; this just gives
  each one a short, citable number. The word "interface" still keeps
  its normal, everyday meanings elsewhere (e.g. the hypervisor's
  management interface, a module's public interface) — it isn't
  reserved for this list.

- **Tasks listed in `planning/TASKS.md` are now numbered with
  `T`-ids** (D86). A task gets its number when it's added, the
  number is retired (never reused) when the task is removed, and the
  file itself records the next number to hand out. Numbering starts
  at `T8`, continuing past the old per-list numbering that came
  before it. This is maintainer-facing only and doesn't affect
  anything users interact with.

- **A new rule, P25, added to root `ARCHITECTURE.md`: a field in the
  machine blueprint format may only exist if more than one backend
  can support it** (D93). The blueprint's own vocabulary is now
  reserved for capabilities that generalize across backends; anything
  only one backend can provide has to go through that backend's
  `backend` field and its `backend-settings` section instead. Wanting
  a capability isn't enough by itself to justify a new blueprint
  field — this is meant to stop the portable blueprint format from
  slowly turning into the union of every backend's own options, added
  one convenient case at a time.

  **This removes a `devices` field that was added and then removed
  within this same unreleased development cycle**, so it never
  actually shipped in a release — it's simply absent from this
  changelog rather than listed as reverted. If you were tracking the
  `main` branch between the commit that added it and this one, change
  `"devices": ["virtio-rng"]` to `"backend": "qemu"` with
  `"backend-settings": {"qemu": {"args": ["-device",
  "virtio-rng-pci"]}}`, which is the form that's kept going forward.
  This is exactly why `-device` was deliberately left available
  through `backend-settings` rather than being blocked like other
  QEMU flags.

### Removed

- **Autoseeding is removed, and nothing is resolved automatically out
  of the built-in codex anymore** (D88). `--autoseed` /
  `--no-autoseed`, `set_autoseed()`, `autoseed()`, and
  `Context(autoseed=)` are all deleted rather than just changing their
  default: the `blueprints` and `scripts` directories are now the
  only place both the CLI and the API look, and a name that isn't
  there is refused, with the error telling you to run
  `rlq seed-blueprint <name>` if the library has it under that name.
  So instead of silently falling back to the built-in codex,
  Reliquary now tells you what command to run. **Getting started is
  now two explicit commands**: seed the blueprint, then run it (U1).
  This restores **P4 as an absolute rule** — the built-in codex never
  feeds automation directly, with no default and no flag to make it
  do so — reversing a knob that D59 had added when it made
  hermeticity configurable.
- **The `search-*` commands are removed** (D88). `search-blueprints`
  and its `search_blueprints()` twin are gone; the never-built
  `search-scripts` and `search-media` are retired before ever being
  built; and nothing replaces the search term parameter — filtering a
  list of results is left to the shell and to `--json` output.
  **`list-codex` is the new command for listing what the library
  codex offers** — following the pattern that each noun names one set
  and no single command spans two: `list-blueprints` /
  `list-scripts` / `list-media` show only your own files, and
  `list-codex` shows what the library ships. Since which command you
  ran now tells you where something came from, the `PROVENANCE`
  column and its `yes` / `seeded` / `user` values are removed along
  with `search-*`.
- **`--builtin` is removed** from `list-blueprints` and `list-media`,
  and `builtin=` is removed from `list_media()` (D88): a command that
  lists what you have shouldn't also carry a flag that turns it into
  a list of what you don't have. There is no replacement for listing
  codex media specifically — media are components inside a `.rlqb`
  file, there's no `seed-media` command, and the old listing was
  enumerating parts that can't actually be seeded on their own.
- **No `list-*` command prints a description column anymore**, for
  any noun. The description is still available in the `--json` output
  instead: free-text descriptions of unbounded length don't fit well
  in a fixed-width table, and how descriptions should be shown to a
  person is intentionally left undecided for now (T8) rather than
  guessed at.

## 0.1.0.dev5 - 2026-07-29

### Added

- **`create-machine --dry-run`, and the `create_machine(dry_run=True)`
  twin.** Scripts could already be checked without being run, but
  machines couldn't — there was no way to ask "is this blueprint
  valid, and what would creating it actually do?" without actually
  creating it. A dry run performs every step that costs nothing and
  changes nothing, stops before the first step that would actually
  commit something, and reports what it would have done: the machine
  id it would have allocated, the backend it would have picked, the
  resolved plan for each drive, and where each piece of media would
  come from.

  **It leaves no state behind**: no machine directory, no
  `machine.json`, no disk image, no downloaded file, no lock file,
  and no blueprint copied out of the codex — a blueprint that only
  exists in the library codex is read directly from there instead of
  being copied into your own `blueprints` directory. And **it never
  prompts you for anything**: if a media location has no concrete
  source it can resolve, the report marks it `unbound` and names the
  key, and states that a real `create-machine` would prompt for it.

  Media locations are resolved but never actually downloaded; each one
  is reported as `cached`, `would-download`, `would-extract`,
  `local-present`, or `unbound`. Nothing is hashed to verify it —
  `cached` only means the file is already present in the cache, not
  that it's the right file — and a byte size is shown only when
  something on the host already knows it, so a `would-download` entry
  includes its URL and its pinned hash but no size.

  A dry run refuses anything a real create would refuse, at the same
  point a real create would refuse it, so a nonzero exit code is the
  verdict either way. Missing *local* payload files are the one thing
  handled differently: instead of stopping at the first one found,
  all of them are collected and reported together, since stopping at
  the first would mean a separate fix-and-rerun cycle for each
  missing file.

  The Python twin returns a `DryRun` object — with `operation`,
  `report`, and `plan` fields — and never a machine id, so a
  `dry_run=True` result can never be mistaken for a real one.
  `--json` prints that same document, following the general rule that
  a command's `--json` output is exactly what its Python twin
  returns.

- **`create-machine --dry-run --backend NAME`** checks whether a
  blueprint would work on a specific *named* backend, rather than on
  whatever's actually available on this host. The check is based on
  that backend's declared capabilities, so the backend doesn't need
  to actually be installed to check against it — if it isn't, that's
  reported as a line in the plan rather than raised as an error. This
  checks the same "does the backend support what the blueprint needs"
  contract used elsewhere, purely statically, without installing or
  booting anything. `--backend` is only accepted together with
  `--dry-run` — a real machine's backend comes from its blueprint, and
  letting a flag override that at creation time would mean the actual
  configuration didn't match the blueprint anymore. This isn't the
  same as simulating the machine: `--dry-run --backend simulator`
  just validates against the simulator backend's requirements and
  stops there; actually running the machine on the simulator backend
  means dropping `--dry-run` and setting that as the real backend.

- `backends.evaluate(name, requirements)` is a new internal function
  that reports two separate things about a backend — whether it's
  available, and which requirements it doesn't meet — instead of a
  single yes/no verdict. This split is what makes the
  `--dry-run --backend` check above possible. `assign()`, the
  function that picks a backend for a real machine, is now
  implemented in terms of it.

- **`run-script --dry-run` now reports how much of the script it
  could actually check statically.** A statement inside an event
  handler only runs if the guest reaches the state that triggers it,
  so static checking can't promise it examined every statement. The
  report now says how many statements it could and couldn't reach —
  for example `10 of 37 statically reachable` on the shipped FreeDOS
  install script — instead of implying it checked everything when it
  couldn't have.

- **A disk image is now locked for the whole time it's being
  accessed at rest**, so two operations can't work on the same disk
  at the same time; a second caller that hits the lock is refused
  immediately with `image.locked` rather than being made to wait.
  This is Reliquary's own lock, and it deliberately claims one byte
  past the end of the image file rather than any of the image's own
  bytes — locking a byte within the image itself would conflict with
  QEMU's own image-serving process. This isn't backed by QEMU's
  built-in image locking, which lives in QEMU's POSIX file driver;
  the Windows file driver used on the delivered host doesn't
  implement any locking at all.

- **A partition is now read according to the type it actually
  declares.** The partition table is walked in the same order a DOS
  guest sees it — primary partitions first, then the logical drives
  inside a DOS extended partition (types `0x05` and `0x0F`) — and
  each FAT partition type is checked against a fixed list of
  recognized values. A partition whose type isn't in that list is now
  **refused by name**, instead of silently skipped: for example
  `partition 1 holds Linux`, `holds NTFS or exFAT`, or `holds a GPT
  protective partition — this disk is GPT, not MBR`. Skipping an
  unrecognized partition instead of refusing it would shift the
  numbering of every volume after it, and could confidently answer
  for the wrong drive. `0x85`, which is Linux's own extended-partition
  type (not DOS's), is refused along with the others.

- **A disk's geometry can now be read while the machine is stopped**:
  the partition table with each entry's declared type, the number of
  volumes, and — where a volume's own boot sector (BPB) states them —
  its heads, sectors-per-track, and derived cylinder count, left
  blank rather than guessed where the BPB doesn't state them. This is
  the "read directly from the host" source that P10 calls for, and
  it's the information the drive-letter map needs to work correctly —
  actually wiring it into the drive-letter map is not done in this
  change.

- **At-rest disk access now only supports the `qcow2` and `raw` image
  formats.** Any other format that QEMU itself could read is refused
  with `image.format-not-at-rest`, instead of being served without
  having actually been tested against it.

### Changed

- **BREAKING: Reliquary is now licensed GPL-3.0-only.** The project
  was BSD-3-Clause through `0.1.0.dev4`; every release from here on is
  copyleft. Anyone can still run, study, modify, and redistribute it,
  but any distributed work that incorporates Reliquary must now also
  be licensed GPL-3.0-only, and Reliquary can no longer be used inside
  a proprietary product. Already-published releases aren't affected:
  whatever went out under BSD stays under BSD, and this change isn't
  retroactive.

  `LICENSE` now contains the GPLv3 text, `LICENSES/BSD-3-Clause.txt`
  is replaced by `LICENSES/GPL-3.0-only.txt`, and the SPDX license
  header on every file in the repository (127 files) now reads
  `GPL-3.0-only`, as do `REUSE.toml` and the `license` field in
  `pyproject.toml`.

- **Reliquary's owner now formally reserves the right to relicense
  the project, and that's why contributions require assigning
  copyright.** Paul Galbraith holds copyright in the whole project
  and reserves the right to relicense it on any terms in the future.
  Nothing is currently planned; the reservation exists just so that
  option stays available rather than being lost by default. It
  doesn't take anything back retroactively — every version already
  published under the GPL stays under the GPL permanently, which
  `CLA.md` section 4 makes a binding legal term rather than just a
  stated intention.

  **New file: `CLA.md`**, a contributor license agreement that
  assigns copyright, with an automatic fallback to an exclusive,
  sublicensable license grant in jurisdictions where copyright can't
  be assigned between individuals, plus a license granted back to the
  contributor so they keep full rights to use their own contributed
  work. It explicitly states that it's still awaiting legal review
  before the first external contribution can be accepted under it.

  `CONTRIBUTING.md` now explains these terms in plain language,
  including the rule most likely to surprise people: **source code
  from a third party can't be accepted at all**, no matter how
  permissively it's licensed, because a contributor can't assign
  copyright they don't personally hold. Whether a contribution can
  legally be assigned — not whether its license is compatible with
  the GPL — is now the test for whether it can be accepted.

- **`AGENTS.md` now defines dependency license tiers, and corrects an
  earlier prior-art note.** Tier 1 dependencies are sublicensable and
  can be depended on freely; tier 2 dependencies are allowed only at
  arm's length (LGPL is allowed as an unmodified dependency, GPL as a
  separate process); tier 3 dependencies are refused outright.
  Build-time-only dependencies are out of scope for these tiers, since
  they aren't distributed with Reliquary.

  These tiers are deliberately stricter than the current GPL license
  alone would require. What the project publicly states is that
  relicensing is reserved and nothing specific is planned; but what it
  actually checks new dependencies and prior-art references against is
  the strictest realistic future — a commercial dual license. So the
  question asked about any external dependency or prior-art reference
  is "could this ship inside a proprietary product?", never "is this
  merely compatible with the GPL?" The GPL side of the project could
  legally absorb a lot of things a future commercial license couldn't,
  and checking only against the looser GPL-compatibility bar would
  quietly give up the reserved relicensing option — at a point when
  the choice was still free and before anyone noticed the option had
  already been lost.

  The prior-art section is also corrected, because the relicensing
  changed the reasoning behind it. It previously said os-autoinst's
  GPL-2.0-or-later license, by itself, ruled out porting its code into
  what was then a BSD-licensed project. That was true at the time and
  no longer is: code under GPL-2.0-or-later can be used under GPLv3,
  so license compatibility stopped being the blocker the moment
  Reliquary itself became copyleft. **The actual rule hasn't changed,
  though.** It was always really based on a separate principle — a
  close translation of someone else's code counts as porting it,
  regardless of what the license technically permits — and that
  principle is now joined by a second, independent one: whether the
  code's copyright can be assigned, which still rules the same code
  out permanently. The `consoles/VNC.pm` exception noted elsewhere is
  corrected on the same basis. The previous suggestion to reconsider
  adopting QEMU's in-tree `QEMUMachine` code is withdrawn: it's
  GPL-2.0-only and its copyright can't be assigned, so the answer is
  no on licensing grounds regardless of how well it's maintained.

- **BREAKING: `check-script` is removed. `run-script --dry-run` is
  now the only way to check a script**, and `check_script()` /
  `ScriptCheck` are deleted along with it, with no alias kept. A dry
  run of a script is exactly what `check-script` always did, so
  keeping two separate names for the same operation is what this
  change removes. `run_script(label, dry_run=True)` returns the same
  `DryRun` object that a dry-run create does.

  Three actual behavior changes come with this merge — this isn't a
  pure rename:

  - **The script selector is optional with `--dry-run`, but still
    required for a real run**, because whether it's given decides
    which set of checks runs: without a selector, only the checks
    that don't depend on a machine; with one, the machine-specific
    checks too. These are the same two modes the script spec has
    always defined; merging the commands without keeping both modes
    would have silently dropped one of them.
  - **A dry run returns a single document, not a stream.**
    `run-script` normally rejects `--json` because a live run's
    output is a stream of events as they happen; under `--dry-run`,
    the twin function returns one document instead, so `--json`
    becomes valid there and prints exactly that document.
    `--progress` and `--display` are still refused with `--dry-run`,
    since a plan has no live event stream to show progress for and no
    window to display.
  - The positional argument keeps `run-script`'s existing name,
    `label`, and is resolved the same way as before — checked as a
    label first, then as a bare filename stem.

  **A bug was also fixed along the way**: `--blueprint` now actually
  reaches the machine-level checks. The script spec has always said
  that either `--blueprint` or `--machine` should add the
  machine-specific rules, but the old `check-script` only actually
  applied them for `--machine` — so `--blueprint freedos` silently
  checked less than it claimed to, even when a machine named
  `freedos-0` already existed. This was caught because the report now
  states which tier of checks it actually ran. A dry run still stops
  before the point where a real run would create a machine, so a
  blueprint with no machine created yet only reaches the static
  checks, and the report says so.

- **BREAKING: `check_key()` is no longer part of the public API.** It
  validated a script property key and returned it — essentially a
  check on a string — and while it was exported from the package, it
  wasn't listed as matching any CLI command and had no command that
  used it, which made it a standing gap in the rule that every public
  API function should correspond to a CLI command. The script parser
  still uses it internally; nobody was actually using it to
  pre-validate a key from outside.

- **A drive image is no longer copied in full just to read it.**
  Reading a disk while the machine is stopped used to work by
  flattening the entire disk into a temporary raw file with
  `qemu-img convert`, reading from that copy, and converting it back —
  a cost proportional to the whole disk's size, paid on every single
  call. QEMU now serves the image over `qemu-nbd` on the loopback
  network interface, and Reliquary reads from it directly, so listing
  one directory now only costs the disk sectors that listing actually
  touches. Nothing about what the guest sees changes; the same five
  file-transfer commands reach the same drives as before.

  ```powershell
  rlq get-files "C:\OUT" .\results --machine rig-0   # no longer copies 2 GB
  ```

  **Writes now go directly into the image file**, backed by a qcow2
  internal snapshot as the commit point: the snapshot is taken before
  the first byte is written, discarded once the write finishes
  successfully, and rolled back to if it doesn't. This preserves the
  same guarantee the old copy-and-swap approach gave — an interrupted,
  refused, or crashed write leaves the disk exactly as it was before —
  but now costs only the disk clusters actually touched by the write,
  rather than the size of the whole disk. If a snapshot is left behind
  by a write that never completed, it's cleaned up the next time the
  disk is accessed, the same way an interrupted machine operation is
  reconciled elsewhere. A **raw**-format image still uses the old full
  staged-copy approach, since raw format has no internal snapshot
  mechanism to use instead; a differencing image is still stored as a
  difference against the same base image afterwards.

### Fixed

- **The drive-letter map no longer assumes what's on a disk without
  checking.** It used to assign hard disks letters starting from `C:`
  in slot order, assuming each one held exactly one volume. If a guest
  repartitioned its disk, that assumption became **silently wrong**:
  every letter after that disk shifted, and the map would confidently
  name the wrong drive instead of failing — so a `get-file` aimed at
  `D:` could silently read a completely different drive.

  Each disk now gets **one drive letter per volume it actually
  contains**, determined by reading the image on the host. A disk
  partitioned into two volumes now takes `C:` and `D:`, and the next
  disk after it starts at `E:` — both volumes are addressable, where
  previously a disk with two volumes was refused outright. A disk
  with **no** volumes at all — for example, a blank disk that was
  just created and hasn't been partitioned by a guest yet — gets no
  letter, matching what DOS itself does, so the next drive after it
  becomes `C:`.

  The volume count is stored in the machine's state and **cleared at
  every `start`**: since a guest can only repartition a disk while
  it's running, a count taken before the current boot can't be
  trusted to describe the disk after it. Reading the count on every
  start is affordable now because the same change that removed the
  full-disk copy (described above) also made this cheap.

  If Reliquary *can't* read a disk's volumes at all, every letter
  after that disk is left unassigned, and the error explains what
  specifically failed — either the backend can't read a disk image at
  rest, or the image itself couldn't be read — rather than just
  reporting that a letter couldn't be determined.

  `drive.volume-count-unsupported` is retired, since a disk with more
  than one volume is now handled correctly instead of being refused.

## 0.1.0.dev4 - 2026-07-29

### Added

- **Files can now be moved to and from an installed disk directly.**
  All five file-transfer commands now work directly with a **drive
  image** while the machine is stopped: the host mounts the disk,
  reads its partition table and the FAT volume behind it, and returns
  the files using the guest's own file naming. If your output lands
  on an installed `C:` drive, you no longer need separate disk-image
  tools to get it out — which is exactly what P16 says Reliquary must
  not require.

  ```powershell
  rlq get-files "C:\OUT" .\results --machine rig-0   # the installed disk
  ```

  FAT12, FAT16, and FAT32 are all readable, whether the disk has no
  partition table or an MBR, including logical drives inside an
  extended partition. Converting a backend's own disk format into raw
  bytes is left to the adapter — the QEMU adapter uses
  `qemu-img convert`, which follows a differencing image's entire
  chain of backing files and creates a temporary flattened copy of
  the disk for the duration of the call.

  **Writing files works the same way, in reverse.** `put-file` and
  `put-files` can now also write into a drive image, so a script's
  input files can be placed onto an installed `C:` drive before the
  machine even boots:

  ```powershell
  rlq put-file .\JOB.BAT "C:\JOB.BAT" --machine rig-0
  ```

  A write is **staged, then swapped in**: it's written to a scratch
  copy of the disk first, and that copy replaces the original disk
  image in one step at the end — so an interrupted or refused write
  leaves the original image completely untouched. Space is allocated
  before any byte is written, so a full volume is refused with the
  file left untouched; both copies of the FAT table are written from
  the same data, so they can never end up out of sync; and a
  **differencing image stays a differencing image** — it's rebuilt on
  top of its own base image rather than being silently collapsed into
  a standalone disk.

  A file name on the guest side has to be a name the guest could
  actually type — **8.3 format, or the write is refused**.
  `RESULTS.TAR.GZ` is rejected outright rather than silently
  truncated into something you wouldn't recognize later.

  Three specific errors are now reported by name, instead of the
  drive just looking empty: `drive.no-at-rest-access` (the backend
  can't flatten its own image format for reading),
  `drive.no-at-rest-write` (it can read the format but can't write it
  back), and `drive.volume-count-unsupported` (the disk holds more
  than one volume, so the drive-letter map can't correctly place it,
  and answering anyway could mean reading or writing the wrong
  drive).

- **File-transfer commands can now reach a drive at any letter.**
  Previously, a machine with an installed `C:` disk plus a
  directory-source drive used for exchanging files couldn't address
  the exchange drive at all: whenever any hard disk was declared, only
  `C:` was mapped, and every drive after it reported
  `drive.letter-undetermined` — because a disk the guest had
  partitioned in two would shift every letter that came after it, and
  the map couldn't account for that. The documented workaround was to
  put the exchange drive in a floppy slot instead, which only holds
  1.44 MB.

  The drive-letter map now places every drive — floppies at `A:`/`B:`
  by slot, hard disks starting at `C:` in slot order, then CD-ROMs —
  based on one stated assumption: **each hard disk holds exactly one
  volume**. That's true of every disk Reliquary creates itself, but a
  guest that repartitions a disk can silently break that assumption,
  so this is now written down explicitly in the mapping's own
  documentation and tracked as a known defect rather than left
  unstated. Reading the actual volume layout off the disk image is the
  work that will close this defect.

  ```powershell
  rlq get-files "D:\OUT" .\results --machine rig-0   # the exchange disk, behind C:
  ```


- **Blueprint error messages now include a line and column number.**
  A bad field in a `.rlqb` file used to only report the field name and
  nothing else — for example `unknown media field: drives.hdd0.bogus`,
  with no way to tell which of several `hdd0` blocks in a long
  document it meant, if there was more than one. It now also reports
  where in the file the problem was, in the same compiler-style format
  script errors already use:

  ```text
  rlq: blueprints\dos622.rlqb:8:34: error: unknown media field: drives.hdd0.bogus (field.unknown)
  8 |       "hdd0": { "media": "disk", "bogus": 1 }
                                       ^
  ```

  The field name is still shown too: it tells you *which* field is
  wrong, while the line and column tell you *where* it is, and both
  are useful. Error ids, exit codes, and the wording of the messages
  are unchanged, so nothing that checks `rule_id` or checks for exit
  code `2` is affected.

  This gap existed because of how the code was structured, not
  because it was simply forgotten: the code that checks a blueprint's
  fields worked on an already-parsed Python object, by which point the
  position information from the original file had already been
  discarded. `jsonc.loads(..., positions=True)` now records where each
  field was written, in a second pass over the same text that
  `json.loads` already parsed — so the actual JSON parsing itself
  still only happens in one place. This was possible because the code
  that blanks out comments before parsing already preserved the
  original character offsets, which is what let the second,
  position-tracking pass agree with the first.

  **Position information is optional, and its absence isn't a bug**:
  it comes from the document's original text, so `load_document(path)`,
  which loads a blueprint from a file, includes a position on every
  error it raises. `parse_document(value)`, which is handed an
  already-parsed value that never had file positions to begin with,
  behaves exactly as it did before, with no position shown. Where the
  parsed data and the raw text disagree about the document's shape,
  positions are simply omitted for that part of the document rather
  than guessed — a caret pointing at the wrong place would be worse
  than no caret at all.

- **A new backend adapter interface separates Reliquary's core logic
  from QEMU specifically.** Every backend operation now goes through
  one common adapter API, defined in `reliquary/backends.py` — this
  was extracted from the existing, working QEMU implementation rather
  than designed up front. It covers discovering backends, reporting
  what each one can do, creating disk images, starting and stopping
  machines, and the session object a control plane is built on top
  of. All of the QEMU-specific code moved into
  `reliquary/backend_qemu.py` — nothing above this adapter interface
  mentions QEMU, qcow2, QMP, or a network port by name anymore. The
  agentless display console also moved, into
  `reliquary/control_display.py`, where it now works with character
  rows and opaque, comparable attribute tokens instead of raw VGA
  bytes — so the cursor-menu-selection logic only has to be written
  once, rather than once per backend adapter.

- **Backends are now picked automatically, and refuse honestly when
  they can't do something.** `create-machine` now checks the host and
  picks a backend when the machine is created: a `backend` field in
  the blueprint pins the choice directly, and otherwise Reliquary
  walks through backends in priority order — **QEMU, VirtualBox,
  VMware Workstation, Hyper-V**, ordered by how well each one can be
  scripted without needing an in-guest agent — and uses the first one
  that's both available on this host and capable of everything the
  blueprint needs. Backend capabilities are reported honestly and
  never faked: if a blueprint needs a control plane, drive medium,
  controller, or materialization mode a backend doesn't support,
  machine creation fails during a preflight check, before any disk
  image work is done, naming the backend and the specific requirement
  it can't meet.
  VirtualBox, VMware Workstation, and Hyper-V currently ship as
  **stub adapters that honestly check the host and report that they
  support nothing**, so the backend walk skips over them even if that
  hypervisor is actually installed — their place in the priority
  order records the intended future order, not something that works
  today.

### Changed

- **An image drive now reports "backend doesn't support this" instead
  of "wrong kind of drive".** Now that drive letters resolve
  correctly, `C:` really is the installed disk, and the actual problem
  was that nothing could read it yet — so `drive.not-a-host-directory`
  is retired in favor of **`drive.no-at-rest-access`**, which also
  names the workaround: give the machine a directory-source drive and
  have the guest copy files to that instead. Reading and writing a FAT
  volume inside a disk image while the machine is stopped is still not
  built at this point, and stays tracked as a known gap.

  An **empty removable drive slot** used to also report itself as an
  image drive, which nobody had actually run into because such a
  drive couldn't be addressed at all; it now reports
  **`drive.slot-empty`** and tells you to insert a medium.

- **BREAKING: how a running machine's VM identity is recorded is now
  backend-generic, and no longer includes a network port at the top
  level.** A running machine's `vm` section in machine state now looks
  like `{backend, backend-id, token, endpoint, pid}` — the backend
  that owns the VM, that backend's own identifier for the machine, a
  token generated fresh each start, and an endpoint whose shape
  depends on the adapter (for QEMU, that's `{port}`) — replacing the
  old `{port, name, uuid, pid}`. Machine states saved by older
  versions will not load under this version; you'll need to recreate
  them. Because the endpoint is now hidden behind the adapter
  interface, **`start_machine()` now returns the machine id** instead
  of a QMP port number; `Machine` is now constructed as
  `Machine(home=..., deadline=...)` with no `port=` argument (and the
  same is true of `send_keys`, `send_text`, `screen_text`,
  `wait_text`, `cursor_menu_select`, and `screenshot`); and the
  undocumented `--port` option is removed from the guest-console
  commands, which now select a machine using `--blueprint` /
  `--machine` like every other command does. `machine_drive_args`,
  `find_qemu`, `find_qemu_img`, `create_hdd_image`, `Qmp`, and `stop`
  are removed from the embedding API entirely: they were internal to
  the QEMU adapter, and the adapter interface is an internal
  engineering contract, not something meant for outside code to use.

- **The wheel now contains only the runtime; the source package
  (sdist) contains the whole project.** `reliquary_tests` is no
  longer included in the wheel — an end user installing Reliquary has
  no use for 135 conformance test fixtures inside their
  `site-packages` — while the sdist now includes the test suite,
  `docs/`, and `planning/design/` alongside the code. This matters
  most for the spec-conformance tests, which read the normative spec
  documents and compare them against the code's actual behavior:
  without those documents present, those tests were being skipped,
  and a source package that can't run its own tests isn't one a
  downstream packager can actually verify. Unpacking the sdist and
  running `python -m unittest reliquary_tests` now runs **902 tests
  with only one skipped** — the opt-in FreeDOS integration test —
  where it previously skipped thirty-three tests.

- **New script: `tools/check_dist.py`, which checks the contents of
  the built wheel and sdist.** Now that the test suite doesn't run
  from inside the installed wheel, nothing checks the wheel's actual
  contents anymore, and missing package data is exactly the kind of
  thing that can go missing without anyone noticing — a dropped
  `script_grammar.lark` file or a missing file under `schemas/*.json`
  would break an installed copy of Reliquary the first time it's
  used, while every test run from the source tree would still pass.
  This script explicitly lists what each built artifact (wheel and
  sdist) must contain — and, for the wheel, what it must *not*
  contain — rather than inferring correctness from a test suite that
  happened to pass. Run it after `python -m build`.

### Fixed

- **`exec` could return before the command had actually run, returning
  leftover screen text from something else**
  ([#6](https://github.com/ferroteca/reliquary/issues/6)). The first
  `exec` call right after `start_machine` would return the guest's
  *boot* output instead of the actual command's output — silently,
  with no error, just a plausible-looking result that actually
  belonged to something else.

  This happened because `exec`'s check for "has the command finished"
  only tested whether a prompt was visible on screen — and
  `wait_ready` (which runs just before, as part of starting the
  machine) already returns precisely *because* a prompt became
  visible. So the very first `exec` was testing a condition that had
  already just been satisfied by the step before it, and its check
  could pass before the guest — still in the middle of finishing its
  boot script — had echoed the command back at all. `exec` now
  requires actual evidence that *this specific command* ran: either
  seeing the command's own echo on screen, or, failing that, seeing
  that the screen has changed at all since the command was sent.

- **`exec` no longer returns screen text it can't actually attribute
  to the command it ran.** When the command's echo couldn't be found
  on screen, the old code just returned everything above the prompt —
  which is the right answer when the output has scrolled past its own
  echo, but the wrong answer when the command never actually ran, and
  the two cases look identical if you only look at the final screen.
  `exec` now tracks whether it ever saw the echo at all: if it did see
  it at some point, a later absence just means the echo scrolled off
  screen, and the visible output is returned as before; if the echo
  was never seen at all, `exec` now reports `screen.no-echo` instead
  of returning rows that belong to something else.

## 0.1.0.dev3 - 2026-07-27

### Changed

- **Every working directory can now be set to a custom path.**
  Reliquary uses six directories — `home`, `blueprints`, `scripts`,
  `cache`, `media`, `machines` — and now all six can be set through
  the CLI and through the embedding API. Before this change, only
  `home` and `cache` could be set; the other four were always
  computed from them (`<home>/blueprints`, `<cache>/machines`, and
  so on), so a caller who wanted machines on a fast disk and media
  on a large one had no way to do it. Each of the six starts unset.
  Unset directories are then filled in: `home` supplies default
  locations for `blueprints`, `scripts`, and `cache`; `cache` —
  whether it was set directly or filled in from `home` — supplies
  default locations for `media` and `machines`. This filling-in
  only touches directories that are still unset. This is defined in
  `docs/spec/asset-resolution.md`, in the section "The working
  directories".

  **The flags are renamed, and the old names no longer work.**
  `--home` becomes `--home-dir` and `--cache` becomes
  `--cache-dir`. Four new flags join them: `--blueprints-dir`,
  `--scripts-dir`, `--media-dir`, and `--machines-dir`. All six
  flags now follow the same `--<name>-dir` pattern, instead of two
  bare names (`--home`, `--cache`) plus four differently-named
  ones. The equivalent Python functions in the embedding API are
  renamed the same way: `set_home()` becomes `set_home_dir()`,
  `set_cache()` becomes `set_cache_dir()`, and four new functions
  are added: `set_blueprints_dir()`, `set_scripts_dir()`,
  `set_media_dir()`, `set_machines_dir()`. Also renamed:
  `media_cache_dir()` becomes `media_dir()`,
  `machines_cache_dir()` becomes `machines_dir()`, and `home()`
  becomes `home_dir()`.

  **`RELIQUARY_HOME` is renamed to `RELIQUARY_HOME_DIR`.** Four new
  environment variables join it: `RELIQUARY_BLUEPRINTS_DIR`,
  `RELIQUARY_SCRIPTS_DIR`, `RELIQUARY_MEDIA_DIR`, and
  `RELIQUARY_MACHINES_DIR`. `RELIQUARY_CACHE_DIR` is unchanged. Each
  variable name is just `RELIQUARY_` plus the flag's own name in
  capitals. **If you still have `RELIQUARY_HOME` set, Reliquary
  will silently stop reading it** — there is no warning, because
  Reliquary makes no backward-compatibility promises before version
  1.0. Rename it to `RELIQUARY_HOME_DIR`.

- **`Context` is now just a plain holder for the six directories**
  plus `autoseed`; all the logic for resolving directory paths
  moved to module-level functions in `home.py`. Its keyword
  arguments now match the flag names exactly: `Context(home_dir=,
  blueprints_dir=, scripts_dir=, cache_dir=, media_dir=,
  machines_dir=, autoseed=)`. This keeps the CLI and the embedding
  API in step with each other, and six separate nullable string
  arguments are easier to call from C or Java than six keyword
  arguments would be (P7). Passing a bare string as `context=` is
  still a shorthand for setting the home directory. The field is
  now `Context.home_dir` rather than `Context.home`, and the
  `home_dir()` and `cache_dir()` methods on `Context` are gone —
  call the module-level functions in `home.py` instead.

- **An unset directory is now an error everywhere, rather than
  silently falling back to something.** If a directory has no
  value when Reliquary needs to resolve it, it raises `StaticError`
  with the id `dir.unassigned`, naming the missing directory and
  how to supply it. The error is raised the first time the
  directory is actually needed, not when `Context` is built — so
  you can build a `Context` before filling in all its directories,
  and when the error does fire, it names the specific directory
  that was actually needed, not some unrelated directory further
  down a chain of defaults. On the CLI, if neither a flag nor an
  environment variable sets the home directory, Reliquary assigns
  it a default; since `home` in turn supplies defaults for the
  other directories, one default reaches all six, and in practice a
  CLI user will never hit this error — that's just how the default
  works, not a special exemption from the rule. The embedding API
  does not assign any default, so a caller there really can trigger
  this error; that is the safety feature the design is for.

- **Principle `P12` is amended, and so is the codex clause in
  `P4`.** Now that the six directories can each be set
  independently, "the home directory" is just the name of one of
  those six, not a container that holds the others. So the actual
  safety guarantee behind `P12` — that Reliquary only writes to
  locations it was explicitly told to use, and never next to its
  own module code or into a source tree — stays true, but its
  wording had to change to match. Similarly, `P4`'s rule that "the
  codex never feeds automation" is now a default behavior rather
  than an absolute rule, since autoseeding (described below) can
  now be turned on or off on both the CLI and the embedding API.
  Both changes are recorded in `planning/DECISIONS.md`, along with
  the reasoning for treating them as interface changes.

### Removed

- **The `--assets` flag is removed**, along with the matching
  `assets=` keyword, `set_assets()` function, `HOME_ASSETS`
  constant, and the internal `HomeSource`/`DirSource` split that
  supported them. `--assets` existed only to let you name a single
  project directory holding both blueprints and scripts, because
  `blueprints` and `scripts` couldn't be set separately. Now they
  can: use `--blueprints-dir <dir> --scripts-dir <dir>` to say
  where each one lives, and a single `DirectorySource` class reads
  each kind from its own directory.

  `--assets` also controlled whether Reliquary was allowed to fall
  back to its built-in codex of stock blueprints and scripts when a
  name wasn't found in your own directories. That behavior is now
  its own separate flag, **`--autoseed` / `--no-autoseed`** (or
  `autoseed=` in the API): it controls whether a name not found in
  your directories may come from the built-in codex. It is **on by
  default on the CLI** and **off by default in the embedding API**,
  so a person using the CLI still finds `freedos` on a fresh
  install, while a library call still never pulls from the codex
  unless it asks to. This splits what used to be one flag into two
  separate settings, so a project directory can keep using the
  codex as a fallback while a home directory can be told to refuse
  it, or vice versa.

  This causes two real behavior changes worth calling out. First,
  whether autoseeding happens now depends on which interface you're
  using (CLI or API), not on which directory you pointed at. So
  `rlq --blueprints-dir ./project` in a CI pipeline will now seed
  from the codex unless you also pass `--no-autoseed` — the old
  `--assets ./project` never did that. Second, `seed-blueprint` and
  `seed-script` now write into whatever directory `blueprints` or
  `scripts` is currently set to, instead of always writing to the
  home directory. This means seeding a first draft straight into
  the project directory you're about to commit is now the normal
  way to do it.

- The `import-vm` command is removed from the CLI. It was
  registered as a command, but its entire implementation was
  `raise NotImplementedError`, while the CLI specification
  described it as if it worked — a synopsis listing `--platform`,
  `--hdd-images`, and `--snapshot`, prose explaining its behavior,
  and a worked PowerShell example — none of which the actual
  command-line parser even accepted. No design work is lost: this
  was already known to be unbuilt and already recorded as such in
  two places (`planning/proposed/FEATURES.md`, under "Machine
  mobility", which took it off the numbered plan on 2026-07-23; and
  U2, which says outright that none of it is implemented). Its
  specification text is removed from the CLI spec for the same
  reason five other not-yet-real commands were removed on
  2026-07-27 — a spec should describe what exists. Its intended
  eventual design stays in `docs/spec/api.md`, whose banner already
  makes clear that document describes the end goal, not what exists
  today.

  The earlier cleanup missed this command, and it's worth recording
  why: the test that checks the command inventory only compares
  command *names*, and `import-vm` appeared as a name in both the
  spec and in `_COMMANDS`. Only the parity check described below —
  which checks whether each named command actually does something —
  could catch that the name led nowhere.

  The same fix reaches other documents that described `import-vm`
  and its siblings as if they worked. `docs/spec/cli.md` no longer
  claims that these four unbuilt "machine mobility" commands have
  matching API functions. The blueprint guide's "Cloning,
  exporting, importing" section — which documented `clone-machine`,
  `export-drive`, `export-machine`, and `import-vm` as if they
  existed, though none of them do — now carries a banner marking it
  as design, not current behavior. And `ARCHITECTURE.md` no longer
  lists "building a blueprint from an existing VM" as one of the
  ways a blueprint can be created.

### Added

- **New commands `list-files`, `get-files`, and `put-files`
  complete the set of commands for moving files in and out of a
  machine's drive.** Before this, there was no way to ask what
  files were on a stopped machine's drive, or to copy a whole
  directory tree across, without opening the drive's directory on
  the host directly. Now `rlq list-files "A:\"` lists what's there,
  `rlq put-files .\suite "A:\"` copies a directory tree in, and
  `rlq get-files "A:\OUT" .\results` copies one back out. The
  matching Python API functions are `list_files()`, `put_files()`,
  and `get_files()`. Like the existing single-file commands they
  join, these only work on a stopped machine, and only over a
  directory-source drive (not a disk image).

  **All five file commands use the same way of writing an
  address.** A directory is addressed the same way the guest names
  it, just like a file is. The one new thing you can now address is
  the drive itself, written as `A:\` or just `A:`. A trailing
  backslash is optional — `A:\OUT` and `A:\OUT\` mean the same
  address. A file address must still point to an actual file.

  `list-files` reports just one directory level by default, or the
  whole tree if you pass `--recursive`. Its `--json` output is a
  flat array sorted by address, with one object per entry:
  `{"address", "name", "kind", "size"}` (`size` is `null` for a
  directory). The addresses it reports are written in the same
  format the file commands accept, so you can feed a listing
  straight into the next command.

  `put-files` and `get-files` copy the **contents** of a directory
  tree into the destination, rather than nesting the source
  directory inside it. They recurse into subdirectories, create any
  directories they need, overwrite files that are in the way, and
  never delete anything — it's a copy, never a mirror. For
  `get-files`, the destination directory is required and is created
  if it doesn't exist; Reliquary never picks a location to write to
  on its own. All five file commands refuse to target a disk-image
  drive by name, since the QEMU adapter has no way to read or write
  files on a disk image while the machine isn't running.

- **New `pacing` setting: a short pause before a script sends
  keyboard input.** A script that waits for a screen to appear and
  then immediately types was sending its keystroke too soon: the
  installer had drawn the screen but hadn't started reading the
  keyboard yet, so the keystroke was lost. This happened for real
  in `freedos-install.rlqs`, which then timed out 30 seconds later
  at the next step, even though pressing Enter by hand at that
  point advanced it immediately. Every guest-input command
  (`enter`, `type`, `press`, `select`) now pauses briefly before
  sending its first key. The default pause is **0.1 seconds**, and
  that default is expected to be tuned further later.

  This pause length can be set at different levels, using the same
  priority order that `timeout` already uses — a setting on the
  individual statement wins over one on the phase, which wins over
  one in the script header, which wins over the built-in default.
  You can set it as a `pacing` header, as a `pacing=` modifier on a
  phase, or as `pacing=` on the verb itself. There is no way to set
  it on a branching `wait`: a `wait` observation can't carry
  `pacing`, so a guest-input verb inside a `wait` handler always
  inherits its pacing from its enclosing phase. This is all worked
  out when the script is parsed, so `check-script` now reports a
  "guest input" section that names each verb's pause length and
  which scope (statement, phase, header, or default) set it — the
  same way it already reports observation timeouts.

  **This is not the same thing as the `delay` verb, and the
  existing rule against using `delay` for this purpose still
  applies.** The distinction is between a pause the script author
  deliberately sequences, and a pause that's just an inherent part
  of delivering keyboard input correctly. Without an agent running
  inside the guest, Reliquary can observe the guest's screen output
  but not whether it's ready to receive *input* — so a control
  plane that types the instant a screen appears is claiming to know
  something it can't actually know. `send_keys` already paused
  *between* individual key events; what was missing was a pause
  before the *first* one. This change adds the ability to tune that
  pause, not the option to add a pause where none existed before.

  `pacing=0s` is allowed, and means "this guest is ready, don't
  wait at all" — it is the one duration setting in the scripting
  language that is allowed to be zero. A zero *timeout* or *bound*
  would be asking for something that can never happen in time,
  which is why `timeout`, `deadline`, and `stable` still reject a
  value of zero. But a zero *pause length* is a perfectly
  meaningful thing to say, and rejecting it would just push authors
  toward writing `pacing=1ms` to say the same thing less honestly.

  Where `pacing` is allowed to appear is enforced: putting `pacing`
  on an observation, or on a host-side verb (`insert`, `eject`,
  `set-boot`, `screenshot`, `set`, `start`, `stop`, `http`), is now
  a parse error that explains why it isn't allowed there. `select`
  is the one verb that does both things at once — it observes the
  screen *and* delivers keyboard input — so it can carry both a
  `timeout` (for the observation) and a `pacing` (for the input),
  and shows up twice in the execution plan as a result. This is
  defined in `docs/spec/script-spec.md`, in the "Timing" section,
  and recorded as decision D60.

- The README's "Blueprints and machines" section now shows the
  blueprint/machine model with a working example, instead of only
  describing it in words. It walks through a complete 1 MB MS-DOS
  blueprint, creating two machines from it, using `insert-media` to
  change one machine but not the other, and a second blueprint for
  a design that's genuinely different. The point of the example is
  stated once, plainly: a blueprint is the design, and a machine's
  own state reflects what has happened to it since it was created —
  so a reader can tell which one they should be editing.

  **`README.md` is now included in the test that checks documented
  examples.** Every blueprint shown in a code block in the teaching
  documents is run through the real parser and checked against the
  published schema. `README.md` was excluded from this test before,
  simply because it had no examples to check — but it's the
  document most people read first and copy code from.

  The rewrite also fixed three outdated claims: the section called
  the blueprint feature set "milestone-1", even though the project
  plan actually reached milestone nine; the status note listed
  **run records** as something Reliquary ships, even though
  decision D36 removed them and a run now stores nothing; and it
  said that picking up a blueprint edit meant destroying and
  recreating the machine, which was true before `apply-blueprint`
  existed. That section now describes `apply-blueprint`, along with
  the real limitation it has — it can't apply a change that alters
  the size of a disk image that's already been created.

- `rlq run-script --help` now actually explains the command,
  instead of just repeating its name. It now covers what `LABEL`
  is resolved against, where the machine used for the run comes
  from and when a new one gets created, what happens before the
  script's first guest-input command runs, the state rules the
  `machine` header enforces, and the fact that a failed run leaves
  the machine running so you can inspect it — nothing is
  automatically torn down. An exit-code table follows. The
  `--display` flag previously had no help text at all; it now
  explains that keyboard or mouse input typed directly into the
  backend's own window is invisible to Reliquary.

- **The lexer and the grammar now assign diagnostic ids too.** This
  is the second pass of implementing decision D55, and the last one
  that can be done from the script's text alone. 82 diagnostic ids
  now cover every check that happens before a machine is even
  involved: the tokenizer (`lex.unterminated-string`,
  `lex.invalid-duration`, and others), line and block shape
  checks (prefixed `syn.`), the node signature checks, and the
  static rules.

  Two new id prefixes were added, as expected: `lex.` for what the
  tokenizer rejects while reading raw characters, and `syn.` for
  shape errors. The grammar's own rejections are deliberately the
  least specific ids in the scheme — `syn.unexpected-token` just
  names the offending token, never a specific rule, because a
  parser at that stage genuinely doesn't know anything more than
  that. `docs/spec/script-spec.md` now explains this, in the part
  that already explains why the S-rules sit above the grammar
  (CFG).

  **The number of test fixtures with no matching diagnostic id is
  now zero**, down from six when the corpus was first written: all
  39 invalid fixtures now name the diagnostic that rejects them.
  What's left without an id belongs to the preflight and runtime
  stages — 30 call sites that no parse-time fixture can reach,
  which is exactly why they live in the corpus's
  `invalid-at-preflight/` bucket instead.

  **A bug the corpus found is now asserted by a test instead of
  just written down in a comment.** A branching `wait` that carries
  a condition is actually rejected by the grammar itself, reporting
  `syn.unexpected-token` — which means the
  `wait.branching-condition` check in `script_validation` can never
  actually run, since the grammar rejects the input first. This is
  exactly the trade-off that `script_grammar.lark`'s own header
  warns about. The test fixture for this case carries a `#
  caught-by:` marker that's checked in both directions, so whichever
  eventual fix lands (fixing the grammar or removing the dead
  validation code) will automatically retire this marker.

- **Diagnostics now carry stable, dotted identifiers** (like
  `obs.two-channels`). `script-spec.md` has required every
  diagnostic to have one of these since the scripting language was
  first adopted, but none actually existed until now. 52 ids were
  added, covering the static rules and the node signature checks.
  `obs.two-channels`, which the spec uses as its own example id, is
  now something the code actually raises, not just an illustration
  in the documentation.

  **The id scheme is more fine-grained than the existing S-numbers,
  and settling how the two relate was the open question this work
  had to answer.** An S-number names a rule, and an id names one
  specific way of violating that rule: S7 is a single restriction
  that can be broken in six different ways, each with its own id.
  So the two schemes aren't competing with each other, and nothing
  needed renaming — an error message carries only the id, and the
  spec's rule list separately records which id maps to which
  S-number. The test corpus demonstrated the need for this before
  the design did: when it was written against S-numbers alone, it
  worked, but it couldn't tell "no condition given" apart from
  "unknown channel", since both are S7 violations.

  The id lives in a **field** on the error object, not embedded in
  the message text, so calling code can check `rule_id` directly
  instead of parsing the message text, and the planned reference
  index of all ids can eventually be generated automatically
  instead of maintained by hand. The wording of the message itself
  is not part of any contract and can still be freely improved.
  `RULE_OF` is a mapping from every id to the rule it belongs to;
  three tests cross-check `RULE_OF`, the spec's own rule lists, and
  the ids the code actually raises, against each other in every
  direction.

  This also strengthened existing tests without extra work: the
  validation test suite used to check which rule a message cited by
  looking for a substring, so a check for `"S1"` would also match a
  message that actually mentioned "S12". It now checks the id
  directly instead.

  **What's left without an id is counted exactly, not guessed at.**
  The lexer, preflight, and runtime diagnostics don't have ids yet.
  The script test corpus records exactly which cases are still
  affected — four fixtures carry a `# id: none` marker, which is
  checked in both directions so the marker can't linger after the
  gap it flags is actually fixed. The full reference index of ids
  is still deferred to the beta release, which is where the spec
  always planned to put it.

- **A new conformance test corpus for the `.rlqs` scripting
  language** — 58 test fixtures in three groups, written directly
  from `script-spec.md` and run by `test_script_corpus.py`. This
  covers the half of principle P24 that the earlier command
  inventory checks didn't reach: P24 asks what a full set of
  spec-derived test cases should look like for each interface, and
  whether the pattern already used for the blueprint corpus
  generalizes to other interfaces — since simply diffing two lists
  (a set difference) isn't the same thing as a real set of test
  cases.

  **The pattern does generalize, and this version is stronger than
  the blueprint corpus.** The blueprint corpus can only assert that
  an invalid fixture was rejected somehow. Its own README names the
  weakness of that: an invalid fixture that gets rejected for the
  *wrong* reason still counts as passing, and only a human reviewer
  would notice. The script language has stable rule ids, so each
  fixture can declare the specific S-id that's supposed to reject
  it, and the test harness checks that the actual diagnostic cites
  that id. This paid off immediately: on the first run, three
  fixtures turned out to be rejected by the wrong rule (a `finish`
  statement in a linear script trips S10 before it ever reaches the
  S8 or S9 check it was meant to test). A simple "was it rejected"
  test would have passed all three, and would have kept passing even
  if the specific rules they were meant to test stopped working.

  **This approach does not generalize beyond document-format
  interfaces (like blueprints and scripts), and the specific reason
  is worth naming.** A conformance corpus needs concrete inputs to
  feed to an implementation; for the CLI or the embedding API those
  inputs would be command-line argument lists or sequences of
  function calls, which is possible in principle — but without
  stable diagnostic ids outside of the S-numbers, such a corpus
  could only check the exit code, which only has six possible
  values. That's why the other eight interfaces got simple
  inventory comparisons instead, and why how deep those comparisons
  can go is limited by how much of decision D55 (stable diagnostic
  ids) is implemented, not by how much effort goes into them.

  The corpus measured how complete decision D55 actually is,
  rather than just claiming it: six of the 39 invalid fixtures
  can't name the rule that rejects them, and carry a `# cites: no`
  line explaining why — parse errors, header cardinality checks,
  duplicate modifier checks, and the signature-check part of S2 all
  raise no diagnostic id at all yet, even though the spec requires
  every diagnostic to have one. These markers are checked in both
  directions, so a marker can't outlive the gap it records once
  that gap is fixed, and the total count of such gaps is checked
  too.

  Writing the corpus surfaced one more finding, recorded in the
  corpus's README: `wait "x" { … }` is actually rejected by the
  **grammar** itself, which means the S8 check for that specific
  case in `script_validation` can never run, and the actual
  diagnostic reported is the generic, unnamed `'{' is not valid
  here`. The grammar file's own header explains why the S-rules are
  checked after grammar parsing rather than baked into the grammar
  — "where a diagnostic can cite its id — encoding them here would
  trade named errors for 'unexpected token'" — and this is exactly
  the tradeoff that shows up in this case.

### Fixed

- **The test suite now passes when run against an installed
  package, not just against the source tree.** Eleven tests read
  files from `docs/` or `README.md` without the guard the rest of
  the test suite uses to check it's running from the source tree.
  As a result, running `python -m unittest reliquary_tests` against
  an installed wheel reported four errors and seven failures — none
  of them real bugs, all of them just because those documentation
  files aren't included when the package is built. The
  documented-example tests now skip as a group when the
  documentation files are missing, and the four script-corpus tests
  that read `script-spec.md` skip individually, so the fixture
  checks that sit alongside them can still run wherever possible.
  This means a downstream packager gets the same test command
  working whether it's run against the unpacked source package or
  the installed package — which is what the repository has always
  claimed was true.

- **Every diagnostic Reliquary can raise now names the rule it
  enforces, with a stable id.** `script-spec.md` requires a stable
  id on *every* diagnostic; the number still missing one is now
  zero, down from 288. 284 ids were added, across 26 subject
  prefixes, and all 26 prefixes are declared in the spec's prefix
  list.

  This final pass covered 108 diagnostics across 13 modules — the
  machine commands, the VM lifecycle, the guest console, DOS drive
  addressing, media acquisition, blueprint authoring, and various
  small helper modules. None of the subject prefixes needed
  debating: `machine.`, `drive.`, `media.`, `value.`, `name.`, and
  `blueprint.` already existed, and four more were added for things
  that had no prefix yet — `image.` for a materialized disk image,
  `screen.` for what the guest displays, `script.` for a script
  file, and `assets.` for the asset source. Reuse of existing ids
  ran deep: `value.not-a-string` is now raised from nine different
  places in the code, `value.not-an-object` from seven,
  `blueprint.unknown`, `machine.not-running`, and `value.not-a-size`
  from five places each, and `media.file-missing` and
  `machine.must-be-stopped` from four each. One rule keeps one id no
  matter how many different code paths can trigger it.

  **Three separate tests now keep this complete automatically, so
  nobody has to re-measure it by hand.** One checks that every
  deliberate `raise` in the package carries an id — 405 raise sites
  were inspected, with a narrow, documented exemption for internal
  faults, private signals, and abstract-method stubs that are never
  actually called. Another checks that every id's subject prefix is
  one the spec lists, in both directions. And both conformance
  corpora (blueprint and script) verify that the id a test fixture
  declares is actually the one that gets raised.

  Writing the first of these tests found something a plain search
  for `raise` statements structurally cannot catch: **six
  diagnostics are *returned* by a helper function** for the caller
  to raise itself, so the actual `raise` statement for them carries
  no id keyword at all. Those helper functions are exempted from
  the raise-site check and are checked instead where the error
  object is constructed, which is the only place an id can actually
  live for them. One of these six had been missed under the old
  approach and now carries the id `machine.backend-failed-to-start`.

  This also exposed a gap in `RULE_OF`, the mapping from ids to
  S-numbered rules: it had been built by scanning specific modules,
  on the assumption that those three modules *are* the entire static
  checking stage — but `script_parser.py` actually raises one
  preflight diagnostic too. `RULE_OF` now covers every id the parser
  code can raise, using `None` for ids that have no matching
  S-number — the same way the `http.` family of ids already did for
  rules that predate the numbering scheme — and its docstring now
  describes its actual scope instead of overstating it.

- **Every blueprint diagnostic now carries a stable id, and the
  blueprint conformance corpus checks it.** The 97 rules in
  `document.py` now each name themselves with an id — 73 distinct
  ids in total. This leaves 108 diagnostics across 13 modules still
  without an id, down from 205 across 14 modules before this
  change.

  The subject prefixes used come from the blueprint model's own
  existing terms, rather than being invented just for this: `ref.`
  for the `${…}` reference syntax, `value.` for what a field's value
  is required to be, `field.` for the document's field vocabulary,
  `drive.` for drive keys, slots, and boot order, and `blueprint.`
  for the document as a whole. Two groups of rules reused ids that
  already existed elsewhere: naming rules use `name.`, since it's
  the same rule regardless of where a name is written, and media
  rules use `media.`, including `media.remote-without-hash`, which
  the resolution code already raised. Using a single `blueprint.`
  prefix for all 97 rules was rejected as an approach, because it
  would have made the prefix identify the *document format* rather
  than the *rule* — something the spec explicitly forbids — and it
  would have given 22 already-named rules a second, redundant id.

  **The blueprint corpus can now check something its own README
  said it couldn't.** That README stated outright that its fixture
  headers were "documentation, not assertions" — because an invalid
  fixture that fails for the *wrong* reason is a false pass that
  only a human reviewer could catch, and the script corpus's
  docstring pointed to exactly this as the reason its own approach
  was stronger. Now, all 47 invalid blueprint fixtures declare which
  diagnostic must reject them, the test harness compares that
  against the actual `rule_id` raised, and the marker is checked in
  both directions so it can't linger after the gap it records is
  fixed. One difference between the two corpora remains, and is
  written down rather than glossed over: the script corpus can also
  check that an id serves the specific rule a fixture is *meant* to
  exercise, because script rules are numbered (S-numbers) and
  blueprint rules aren't.

  Some ids are deliberately broad, where the underlying rule really
  is just one rule. `ref.not-allowed-here` rejects nine test
  fixtures from three separate raise sites in the code — covering a
  `${…}` reference used in `backend`, `control-planes`,
  `controller`, `materialize`, `platform`, `type`, a name, a drive
  key, or a children path — because refusing a reference in any of
  these closed or identity-defining positions is a single rule
  (decisions D26/D27), and the specific field involved is named in
  the message text instead. Code that switches on the id learns
  which rule was broken; a person reading the message learns exactly
  where.

- **Diagnostic ids now reach the properties file, the credential
  store, and the CLI too.** 40 more diagnostics gained an id: 15 in
  `properties.py`, 3 in `credentials.py`, 13 in `cli.py`, and 9
  places in `machines.py` that raise a rule already named elsewhere.
  Three modules are now completely covered and drop off the
  "missing an id" list entirely, leaving 205 diagnostics across 14
  modules still without one, down from 245 across 17.

  **Reusing ids across interfaces is the whole point of the scheme,
  and applying it to a second interface proved that immediately.**
  Two of the properties file's rules turned out to already be named
  on the scripting-language side: a key in the reserved `rlq`
  namespace is `name.property-reserved-namespace` whether it's
  declared in a script or defined in a properties file, and a key
  defined twice is `name.duplicate-property` either way. If the
  prefix had instead identified which interface or which stage
  raised the error, those would have needed four separate ids for
  what are really just two rules. The same was true for the CLI:
  "machine is not running", "select a machine with --blueprint or
  --machine", "is running but has no recorded VM identity", and "not
  implemented for platform" were all rules the scripting language
  had already named, so the CLI now reuses those same ids — and the
  duplicate raise sites in `machines.py` were fixed to match, since
  having one copy of a rule properly identified and its duplicate
  left bare would be worse than either extreme. `machine.not-running`
  is now raised from five different places, all using the same id.

  **The list of allowed subject prefixes is now fixed and enforced
  by a test.** The spec said the prefix identifies the subject and
  gave a list of allowed subjects, but nothing in the code actually
  enforced that list — so a new diagnostic could use whatever prefix
  its author happened to pick, and a prefix list that drifts can't
  reliably keep one id for a rule that spans two interfaces, which
  is the entire reason this scheme exists. A test now checks the
  code's actual subject prefixes against the spec's list in both
  directions: an undeclared prefix in the code fails the test, and a
  prefix declared in the spec that nothing actually raises also
  fails the test. Both currently agree on 17 subjects, with
  `platform.`, `progress.`, and `store.` newly added as part of this
  work. The test also checks that ids shared across interfaces stay
  shared, so a future change can't quietly give one rule a second
  name.

- **A blueprint that names a backend Reliquary hasn't actually built
  is now refused, instead of silently running on QEMU anyway.**
  Before this fix, `"backend": "virtualbox"` in a blueprint was
  accepted and recorded, but then simply ignored: `create-machine`
  would still create a **qcow2** disk image, and `start-machine`
  would have launched QEMU — so the backend recorded for the machine
  and the backend actually used for it disagreed, and nothing told
  you. `create-machine` and `apply-blueprint` now refuse this and
  name the gap explicitly — exiting with code `3`, before doing any
  image work — the same way they already refuse an unwired control
  plane or a non-`ide` disk controller. Principle P11 (capability
  honesty) requires Reliquary to say plainly when it can't do
  something, rather than silently substituting something else, and
  this backend check was the third of three places that weren't
  following that rule yet.

  The field reference document's backend/format table had actually
  promised a VDI disk format for that same `virtualbox` declaration
  — meaning the documentation was correct and the code was wrong.
  That table now marks which of its four rows describes something
  actually built, and which describes something merely intended, and
  ties each intended row to the feature proposal that would build it.

  This was found while resolving an unrelated documentation task,
  and the reasoning is worth recording. That task asked whether two
  orphaned rules in the descriptive field reference should be
  promoted into a formal, normative spec. The answer for both was
  no, and for the same reason: both describe capability that doesn't
  actually exist, and a spec is supposed to describe what exists.
  But the two rules weren't otherwise alike. The `controller`
  ordering caveat was correctly marked as describing an unreachable
  case, so it was only ever prose about a machine configuration
  nobody could actually create. The backend/format table wasn't
  marked that way at all, so it was prose the code actively
  contradicted (as described above). Either way, a rule about
  capability that hasn't been built yet belongs alongside the
  feature proposal that would build it — so both constraints were
  moved into the relevant proposed-feature documents, rather than
  into a spec or being deleted outright.

- **`put-file` and `get-file` now refuse to guess a disk-drive letter
  on a machine whose disks use more than one controller type**,
  instead of answering purely from slot order. Slot order only
  reliably determines drive order *within* one controller type; when
  a machine mixes controller types, the guest's own firmware decides
  how the controllers themselves get enumerated, so even "the first
  hard disk" isn't a fact Reliquary can rely on — and P17 requires
  Reliquary to fail rather than guess whenever the known facts leave
  a drive address ambiguous. Floppy drives are unaffected: DOS
  always gives them `A:` and `B:` regardless of what the hard disks
  do.

  No real machine can hit this case today, since creating a machine
  with a non-`ide` controller is already refused — but this new
  guard is checked by a test anyway. That's deliberate: this
  invariant properly belongs inside `platform_dos.drive_letters`
  itself. Leaving it to be enforced only by an unrelated capability
  check three modules away would mean that the day a second
  controller type is actually wired up, the drive-letter mapping
  would quietly start answering a question it has no real basis for
  answering. Previously, having multiple disk volumes was the only
  documented reason a drive letter could be undetermined; this
  controller-mixing case is the second reason, and it's now
  documented in the same docstring.

- **Every diagnostic the scripting language can raise now carries a
  stable id.** `script-spec.md` requires one on *every* diagnostic.
  Before this change, the static-checking stage had 82 ids, but the
  preflight and runtime stages had none at all — so code checking
  `rule_id` got back `None` for things like an unbound property, an
  unknown media reference, an undeclared drive slot, or any expired
  timer. 43 diagnostics gained an id, across property binding, media
  resolution, the script runner, and the timing model.

  The `rule_id` field lives on `ReliquaryError`, the base error
  class, rather than on a separate new class for each stage. The
  spec puts every id in one shared namespace across all the error
  classes, and putting the field on the base class is the code
  saying the same thing — a diagnostic's identity doesn't depend on
  which stage raised it. Every existing error class picked up the
  field automatically, with no new machinery needed — what was
  actually missing was just the identity itself, not any new
  infrastructure. *Location* information already existed in two
  different forms — `ScriptParseError`'s line and column, and the
  script runner's statement citation — and conflating those two
  separate things with the missing id is what made this look like a
  bigger job than it actually was.

  Two new subject prefixes were added, `media.` and `machine.`, and
  they illustrate why the prefix identifies the subject rather than
  the stage: `media.unknown` is the same id whether the media
  resolution code finds no such media defined, or a script's
  `insert` command names a media that doesn't exist. One underlying
  condition gets one answer, regardless of which code path detects
  it. If the prefix had instead identified the stage, that single
  condition would have needed two different ids, and calling code
  would have had to know which stage noticed it to check the right
  one. For the same reason, four places in the code that re-report
  an error caught elsewhere against a specific script line now
  **forward the original error's id** instead of minting a new one —
  so `set-boot hdd6` used inside a script reports the exact same
  rule id as running `rlq set-boot-order hdd6` directly. Each kind of
  timer got its own id — run deadline, phase deadline, observation
  timeout, and reactive interval — since a program that can't tell
  which timer expired can't decide what to do about it.

  The script conformance corpus now checks more than it used to be
  able to. Its `invalid-at-preflight/` group of fixtures previously
  only checked that a fixture *parses successfully* — that was all
  it could check while preflight diagnostics had no ids. It now
  actually runs the preflight stage (the machine rules, then
  noninteractive property binding) and checks the resulting id, in
  both directions just like the parse-error group, plus checks that
  the rejection is specifically a PREFLIGHT ERROR rather than
  something caught even later. Writing this check immediately caught
  a bug: a fixture that should have been rejected by
  `machine.slot-not-removable` was instead claiming `media.unknown`
  — which turned out to be because the test harness's own fake
  machine setup was wrong. This is exactly the kind of false pass
  this group of tests exists to catch.

  `RULE_OF` still deliberately maps only the static-checking stage.
  It maps an id to the S-numbered rule it enforces, and S-numbers
  only name syntactic rules — so a machine rule (checked at
  preflight) has no S-number to map to. Leaving those ids out of
  `RULE_OF` is correct, not a gap, and the test that checks
  `RULE_OF` against the spec now documents that explicitly.

  **This work closed one gap and, in doing so, measured the size of
  a bigger one.** Because decision D58 made the error classes apply
  to every interface, not just scripts, the spec's requirement that
  every diagnostic have an id travels with them: a malformed
  blueprint is a STATIC ERROR in exactly the same sense a malformed
  script is, so it owes an id on the same terms. 245 diagnostics
  across 17 modules still don't carry one — 97 of them in the
  blueprint document parser alone — and this gap is now filed as a
  known defect, with an exact per-module count, rather than left for
  someone to notice later. The id scheme itself needs no changes to
  cover them; what's needed is agreeing on the right subject prefixes
  for the blueprint interface, which is separate follow-up work.

- **Ordinary user mistakes no longer exit with code `1`**, which is
  the exit code reserved for bugs in Reliquary itself. Five cases
  were measured and all five used the wrong code: naming a media,
  blueprint, machine, or script label that doesn't exist all exited
  `1` instead of the correct `3`, and malformed blueprint JSON
  exited `1` instead of the correct `2`. The system of error classes
  and exit codes was already implemented correctly — but only the
  scripting-language code path actually used it. Elsewhere, 242
  raise sites across 19 modules just raised plain Python exceptions
  (`ValueError`, `KeyError`, `RuntimeError`, `FileNotFoundError`),
  and the CLI had a clause that caught seven specific builtin
  exception types and turned every one of them into a generic exit
  `1`. This meant a program driving the CLI couldn't tell "you made
  a typo" apart from "Reliquary itself crashed" — a distinction U9
  depends on being able to make, and which P7 argues for as a
  matter of principle.

  Every raise site now uses a proper typed error class, and decision
  D58 states that the four error classes describe **every
  interface**, not just a script run. This is a confirmation of
  existing intent, not a new direction: milestone 9's in-band file
  exchange already raised `PreflightError` from nine one-shot
  command code paths, and the single condition "machine X is not
  running" was previously being raised in three different places as
  three different classes — exit 1, exit 1, and exit 3, all for the
  same underlying condition. What actually decides which class
  applies never depended on scripts specifically: is the problem
  settled by the input alone (STATIC ERROR)? does the actual state
  of the world satisfy that input (PREFLIGHT ERROR)? did the work
  itself fail while running (RUN FAILURE)? A capability that this
  version of Reliquary declares support for but hasn't actually
  wired up is the third case — it now exits with code `3` instead of
  crashing, which is what the capability-honesty principle (P11)
  calls for.

  Exit code `1` keeps the same meaning it always had, and now also
  has a proper error class behind it. `InternalError` represents a
  deliberate internal fault — a consistency check that Reliquary ran
  against its own state and failed — and it's a subclass of
  `ReliquaryError`, the root error class, so `except ReliquaryError`
  remains the catch-all the API documentation describes. It falls
  through to exit code `1`, the same as a genuine accidental
  exception that was never wrapped as a `ReliquaryError` at all.
  Cases where the home directory's state is broken are split by
  whether a normal user could actually cause them: an interrupted
  `create-machine`, or a VM already using the expected network port,
  are conditions in the real world with a suggested fix, so they
  exit `3`; while a corrupted state file or an unrecognized machine
  phase can only happen due to a bug, so they remain treated as a
  fault (exit `1`).

  Several other cases were fixed along the way, each one an ordinary
  mistake that was being reported as if it were a crash: `rlq press
  <typo>` raised a bare `KeyError` from a helper function the CLI
  calls directly; an unreachable QMP socket reported exit `1` when
  the real problem is simply that the VM isn't running (now exit
  `3`); five places raised a bare `TimeoutError` when a guest never
  responded, causing an exit `1`, even though the builtin
  `TimeoutError` is supposed to be reserved for a handle's
  `wait(timeout=)` call expiring, where nothing has actually failed;
  two helper functions *returned* a `RuntimeError` object for the
  caller to raise, which a simple search for `raise` statements
  would never have found; and a malformed properties file and an
  unreachable credential store both had docstrings admitting they
  fell outside the four error classes, so both exited `1` for what
  are actually just a legality error and a machine-state rule,
  respectively.

  This rule is now enforced automatically by a test, instead of
  relying on code review: a test walks all 393 `raise` statements in
  the package and fails if any of them raises a forbidden plain
  builtin exception, so this guarantee can't quietly erode over
  time. The CLI's clause that caught seven specific builtin
  exception types is deleted, since it would have silently absorbed
  any missed raise site and printed it as a tidy exit `1`. Whatever
  still reaches the CLI's remaining catch-all now prints a full
  traceback and still exits `1`, because a genuine internal fault
  should be loud, not tidy. Roughly a hundred tests were updated in
  the same change to check for the proper error-taxonomy classes
  instead of raw builtin exception types — which also means those
  tests now check the actual intended contract, rather than
  happening to pass due to an implementation detail. The blueprint
  conformance corpus's check that used to accept any of
  `(ValueError, KeyError, TypeError)` now checks for `StaticError`
  specifically.

- The `--qemu` flag is removed from the CLI's internal flag-arity
  table. The spec already says the old global `--qemu`, `--platform`,
  and `--port` flags "are removed", and no command parser has
  defined `--qemu` for some time — but the internal table still
  listed it, meaning the code referred to a flag the spec said no
  longer existed. `--platform` and `--port` remain in that table:
  they are still live options on individual commands, and their
  presence there relates to the "argument order doesn't matter"
  rewrite, not to the removed global flags.

  Simply deleting the table entry, on its own, would have made the
  error message worse — this was actually measured, not just
  reasoned about. Before the deletion, `rlq --qemu foo list-machines`
  reported the useful `unrecognized arguments: --qemu foo`, because
  the arity table entry told the argument-reordering code to treat
  `--qemu foo` as a flag-and-value pair and skip past it to find the
  real command word. Without that entry, argparse instead blamed the
  *value* — reporting `invalid choice: 'foo'` and never naming the
  actually-wrong flag. So the argument-reordering code was changed
  to look past an unknown flag's value to find the real command word
  even without a table entry, restoring the useful message. **This
  is actually better than the situation before the deletion**, not
  merely as good: the useful message used to only work for flags
  that had an arity table entry, so it only ever worked for
  `--qemu` and nothing else. Now `rlq --qmu foo list-machines` (a
  typo of `--qemu`) also correctly names `--qmu` as the problem. A
  bare word with no unrecognized flag in front of it still stops the
  scan immediately, so a plainly misspelled command name is still
  reported as the invalid command it is.

- `instance-model.md` still listed `clone-machine`, `export-drive`,
  and `export-machine` in a command synopsis, written in the same
  `rlq ...` command-line form as if they existed — the same three
  unbuilt commands that the 2026-07-27 cleanup already removed from
  the CLI spec. This directly contradicted this document's own
  banner, which says clone and export remain unbuilt. A nearby
  sentence also incorrectly claimed these commands "require
  `ready`". Both the synopsis and that sentence are removed; the
  commands are now simply named as unbuilt, with their design left
  in the documents that own it.

  **The test written to catch exactly this kind of mistake had a
  blind spot.** The command inventory test only read
  `docs/spec/cli.md` and nothing else, so a second copy of the exact
  bug it was written to catch survived undetected in a different
  document. It now reads every spec document. This check is
  deliberately one-directional: no spec document may name a command
  that doesn't exist, but the requirement that "every command must
  be documented somewhere" still applies only to `cli.md`, since
  other spec documents are free to mention only the commands
  relevant to their own subject.

  The machine lifecycle phases are now checked for agreement across
  all three places they're stated: the prose sentence that lists
  them, the enum in `machine-state.schema.json` (which `AGENTS.md`
  requires to stay in sync), and the literal phase values
  `machines.py` actually writes. All were checked and found to
  agree.

- Media handling and the built-in `rlq.*` property facts now have
  tests derived directly from the spec, and — for the first time in
  this round of work — **these tests found no actual mismatch**. The
  `materialize` modes the media spec lists in its table are exactly
  the four modes the parser accepts, and each one parses correctly
  under the table's own "needs" column. The `rlq.*` facts the
  properties spec lists are exactly what `is_fact` recognizes, with
  `rlq.host.hostname` correctly documented as a planned-but-not-yet-
  shipped candidate rather than something that ships today, and the
  `rlq.env.*` family correctly resolved by matching a prefix rather
  than by an exhaustive list. The order in which property sources
  are checked was verified by hand against the spec's numbered list
  and matches: the lookup nests the environment-variable and file
  tiers inside the parameter tier, so that a redirect can substitute
  a different lookup key — which reads like a change in ordering but
  is not actually one.

  Both of these new tests act as guards against future drift, rather
  than fixes for anything broken now — which is exactly what a
  passing inventory comparison is for. One thing is explicitly named
  as excluded rather than silently skipped, per P24's requirement:
  the media *field* vocabulary itself is not compared. Seven of its
  eleven fields have their own section in the media spec, and the
  other four are specified in prose elsewhere, in the blueprint
  model — so comparing against the combined set would mean
  hardcoding which four fields live elsewhere, which is exactly the
  kind of special-casing the principle warns against.

- `docs/spec/asset-resolution.md` had no status banner at all, and
  had drifted out of sync with the code in six places while nobody
  noticed, because of that missing banner. It was the one document
  in `docs/spec/` breaking the rule that the `docs/spec/` directory
  itself states — that the banner is what marks a document as
  binding, and without one the directory is just a shelf for
  documents of unknown status — so nothing this document said was
  actually guaranteed to be true. It now declares itself normative
  (binding), which is what it always meant to be: its own closing
  line already called the home directory layout a contract that
  external tools rely on, and the spec index already listed it under
  "The interfaces".

  Here is what had drifted out of date: the document described
  `.rlqm` as a kind of media file, but media stopped being separate
  files when the composed blueprint model (D30) was adopted — media
  are now specified inside a `.rlqb` blueprint file. It didn't
  mention `.json` at all, even though the code accepts `.json` as
  the legacy blueprint file extension. It said home mode resolves
  assets from a `media/` folder that doesn't actually exist, and
  that isn't even shown in the document's *own* layout diagram. It
  called directory mode the behavior of "*every* embedding-API
  call", just ten lines above a passage explaining that the API only
  reaches home mode through an explicit marker. And it described a
  `landmarks/` folder in the home layout with no corresponding
  `landmarks_dir` actually implemented anywhere.

  The sixth outdated item was a `.rlql` "landmark" file kind listed
  in `KIND_EXTENSIONS` that nothing in the code ever actually
  requested — only `blueprint` and `script` kinds are ever asked
  for, and home mode had no folder to resolve a landmark file from
  anyway. It's now removed from the code and instead listed in the
  banner as reserved-but-unbuilt, alongside the `ObjectSource` third
  asset source — the same treatment already given to `screen.read`
  (mentioned above). The landmarks feature itself remains settled
  design, documented in `planning/pledged/design/landmarks.md`.

  Two tests now keep this document accurate: one checks the kind
  table against the kinds any module actually requests, and the
  other checks the home-layout diagram against the folders
  `home.py` actually resolves. Both tests read the list of
  reserved, not-yet-built names out of the document's own banner, so
  a designed-but-unbuilt feature can stay documented without the
  document falsely claiming it already works.

- The codex spec's status banner described `search-` commands,
  `seed-` commands, and the provenance column as "still planned",
  even though all three had already shipped. This isn't just a
  cosmetic mistake: under the rule that the banner is what marks a
  document as binding, a document marked as not-yet-binding isn't
  claiming to be true — so those sections couldn't be checked
  against anything. This is the same underlying failure that hid six
  mismatches in the CLI spec (described elsewhere in this
  changelog), just in the opposite direction — here the banner
  understated what exists, instead of overstating it. The banner now
  correctly says what actually ships, and honestly scopes the codex
  index to just blueprint names and descriptions, nothing more.

  Fixing the banner immediately made a real mismatch visible. The
  spec's provenance table was headed `CODEX` and gave a **blank**
  value for its third row; but the actual `search-blueprints`
  command prints a `PROVENANCE` column whose third possible value is
  the word `user`, never blank. A program parsing the `--json`
  output and checking for a blank value there would never have
  matched anything. The spec now documents the actual shipped values
  — `yes`, `seeded`, or `user`, never blank — and a test reads those
  three words directly out of the spec's table and exercises all
  three code paths, so the spec and the code can't drift apart
  again without the test catching it. The tests that already existed
  checked each value individually and would have kept passing no
  matter what the spec said — which is exactly the kind of gap
  principle P24 is meant to catch.

  `codex.json` also had a `media` block that nothing in the code
  actually read. It listed only two of the four media items the
  codex's built-in blueprints declare — but since D30, media are
  components defined inside a blueprint and derived from it, so this
  separate block was guaranteed to go stale over time. It's now
  removed, and a test pins the codex index to the blocks that
  actually ship. A second new test catches the case where a codex
  blueprint ships with no matching index entry — a case
  `list_builtin_blueprints` would otherwise silently skip — since the
  test that already existed only checked the opposite direction (an
  index entry with no matching blueprint).

- `screen.read` was declared as a valid event kind in the spec, but
  nothing in the code ever actually emitted it. It had a constant
  defined, a rendering branch for it, and a line in the script
  spec's minimum event vocabulary saying it was "emitted by the
  `screen` command" — but the `screen` command actually prints its
  output straight to stdout and never writes to an event stream at
  all; only `run-script` and `fetch-media` support the `--progress`
  event stream in the first place, so there was never anywhere for
  this event to come from. Code written to listen for this event on
  the stream would have waited for it forever. `screen.read` now
  joins the spec's existing list of reserved-but-unemitted event
  kinds, alongside the `ended` terminal event and the U6 handover
  kinds, and its code constant and rendering branch are removed to
  match: **a reserved event kind has no code constant**, which the
  spec now states explicitly, and a test enforces by comparing the
  declared event vocabulary against what any module actually emits.
  `events.KINDS` is that declared set. Nothing else turned out to be
  dead — the other 19 event kinds are all actually emitted somewhere.

  This is P24's check applied to Reliquary's event output. Since the
  spec describes the event vocabulary in prose rather than as a
  table, there's no ready-made list of names to directly diff
  against the code. What can actually be checked is the underlying
  claim behind that prose list — that the event stream really does
  carry each of the kinds it names.

- `fetch_media` was missing from the package's `__all__` list. You
  could still import it directly, it was documented in the API
  reference, and it was the twin of a shipped command, but it was
  left off the declared list of exports — so `from reliquary import
  *` did not bring it in. It was the only function left off this way.

- CLI and API command names are now checked against each other by a
  test, not just by discipline. The rule has always been that a CLI
  command's name is its API twin's name with dashes in place of
  underscores, and nothing exists only in the CLI. A new test
  compares `cli._COMMANDS` against the package's declared exports,
  checking both that every command has a twin and that every twin is
  exported. The guest-console family is exempt from this rule, and
  that exemption is defined in `docs/spec/api.md` rather than
  hardcoded into the test, so it cannot be quietly widened.

  This is P24's pass over the embedding API. Unlike the other
  interfaces, it deliberately does not compare the full inventory:
  `docs/spec/api.md` describes the *end-goal design*, so it names
  capability that does not exist yet and cannot be checked against
  the current code. What the test checks instead is the specific
  rule the spec states today, and only one direction of that rule can
  be checked mechanically. The other direction — that no public
  capability is unreachable from the CLI — would need a curated list
  of the non-command surface (types, path helpers, parsers, lifecycle
  functions), which is a design task, not something a test can do
  yet.

- In-band file exchange no longer guesses at a DOS drive letter it
  cannot actually know. The old letter map assumed one drive letter
  per hard disk, so a guest that partitioned a disk into more than
  one volume shifted every later letter, and `put-file "D:\X.TXT"`
  would confidently write to the wrong drive. Only two things can
  actually be determined from what a blueprint declares: floppies
  always take A: and B: no matter what the disks contain, and the
  first hard disk is always C:, with cdroms taking those letters only
  when no hard disk is declared, since nothing can shift them.
  Addressing any other drive is now a preflight error: it says
  Reliquary cannot determine which drive that is, lists the letters
  it could determine and the ones it could not, and names the fix —
  address a determined letter, or give the exchange drive a floppy
  slot. It no longer reports "the machine declares no drive at D:",
  which was untrue when a drive was there. Reliquary simply has not
  built this capability yet, rather than refusing it outright: the
  actual volume layout can be read from the drive images on the host,
  and the letter map may grow to do that later (D56).

- Watch patterns in scripts are now checked before the run starts,
  which **S13** has always required ("watch patterns are non-empty
  and regexes compile") but nothing enforced. `wait /a(b/` used to
  parse fine and only fail later, raising `re.error` from the sample
  loop and exiting with code `1` — a fault outside the normal error
  categories, for a mistake that was visible in the script text all
  along. `wait ""` and `wait //` used to parse into an observation
  that matched every screen, so the wait passed on its first sample
  and effectively waited for nothing. Both cases are now static
  errors citing S13; the regex one also names the compile error and
  says which regex dialect applies (Python's `re`, which the spec
  names as the language's contract). A pattern that is only a
  property reference, like `wait "${target}"`, does not count as
  empty — it is text the run fills in later.

  This was found by checking the spec's requirements against the
  code, rather than by reading the code alone. The scripting
  language now gets the same kind of inventory comparison the CLI
  already gets against its command list: the S-ids the spec defines
  are checked against the S-ids the diagnostics actually cite, the
  node vocabulary against the lexer's keywords, each node's modifier
  signature against the parser's, and the error classes and exit
  codes against `errors.exit_code`. S13 was the one place they
  disagreed; the other three checks already matched. This is P24's
  second interface: the plan is for every enumerated interface to
  carry tests that check it *against its own specification*, which is
  what catches a requirement the spec states but the code never
  actually implemented.

- Reserved node names are now actually reserved. The script spec has
  always said they "cannot name phases or property keys" — this is
  stated twice, in the grammar rules and in **S5** — but nothing
  enforced it, so `phase enter { … }` and `property text press` both
  used to parse without complaint. The lexer only treats a word as a
  keyword where a node may start, which is deliberate and unchanged;
  what was missing was validation that refuses those words when an
  author tries to use them as identifiers. Both examples now fail as
  static errors citing S5. **The closed vocabularies stay
  contextual** (D53): a phase can still be named `cdrom0` or `esc`,
  and `press enter` still names the key — the language's own syntax
  words are reserved, but words from the domain's own vocabularies
  are not.

- The CLI specification described five commands that were never
  built — `clone-machine`, `export-machine`, `export-drive`,
  `search-media`, and `search-scripts` — written in present tense
  with worked example output, and it left out five commands that do
  exist: `add-media`, `prune-media`, `put-file`, `get-file`, and
  `get-machine-var`. Anyone who followed the spec for the first five
  got `invalid choice` from the CLI. The unbuilt commands are now
  removed from the spec (their designs are still kept under
  planning/proposed/FEATURES.md), the five real commands are now
  documented, and a test checks both directions so the two lists
  cannot drift apart again. `clean-archives` was removed along with
  them, since it had already been removed from the code when the
  single media cache landed.

- Two error messages named `hostdir`, a drive field that was retired
  when the composed blueprint model landed. Trying to `insert-media
  --file` a directory now says the directory reaches a guest as "a
  declared media whose location is that directory" instead of "a
  declared hostdir drive"; and the in-band file-exchange refusal now
  asks for a "directory-source drive" without also naming the old
  `hostdir` field. Neither of the old messages named something you
  could actually write in a blueprint anymore. vvfat is unchanged —
  it is still how this kind of media attaches.

- A script that inserts a media the active source does not define now
  fails at preflight instead of partway through the run. The script
  spec has always required this — preflight is supposed to reject
  "media references (`@name`) naming no media the namespace
  defines" — but nothing implemented it, so `insert cdrom0 @typo`
  would start the machine, run as far as that statement, and only
  fail there, possibly after the script had already sent guest input.
  It is now a preflight error (exit code 3) raised before the machine
  starts, naming the missing media and suggesting the closest
  declared names. `check-script` reports the same problem. A
  `$property` media argument is deliberately not checked this way,
  since it only resolves once the run binds it, not before. When one
  statement gets both the slot and the media wrong, the slot error is
  still reported first, matching the order the author wrote them in.

- A blueprint that asks for a control plane Reliquary has not built
  now fails with a clear error naming the plane. The blueprint
  model's `control-planes` field accepts four values, but only
  `agentless-display` is actually wired up — so `create-machine` and
  `apply-blueprint` (twins `create_machine` / `apply_blueprint`) used
  to accept any of the four without complaint and record a policy
  promising `vnc`, `serial-console`, or `guest-agent`, even though
  nothing could actually reach the machine over them. The check now
  runs before any disk image work happens, so a refused
  `create-machine` leaves no machine behind and a refused
  `apply-blueprint` leaves the machine exactly as it was. The parser
  still accepts all four values in the field — it still names all
  four planes as valid — and it's this new check, not the parser,
  that reports which ones Reliquary can actually deliver.

## 0.1.0.dev2 - 2026-07-26

### Added

- `insert-media` gained a `--file <path>` mode (twin
  `insert_media(slot, media=None, file=None)`) that mounts an image
  file you built yourself, without declaring it as media first: it
  attaches in place, you can still write to it, Reliquary never
  copies it, and Reliquary never hash-verifies it — it is yours to
  manage. On a running machine the guest sees the change live, so a
  program can mount an image, run it, eject it, rebuild it, and mount
  it again with no reboot in between.

- Swapping a floppy image on a running machine is now checked against
  the drive's geometry from when it was launched. QEMU fixes a floppy
  drive's geometry when it attaches the medium at launch, and a live
  swap does not change that geometry — so mounting a differently
  sized image used to reach the guest as read and write errors
  instead of showing up as a new disk. A slot launched empty takes
  QEMU's own default geometry, which Reliquary never chose. Both
  cases now fail with a clear error naming the sizes involved and the
  fix: stop the machine, insert the new image, and start it again;
  after that, live swaps of an image the same size work fine. This
  was found by actually running the swap cycle against FreeDOS on
  QEMU, not by reading the documentation.

- New commands for moving a single file between host and guest,
  addressed the way the guest itself names the file:
  `put-file <host-path> <guest-address>` and
  `get-file <guest-address> <host-path>` (twins `put_file` /
  `get_file`) move one file, addressed as something like
  `A:\TEST.EXE`, never as a host disk image or a staging directory.
  The drive-letter map is built from the machine's declared platform
  and Reliquary's own drive assignment — nothing is figured out by
  inspecting the guest. Both commands work only on a stopped machine
  and require a directory-source (`hostdir`) drive; anything else
  fails with a clear error naming the problem. Non-DOS platforms
  raise `NotImplementedError` instead of assuming DOS's rules apply.

- Machine variables let a script pass a small value back to the
  host. A script's new `set <key> "<value>"` statement records one;
  `rlq get-machine-var <key>` (twin `get_machine_var`) reads it back
  from any process. If the key was never set, the command prints
  nothing (or `null` in JSON) and still exits successfully, so you
  can poll for it in a plain loop. Variables are stored in
  `machine.json` under the operation lock and are cleared every time
  the machine `start`s, so a variable always reflects what the
  current boot produced. The `rlq` and `reliquary` key namespaces are
  reserved. Reliquary uses this same channel for readiness checks:
  you write your own ready script that sets a variable and poll for
  it — Reliquary does not ship a readiness script of its own.

- `run-script` and `fetch-media` now show live progress: both gained
  `--progress (auto | pretty | plain | jsonl)` (twins take a
  `progress=` argument). `auto` picks a mode based on whether stderr
  is a terminal; `pretty` shows one live line, updated in place, with
  elapsed time against the limit; `plain` prints one line per event
  plus a periodic heartbeat; `jsonl` writes the run's whole event
  stream to stdout as JSON Lines and nothing else, with the last line
  being the terminal event that states the outcome. `plain` and
  `jsonl` never prompt for input, so an unbound property now fails at
  preflight instead of leaving the program hanging on a hidden
  question. When a run fails, it now reports what it was waiting for,
  which timeout expired and where that timeout came from, the path it
  took through the phase graph (including how many times each phase
  was revisited), the screen row that came closest to matching, an
  automatic screenshot, and a suggested next command to run.

- All of Reliquary's deliberate errors now share one base class:
  every one of them subclasses `ReliquaryError`, so `except
  ReliquaryError` always works as a catch-all. The four error classes
  used during a run carry the CLI's exit codes — `StaticError` (exit
  2), `PreflightError` (exit 3), `RunFailure` (exit 4), and
  `RunCancelled` (exit 5, which subclasses `ReliquaryError` directly
  and never `RunFailure`, since a cancellation is neither a success
  nor a failure). Exit code `1` now means specifically an unexpected
  fault outside this set of error classes, rather than the catch-all
  bucket everything used to fall into. Pressing Ctrl-C during a
  foreground run now ends it at the next event boundary — any guest
  input already in flight is allowed to complete — emits a
  `cancelled` terminal event, exits with code `5`, and leaves the
  machine exactly as it was.

- A media's `location` field (or its `sha256` field) can now
  reference a property with `${key}`, resolved by `create-machine`,
  `recreate-machine`, or `apply-blueprint` following the normal
  property source order. This lets a blueprint name a
  non-redistributable ISO as `${windows.iso}`, and each host then
  supplies its own path or URL through `--property`, a blueprint
  parameter, a `RELIQUARY_PROPERTY_*` environment variable, the
  properties file, or an interactive prompt. Those three commands
  gained `--property` and `--properties` flags to support this. The
  resolved location is recorded in the machine's state, so `start`
  never resolves it again; an unbound key fails the create before any
  drive is built, and a bound value that is itself another reference
  is refused — a location resolves once and does not chain through
  multiple references. This completes milestone 8.

- A script property can now declare how to derive its own default
  value, using one or more repeatable `default=` candidates, tried in
  order. The first candidate whose references all resolve supplies
  the value; this check happens between the properties file and the
  interactive prompt in the normal resolution order. A candidate can
  reference literal text, another declared property (`${key}`), or
  an `rlq.*` host fact: `rlq.host.username` (normalized the way a
  login name is), `rlq.host.full-name`, or `rlq.env.<NAME>` (the raw
  environment variable value). If a fact is empty or unavailable, that
  candidate is skipped and resolution falls through to the next one.
  Static checks reject a `secret` property that also declares
  `default=`, a candidate that references a secret or an undeclared
  key, a candidate placed after a literal one (which could never be
  reached), and a cycle between properties deriving from each other.
  `check-script` reports which derivation supplies a key's value
  without actually running it.

- Scripts now resolve the properties they declare before the machine
  starts. Each declared property is resolved from the first source
  that supplies a value, checked in this order: a repeatable
  `--property KEY=VALUE` flag (this can never carry a secret — the
  command line is not a credential store), a blueprint `parameter`
  (either a direct value or a `{"property": "<key>"}` redirect), a
  `RELIQUARY_PROPERTY_*` environment variable (with a preflight check
  that fails closed if two of these variable names would collide
  once normalized), the properties file (where a secret is read from
  the credential store), or — if running in a terminal — an
  interactive prompt. Outside a terminal, an unresolved property now
  fails before the machine starts, so a program never hangs on a
  hidden prompt. `run-script` and `check-script` both gained
  `--property` and `--properties` flags; `check-script` reports which
  source supplies each declared property, but never its actual value.
  A `secret` property is only expanded inside `enter`/`type`
  statements, and its value is redacted from the transcript and from
  diagnostics, shown as `«secret»`. Declaring how a property is
  derived, and `${key}` references inside a media `location`, both
  arrive in later milestone-8 stages.

- Secret properties are now actually secret: `set-property <key>
  --secret` stores the value in the host's credential store (using
  the new `keyring` runtime dependency) and writes only an `@secret`
  marker to `user.properties`. The value never appears on the command
  line — on a terminal the command prompts for it without echoing
  what you type, and otherwise it reads the value from stdin until
  EOF — because process listings and shell history are not
  credential stores. Secrets are scoped to the absolute path of the
  properties file that holds the marker, so a `--properties` file and
  the home's own file never share one secret. There is no plaintext
  fallback: on a host with no usable credential store, this fails
  closed instead of falling back to plaintext. Updates are ordered to
  fail safely (writing the credential before the marker, and clearing
  the marker before the credential), so the only leftover an
  interrupted update can produce is an orphaned credential with no
  marker pointing to it — an ordinary `set-property` refuses to
  overwrite that credential, and `unset-property` clears it.
  `get-property` and `list-properties` print a warning to stderr if a
  marker's credential is missing, without changing the result they
  return.
- `--properties <path>`, now available on every property command
  (API `properties_file=`, environment `RELIQUARY_PROPERTIES`),
  selects a properties file that **replaces** the home's file for
  that invocation, so a project-committed properties file makes a run
  self-contained.

- `user.properties` now actually matches the simple, line-based
  format its spec describes: `key = value` lines, `#` comments, blank
  lines, dotted keys that are validated (each segment made of
  letters, digits, `_`, and `-`, starting with a letter; the `rlq`
  and `reliquary` namespaces are reserved), and values taken
  literally as the trimmed rest of the line — no quoting, no escape
  characters, no line continuations. A leading `@` marks a special
  kind of value: `@secret` is the secret marker, and `@@` is how you
  write a literal `@` at the start of a value. Property commands edit
  the file surgically, so every comment, blank line, and ordering
  choice outside the key being changed survives, and writes happen
  atomically. A malformed file is now reported with its path and line
  number, and is never partly rewritten. `list-properties` gained a
  `[PREFIX]` argument that selects one key and its dotted
  descendants.

- Published a JSON Schema for machine state
  (`planning/design/machine-state.schema.json`, covering
  `reliquary-machine.json`), alongside the existing blueprint and
  media-definition schemas. A shared corpus of valid and invalid test
  fixtures (`reliquary_tests/fixtures/conformance/`) now runs every
  fixture against both the parser and the schema, so the two cannot
  drift apart (the schema checks use `jsonschema`, a new dev
  dependency, and are skipped when it or the repo's schemas are
  missing).
- Where blueprints, media definitions, and scripts are read from is
  now controlled by a single global `--assets <dir>` flag (API
  `assets=`). Without it, Reliquary runs in **home mode**: it reads
  from the home's `blueprints/` / `media/` / `scripts/` folders and
  seeds any missing built-in names from the codex — a convenience for
  interactive CLI use. With `--assets <dir>`, Reliquary runs in **dir
  mode**: it walks that project directory recursively by file
  extension as the **only** source, with no home, no codex, and no
  seeding — for automation that needs reproducible results. The
  embedding API has no default source at all, and fails closed until
  one is named, so automation can never silently pick up assets from
  the home directory or the current directory by accident.
  `list-blueprints` / `list-scripts` gained API twins
  (`list_blueprints` / `list_scripts`).
- `--blueprint <name>` now only matches machines within the current
  invocation's asset resolution: it selects only machines whose
  recorded `blueprint-source` equals the blueprint this invocation
  resolves to. This means two projects with same-named blueprints
  never select — and `apply-blueprint` never adopts — each other's
  machines.
- The cache root (`cache/downloads/`, `cache/media/`,
  `cache/machines/`) now resolves independently of the Reliquary
  home: `RELIQUARY_CACHE_DIR`, `--cache`, and `set_cache()` work the
  same way `RELIQUARY_HOME` / `--home` / `set_home()` do for the
  home, and default to `<home>/cache`. Seeding (`seed-blueprint` /
  `seed-media` / `seed-script`) is not affected by this — it always
  writes into `<home>/blueprints` / `<home>/media` /
  `<home>/scripts`.
- `Context(home=None, cache=None)` is now exported from the package
  root. Every function that resolves a path under the home or cache
  now accepts a `context=` parameter, replacing the old `home=`
  parameter. Omitting it uses the same process-global default as
  before; passing a bare string is shorthand for
  `Context(home=that_string)`; passing a `Context` instance pins both
  home and cache explicitly, which is safe to vary from call to call
  within one embedding process. The CLI itself only ever drives the
  process-global default, through `--home`/`--cache` — using a scoped
  `Context` per call is only available through the embedding API.
- Packaging metadata now declares the project homepage
  (`https://github.com/ferroteca/reliquary`) so PyPI can link to
  the repository.
- ROADMAP milestone 5 is complete: `.rlqs` scripts can now declare an
  HTTP server, running only for the life of the script, to serve
  installer answer files. It can serve named content that is either
  written inline in the script or read from a script-relative file
  (`from=`), start with a chosen or redefined set of content at
  `http start`, and expose the reserved `rlq.http.ip` /
  `rlq.http.port` / `rlq.http.url` bindings. It shuts down either
  explicitly with `http stop` or automatically when the script ends.
- Built-in OpenBSD 7.9 amd64 codex assets: an `openbsd-7.9-amd64`
  blueprint, an install ISO media definition, and an install script
  that drives OpenBSD's autoinstall feature over the script's own
  HTTP server.
- Machine blueprints are now validated against the full field
  reference. The parser now checks `backend`, `cpus`, per-drive
  `controller`, `base` (with `difference`/`duplicate`), `hostdir`,
  `enabled`, `control-planes`, `backend-settings`, and `parameters`,
  each failing with a clear error naming the problem. A `cdrom` drive
  accepts only a `media` reference or an empty slot — `size`, `base`,
  and `hostdir` are rejected on optical media. Fields that only
  belong in machine state (`blueprint-digest`, `blueprint-source`,
  `backend-id`, `id`) are rejected by name if used in a blueprint.
  Actually building `base`/`hostdir` drives, and checking whether the
  backend supports what is asked, are later milestone-6 work.
- Media definitions now accept the definition-level annotation
  fields `description`, `notes`, and `redistributable-under`, on
  both the item and the archive forms.
- `create-machine` now actually builds `base` drives (either a
  differencing qcow2 image backed by the base image, or a full
  `duplicate` copy) and `hostdir` drives (a host directory served to
  the guest over vvfat). It resolves platform defaults (`memory`,
  `cpus`, `control-planes`) into the machine's state, and records
  where the machine came from: `blueprint-source` (the resolved
  blueprint's path), `blueprint-digest` (the snapshot it was resolved
  from), and `backend-id`. Controllers other than `ide` are refused
  for now, until the adapter for them is built.
- `insert-media` / `eject-media` now work on a **running** machine,
  not just a stopped one. The change is applied live, over a QMP
  session that verifies the machine's identity first (each removable
  drive is launched with a stable QMP id), and is saved to the
  machine's state at the same time, so what the guest sees and what
  is recorded always match. On a stopped machine, these commands
  still just edit the state, taking effect at the next `start`.
  `set-boot-order` still only works on a stopped machine.
- The global `--json` flag now prints a command's result as one JSON
  document on stdout — exactly what its API twin returns, or `{}` for
  a twin that returns nothing — while all other output stays on
  stderr and exit codes are unchanged. `run-script` and `fetch-media`
  reject `--json`, since they stream output; they point to
  `--progress jsonl` as their machine-readable form instead.
- `search-blueprints` / `search_blueprints()` searches both codex and
  home blueprints, matching a search term against name, description,
  and platform, and reporting where each result came from (`yes` for
  built-in, `seeded`, or `user`). The `seed-blueprint` / `seed-media`
  / `seed-script` commands gained `--only` (API `only=`), to copy
  just the named file without also copying everything it depends on.
- `recreate-machine` / `recreate_machine()` destroys a machine and
  recreates it under the same id, re-resolving the current blueprint.
  `get-machine-dir` / `get_machine_dir()` prints a machine's cache
  directory as an absolute path — this is the door for exchanging
  files outside of Reliquary's own file-exchange commands, and it
  works no matter what phase the machine is in.
- `apply-blueprint` / `apply_blueprint()` re-applies the current
  blueprint to a stopped machine, including bringing a machine whose
  state has diverged from a script back in line with its blueprint's
  shape: memory, cpus, boot order, control planes, metadata, and
  added, removed, `media`, `hostdir`, or empty drive changes are all
  applied, and the machine's baseline digest is re-recorded. If a
  drive's `size` or `base` has changed and that image has already
  been built, the command refuses and points you to
  `recreate-machine` instead.
- Machine lifecycle operations are now crash-safe. Every operation
  that changes a machine takes an exclusive per-machine lock and
  records an operation generation number. The in-between phases
  `creating` / `stopping` / `destroying` are checked and resolved the
  next time any operation touches that machine: an interrupted stop
  finishes, an interrupted create or destroy is rolled forward to a
  full removal, and a create that fails partway through building the
  machine leaves nothing behind.

### Changed

- **A run now returns its output instead of writing it to disk.**
  `run_script()` now returns the run's whole event stream as
  `ScriptRun.events` (a list of plain dicts, in order, with the
  terminal event last) instead of returning the path to a directory
  it wrote. The event stream only exists live — it is what
  `--progress` renders, and it is gone once the run ends — so a
  caller that wants to keep a record needs to hold on to the one it
  was handed. This also makes running scripts on multiple threads
  simple: each run returns straight to its own caller, with no shared
  directory that needs numbering or locking. `ScriptRun.run_dir` is
  gone; `execute_script` now takes an `events=` argument in place of
  `run_dir=`. A screenshot a script asks for now goes under the
  machine's own `screenshots/` directory.

- **The result goes to stdout; everything else goes to stderr.** A
  command that returns a result now prints, in plain mode, exactly
  the human-readable version of what its API twin returns —
  `create-machine` prints `freedos-0`, `new-blueprint` prints the
  path it wrote, `start-machine` prints the port — so you can pipe
  the output without extra flags. Narration ("destroyed machine …",
  "inserted … into …"), progress output, and QEMU's own launch
  messages now go to stderr, and the human `--progress` modes leave
  stdout empty entirely.

- A media-slot preflight failure — `insert`, `eject`, or `set-boot`
  naming a drive the machine does not declare — is now a
  `PreflightError` that exits with code `3`, instead of being
  reported as a run failure. It is caught before any guest input is
  sent, which is what makes it a preflight-level error rather than a
  run failure.

- **Windows is now declared as the supported host.** The packaging
  classifier changes from `Operating System :: OS Independent` to
  `Operating System :: Microsoft :: Windows`, and the README says so
  too. No code changed: the host-path handling for macOS and Linux
  is still there and still written portably, but it is untested, and
  Reliquary would rather leave an untested platform unclaimed than
  quietly promise it works. What it would take to widen support is
  listed in the roadmap's Horizon section.
- **One media cache, and it can always be rebuilt.** Every cached
  payload now lives in `cache/media/`, keyed by the name of the media
  it is — a container (an archive) is just a media like any other, so
  `cache/archives/` is retired, along with `clean-archives` /
  `clean_archives()` and `archives_cache_dir()`. Each cached file is
  named `<media-name>.<ext>`, and that name is its whole identity:
  nothing enters the cache except by downloading or extracting it, so
  every cached file can always be produced again, and there is no
  separate record kept of where it came from.
- **The media cache commands.** `clean-media` reclaims cached
  payloads, skipping anything a running machine still has open;
  `clean-media <name>` deliberately evicts one specific payload.
  `prune-media [--dry-run]` keeps what it calls the **attachment
  closure** — everything the active asset source could still attach —
  and drops whatever only existed to produce that, so after an
  install finishes, the extracted ISO stays cached but the zip it was
  extracted from is deleted. API twins: `clean_media(name=None)`,
  `prune_media(dry_run=)`.
- **`add-media` now declares a local file instead of caching a
  downloaded one.** Codex blueprints for commercial systems ship
  pinned to a specific build but without a URL, since Reliquary has
  no right to redistribute something like a Windows ISO — they name
  the build their scripts expect and leave you to supply the file
  yourself. `add-media <name> <file>` now writes
  `blueprints/<name>.rlqb` declaring that media, pointing at your
  file and pinned to its SHA-256 hash, which the command computes for
  you. The file itself is not copied or moved; the result is an
  ordinary blueprint that you own and can edit. The twin
  `add_media(name, path)` returns the blueprint's path, and the
  function moved out of `reliquary.media` into the
  blueprint-authoring functions.
- **Codex names are generic now, and never tied to a version.** The
  codex exists as a starting point for real blueprints, so its
  entries are now named for the system, with the version living
  inside the file as the source URL and hash instead of in the name:
  `freedos-1.4-plain` → `freedos`,
  `openbsd-7.9-amd64` → `openbsd`, with the media following
  (`freedos-1.4-livecd` → `freedos-livecd`,
  `openbsd-7.9-amd64-install` → `openbsd-installer`). Scripts are
  named for what they do, never for a release:
  `freedos-1.4-plain-install` → `freedos-install`,
  `freedos-1.4-verify` → `freedos-verify`,
  `openbsd-7.9-install` → `openbsd-install`. The `-plain` variant
  marker goes away along with them — the codex entry *is* the plain
  install, and any variants belong to you, not the codex. Bumping the
  codex to a new version is now just a content update under the same
  name, and machine ids get shorter along with their blueprints (for
  example `freedos-0`). Descriptions still name which release each
  entry is tested against.
- **Composed blueprint model.** Reliquary's two separate authored
  JSON formats are now combined into one blueprint file, `.rlqb`. Its
  root is an **array of specs**, each either a `machine` or a
  `media`. As a shortcut, a single spec object by itself is accepted
  in place of a one-item array, and a bare string by itself is
  accepted as a media located at that string. The `type` field
  defaults to `media`, so an object with no `type` field is read as a
  media — the old reading, where a bare root object meant a machine,
  is gone. A machine spec that forgets to write `"type": "machine"`
  now gets a did-you-mean error naming which machine field it used.
  There is no separate `source` or `archive` type any more: a source
  is just a media's `location` field, and an archive is just a media
  that other media name as their **parent** — this was never a
  property of the file itself, only of how it was being used.
  A machine's drive can now name a media by its name, be `null` for a
  removable slot that is declared but starts empty, carry
  `{media, controller, enabled}`, or hold a media written directly in
  place — including the blank `{"size": "20M"}` form with no other
  content, which is the format's one media that has no name of its
  own: it belongs to no namespace, and is named for its drive slot
  once it is built. The old four-way choice of drive content (`size`
  / `base` / `media` / `hostdir`) is gone.
  How a media is built is now controlled by the media itself, with a
  `materialize` field of `new`, `difference`, `copy`, or `use` (`use`
  is the default), plus `size`, one `location` field, a conditionally
  required `sha256`, `read-only`, `extension`, and `children`.
  **Containment works through `parent`/`children`**: any media can
  declare `children` (which can recursively nest more media, with a
  bare string as shorthand for a path) or declare its own `parent`
  from the child's side — either way, the relationship is always
  resolved as the child declaring its parent.
  **Locations follow one rule: a string is interpreted, an object is
  explicit.** Every accepted string form has exactly one equivalent
  object form, which is the canonical form underneath it. A string is
  read by its scheme — a bare path, an http(s) URL,
  `${media:<name>/<path>}`, or `${<key>}` — and the equivalent object
  form is `url` / `local` / `parent`+`path` / `property`. A list of
  these is a list of mirrors, tried in order. A string that looks like
  it uses a scheme but is not recognized is now a parse error, instead
  of being silently treated as a relative path — with an exception for
  a Windows drive letter like `C:/...`, which is not mistaken for a
  scheme.
  **`${...}` is now the one reference syntax in a blueprint.** An
  unqualified reference can be substituted into any string field
  (`\${` is how you write a literal `${` instead); a qualified
  `${media:...}` reference must be the whole value, not part of a
  larger string. References are refused in fields that identify things
  or form the file's structure (`name`, `type`, `children` paths,
  drive keys) and in the closed-vocabulary fields (`platform`,
  `backend`, `materialize`, `controller`, `control-planes`) — those
  stay plain values so an editor can still offer autocomplete from the
  published schema's enum lists. The
  reference syntax itself only supports two forms and carries no
  operators. Actually binding a property's value arrives later, with
  script properties; until then, a `${key}` reference parses
  successfully but then fails with a clear error naming properties as
  not yet supported.
  Validation now happens in **two phases**: the file's shape is
  checked at parse time, and field values are checked at resolution
  time — this is where the rule "a remote location requires a
  `sha256`" now applies, since a referenced value might only resolve
  to a URL once the reference is followed.
  A media's identity is the pair `(name, type)`, tracked in one shared
  catalog. A name is either written explicitly or derived from the
  media's content — never from its drive slot or from the `.rlqb`
  filename — and if the derived name does not fit the naming rules, it
  is repaired automatically with a warning naming both the derived
  name and where it came from, or the whole thing fails if it cannot
  be repaired. Names are matched case-sensitively, but two names that
  only differ in case still count as a collision. Two specs with the
  same identity can coexist across different files only if they are
  identical; if they differ, that is reported as a collision naming
  both.
- **Machine directory reorganized.** `cache/machines/<id>/` now holds
  `machine.json` (previously `reliquary-machine.json`), with the live
  VM's identity folded into it as a `vm` section, written atomically
  together with `phase`. Per-machine disk images move to
  `media/<media-name>.<ext>` (previously `drives/<key>.<ext>`), now
  keyed by the media's name so that swapping a removable slot never
  overwrites the wrong file. Backend-specific files (QEMU's captured
  stderr) move into a `<backend>/` subdirectory. `lifecycle.py` no
  longer owns a state file — `launch_owned_qemu` now returns the
  identity, and `machines.py` is responsible for saving it. Every
  cached payload now lives in the one `cache/media/` directory, keyed
  by the name of the media it is: a container is just a media like
  any other, so there is no separate archive cache.
- The cache-reclaim command `clean-downloads` and its API twin
  `clean_downloads()` are renamed to `clean-archives` /
  `clean_archives`, matching the `cache/archives/` cache they reclaim
  and the composed model's `archive` media. There is no
  backward-compatible alias, since the project is still pre-beta.
- **One published schema.** The blueprint and media-definition JSON
  Schemas are now combined into a single
  `reliquary/schemas/blueprint-schema-v1.json` (packaged with the
  project and versioned as v1 so editors can bind to it), with two
  variants at the root — a machine, which requires its `type` field
  to be declared, and a media, for which `type` may be left out.
  `.rlqm` is retired, and with it the separate `media` asset kind and
  the `<home>/media` folder — media are now specs written inside a
  blueprint.
- `list-blueprints` (the local listing) now resolves through the
  active asset source: in home mode it lists the home's canonical
  `blueprints/` folder (recursively), and with `--assets <dir>` it
  lists the project root instead. It reports each blueprint's
  identity name alongside its full path.
- The blueprint's `name` field is now the id-safe **identity** (used
  as the selection key, and as part of a machine's id), and it
  overrides the filename stem when it is declared. It is not meant
  as a human-readable label — that belongs in `description`.
  `new-blueprint` no longer writes a `version` field, since
  blueprints do not carry a version before beta.
- Media definitions now reject unknown keys, matching both the
  schema's `additionalProperties: false` rule and the blueprint
  parser, so a misspelled field is now a loud error instead of being
  silently ignored.

### Fixed

- A media declared at a local path that no longer exists now fails
  with a `PreflightError` (exit code 3) naming the media and the
  missing path, instead of reaching QEMU as a failure to open the
  file — or, when the media had no `sha256` recorded, being passed
  along anyway and only surfacing as an unexplained QEMU error at
  launch. A local file is used in place rather than downloaded, so it
  has to actually still be there, and this check now runs at every
  fetch: when creating a machine, starting one, and when running
  `fetch-media`. Directory sources (vvfat) are not affected by this
  check.

- Pressing Ctrl-C now stops a run during a large media fetch, instead
  of only taking effect minutes later. Cancellation used to only be
  checked between statements, so an `insert` that had to download a
  LiveCD would run the whole download, its hash check, the
  extraction, and that extraction's own hash check to completion
  before noticing the cancellation — even though the documented
  behavior promises that guest input deliveries are atomic while host
  transfers can be aborted. The run engine's cancellation check now
  reaches into the transfer loops themselves and is checked at every
  chunk (D40).
- An `insert` statement that fetches media now reports its progress.
  It never passed the run's event stream down to the fetch, so a
  multi-hundred-megabyte download would print one line and then
  nothing until it finished — silence that looked like a hang.
  Transfer and verify events now appear as they happen, the same as
  every other fetch (D40).
- A second Ctrl-C now interrupts immediately, instead of repeating
  the same graceful stop request. The handler used to treat every
  repeat press as the same single flag, leaving no way to escape a
  stop that would not complete short of killing the terminal (D40).
- A download that stalls after connecting now fails that mirror
  instead of hanging forever: `urlopen` now has a 30-second timeout,
  and a mirror that times out falls through to the next one (D40).
- An interrupted transfer no longer leaves its scratch file behind in
  `cache/media/`. A fetch writes to `<name>.part` and only renames it
  once the download is complete, but a cancelled or failed fetch used
  to leave the partial file behind — up to hundreds of megabytes for
  a LiveCD. There is no resume support, so the partial file is now
  deleted on every incomplete download (D40).
- The built-in FreeDOS install script no longer stalls at the
  installer's first confirmation screen. It used to press Enter on a
  menu the installer draws *before* it starts reading the keyboard,
  so the keystroke was lost and the install timed out at the next
  step. It now uses `select "Yes"`, like every other confirmation in
  that script — `select` waits for feedback and confirms the
  highlight has actually moved before committing to the choice.
- The guest-console commands (`screen`, `type`, `enter`, `press`,
  `exec`, `select`, `wait`, `screenshot`, `hmp`) work again against a
  machine chosen with `--machine` / `--blueprint`. They used to
  resolve the machine's QMP port but not its directory, so the
  identity check looked for the recorded VM in the Reliquary home
  instead of in the machine's own directory, found nothing there, and
  refused every command as an identity mismatch.
- `set-property --secret` no longer writes the secret's value into
  `user.properties` in plaintext; it now stores the value in the host
  credential store and records only the marker there. (Previously,
  the command accepted the `--secret` flag but silently ignored it.)
- Usage and help text now names whichever entry point was actually
  invoked (`reliquary -h` prints `usage: reliquary ...`, `rlq -h`
  prints `usage: rlq ...`), instead of always hardcoding `rlq`.

### Removed

- Run persistence, and the commands that managed it, are removed.
  There is no more `cache/machines/<id>/runs/` directory, no stored
  `run-events.jsonl` or `transcript.txt`, no retention policy, and no
  `list-runs` / `run status` / `run delete` / `begin-run` /
  `end-run`. The stored event stream existed so that a separate
  process could follow along and read it, but following a run you did
  not start yourself is unfinished work that was left for later — so
  nothing actually read the stored file. The whole recorded-run model
  only comes back if that follow-along feature gets built.

- The milestone-1 root-home machine model is gone, absorbed into the
  cached-machine model: `reliquary.Runner`, `MachineConfig`,
  `run_guest_program()`, `run_task()`, and the module-level `start()`
  (all of `workflows.py`), the old root-home `machine.json` /
  `drives/` / `vm.json` layout and the `drives_dir()` path helper, the
  legacy filesystem drive auto-discovery (`drives.py`), and bare `rlq
  start-machine` / `rlq stop-machine` with no selector. Machines are
  now created and driven through `create-machine` / `start-machine`
  (a selector is required) and `run-script`. There is no backward
  compatibility kept before beta.
- The media-definition `redistributable-under` field is removed, as
  overkill: Reliquary does not attach licensing metadata to a
  definition at all. Whether a codex definition may carry a `url` is
  now a maintainer discipline instead — the codex may only link to
  downloads that are actually legal to redistribute — rather than a
  field recorded per definition.
- The dead `downloads_cache_dir` path helper (both the `Context`
  method and the module-level twin) is removed — it was a leftover
  pointer at the retired `cache/downloads/` directory. Its live
  replacement, `archives_cache_dir` (`cache/archives/`), is now
  exported from the package root in its place.
- `delete-media` / `delete_media()` and `seed-media` / `seed_media()`
  are removed outright. Media are now components inside a `.rlqb`
  file, so the first command could only ever fail and the second
  could only ever do nothing — neither is kept around as a
  do-nothing shim. Removing a media now means editing the blueprint
  that declares it, and seeding a blueprint brings its media along
  inside the same file. Every media command now refers to the media
  itself, never to the file that owns it.

## 0.1.0.dev1 - 2026-07-22

### Added

- [TRADEMARKS.md](TRADEMARKS.md): the name **Reliquary** is owned by
  Paul Galbraith and cannot be used for a fork or redistribution; the
  BSD-3-Clause license only covers the software itself. Linked from
  the README and CONTRIBUTING.
- `list-media` / `list_media()` lists the names of media items in the
  home library, or in the codex with `--builtin` / `builtin=True`.
- `delete-media` / `delete_media(name)` removes a media definition
  from the home, and refuses to if any machine drive still
  references an item from that definition.
- `delete-blueprint` / `delete_blueprint(name)` removes a blueprint
  file from the home, and refuses to if any machine of that
  blueprint still exists, naming the machine ids.
- An opt-in FreeDOS install-and-verify QEMU integration test is added
  (`reliquary_tests.test_freedos_install_integration`): set
  `RELIQUARY_INTEGRATION=1` to run it, and optionally set
  `RELIQUARY_INTEGRATION_HOME` to keep the media cache between runs.
  It is skipped by default under the regular unit test suite.

### Fixed

- Script samples now treat a guest power-off as `machine=stopped`
  when `lifecycle.qmp_session` raises its "no longer reachable"
  `RuntimeError` after clearing a stale `vm.json`. A genuine identity
  mismatch still fails closed as before. This unblocks the FreeDOS
  install/verify scripts' shutdown after `fdapm poweroff`.

### Changed

- Milestone 4 (script-surface realignment) is complete: FreeDOS'
  `run-script install` and `run-script verify` now finish end to end
  on `--blueprint freedos-1.4-plain`, and `check-script` reports the
  timing plan.
- Documentation now follows the redesigned script surface and the
  twin-name CLI: `planning/examples/README`, the script-spec and
  related design pages, and `docs/` all use `run-script`, the
  colon-free `machine` header, and `insert`/`eject`/`set-boot`,
  instead of the names they replaced.
- The old script surface and the CLI/API names it replaced are gone
  from the live source tree. `reliquary_tests.test_old_surface_purge`
  fails the test suite if they reappear anywhere in the package,
  tests, docs, README, AGENTS, examples, or shipped codex scripts.

- CLI and API command names are now identical, dash-separated
  (ROADMAP milestone 4, task 9): every command's name is its API
  twin's name with dashes instead of underscores. The lifecycle verbs
  are `create-machine` / `start-machine` / `stop-machine` /
  `destroy-machine`; listings are `list-machines` / `list-blueprints`
  / `list-scripts` (the old nested `list …` form and its singular
  aliases are gone); media and cache commands include `fetch-media`,
  `clean-downloads`, `clean-media`, `insert-media`, `eject-media`, and
  `set-boot-order`; and the guest-console family now matches the
  script language (`type` raw / `enter` / `press` / `exec` / `select`
  / `screen`). Flags can appear before or after the command word,
  without needing a separate hidden parent-parser copy of each one.
  `--machine` now takes the full `<blueprint>-<n>` id exactly — no
  prefix matching, and no more pairing `--blueprint` with a bare
  number — and is mutually exclusive with `--blueprint`. The
  embedding API's names match this too (`create_machine`,
  `start_machine`, `stop_machine`, `destroy_machine`).

### Added

- The redesigned script surface now has a typed parser:
  `reliquary/script_grammar.lark` mirrors the formal grammar in
  `planning/design/script-spec.md`, and `reliquary.script_parser`
  builds a typed tree from it. Reliquary's own lexer feeds tokens
  into lark's LALR(1) parser through a custom lexer, so lexical error
  messages keep their originally authored wording. `lark` joins the
  runtime dependencies. The runtime itself still runs on the old
  surface for now; wiring the new parser into the runtime is ROADMAP
  milestone 4's runner retarget.
- Static validation of the redesigned surface: `reliquary.script_validation`
  checks the legality rules the grammar deliberately does not
  enforce, and each diagnostic names the construct involved and cites
  its rule id — the two script shapes and what belongs in each (S3,
  S10), unique phase names (S5), one condition per observation on a
  known channel of the right kind (S7), the branching `wait`'s shape
  and depth limit (S8), whether phases are sequential or reactive
  (S9), and the rules for terminating statements (S11). Parsing a
  document now runs these checks.
- The script timing model: `reliquary.script_timing` resolves a
  script's whole timing plan at parse time — every observation's
  effective timeout and which scope supplied it (the innermost of
  statement, branching `wait`, phase, header, or the built-in 60
  seconds wins), each phase's per-activation time budget, and the
  run's overall deadline. Because of this, a timing failure can name
  the specific clock that expired and where it came from, and
  `check-script` can report the whole plan without running anything.
  Alongside this, the placement-matrix rejections now explain why and
  cite S2: putting `deadline` on a single observation would just be
  another word for `timeout`, `timeout` on a handler belongs on its
  container instead, and `stable` needs something to actually match
  before it can hold. Durations must be positive (S5), and a phased
  script whose reachable phase graph can cycle must declare a header
  `deadline` (S12) — the diagnostic names the route that closes the
  cycle.

- The script runtime now executes the redesigned surface. `.rlqs`
  runs walk the phase graph from `entry` to `finish`, dispatch
  branching `wait` blocks in the order they are declared, and run a
  reactive phase's standing `always` handlers to completion. A fired
  handler is consumed for that appearance and only re-arms once a
  later sample shows its condition no longer holds, so a confirmation
  screen that stays on the display produces input once per appearance
  rather than once per sample. Every clock comes from the timing plan
  built at parse time, so a timing failure names the clock that
  expired and where it came from, and observation timeouts, reactive
  intervals, per-activation phase budgets, and the run deadline are
  all enforced at every sample and statement boundary.
- The shipped scripts now use the redesigned surface: the built-in
  `freedos-1.4-plain-install` and `freedos-1.4-verify`, and the pair
  under `planning/examples/`. The install script is the language's
  reference example. Seeding a script still brings along the media
  definitions its `insert` statements name — the scan now follows the
  `@name` spelling, and a `$key` property reference does not name any
  static item to seed.
- Script sessions are now identity-verified. Every sample and input
  statement opens its own QMP session through `Machine.qmp()`, so the
  runtime can no longer drive a VM it has not confirmed is the one
  this home actually started, and no session is held open while a
  handler body runs.
- `check_script()` / `rlq check-script` now report a script's
  resolved timing plan without running it: each observation's
  effective timeout and which scope it came from, phase budgets, and
  the run deadline. The check is read-only — it does not seed
  anything or create a machine. With a machine selector, it also
  preflights media slots. Static errors exit with code 2.
- `press` key names are now statically checked against the script
  language's closed, portable vocabulary (S14). Unknown names, bare
  printable characters, and malformed chords now fail before the
  machine starts; chords such as `ctrl+c` remain valid.

### Removed

- The milestone-one script parser (`reliquary.script`) is gone,
  along with the surface it parsed: `state`/`->`/`done`/`expect`,
  colon headers, comma modifiers, the `regex` keyword, bare
  `stopped`, `<key>` tokens inside `type`, and the `boot` verb (now
  `set-boot`). `parse_script` and `load_script` now live in
  `reliquary.script_parser` and speak the new surface; the `State`
  and `ExpectBranch` exports are replaced by `Phase`, `Handler`, and
  `Property`. Scripts written for the old surface no longer parse —
  they need to be rewritten, since there is no bridge between the two.
- `ScriptRun.final_state` is renamed to `ScriptRun.final_phase`, and
  `rlq run-script` now prints `final script phase:`.
- Scripts no longer carry embedded JSON. The `media <label> { ... }`
  block is deleted from the language, along with the planned
  `landmark <name> { ... }` block, the install-on-first-run model
  they implied, and `fetch-media --script`. Media definitions
  (`.rlqm`) and landmark declarations (`.rlql`) are now their own
  authored files, resolved next to the script and referenced by
  `@name`. A script that still contains a `media` block no longer
  parses; move that definition into its own file next to the script.
  The parser's `EmbeddedMedia` model and the `reliquary.EmbeddedMedia`
  export are gone. The reasoning behind this, and what was weighed,
  is in `planning/DECISIONS.md`.

### Changed

- Screenshot conversion now uses Pillow in place of a hand-written
  PNG encoder and PPM header parser, so `pillow` joins the runtime
  dependencies. It also underpins the planned landmark image assets:
  decode normalization, pixel comparison, and PNG text chunks that
  record where a capture came from.
- `rlq list-machines` and `rlq list-blueprints` now print an explicit
  `(no ...)` message when the result is empty, instead of a column
  header sitting over zero rows — matching `list-scripts`, which
  already did this. (`#5`)
- `rlq list-scripts --blueprint <name>` now heads its first column
  `LABEL`, naming what it actually lists: the labels from the
  blueprint's scripts map, used as `run-script` verbs. The bare `rlq
  list-scripts` listing keeps the header `NAME`, which is what it
  lists: script file stems.
- Scrubbed private project-history references from release-facing
  documentation and package metadata.
- Removed obsolete references to a superseded installation
  abstraction; built-in blueprints, media definitions, and scripts
  are now the documented way to share assets.
- Reinstated the released 0.1.0.dev0 section of this changelog to its
  exact release-time wording, including prior-project history — it is
  real history. From here on, released changelog history is
  append-only: it is never retroactively edited, with two exceptions —
  minimal privacy or legal redaction, and a wording-only pass to plain
  English (2026-08-26, this repo's standing style rule — see
  `AGENTS.md`) that changed no fact, date, number, or name in any
  entry. The specific text this rule exists to protect — the
  prior-project history above — was left untouched by that pass; check
  `git log -p -- CHANGELOG.md` for the exact wording of any entry as
  first released.

## 0.1.0.dev0 - 2026-07-20

The relict project — the agentless QEMU guest automation harness Reliquary
was built on — has been folded into Reliquary. Its modules now live in the
`reliquary` package (its drive-inventory module renamed to `drives.py`), its
CLI commands are `reliquary` subcommands alongside `install`, and its home,
`RELICT_HOME`/`RELICT_QEMU_HOME` environment variables, and default
`Documents/relict` directory are replaced by the Reliquary equivalents
(`RELIQUARY_HOME`, `RELIQUARY_QEMU_HOME`, `Documents/reliquary`). The notes
below merge both projects' unreleased histories with the relict entries
renamed accordingly.

### Recipe layer

Initial scaffold: package structure, CLI stub, and recipe module convention.

The planned `.rlqs` scripting language now separates linear scripts
from explicit state machines, uses run-to-completion reactive states,
and adds immutable text, media, and secret inputs bound from JSON
responses, a home-wide user property registry, or interactive prompts.
Ordinary reusable values live in `properties.json`; passwords and
product keys can use secret markers backed by the host credential
store, and script declarations bind them with `property:`. Scripts may
also embed the same JSON media-definition objects used by the shared
library; after preflight, running a script installs missing definitions
into `media/` without overwriting or updating existing files, while
verified artifacts continue to use shared caches. Console input is
expressed with `enter` rather than a separate `run` verb; guest reboot
remains console or menu input, while host power cycling is the explicit
`stop`/`start` pair. Timing, matching, preflight, transcript, and
offline file-exchange semantics are specified consistently ahead of
implementation.

Added the `freedos-plain` recipe's preparation steps: the FreeDOS 1.4
LiveCD ISO is downloaded into the Reliquary home (the distribution
zip is deleted after extraction) and SHA-256 verified on every run,
and
a 20 MiB dynamically allocated qcow2 (v3) target disk is created. The
`reliquary install <recipe>` CLI command runs a recipe by name, and
`--display` (the `display` recipe parameter) requests a visible QEMU
window for a recipe's guest steps.

The recipe now extracts the LiveCD ISO and boots the installation
machine with the ISO and target disk mounted, booting
from the CD. After start it waits for the LiveCD's first install menu
(`Welcome to FreeDOS 1.4 (LiveCD)`), selects "Install to harddisk",
accepts the defaults for preferred language and the installer welcome
screen with Enter, confirms partitioning drive C: and the required
reboot with Yes, accepts the default keyboard layout with Enter,
chooses the "Plain DOS system" package set (excluding the "with
sources" sibling), and confirms with Yes on the ready-to-install
prompt. `install` then blocks while the machine runs and always shuts
it down when it ends — including on Ctrl-C, which the CLI reports as
an interruption instead of a traceback.

The recipe layer has since been retired in favor of the `.rlqs`
install/verify scripts on the blueprint machine model (see the
machine-layer notes below); `rlq install` no longer exists.

### Machine layer (formerly relict)

### Changed

- Machine ids are `<blueprint>-<n>` instead of random UUID hex.
  `create` allocates the lowest free number for the blueprint
  (reused after `destroy`), serialized by a per-blueprint lock.
  Select with `--machine NAME-N`, `--blueprint NAME --machine N`,
  or `--blueprint NAME` when that blueprint has exactly one machine.
  `short_id()` is removed; the id is already the display form.

### Fixed

- An interrupted machine deletion, such as a transient Windows file lock,
  no longer leaves the machine permanently in the `destroying` phase;
  rerunning `rlq destroy` now retries it safely.

- A configured drive source for a slot already declared by a filesystem
  drive now fails closed with a slot-clash error instead of silently
  replacing it. An explicit `enabled: true` on the configured entry
  remains the deliberate way to override the filesystem drive, and
  `enabled: false` still unmounts it.

### Removed

- The recipe layer is retired (milestone-1 Spike 12): the `recipes/`
  package, the `rlq install <recipe>` command, and the recipe-era
  helpers (`ensure_media`, `install-media/` and `machines/<recipe>/`
  home paths) are deleted. The `.rlqs` install/verify scripts on the
  blueprint machine model replace them; there is no migration
  (pre-release).

### Added

- Milestone-1 Spike 13 lands the media-in-script machine model:
  blueprints declare empty removable drives (`"cdrom0": null`) — the
  blueprint alone defines machine topology — and scripts `insert` a
  defined media item to a declared slot and `eject` it, persisted in
  `reliquary-machine.json` across stop/start (`insert_media` /
  `eject_media` on the Python surface; stopped machines only for
  now). The new `machine: running | stopped` script header declares
  the state a script expects: `stopped` scripts start the machine
  themselves after inserting media, and `script` no longer
  unconditionally auto-starts. Insert/eject slots are statically
  preflighted against the machine before any guest input, and a
  guest-initiated power-off observed by `wait stopped` reconciles the
  machine back to phase `ready`. The built-in `freedos-1.4-plain`
  blueprint boots `["hdd0", "cdrom0"]`: a blank hard disk falls
  through to an attached LiveCD for install, then boots the
  installed disk afterward with no boot-order change. Scripts may
  still reorder boot devices with the `boot` verb / `set_boot_order`
  while the machine is stopped.

- Milestone-1 Spike 10 wires `rlq --blueprint|--machine script <label>`:
  resolve the label through the blueprint `scripts` map (bare stem when
  absent), seed a missing script from the built-in library, create a
  machine when `--blueprint` names one with none yet, and execute under
  an append-only run directory
  `cache/machines/<id>/runs/<timestamp>-<run_id>/` with `transcript.txt`,
  `screenshots/`, and `output/`. `run_script()` is the Python surface;
  `--display` forwards to the runtime. A `screenshot` inside a run
  verifies the QMP session against the machine's own `vm.json` while
  writing the image into the run record (`machine.screenshot()` gained
  a `directory` override to separate the destination from the
  identity home). Embedded media blocks,
  `--responses`, and `check-script` remain later spikes.

- Milestone-1 Spike 9 executes FreeDOS-shaped `.rlqs` scripts against a
  cached QEMU/DOS machine: normalized VGA `wait`/`expect`,
  `enter`/`type`/`press`/`select`, `screenshot`, host `start`/`stop`,
  and (with Spike 13) stopped-machine `insert`/`eject`/`boot`,
  starting a ready machine when needed and leaving it running unless the
  script stopped it. `expect` closes its polling QMP session before
  running the matched branch: QEMU's QMP server admits one client at
  a time, so a branch statement opening its own session while the
  polling session was still held would block forever.

- The global `--home` now reaches the `start`/`stop`/`destroy`
  subcommands: their own `--home` options no longer clobber an
  already-parsed global value with their default, which silently
  targeted machines in the default home.

- VM identity is per QEMU instance, not per name: every start passes
  a fresh `-uuid`, records it in `vm.json` beside the name, and every
  session verifies `query-uuid` as well as `query-name`. Same-numbered
  machines of one blueprint in different homes share their readable
  name, so a name match alone can no longer authorize a command
  against the wrong home's VM. The legacy root-home start path now
  uses the readable name `reliquary-machine` instead of a random hex
  suffix, since uniqueness comes from the uuid. A machine stop that
  fails closed on an identity mismatch no longer resets the phase to
  `ready`: the machine's own QEMU may still be running, so the phase
  only reconciles when the recorded VM is actually gone.

- Milestone-1 Spike 8 parses the FreeDOS-shaped `.rlqs` language into an
  immutable script model: headers, embedded media definitions, linear and
  state-machine bodies, `wait`, `expect`, `enter`, `type`, `press`,
  `select`, `screenshot`, `insert`, `eject`, `boot`, `start`, `stop`,
  and explicit transitions report source-located, compiler-style
  syntax and static-validation errors.

- The built-in library seed: blueprints, media definitions, and
  scripts ship inside the package under `reliquary/codex/`
  (included in wheels and sdists, readable from zip-bundled
  installs) and are copied out into the home on first reference —
  resolving an unknown blueprint via `create` seeds
  `blueprints/<name>.json` plus the media definitions and scripts
  it references, and resolving an unknown media name seeds its
  definition. A file already present in the home is never
  overwritten; deleting a copy is how it is refreshed. First
  entries: the `freedos-1.4-plain` blueprint, the
  `freedos-1.4-livecd` media definition (URL carried with an
  explicit redistribution assertion — FreeDOS is GPL free
  software), and the install/verify scripts.
- Machine lifecycle CLI and API for cached machines: `create`
  / `start` / `stop` / `destroy` / `list machines`, with
  `--blueprint` (sole machine of that blueprint),
  `--machine <blueprint>-<n>` (full id or unambiguous prefix), or
  `--blueprint NAME --machine N` (machine number). Machine ids are
  `<blueprint>-<n>` with the lowest free number reused after
  destroy; allocation is serialized per blueprint. `create_from_blueprint()`,
  `list_machines()`, `resolve_machine()`, and `machines.start` /
  `machines.stop` / `destroy` operate on `cache/machines/<id>/`;
  QEMU ownership (`vm.json`) lives under the machine directory.
  Bare `rlq start` / `rlq stop` without a selector still use the
  transitional root-home `MachineConfig` path. `apply`,
  interaction-via-selector, and multi-backend remain later spikes.
- Immutable machine-blueprint parsing for the milestone 1 subset:
  `parse_blueprint()` / `load_blueprint()` accept `platform`, `memory`,
  `drives` (`size` or `media`), `boot`, `name`, `description`, and
  `scripts`; canonicalize drive aliases, sizes, memory, and boot keys;
  resolve media names through the shared media library; and reject
  unknown fields, slot clashes, invalid sources, and undeclared boot
  targets.
- Machine materialization: `create(blueprint)` writes
  `cache/machines/<blueprint>-<n>/reliquary-machine.json`, qcow2
  images for `size` drives, and media payload paths for `media`
  drives; `machine_drive_args()` renders QEMU `-drive` tokens from
  that state.
- Media definitions per docs/media-spec.md: `parse_definition` /
  `load_definition` validate both the item (direct-download) form and
  the archive form (one source archive itemizing payloads, single
  URL), and `resolve_media(name, home=None)` resolves an item by name
  across the `media/` library, failing on duplicates. Mirror URL
  lists and several definitions sharing one archive remain
  unimplemented (milestone 2).
- `fetch_media(name, home=None, on_mismatch="fail")` returns a
  defined item's verified payload on demand, trying the cheapest
  source first: an existing payload that verifies is returned
  untouched, a cached source archive that verifies is re-extracted,
  and only then is the definition's URL downloaded. Source archives
  are cached under `cache/downloads/` and payloads under
  `cache/media/`; every file is SHA-256-verified before use, and a
  missing source is an error naming the item, file, and hashes.
  An existing payload or archive that fails its hash is never
  silently discarded: `on_mismatch` picks between failing fast with
  both hashes (`"fail"`, the default), an interactive
  delete-and-refetch checkpoint (`"prompt"`), and pre-approved
  deletion (`"refetch"`, which the planned `--refetch-mismatched`
  CLI flag will map to). A mismatched file whose definition names no
  source is always kept and reported.
- Path helpers for the planned blueprint home layout:
  `blueprints_dir`, `media_dir`, `scripts_dir`, `cache_dir`,
  `downloads_cache_dir`, `media_cache_dir`, and `machines_cache_dir`
  (each accepts optional `home=`). The existing `drives/` /
  `machine.json` / `vm.json` machine model is unchanged.
- `cursor_menu_select(item, timeout=30, exclude=(), port=None,
  home=None)` and the `Reliquary menu ITEM [--exclude TEXT]` CLI
  command select an entry in a text menu that is navigated with the
  cursor keys — a boot menu, for example. Rows containing the
  `exclude` text are never selected. On menus that rewrite their rows
  as the highlight moves (like the FreeDOS installer's language
  chooser), Reliquary navigates using the row where the item last
  matched, before the row was rewritten.
  Navigation works by watching what the screen actually does:
  Reliquary presses the up and down cursor keys, tracks the selection
  highlight by reading the VGA attribute bytes, and only presses
  Enter once the highlight is on the one screen row that matches the
  given text (matched case-insensitively; an exact match on a row
  wins over a row that merely contains the item, and any other match
  must be unique). After each keypress, Reliquary waits for the
  screen's repaint to finish and settle, rather than acting on the
  first change it sees — so a menu that repaints slowly (like the
  FreeDOS language chooser, which pauses partway through as it loads
  each translation) is never read while it is only half-drawn: if a
  screen difference does not show a row gaining the highlight's
  attribute, Reliquary reads the screen again instead of acting on
  it, because a key sent to a menu that is still repainting can be
  lost when the menu flushes its keyboard buffer.
  Before the first keypress, Reliquary waits for the screen to hold
  still and only then takes its baseline reading, so that
  self-repainting parts of the screen — a clock, a countdown, a
  blinking indicator — are ignored for the rest of the navigation.
  Skipping this wait would let the menu's own first paint be mistaken
  for one of those self-repainting cells, hiding the very thing
  Reliquary is trying to track. If a keypress produces a screen change
  that cannot be classified, Reliquary re-learns which cells are
  self-repainting and finds the highlight directly by its attribute
  instead — so a keypress that lands at the edge of the menu, or a
  read that was briefly confused, recovers instead of failing. Enter
  is only sent once a fresh read confirms the highlight is actually
  on the target row. This is also available as
  `Machine.cursor_menu_select()`; `machine.vga_screen(qmp)` now also
  exposes the attribute bytes alongside the text rows.
- `create_hdd_image(filename, capacity)` creates a sparse qcow2 v3
  (`compat=1.1`, no preallocation) hard-disk image at the given path.
  Capacity accepts a qemu-img size string (`"2G"`, `"512M"`) or a
  positive integer MiB value. `find_qemu_img()` resolves `qemu-img`
  with the same search order as `find_qemu()`.
- `Machine.screen_text()` and `Machine.wait_text(pattern, timeout=60)`
  read and wait on the guest's VGA text screen directly from a `Machine`,
  so tasks and adapters can block until specific output (for example a
  boot menu) is displayed. The module-level `screen_text()` and
  `wait_text()` now delegate to these methods.
- `documents_dir()` publicly resolves the user's platform Documents
  folder (or `None` when it cannot be determined), so embedding
  projects can anchor their own state directories the same way Reliquary
  anchors its home.

### Removed

- The `boot-to-dos` CLI command. Wait for a prompt with `reliquary wait`.
  Programmatic boot readiness remains `AgentlessGuestExec.wait_ready()`.

### Changed

- Keyboard input and screen interaction moved to the platform-neutral
  machine layer, since they need only QMP and VGA text mode, not DOS:
  `char_keys()`, `send_keys()`, `send_text()`, `cursor_menu_select()`,
  `screen_text()`, and `wait_text()` now live in `reliquary.machine`, and
  `Machine` gains `send_keys()`, `send_text()`, and
  `cursor_menu_select()` methods. `interaction_agentless` retains only
  the DOS prompt-driven `AgentlessGuestExec` adapter. Package-level
  imports (`reliquary.send_text`, ...) are unchanged.
- Added an internal, runtime-checkable `GuestExec` protocol and isolated the
  QMP keyboard/VGA implementation as `AgentlessGuestExec`, with the DOS
  workflow and CLI consuming that adapter directly. The former
  `boot_to_dos()` and `run_command()` Python facades were removed; use
  `AgentlessGuestExec.wait_ready()` and `.execute()`.
- Exposed the identity-verified QMP session through `Machine.qmp()` for raw
  `cmd()` and `hmp()` access; interaction adapters now depend on `Machine`
  instead of opening QMP connections themselves.
- One validated `MachineConfig` now threads through the workflow and
  lifecycle layers. `start()`, `run_task()`, and `run_guest_program()` take a
  `MachineConfig`, versioned mapping, or JSON path as their sole machine
  settings input; `Runner.run()` passes its configuration through unchanged,
  and the QEMU launcher consumes that configuration instead of loose hardware
  arguments. The default QEMU argument vector is unchanged.
- The Python API now automatically discovers and loads `<home>/machine.json`
  when no explicit configuration is provided, matching CLI behavior. Explicit
  API values (passed as `MachineConfig`, mapping, or path) override the file
  values; `Runner` likewise loads the file when `config=None`.

### Added

- `--machine PATH` CLI argument for explicit machine configuration file selection; when omitted, the CLI automatically
  loads `<effective-home>/machine.json` if present, otherwise uses the default `MachineConfig()`. Explicit CLI
  overrides (`--platform`, `--qemu`, and raw QEMU arguments) apply on top of the loaded configuration; an omitted
  `--platform` leaves the file's platform unchanged, while `--platform dos` still overrides a non-DOS file value.
- `MachineConfig.from_file()` and `MachineConfig.from_mapping()` load a versioned JSON/mapping machine document
  (`version` must be `1`), normalize it immutably, resolve relative drive sources from the file directory or an
  explicit `base_dir`, and apply field overrides with deterministic merge rules for drives and options.
- Package-based `reliquary/` source layout split into home containment, declared media, ownership-safe lifecycle, generic
  machine interaction, DOS platform behavior, workflow orchestration, and CLI modules while preserving the existing
  root import and command-line interfaces.
- The complete DOS runner from the original implementation: DOS remains the default platform, while
  `MachineConfig(platform=...)` and `--platform` make the platform choice explicit. The reusable QEMU machine layer is
  shared; unimplemented non-DOS platform workflows fail explicitly instead of borrowing DOS assumptions.
- DOS 8.3 executable-name validation now belongs to the DOS platform module rather than generic workflow
  orchestration, so future guest-program workflows are not constrained by DOS naming rules.
- `Runner`/`MachineConfig`: the generic embedding surface for callers driving Reliquary as a runner.
  `Runner(home=None, config=None)` is a configured DOS test machine bound to one absolute home (the established
  process default when omitted), and
  `run(exe_path, args)` automatically ensures bootable media before performing the full `run_guest_program()`
  lifecycle. Provisioning is private; callers create distinct runners with distinct homes for concurrent runs, and
  per-home `vm.json` keeps VM ownership sound.
- Removed the `boot_floppy_image` and `boot_hdd_image` configuration shortcuts. Custom boot media uses the ordinary
  declared-drive inventory.
- `MachineConfig.drives` adds immutable configured drive specs using canonical logical slots plus `floppy`/`hdd`
  slot-zero aliases. A spec accepts a source path or `{source, options}` mapping; files mount as images, floppy and
  hard-disk directories mount as vvfat, and CD-ROM directories fail validation. Configured and home-directory media
  resolve into one inventory with slot conflicts rejected before launch.
- `MachineConfig.machine` maps directly to one QEMU `-machine` argument. A string selects the machine type; a mapping
  combines required `type` with immutable scalar properties and renders Boolean values as `on`/`off`. A raw
  `-machine` or `-M` in `qemu_args` conflicts with the structured field.
- `MachineConfig.memory` configures guest memory as a positive integer number of MiB, defaulting to 16 for DOS, 64
  for Win9x, and 256 for WinNT. It maps to one QEMU `-m` argument; an explicit value conflicts with raw `-m` in
  `qemu_args`, while a raw `-m` alone suppresses the platform default.
- The `drives/` directory under the home declares the whole machine by filename, with image content never
  interrogated. Image files `floppy[_<n>].<ext>` (slots 0–1, A: and B:), `hdd[_<n>].<ext>` (slots 0–3, the IDE bus),
  and `cdrom[_<n>].<ext>` (the IDE slots after the hard disks) mount as that medium; bare directories `floppy[_<n>]`
  and `hdd[_<n>]` mount as virtual FAT drives. An unindexed name means slot 0 (so `hdd.img` and `hdd_0.img` clash,
  as do all duplicate slots — fail closed). The idiomatic extension declares the image format: `*.img` and `*.iso`
  are taken as raw and pinned (avoiding QEMU's format-probing warning); any other extension (`hdd.qcow2`,
  `hdd.vmdk`, ...) is handed to QEMU to identify. Memory defaults to 16 MB and the boot order to a best guess from
  the declared media (slot-0 floppy image, else slot-0 hard-disk image, else cdrom); `-m` or `-boot` in the extra
  QEMU arguments overrides the corresponding default.
- The staged guest hard drive's letter is explicit configuration: `staged_drive` on `MachineConfig` and
  `run_guest_program()` (valid C–Z, normalized uppercase; default: match the declared machine, one letter per
  hard-disk slot before the staged drive, so C: on a floppy-boot machine and D: behind a slot-0 hard-disk image;
  letters below the default are rejected) declares where the staged vvfat hard disk appears in the guest — the drive
  Reliquary switches to for guest program runs. Staging targets the highest staged directory declared among the
  hard-disk slots, or `drives/hdd` created on demand.
- Explicit `home=` keyword on `download()`, `start()`, `stop()`, `run_guest_program()`, and the `drives_dir` path
  helper, overriding the process-global home per call. The
  existing `set_home()`/`--home` surface is unchanged.
- Installable `reliquary_tests` unit-test package, runnable with
  `python -m unittest -v reliquary_tests` so users and downstream packagers can verify an unpacked source distribution or
  installed wheel.
- Contributor guidelines covering development, verification, pull requests, and BSD-3-Clause contribution licensing.
- agentless DOS-under-QEMU automation harness — boot DOS headless, send keystrokes over QMP, scrape the 80x25 text
  screen from VGA memory, run commands with prompt-based completion detection, take screenshots, stage guest media
  via vvfat, and run guest programs end to end
  (`run_guest_program`, returning the program's redirected output).
- Visible manual VM sessions with `reliquary start --display`: the command returns once QEMU is ready, leaves the DOS VM
  running for direct interaction, and `reliquary stop` closes it through the same ownership-verified lifecycle.
- Bring-your-own boot image: Reliquary boots whatever the user declares under `drives/`.
- Test-framework result parsing is out of scope: Reliquary hands back raw guest output, and interpreting it belongs to
  the caller.
- QEMU binary discovery: `RELIQUARY_QEMU_HOME` / `QEMU_HOME`, then PATH, then well-known install locations; `--qemu`
  overrides.
- Home directory (boot images, staged guest drives, screenshots) defaulting to `reliquary/` under the user's Documents
  folder (the Windows known Documents folder, `~/Documents` on macOS, `xdg-user-dir DOCUMENTS` on Linux/BSD), falling
  back to `~/reliquary` when no Documents folder can be determined; override with `RELIQUARY_HOME`, `--home`, or
  `set_home()`.
- Native PNG screendump on QEMU >= 7.1 with a zero-dependency PPM-to-PNG fallback for older QEMU.
- Automatic QMP port selection with the selected port returned by
  `start()`, active-VM metadata under the Reliquary home for separate CLI invocations, and unique-name verification
  before any VM is controlled.
- DOS startup commands such as switching to C: use the ordinary
  `AgentlessGuestExec.execute()` interface rather than special boot options.
- Screenshot names are constrained to filenames so captured images cannot be written outside the Reliquary home.
- The installable test suite uses Python 3.9-compatible syntax, matching the package's declared minimum version.
