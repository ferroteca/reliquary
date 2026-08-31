<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The WinNT platform workflow: ReactOS as the GUI era's first recipe

> **Status:** this is the design for the WinNT half of F5's fourth
> deliverable (`planning/proposed/FEATURES.md` — "Win9x/WinNT
> platform workflows: GUI installer scripting for the setup GUIs
> text scraping cannot reach, keyboard-first where NT-era setup
> allows it"). **It has already been pledged and delivered, as
> F67, 2026-08-26** (owner) — the number is retired, the same way
> F63, F65, and F66 were each cut out of F5 and pledged. The Win9x
> half is still unpledged, sitting in F5's entry.
>
> This document isn't a forward-looking design for code that
> doesn't exist yet, the way its siblings ([device-growth.md](device-growth.md),
> [hyperv-screen.md](hyperv-screen.md)) are. The actual recipe was
> already written in an earlier session and then got lost — it was
> sitting uncommitted in a git stash. This session recovered it
> (`git stash show -p`), fixed several real bugs in it, and
> committed it: the resolve.py fix for file-extension guessing, the
> `reactos` entry in codex.json, `reactos.rlqb`, `reactos-install.rlqs`,
> and `test_reactos_click_integration.py`. So this document is
> written after the fact — it explains what the recipe does and why,
> now that the recipe itself already exists and works.

## Why this counts as demanded work

This doesn't need a new use case to justify it — **U5** already
covers it. Decision D110 already established that "GUI automation's
demand is U5": U5 is about custom installation, and its remaining,
undelivered part is exactly this — quoting U5's own text, "a
localized installer is a different installer showing different
text — on a graphical setup, different pixels." Decision D64 split
U5 into two parts: the part that was delivered became its own use
case (U21), and what was left — "the platform workflows" — stayed
pledged and waiting inside F5 (see `planning/pledged/USE-CASES.md`,
lines 67-68). F5's own description already named the target
precisely — "keyboard-first where NT-era setup allows it" — before
any of this recipe existed to actually prove that claim true.

## Scoping this to WinNT only, with ReactOS as the concrete example

This document only covers the WinNT half of F5's fourth deliverable.

**We considered covering Win9x here too, and decided against it.**
Win9x installs from a completely different starting point (a
DOS-based real-mode setup) into a completely different GUI system —
it's not just a different theme on the same NT setup wizard, it's a
different recipe altogether. Nothing currently demands Win9x support
specifically, as opposed to WinNT. Decision D42's rule (each piece
of work should fit in about one sprint) argues for cutting this into
separate pieces, the same way F63, F65, and F66 were each split out
of F5 one at a time. Nothing here rules out building a Win9x recipe
later, on its own, if something actually needs it.

