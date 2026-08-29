<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The platform dialect: adding OpenBSD without a second loop

> **Status:** this is the design for **F64**
> (planning/proposed/FEATURES.md, the OpenBSD platform workflow) —
> owner round, 2026-08-22. **Nothing here is pledged.** F64 states the
> demand and how the work is being split; this document works out the
> shape that split delivers, so the pledge round can start from an
> actual design instead of from F64's short description.
>
> **Spike 0 has already run** (2026-08-22; F64 covers its first pass,
> and its second pass is folded into this document). The OpenBSD
> install recipe completed a real install for the first time — and
> **two of the calls this document originally made did not survive
> that test.** The section on how the screen gets read, and the
> section on how readiness is detected, are both rewritten below
> against what was actually measured. Each says what it used to claim
> before being corrected, because quietly deleting a design's wrong
> guesses teaches the next reader nothing.

## The core idea

`interaction_agentless.py` is written entirely in DOS terms today —
every constant in it assumes DOS — but its actual control loop
doesn't need to be. That loop — type the line, catch the echo where
the prompt was (D111), wait for a prompt to come back (D112), hold
until the screen underneath it settles (D115), then slice out the
rows in between — is what any line-oriented shell on a text console
needs. `ksh` running on OpenBSD's `wscons` console is exactly such a
shell. What actually differs from platform to platform is a
**dialect**: a small set of values the loop reads to know what that
platform's prompts and commands look like. So OpenBSD support is a
dialect plugged in *behind* the existing loop, never a second loop
written from scratch — and the way to test that this actually works
is that **the existing DOS test suite still passes byte for byte**
once DOS itself is moved behind this same mechanism.

## The dialect fields, and why there are so few of them

D112's completion rule already does most of the work here: a command
counts as complete once the bottom row is either *the standard prompt
shape, or exactly the prompt the guest was showing when the command
was typed*. That second option reads the prompt straight off the
screen and doesn't name any specific platform, so any shell's prompt
can complete a command with nothing platform-specific declared at
all. So the dialect only needs to carry exactly what the loop
genuinely can't read off the screen on its own:

