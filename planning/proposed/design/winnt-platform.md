<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The WinNT platform workflow: ReactOS as the GUI era's first recipe

> **Status:** the design for **F5**'s fourth deliverable
> (`planning/proposed/FEATURES.md` — "Win9x/WinNT platform
> workflows: GUI installer scripting for the setup GUIs text
> scraping cannot reach, keyboard-first where NT-era setup allows
> it"), narrowed to its WinNT half. **Nothing here is pledged.**
> Unlike this document's siblings
> ([device-growth.md](device-growth.md),
> [hyperv-screen.md](hyperv-screen.md)), the work below is not a
> forward design for code yet to be written: it is the record for a
> recipe that was already authored and then lost to an uncommitted
> stash (`git stash show -p` recovered it this session — the
> resolve.py extension-fallback fix, the codex.json description
> entry, `reactos.rlqb`, `reactos-install.rlqs`, and
> `test_reactos_click_integration.py`, landed on `main` with this
> document's sibling commit). This document is what would have been
> written *before* that work, reconstructed *after* it, so the
> record says what the project means and the code already shows it.

## The demand

**U5** underwrites this, not a fresh use case: D110 settled that
"GUI automation's demand is U5" — the customized-installation
remainder, "a localized installer is a different installer showing
different text — on a graphical setup, different pixels." D64's
split put the delivered half under U21 and left the rest, "the
platform workflows," pledged and waiting in F5
(`planning/pledged/USE-CASES.md:67-68`). F5's own banner already
named the target precisely — "keyboard-first where NT-era setup
allows it" — before any of this recipe existed to prove the claim.

## The scope call: WinNT only, ReactOS the concrete instance

This document covers the WinNT half of F5's item 4 alone. **WEIGHED
AND DECLINED — covering Win9x in the same document**: Win9x installs
from a DOS-bootstrapped real-mode setup into a wholly different GUI
stack, not merely a different theme on the same NT setup wizard — it
is a different recipe with no demand of its own distinguishing it
from WinNT today, and D42's one-sprint bound argues for cutting each
slice separately exactly as F63, F65, and F66 were each cut out of
F5 one at a time. Nothing here forecloses a Win9x recipe later, on
its own pledge, if a demand for it ever arrives.

Within WinNT, the concrete guest is **ReactOS** (0.4.15-x86,
`reactos.rlqb`), not a licensed Windows NT-family release. This is
not merely convenient: the codex ships no media (U5's own text — "the
codex will not carry such flavors") and never needed to for licensing
reasons either way, since every codex media declaration is a location
and a hash, never a copy. ReactOS is chosen because it is what the
recovered work targeted, its setup **is** a genuine Win32 GUI
application (unlike FreeDOS's text-mode installer, which cannot
exercise `click` at all), and it is freely redistributable, which
keeps the worked example runnable by anyone who seeds the codex
without a license to source.

## Why this is not a `GuestExec` dialect

F64's own design excludes this ground explicitly: platform-dialect.md
names `win9x` and `winnt` **out of scope**, "no recipe, no text
console to bet on" (`planning/proposed/design/platform-dialect.md:263`),
and even states what its own registry refactor of `_running_guest()`
would do to them — keep refusing, "which is P11 doing its job"
(`platform-dialect.md:64-66`). That refusal is correct and this
design does not touch it.

The reason is architectural, not a gap: `_running_guest()`
(`machines.py:1653-1670`) gates exactly two verbs, `exec` and
`wait-ready` — the ad hoc, host-invoked session channel. It is not a
gate on `create_machine`, `apply_blueprint`, or `run-script`. A
script's own statements (`insert`, `start`, `wait`, `click`, `select`)
drive the machine through the control-plane carriers directly
(`text_screen()`, `framebuffer()`, `pointer_event()`); `script_runner.py`
reads a script's `platform` header only to report it on the
`RUN_START` event (`script_runner.py:653`) and never validates it
against anything. **A `winnt`-platform blueprint driven entirely by
`insert`/`start`/`wait`/`click` already runs today, unmodified** — the
schema's `platform` enum has carried `win9x`/`winnt` since before this
document (`blueprint-schema-v1.json:37-40`), `document.py`'s `_PLATFORMS`
set validates them closed the same way (`document.py:30`), and
`machines.py`'s `_PLATFORM_MEMORY`/`backend_qemu.py`'s `_PLATFORM_ARCH`
tables already carry `winnt: 256` / `winnt: "x86_64"` entries. This
session confirmed it directly: `reactos.rlqb` and
`reactos-install.rlqs` both parse clean against current
`document.py`/`script_parser.py`, and the full non-integration suite
(2342 tests) passes unchanged with the recovered recipe and the
resolve.py fix present.

**Noted here, not proposed as a wording change** (the owner's call
this round): `exec`/`wait-ready` and `run-script` are two genuinely
different shapes of platform workflow. The first needs a per-platform
dialect — a frozen record of prompt shape, probe, sentinel — because
it is asking a shell to run one more command on demand. The second
needs no platform-specific code of any kind, because its "readiness"
and "interaction" are already stated as script conditions over a
control-plane carrier, and a GUI installer has no shell to dialect in
the first place. WinNT/ReactOS workflows are — permanently, by their
nature — the second shape, which is *why* platform-dialect.md excludes
them rather than merely deferring them. AGENTS.md's "Platform
selection" text ("provisioning, readiness, remote-task execution, and
result collection belong to platform workflows... until a non-DOS
workflow is complete and tested, it must raise `NotImplementedError`")
is not wrong about this, but the recovered recipe shows the DOS-only
`NotImplementedError` boundary was already never load-bearing outside
`exec`/`wait-ready` — the principle describes a discipline the code
already generalized past for `run-script`, and this document leaves
that wording exactly as it stands.

## What the recovered recipe does

`reactos.rlqb` (`src/reliquary/codex/blueprints/`): one machine
(`platform: "winnt"`, `pointing-device: "tablet"`, `control-planes:
["vnc"]`, 512M, a blank 2G `hdd0`, an empty `cdrom0`, `boot:
["hdd0", "cdrom0"]`) and one media chain (a SourceForge zip download
with an `extension: "zip"` override — the resolve.py fix this same
stash carries, since the SourceForge link's own path ends in
`/download`, not `.zip` — extracting the install ISO by path and
hash). **The boot order is hard-disk-first, and that is a
correction to the recovered blueprint, not its choice**: the
recovered copy pinned cdrom-first on the claim that ReactOS's
installer detects its own in-progress state across the
stage1-to-stage2 reboot and continues — which proved
timing-dependent, not dependable (measured 2026-08-26: under TCG
the rebooted CD starts Setup over, finds the half-installed disk,
and stops dead at an upgrade/repair screen whose only bindings are
U/ESC/F3). Hdd-first needs no such promise from the guest: the
blank image has no boot signature, so the first boot falls through
to the CD by itself, and the post-copy reboot boots the installed
disk straight into the GUI second stage. A `with boot` scope
(freedos.rlqb's pattern) is not available here even in principle —
this install script deliberately leaves the machine running, and a
boot restore on a running machine is refused (D104) — which makes
the permanent hdd-first order the whole of the mechanism.

`reactos-install.rlqs` is **deliberately thin** — `insert cdrom0
@reactos-iso` then `start`, nothing else — because of the capability
gap below. Everything past the boot is not a script statement; it is
`test_reactos_click_integration.py`, an opt-in `--integration` test
mirroring `test_freedos_vnc_integration.py`'s own discipline for
F65's proof.

**The font-recognition gap, named as a capability boundary.**
ReactOS's text-mode setup paints its own font, and `text_screen()`
reads back noise against it — confirmed against a live capture, with
the raw pixels themselves correct. This is not a defect: the shared
recognizer's glyph banks are extracted from what "a host offers"
(`AGENTS.md`, the `text_recognize.py` account of `guest_glyph_banks`)
— the backend's own BIOS/firmware binaries — and a guest painting a
bespoke font while running under the `vnc` plane (framebuffer capture,
never the VGA text-memory scrape) is a font no extraction path was
ever positioned to reach. **WEIGHED AND DECLINED — extending the
recognizer to accept a guest-supplied font bank**: the only content in
that phase is eight always-default-highlighted confirmations
(language, alpha-version notice, device settings, partition, format
method, format confirmation, bootloader location, install directory)
— nothing there needs to be *read*, only advanced past, so building
recognition for it would be capability nobody's script would ever use
P11 says to name a gap rather than build around one this narrow.

The chosen disposition instead: drive the text-mode phase by raw
frame-settling alone — poll `session.framebuffer()` until consecutive
reads agree, press Enter, repeat a measured eight times — never
through `text_screen()` or a script `wait`. Once the guest reaches its
800×600 GUI second stage, drive it the ordinary way: author a
landmark live from the plane's own capture (`_write_landmark`,
mirroring F65's `test_freedos_vnc_integration.py` pattern exactly),
then `wait @landmark` / `click @landmark spot="..."` as any other
click-driven script would. The test's own round trip — `next` then
`back` then re-matching the *original* welcome landmark, authored
before either click ran — is F66's own done-when for a click that
actually moves a real, uncontrolled cursor and still leaves the
built-in park-zone mask and fuzzy residual tolerance able to re-match
what they matched before.

No new pointer primitive is used or needed: every click in the
recovered test is a single left click at a named spot, exactly script-spec.md's
delivered surface. `button=`, `count=`, and drag remain what
script-spec.md already calls them — "additive sibling growth (G7)
with no named demand yet" — and this recipe supplies no such demand,
since a Next/Back wizard needs none of them.

## Live confirmation: achieved, after the driver was fixed

The recovered recipe's blueprint, media chain, and wizard-phase
proof are all sound; the recovered *text-mode driver* was not, and
every one of its failures was its own. The full trail, kept because
each wrong theory it retired is one a future reader would otherwise
re-run (2026-08-26, this session):

- **Thirty consecutive install attempts failed identically** — the
  shipped 3-attempt pytest run, a single 1500s-window attempt, a
  10-attempt run, and a 10-attempt run under confirmed WHPX host
  acceleration (`backend-settings.qemu.args: ["-accel", "whpx",
  "-accel", "tcg"]` in a scratch home copy; QEMU's stderr shows no
  fallback) — every attempt completing all its keypresses and then
  timing out short of the 800×600 GUI stage. Acceleration changed
  nothing, which retired the host-speed theory; determinism retired
  the recovered comments' guest-reset theory.
- **The actual defect was a fencepost plus the wrong stability
  measure.** The driver pressed a hand-counted 8+1 Enters, but the
  pre-GUI sequence is longer (the bootloader screens land after the
  file copy; the reboot path adds more) and was observed to vary
  between runs — so the presses ran out early and the guest sat
  forever on a screen waiting for input. Compounding it, the
  driver's naive frame-equality settle can never see that screen as
  settled: the install-directory screen carries a **blinking text
  cursor** (38 minutes observed in front of it without a press).
  Reliquary already owned the right measure — `screen_stability`
  masks a recurring cursor as decoration, and F65 generalized
  `observe` to pixel frames — and readings against the live guest
  confirm it (`stable=True` with the cursor's pixels excluded as
  animated).
- **The fix**: `_drive_text_mode_setup` no longer models a screen
  count at all — it presses Enter on every `screen_stability`-stable
  pre-GUI screen until the wizard appears (copy-progress and reboot
  screens never read stable, so they draw no press), and
  `_settled_capture` uses the same measure. One more trap the live
  run exposed: the second-stage **desktop paints before the wizard
  window** and sits stable while it loads, so the driver
  distinguishes the wizard by its white dialog sheet before
  returning a frame a landmark is authored from.
- **F66's wizard-phase proof then completed live in 5.5 seconds**:
  landmark authored from the real welcome screen, `click
  @reactos-welcome spot="next"` advanced it (screen change
  confirmed), `click spot="back"` returned it, and the original
  landmark re-matched afterward — the park-zone mask and fuzzy
  residual surviving a real uncontrolled cursor, on the measured
  `{498, 470}` / `{403, 470}` spots, unchanged from the recovered
  values.
- **The corrected boot order was the last stacked defect.** Two
  cold re-runs after the driver fix still failed — one at a
  silently-exited QEMU (the genuine Alpha-stage death, below), and
  one deterministically: 296 unanswered Enter presses in front of
  Setup's upgrade/repair screen, which is where a cdrom-first
  reboot lands (the blueprint section above). With the boot order
  corrected to hdd-first, **the full test passed cold: 4 minutes
  end to end, first attempt, no retries, unaccelerated TCG** —
  seed, fetch, install, text-mode drive, reboot into the wizard,
  landmark authoring, click next, click back, original landmark
  re-matched.

**The guest-death behavior the recovered comments describe is
real** — and distinct from the driver defect above. Two cold
end-to-end runs after the driver fix each ended with QEMU exiting
**silently** (empty stderr, the exact evidence the recovered
comment recorded) at unpredictable points — 5 and 14 minutes in —
surfacing as `machine.vm-unreachable` at the next session open.
Both failure populations therefore existed at once: the
driver's systematic fencepost timed out every attempt, and
underneath it the genuine Alpha-stage VM death arrived at random.
The recovered retry loop was aimed at the second and could never
catch it — it retried on `AssertionError` alone, while a dead VM
raises the adapter's `PreflightError` — so the fix widens the
retry to exactly the `machine.vm-unreachable` refusal, every other
refusal still propagating as a real defect. A weak but consistent
observation for whoever next tunes this: every observed death was
an unaccelerated TCG run; the WHPX-accelerated by-hand attempts
(roughly an hour of guest time) never died. If that correlation
firms up, it feeds the acceleration question `backend_qemu.py`
already leaves open (no `-accel` is ever passed).

**Still open**: whether three attempts is enough budget against
the observed death rate on TCG hosts, and the Next/Back spot
pinning across ReactOS releases — a version bump re-measures two
constants.
- **The version pin.** `0.4.15-x86` is a specific release, matching
  the blueprint's own header doctrine ("a launching point, not a
  version library... named for the system, [with] the version [as]
  the location and its hash"). A newer release might fix the
  Alpha-stage reset the test budgets around; re-pinning is a version
  bump, not a design change, and is left to whoever next touches the
  recipe.

## Out of scope

Win9x (the scope call above); the VMware Workstation and Hyper-V
adapters (F5 items 5–6, unrelated to this slice); richer pointer
input — drag, double-click, right-click, `button=`, `count=` (no
demand from this recipe, per script-spec.md's own G7 note); the
host-side landmark-cropping convenience (already named as F5's own
leftover, untouched here); any AGENTS.md wording change (noted
locally above instead, per this round's call).

## What remains before this can be pledged

1. ~~Confirm the integration test passes live~~ — **done**
   (2026-08-26, the cold pass above).
2. ~~Stage and commit the recovered work as one change~~ — **done**
   (2026-08-26): the resolve.py `_container_format`
   extension-fallback fix, the codex.json `reactos` description
   entry, `reactos.rlqb`, `reactos-install.rlqs`, and
   `test_reactos_click_integration.py`, with this session's driver,
   boot-order, and retry-scope fixes folded in.
3. Cut a fresh F-number for this slice and pledge it, exactly as
   F63, F65, and F66 were each cut from F5 and pledged the same day
   their piece was ready (D110 for the pattern) — the owner's call,
   per D43's standing rule that entry to `pledged/` is authority the
   owner alone holds today.

**Done when** (F5's own criterion, narrowed to this slice): the
`reactos` codex recipe installs unattended end to end, and
`test_click_advances_and_returns_through_reactos_setup` passes
against a live QEMU install.