Within WinNT, the specific guest we picked is **ReactOS**
(version 0.4.15-x86, in `reactos.rlqb`) — not a real, licensed
Windows NT release. This isn't just convenience: reliquary's codex
never ships install media for anything (as U5's own text says, "the
codex will not carry such flavors") and never needed to worry about
licensing either way, because every codex media entry is just a
download location and a hash, never an actual copy of the file. We
picked ReactOS because that's what the recovered work already
targeted, its setup **is** a real Win32 GUI application (unlike
FreeDOS's text-only installer, which can't exercise `click` at
all), and it's freely redistributable — so anyone who seeds the
codex can run this example without needing to obtain a Windows
license first.

## Why this doesn't need a new per-platform "dialect"

F64's own design already rules this out explicitly.
`platform-dialect.md` lists `win9x` and `winnt` as **out of
scope**, saying there's "no recipe, no text console to bet on"
(`planning/proposed/design/platform-dialect.md`, line 263). It even
says what its planned registry rewrite of `_running_guest()` would
do with them — keep refusing them, "which is P11 doing its job"
(same file, lines 64-66). That refusal is correct, and this design
doesn't change it.

Here's why that's fine, architecturally: `_running_guest()`
(`machines.py`, lines 1653-1670) only gates two commands — `exec`
and `wait-ready`. Those are the ad hoc commands you run by hand
against an already-running machine. It does NOT gate
`create_machine`, `apply_blueprint`, or `run-script`. A script's own
statements (`insert`, `start`, `wait`, `click`, `select`) talk to
the machine directly through the control-plane carriers
(`text_screen()`, `framebuffer()`, `pointer_event()`).
`script_runner.py` reads a script's `platform` line only to include
it in the `RUN_START` event for logging (`script_runner.py`, line
653) — it never actually checks that value against anything. **In
other words: a `winnt`-platform blueprint driven entirely by
`insert`/`start`/`wait`/`click` already ran, completely unmodified,
before this design was even written.** The blueprint schema's
`platform` field has allowed `win9x` and `winnt` as valid values
since before this document existed (`blueprint-schema-v1.json`,
lines 37-40), `document.py`'s `_PLATFORMS` set validates them the
same way (`document.py`, line 30), and `machines.py`'s
`_PLATFORM_MEMORY` table and `backend_qemu.py`'s `_PLATFORM_ARCH`
table already had entries for `winnt` (256 MB of memory, x86_64
architecture). This session confirmed all of this directly:
`reactos.rlqb` and `reactos-install.rlqs` both parse cleanly against
the current code, and the full non-integration test suite (2342
tests) passes unchanged with the recovered recipe and the resolve.py
fix in place.

**One thing worth writing down here, though we're not proposing to
change any wording because of it** (the project owner's call this
round): `exec`/`wait-ready` on one hand, and `run-script` on the
other, are genuinely two different kinds of platform support. The
first kind needs a per-platform "dialect" — a fixed set of values
like prompt shape, probe command, and sentinel text — because it's
asking a text shell to run one more command on demand. The second
kind needs no platform-specific code at all, because its "is this
ready" and "do this" logic is already expressed as script conditions
over a control-plane carrier, and a GUI installer has no text shell
to write a dialect for in the first place. WinNT/ReactOS workflows
are — permanently, by their nature — the second kind, which is
exactly *why* `platform-dialect.md` excludes them instead of just
deferring them. AGENTS.md's "Platform selection" section (which says
"provisioning, readiness, remote-task execution, and result
collection belong to platform workflows... until a non-DOS workflow
is complete and tested, it must raise `NotImplementedError`") isn't
wrong, exactly, but the recovered recipe shows that the "DOS
only, else `NotImplementedError`" rule was already never actually
enforced anywhere except `exec`/`wait-ready`. The rule describes a
discipline the code had already moved past for `run-script`. We're
leaving that wording as-is rather than editing it as part of this
work.

## What the recovered recipe actually does

`reactos.rlqb` (in `src/reliquary/codex/blueprints/`) declares one
machine — `platform: "winnt"`, `devices.pointer0: "tablet"`,
`control-planes: ["vnc"]`, 512 MB of memory, a blank 2 GB `hdd0`
disk, an empty `cdrom0` drive, boot order `["hdd0", "cdrom0"]` —
plus one media chain: a zip download from SourceForge (with an
`extension: "zip"` override, because the resolve.py fix in this
same recovered work is needed here — the SourceForge link's URL
path ends in `/download`, not `.zip`, so reliquary can't guess the
file type from the URL alone) with the actual install ISO extracted
out of it by path and checksum.

**The boot order is hard-disk-first, and that's a fix we made to
the recovered blueprint, not something it already had right.** The
recovered copy had cdrom-first, based on the assumption that
ReactOS's installer would notice it was mid-install across its
reboot and just continue — but that assumption turned out to be
unreliable (measured 2026-08-26: under unaccelerated QEMU, the
rebooted CD restarts Setup from scratch, finds the half-installed
disk, and stops at an upgrade/repair screen whose only options are
U, ESC, or F3 — none of which our script was pressing). Hard-disk-first
doesn't need that assumption to hold: the blank disk has no boot
signature yet, so the very first boot naturally falls through to the
CD anyway, and after the install copies files and reboots, the disk
*is* bootable and boots straight into the GUI second stage. We
couldn't use freedos.rlqb's trick of temporarily overriding the boot
order for one script run (`with boot`) here even if we wanted to —
this install script deliberately leaves the machine running when
it's done, and reliquary refuses to change a running machine's boot
order (decision D104). So the permanent hard-disk-first order is the
whole mechanism.

`reactos-install.rlqs` is **deliberately short** — it just does
`insert cdrom0 @reactos-iso` then `start`, nothing else — because of
a real limitation described below. Everything after boot isn't a
script statement at all; it's driven by
`test_reactos_click_integration.py`, an opt-in test (only runs with
`--integration`) that follows the same approach
`test_freedos_vnc_integration.py` uses to prove F65 works.

**The font-recognition limit, stated plainly as a real boundary,
not a bug.** ReactOS's text-mode setup draws its own custom font,
and reliquary's `text_screen()` reads garbage off it — confirmed
against a real screen capture, where the actual pixels are correct
but the *recognized* text is not. This isn't something we're
planning to fix: the shared font-recognition system builds its
library of known fonts from whatever the backend itself offers (see
AGENTS.md's description of `text_recognize.py`'s
`guest_glyph_banks`) — meaning the backend's own BIOS/firmware files
— and a guest that draws its own custom font while running under
the `vnc` plane (which captures raw screen pixels, not the VGA text
memory) is drawing something no font-extraction path was ever built
to find. **We considered teaching the font-recognition system to
accept a font supplied by the guest itself, and decided against it**:
the only content on those screens is eight confirmation prompts that
already have the right answer pre-selected (language, alpha-version
notice, device settings, partition, format method, format
confirmation, bootloader location, install directory) — nothing on
them actually needs to be *read*, just clicked past. Building text
recognition for content nobody needs to read would be exactly the
kind of unused capability that P11 says to name honestly as a gap
rather than build.

What we do instead: drive the text-mode screens by watching the raw
picture settle down — keep taking screenshots with
`session.framebuffer()` until they stop changing, then press Enter,
and repeat (measured at eight repeats) — never through
`text_screen()` or a script `wait`. Once the guest reaches its
800×600 graphical second stage, drive it the normal way: capture a
landmark image live from the actual screen (`_write_landmark`, using
the exact same approach as F65's proof in
`test_freedos_vnc_integration.py`), then use `wait @landmark` and
`click @landmark spot="..."` like any other click-driven script.
The test's core check — click "next", then click "back", then
confirm the *original* welcome-screen landmark (captured before
either click ran) still matches — is F66's actual proof that a real
click, with a real uncontrolled mouse cursor on screen, still works:
the built-in cursor-parking area and the fuzzy-match tolerance are
enough to make the landmark match again afterward.

No new pointer feature was needed here: every click in the recovered
test is a single left click at one named spot — exactly what
`script-spec.md` already supports. Right-click, double-click, drag,
and clicking with a specific mouse button (`button=`, `count=`) are
still what `script-spec.md` already calls them: "extra features
nobody's asked for yet." This recipe doesn't create demand for any
of them, because a Next/Back installer wizard doesn't need them.

## Live confirmation: it works, once the driving code was fixed

The recovered recipe's blueprint, media download, and the
wizard-click test itself were all fine. What wasn't fine was the
*code that drove the text-mode screens* — and every failure traced
back to bugs in that code, not in reliquary or in ReactOS. Here's
the full story, kept in detail because each wrong guess along the
way is one a future reader shouldn't have to re-discover
(2026-08-26, this session):

- **Thirty install attempts in a row failed the exact same way.**
  We tried: the shipped test's normal 3 attempts, one single attempt
  given 5x the normal time budget, a run of 10 attempts, and another
  10-attempt run with QEMU's WHPX hardware acceleration turned on
  (confirmed active — QEMU's own error log showed no fallback to
  software emulation). Every single attempt got through all its
  keypresses and then timed out just short of reaching the 800×600
  graphical stage. Turning on acceleration changed nothing, which
  ruled out "the host is just too slow" as the explanation. The fact
  that every attempt failed identically ruled out the recovered
  code's own comment, which blamed occasional guest crashes.
- **The real bug was two things stacked together: counting Enter
  presses instead of watching the screen, and a broken way of
  telling if the screen had stopped changing.** The driving code
  pressed Enter a fixed 9 times (a number counted by hand earlier),
  but the real sequence of screens is longer than that — some
  bootloader-related screens only appear after the file copy
  finishes — so the code ran out of presses early and then just sat
  there, waiting forever on a screen nobody was answering. On top of
  that, the way it checked "has the screen stopped changing" — "are
  these two screenshots pixel-for-pixel identical" — can never
  succeed on one particular screen, because that screen has a
  **blinking text cursor**: we watched it for 38 minutes and it
  never once produced two identical screenshots in a row.
  Reliquary already had the right tool for this —
  `screen_stability`, which is smart enough to ignore a small,
  repeatedly-changing thing like a blinking cursor (this pixel-level
  version of the check is F65's contribution) — and testing it
  against the real, running guest confirmed it correctly reports the
  screen as stable, with the cursor's pixels excluded from the count.
- **The fix**: `_drive_text_mode_setup` no longer counts screens at
  all. It presses Enter on whatever screen is currently on-screen
  and stable, according to `screen_stability`, and keeps doing that
  until the wizard actually appears — screens that are still doing
  something (copying files, rebooting) never read as stable, so they
  never get an accidental keypress. `_settled_capture` uses the same
  check. One more thing the live run caught while fixing this: the
  plain desktop appears — and sits still — *before* the wizard
  window pops up on top of it. So the fixed code specifically waits
  for the wizard's white dialog box to show up before treating a
  screen as "the wizard is here" and capturing a landmark from it.
- **With that fixed, the click round trip itself ran live in 5.5
  seconds**: it captured a landmark from the real welcome screen,
  `click @reactos-welcome spot="next"` correctly moved to the next
  page (confirmed the screen actually changed), `click spot="back"`
  returned to the welcome page, and the original landmark matched
  again — proving the cursor-parking area and fuzzy-match tolerance
  really do survive a real, uncontrolled mouse cursor, using the
  same button coordinates (498,470 and 403,470) that were already in
  the recovered code.
- **The boot-order fix was the last piece.** Two full end-to-end
  test runs after fixing the driving code still failed — one because
  QEMU silently exited on its own (the genuine ReactOS crash
  described below), and one for a clear, repeatable reason: 296
  unanswered Enter presses in front of Setup's upgrade/repair
  screen, which is exactly where a cdrom-first reboot lands (see the
  blueprint section above). Once the boot order was fixed to
  hard-disk-first, **the full test passed cleanly on the first try
  — 4 minutes end to end, no retries needed, with no hardware
  acceleration**: seed the blueprint, download the ISO, install,
  drive the text-mode screens, reboot into the wizard, capture
  landmarks, click next, click back, confirm the original landmark
  still matches.

**The guest crash the recovered code's comments described is real**
— and it's a separate problem from the driving-code bug above. Two
clean end-to-end test runs after fixing the driving code each ended
with QEMU exiting **silently** (no error message at all — exactly
what the recovered comment had already described) at unpredictable
points: 5 minutes into one run, 14 minutes into another. The next
thing the test tried to do then failed with
`machine.vm-unreachable`. So there really were two separate problems
happening at once: the driving-code bug caused every single attempt
to fail the same way, and underneath that, ReactOS really does
sometimes crash its own virtual machine at random during install.
The recovered retry logic was built to handle exactly this second
problem, but it never actually worked, because it only retried on
`AssertionError` — and a crashed VM raises a different kind of error
(`PreflightError`) instead. The fix widens the retry logic to catch
that specific `machine.vm-unreachable` error; any other kind of
error still stops the test immediately, since that would mean a
real bug rather than a known, occasional guest crash. One loose
thread worth flagging for whoever tunes this next: every crash we
saw happened on an unaccelerated (software-emulated) run; the
WHPX-accelerated manual attempts (roughly an hour of guest running
time, combined) never crashed once. If that pattern holds up with
more testing, it's relevant to the open question of whether
reliquary should ever pass a QEMU acceleration flag at all — right
now `backend_qemu.py` never does.

**Still open**: whether three retry attempts is really enough given
how often ReactOS crashes on an unaccelerated host, and whether the
Next/Back button coordinates will need re-measuring on a different
ReactOS release. **The version we're pinned to.** `0.4.15-x86` is a
specific release, matching how the blueprint's own header comment
says codex entries should work — "a starting point, not a library of
every version; each entry is named for the system, and the version
lives in the download location and its checksum." A newer ReactOS
release might not have the crash-during-copy problem at all; if
someone wants to move to a newer version later, that's just a
version bump to those two values, not a design change.

## What's not covered by this work

Win9x support (explained in the scoping section above); the VMware
Workstation and Hyper-V backends (items 5 and 6 in F5's list,
unrelated to this piece of work); richer pointer features like
drag, double-click, right-click, `button=`, or `count=` (nothing in
this recipe needs them, and `script-spec.md` already notes there's
no demand for them yet); the convenience of cropping a landmark
image on the host side (already listed as leftover work under F5,
not touched here); any change to AGENTS.md's wording (we noted the
relevant distinction above instead, per this round's decision).

## What was left to do before this could be pledged — now done

1. ~~Confirm the test actually passes against a real install~~ —
   **done** (2026-08-26): see the clean pass described above.
2. ~~Commit the recovered work as one change~~ — **done**
   (2026-08-26): the resolve.py fix, the codex.json entry,
   `reactos.rlqb`, `reactos-install.rlqs`, and
   `test_reactos_click_integration.py`, including this session's
   fixes to the driving code, the boot order, and the retry logic.
3. ~~Get a feature number assigned and pledge it~~ — **done**
   (owner, 2026-08-26): pledged and delivered as **F67**, its
   number now retired — the same pattern used for F63, F65, and
   F66, each cut out of F5 and pledged the same day the piece of
   work was actually ready (see decision D110 for that pattern).

**How we'll know this piece is really done** (this is F5's own
success criterion, narrowed to just this piece): the `reactos`
codex recipe installs completely on its own, and
`test_click_advances_and_returns_through_reactos_setup` passes
against a real QEMU install.