| field | DOS (today's constants) | OpenBSD |
|---|---|---|
| `name` | `dos` | `openbsd` |
| `plane` | `agentless-display` — reading text directly out of QMP's VGA memory | **`vnc`** — reading VGA memory directly can't see this guest's screen at all (measured; see below), so this platform's *default* control plane has to differ. That's exactly the kind of extension the blueprint model already anticipates: when `control-planes` is omitted it resolves to the platform's default, and a platform gets a different default only once it has planes that justify one |
| `prompt_shape` | `^[A-Z]:(\\[^>]*)?>$` — needed because `CD` changes the *text* of the prompt and the shape still has to recognize it as complete | a row ending in `# ` or `$ ` after a non-blank start; `ksh`'s prompt doesn't change on `cd`, so this shape only needs to cover the standard case, and D113's `prompt=` still covers a prompt that's been redrawn |
| `probe` | `IF ERRORLEVEL 1 ECHO RLQ-EXEC-FAILED` | `test $? -ne 0 && echo RLQ-EXEC-FAILED` — its own separate line, read through the same echo-catching logic as everything else; in `ksh`, `$?` is the previous line's exit status, and it comes back `127` for a command the shell couldn't find at all — so the gap DOS's probe has (`COMMAND.COM` leaves `ERRORLEVEL` untouched in that case) simply doesn't exist here. Both facts are stated plainly, per P11 |
| `sentinel` | `RLQ-EXEC-FAILED` | the exact same word — it's text Reliquary itself writes out and reads back (G2, P18), so there's no reason for the two platforms' probes to use different spellings, and using the same one keeps them sharing the same rule ids |
| `ready` | a settled prompt on the bottom row | **a login handshake, then a settled prompt** (measured; see below): the guest shows `login:`, gets the username typed in; shows `Password:`, gets the secret typed in; then shows `openbsd#`. DOS has no such handshake, so this is the one dialect field where OpenBSD needs a whole *sequence* of steps instead of a single value |
| narration | "waiting for a DOS prompt…" / "at DOS prompt:" | the same two narration lines, with the dialect's own word substituted for its prompt |

None of the underlying rule ids change: `screen.no-echo`,
`screen.no-match`, `command.signalled-failure`,
`command.outcome-unreadable`, and the timeout stays `WaitExpired`
(D114). Adding a dialect adds no new event and no new statement (S3
and S7 are unaffected).

**Which dialect gets used is decided by the machine's recorded
`platform` field, never by inspecting the guest** (P10; AGENTS.md
"Platform selection"). `_running_guest()` in `machines.py` is the one
gate this passes through today (`platform != "dos"` fails with
`platform.verb-not-implemented`); it becomes a lookup into a registry
of the platforms that actually have a workflow built, and a platform
missing from that registry keeps failing with that same error — that
includes `win9x` and `winnt`, which is exactly P11's rule doing its
job. The adapter is built with its dialect passed in
(`AgentlessGuestExec(machine, dialect)`), and each dialect is a frozen
data record living in its own module, one per platform
(`platform_dos.py`, `platform_openbsd.py`), so adding a third platform
means adding one file plus one line in the registry.

**None of this touches the scripting language itself.** `platform
openbsd` already parses today. `exec` is a CLI/API feature built on
top of the language, not part of it, and a script still drives the
guest with `enter` and `wait` exactly as it always has.

## Reading the screen: why the framebuffer plane wins, and why "is it text mode?" was the wrong question

**This section used to claim the existing agentless plane would work
unchanged** — the reasoning was that the console runs in text mode,
so reading QMP's text memory directly would work, with the VNC plane
only as a fallback in case the console ever left text mode. Spike 0
confirmed the premise but proved the conclusion wrong.

The premise did hold: OpenBSD/amd64, booted by BIOS on QEMU's `-vga
std`, really does run its console on `vga(4)` in text mode, and says
so on screen — `wsdisplay0 at vga1 mux 1: console (80x25, vt100
emulation)`. **But reading VGA text memory directly still can't read
that console.** A 32 KB dump of physical address `0xb8000`, taken
while the installer's menu was actually showing on screen, contains
no installer text at all — it still shows what SeaBIOS originally
wrote there before OpenBSD even started. `vga_screen()`
(`backend_qemu.py`) reads a fixed address, `0xb8000`, and assumes the
visible screen starts there. That assumption is true for DOS, which
scrolls by moving bytes around inside that fixed memory window. It's
false for a guest whose `wscons` driver takes over the graphics
adapter and paints the screen through its own separate memory window
instead. The visible symptom is worse than a blank screen: the
reading looks frozen at the boot banner while the guest keeps running
underneath it — a stale reading that looks live.

So **"is the console in text mode?" turned out to be the wrong
question to ask, and being right about the answer bought nothing.**
What actually decides whether this plane works is whether the guest
paints through that legacy fixed memory window at all — and for a
guest that doesn't, only reading the actual framebuffer image can
answer. And reading the framebuffer works well: with
`control-planes: ["vnc"]`, the shared fixed-font recognizer correctly
read every screen this platform shows — the boot loader, the kernel's
boot log, the installer's menu, the installed system booting, its
`login:` prompt, and its shell — with no font declared and nothing
tuned by hand. The font-recognition failure this design was worried
about never actually came up.

**So the control plane itself becomes a dialect field** (see the
table above), not a choice left up to whoever writes the blueprint.
This needs no new mechanism to support: the blueprint model already
resolves `control-planes` to the platform's default whenever it's
left unset, and already anticipates that a platform gets a different
default once it has planes that justify one. This is exactly that
happening. A machine of this platform left on the inherited default
control plane isn't just slower — it's blind, and P11's rule is that
this gets stated plainly, right where a blueprint author would run
into it.

### A difference that belongs to the plane, not to this platform: the cursor is drawn as a character

When reading VGA text memory directly, the cursor is hardware state —
it's never actually a character in the memory being read. When
reading the framebuffer instead, the guest has *drawn* the cursor as
part of the image, so the recognizer reads it back as an ordinary
cell like any other, and the bottom row comes back as `openbsd# _`
rather than `openbsd# `. Every rule that matches a prompt as an
**exact row** — D112's second matching shape, and D113's declared
`prompt=` — runs into that trailing cell, and a shape anchored to the
end of the row misses by exactly one character.

This belongs to the framebuffer plane itself, not to OpenBSD
specifically, so it will show up on a DOS guest too, the moment DOS
gets driven over VNC (F63). It's written down here only because this
is where it was first measured. It's really **a question for the
seam between Reliquary and the backend, not a question for this
dialect**: however it gets settled — the recognizer learning to
account for the cursor cell, or every prompt shape learning to
tolerate a trailing character — one single answer has to serve both
platforms. Two different answers would be exactly the kind of
duplicated solution G6 refuses.

## Readiness: the guest boots straight to `login:`, so readiness logs in

**This section used to describe arranging a shell prompt instead of
actually logging in.** The plan was to have the install recipe answer
the installer's `Exit to (S)hell, (H)alt or (R)eboot` prompt with
`shell`, then edit `/mnt/etc/ttys` right there at the installer's own
shell prompt so that `init` would run `/bin/ksh` on `ttyC0` once
booted — readiness detection shaped just like DOS's, no credential
needed in the transport, using four statements the scripting language
already had. It was the cheaper route to take. It doesn't exist,
because it doesn't work.

**Spike 0 disproved it: under autoinstall, the installer never asks
that question at all.** `Exit to (S)hell, (H)alt or (R)eboot` is a
question that only an *interactive* install ever asks, so a
response-file line trying to answer it does nothing — the install
just finishes, the machine reboots on its own, and the next thing
that appears on the console is:

```
OpenBSD/amd64 (openbsd.my.domain) (ttyC0)

login:
```

There's never a moment where a script is holding open the installer's
own shell, so there's nothing there for a `sed` command to run
against. (OpenBSD does have its own hook for running commands at the
end of an install — an `install.site` set — but that's a different
mechanism: it wants its sets served over the network rather than read
from `cd0`, and it isn't something this design weighed. It's still
available as an option, just not one this design argues for or
against.)

**So readiness detection has to log in — and that isn't a fallback
for later, it's the only mechanism there is.** Measured by hand
against the installed guest:

| the guest shows | readiness detection does |
|---|---|
| `login:` | types the username |
| `Password:` | types the secret; the guest echoes nothing back, so there's no echo to catch here |
| `openbsd#` | ready |

The prompt shape this design had guessed at turns out to be exactly
right: root's `ksh` prompt is `<hostname>#`.

This has three consequences, and none of them are cosmetic:

- **The login credential is needed from the very first delivery of
  this feature**, not something that can be deferred to a later
  piece of work. It comes in through the property sources and the
  credentials module (P13) — never as a blueprint field — with the
  codex recipe's own root password used as the seeded default for
  the codex machine.
- **The dialect's `ready` field has to carry a whole sequence, not
  just a single value**: two separate screens, answered in order,
  before a prompt is even waited for. The underlying loop itself
  doesn't change — this sequence sits in front of it — but it's the
  one place where the OpenBSD dialect is structurally bigger than
  DOS's.
- **Exactly how the credential gets passed through the API surface is
  a question this design leaves open** (S2, and S4 too if the machine
  document ever ends up naming the account). `wait_ready(user=,
  password=)` is the obvious shape for this, but it's *not* decided
  here — it's the kind of decision that deserves its own separate
  round, and D113's `prompt=` precedent — where the caller declares
  what the guest is expected to draw — is the natural starting point
  for that round.

**A guest that already boots straight to a shell needs none of
this**, and nothing above rules that out: a user running their own
OpenBSD console shell fits the DOS-shaped path just fine, because
`ready` is a per-dialect field, and an already-installed system is
free to differ from the codex machine's own defaults.

## Output and returned values

The rows returned are the ones between the echo and the returned
prompt, one screen deep — F14's existing limit stays in force
unchanged. The channels for returning values are the same ones every
platform already has: a guest program writes to a drive, and the
caller reads that back on the host — Reliquary never reads a byte
of what's inside a drive itself, per P16's carve-out (D108). OpenBSD
mounts a vvfat hard disk as `msdos` through its `mount_msdos(8)`
command, which is what makes a directory-source medium usable from
this guest at all. The machine-variable channel belongs to the script
and is already platform-neutral.

## Proof

Integration testing, requested by name the same way the DOS boot
tests are:

0. **Already done** (2026-08-22, both passes). The install completes
   for real: the codex recipe's own answers drove a real autoinstall
   through to `CONGRATULATIONS! Your OpenBSD install has been
   successfully completed!` in about eleven minutes, served from the
   run-scoped HTTP server and watched throughout over the VNC plane.
   What this run found has already been folded into the sections
   above — the correct plane, the cursor-cell issue, the dead
   exit-to-shell route, the login handshake, and a loader-step bug in
   the codex recipe. The actual product of a run is the disk (P20),
   so what's kept from this run is the installed machine itself.
1. A boot, then `wait_ready`, then `exec "uname -a"` reading back the
   kernel version line; `exec "false", check=True` raising
   `command.signalled-failure`; `exec "nosuch"` raising that same
   error (this is the `127` case); and a row slice that correctly
   excludes the boot's own output.
2. The existing agentless DOS test suite passing byte for byte with
   DOS itself now running through this same dialect mechanism — the
   dialect isn't allowed to shift a DOS reading by even one row.
3. Every norm this touches tested against its own actual wording
   (P24): the verbs' "DOS is the delivered workflow" statements in
   `docs/spec/` get amended along with this delivery, and
   `docs/dos-automation.md` gains either an OpenBSD sibling document
   or a platform-specific section.

## How this gets split up for pledging

This is too large to pledge as a single feature, so here's how it
splits. At pledge time, F64 retires and each piece below gets its own
fresh feature number; (b) depends on (a):

- **(a) the dialect mechanism itself** — DOS moved to run through it,
  the registry added to `_running_guest()`, the existing test suite
  unchanged. This adds no new behavior on any application surface;
  proof item 2 alone covers it.
- **(b) the OpenBSD dialect, readiness detection included** — proven
  against the machine spike 0 actually installed; the platform's
  `vnc` default; the loader-step fix in the recipe; an
  `openbsd-verify` counterpart to `freedos-verify`; the amended norms.
  This touches surfaces S1 and S2 (`exec`, `wait_ready`, and `check=`
  all gain a platform following the same contract), S6 (the install
  recipe), and S4 too if the credential ends up needing a name in the
  machine document.

**There is no longer a piece (c)**, and the spike is why: it used to
be "readiness detection that logs in," but the measurement folded
that into (b) by ruling out the cheaper route that would have avoided
needing it. A login handshake can't be separated out from a dialect
that has no way to reach a prompt without going through one. Whatever
extra scope (b) picked up from this, it now also carries — the open
question about how the credential crosses the API surface, above, is
the first thing (b)'s own pledge round has to settle.

Spike 0 is no longer something the pledge is waiting on: it has
already run, and what it found is written directly into the sections
above rather than left as an open condition on them.

## What's out of scope, given this split

ssh as a control plane (the recipe already allows root login over
ssh; building a native control plane for it follows its own separate
timeline, under P3 and F4). Guest-file verbs running over ssh (same
reason, plus D108). `win9x` and `winnt` (no install recipe exists for
either, and no text console to build this dialect approach on). Any
component running inside the guest. And the GUI era in general (F5).
