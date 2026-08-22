<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The platform dialect: a second agentless workflow behind one loop

> **Status:** the design for **F64** (planning/proposed/FEATURES.md,
> the OpenBSD platform workflow) — owner round, 2026-08-22.
> **Nothing here is pledged.** F64 carries the demand and the cut;
> this document holds the shape the cut delivers, so the pledge
> round starts from it rather than from the entry's prose.
>
> **Spike 0 has run** (2026-08-22; F64 carries its first pass, and
> its second is folded in here). The OpenBSD recipe completed a
> real install for the first time — and **two of this document's
> calls did not survive it.** The transport and the readiness route
> are rewritten below against what was measured, and each says what
> it used to claim, because a design whose refuted half is quietly
> deleted teaches the next reader nothing.

## The claim

`interaction_agentless.py` is DOS from its first constant and
platform-neutral in its loop. The loop — type the line, catch the
echo where the prompt was (D111), wait for a prompt to come back
(D112), hold it until the screen under it settles (D115), slice the
rows between — is what any line-oriented shell on a text console
needs, and `ksh` on OpenBSD's `wscons` is one. What differs by
platform is a **dialect**: a handful of values the loop reads. So
the seam is a dialect *behind* the loop, never a second loop, and
the test of the seam is that **the DOS suite passes byte for byte**
with DOS moved behind it.

## The dialect, and why it is small

D112's completion rule already does most of the work: a command
completes when the bottom row is *the standard prompt shape, or
exactly the prompt the guest was at when the command was typed*.
The second half reads the prompt off the screen and names no
platform, so any shell prompt completes a command with nothing
declared. The dialect therefore carries exactly what the loop
cannot read off a screen:

| field | DOS (today's constants) | OpenBSD |
|---|---|---|
| `name` | `dos` | `openbsd` |
| `plane` | `agentless-display` — the QMP text-memory scrape | **`vnc`** — the scrape is blind to this guest (measured; below), so the platform's *default* control plane differs. That is the extension the blueprint model already anticipates: "omitted, it resolves to the platform's default … defaults that differ by platform arrive with the planes that justify them" |
| `prompt_shape` | `^[A-Z]:(\\[^>]*)?>$` — needed so `CD` can change the prompt's *text* and still complete | a row ending in `# ` or `$ ` after a non-blank head; `ksh`'s prompt does not change on `cd`, so the shape is only the standard-readiness door, and D113's `prompt=` carries over for a redrawn one |
| `probe` | `IF ERRORLEVEL 1 ECHO RLQ-EXEC-FAILED` | `test $? -ne 0 && echo RLQ-EXEC-FAILED` — its own line, read through the same echo discipline; `$?` is the previous line's status in `ksh`, and is `127` for a command the shell could not find, so the DOS probe's stated gap (`COMMAND.COM` leaves ERRORLEVEL alone) does not exist here (P11, stated either way) |
| `sentinel` | `RLQ-EXEC-FAILED` | the same word: it is text Reliquary composed and reads back (G2, P18), and one spelling keeps the rule ids the two probes share |
| `ready` | a settled prompt on the bottom row | **a login handshake, then a settled prompt** (measured; below): `login:` → the user → `Password:` → the secret → `openbsd#`. DOS has no handshake, so this is the one dialect field with a *sequence* in it rather than a value |
| narration | "waiting for a DOS prompt…" / "at DOS prompt:" | the dialect's word for its prompt, in the same two lines |

The rule ids do not change: `screen.no-echo`, `screen.no-match`,
`command.signalled-failure`, `command.outcome-unreadable`, and the
expiry stays `WaitExpired` (D114). A dialect adds no event and no
statement (S3, S7 unchanged).

**Selection is by the recorded `platform`, never by inspection**
(P10; AGENTS.md "Platform selection"). `_running_guest()` in
`machines.py` is the one gate today (`platform != "dos"` →
`platform.verb-not-implemented`); it becomes a lookup in a registry
of the platforms with a delivered workflow, and a platform absent
from the registry keeps refusing by the same rule id — `win9x` and
`winnt` included, which is P11 doing its job. The adapter is
constructed with the dialect (`AgentlessGuestExec(machine,
dialect)`), the dialect being a frozen record in a module per
platform (`platform_dos.py`, `platform_openbsd.py`) so a third
platform is a file and a registry line.

**Nothing in the scripting language moves.** `platform openbsd`
parses today; `exec` is a CLI/API composite above the language, and
a script drives the guest with `enter` and `wait` as it always did.

## The transport: the framebuffer plane, and why text mode did not decide it

**This section used to say the agentless plane applied unchanged** —
the console is in text mode, so QMP text memory out, with the VNC
plane as the fallback should the console ever leave text mode. Spike
0 kept the premise and broke the conclusion.

The premise held: OpenBSD amd64 booted by BIOS on QEMU's `-vga std`
does take its console on `vga(4)` in text mode, and says so —
`wsdisplay0 at vga1 mux 1: console (80x25, vt100 emulation)`. **And
the text scrape still cannot read it.** A 32 KB dump of physical
`0xb8000`, taken while the installer's menu was on screen, holds no
installer text at all: it still carries what SeaBIOS wrote.
`vga_screen` (`backend_qemu.py`) reads a fixed `0xb8000` and takes
the visible screen to begin there — true of DOS, which scrolls by
moving bytes inside that window; false of a guest whose wscons
attaches the adapter and paints through its own aperture. The
symptom is a screen frozen at the boot banner while the guest runs
on, which is worse than a blank one: it is a stale reading that
looks live.

So **"is the console text?" was the wrong question, and being right
about it bought nothing.** What decides the plane is whether the
guest paints through the legacy aperture, and only the framebuffer
can answer for a guest that does not. It answers well: over
`control-planes: ["vnc"]` the shared fixed-font recognizer read
every screen this platform shows — the loader, the kernel's dmesg,
the installer's menu, the installed system's boot, its `login:` and
its shell — with no font declared and nothing tuned. The
font-recognition stop this design feared is not in play.

**The plane is therefore a dialect field** (the table above), not a
deployment choice left to whoever writes the blueprint. It needs no
new mechanism: the blueprint model already has `control-planes`
resolving to *the platform's default* when omitted, and says that
defaults differing by platform arrive with the planes that justify
them. This is that arrival. A machine of this platform left on the
inherited default is not slower — it is blind, and P11 wants that
said where an author meets it.

### One plane difference, not a platform one: the cursor is a glyph

On the text scrape the cursor is hardware state and never a
character. On the framebuffer the guest has *drawn* it, so the
recognizer reads it as a cell like any other and the bottom row
comes back `openbsd# _`, not `openbsd# `. Every rule that matches a
prompt as an **exact row** — D112's second shape, D113's declared
`prompt=` — meets that trailing cell, and a shape anchored at the
end of the row misses by one character.

This belongs to the plane and not to OpenBSD, so it reaches the DOS
guest the moment DOS is driven over VNC (F63). It is recorded here
because here is where it was first measured, and it is **the seam's
question rather than this dialect's**: whichever way it is settled —
the recognizer accounting for the cursor cell, or every prompt shape
tolerating it — one answer serves both platforms, and two would be
the second spelling G6 refuses.
## Readiness: the guest boots to `login:`, so readiness logs in

**This section used to arrange a prompt instead of logging in.** It
had the recipe answer the installer's `Exit to (S)hell, (H)alt or
(R)eboot` with `shell`, then edit `/mnt/etc/ttys` at the installer's
own prompt so `init` would run `/bin/ksh` on `ttyC0` — readiness
DOS-shaped, no credential in the transport, four statements the
language already had. It was the cheaper route and it does not
exist.

**Spike 0 refuted it: under autoinstall the installer never asks.**
`Exit to (S)hell, (H)alt or (R)eboot` is an *interactive* install's
question, so a response-file line answering it is inert — the
install ends, the machine reboots on its own, and the next thing on
the console is

```
OpenBSD/amd64 (openbsd.my.domain) (ttyC0)

login:
```

There is no moment at which a script holds the installer's shell, so
there is nothing for a `sed` to ride. (OpenBSD's own hook for
running commands at the end of an install is an `install.site` set;
it is a different mechanism, wants the sets served rather than read
from `cd0`, and is not what this design weighed. It stays available
and unargued.)

**So readiness logs in — and that is not the later general
mechanism, it is the only one.** Measured by hand against the
installed guest:

| the guest shows | readiness does |
|---|---|
| `login:` | types the user |
| `Password:` | types the secret; the guest echoes nothing, so there is no echo to catch |
| `openbsd#` | ready |

The prompt shape this design guessed is confirmed exactly: root's
`ksh` prompt is `<hostname>#`.

Three consequences, none of them cosmetic:

- **The credential is load-bearing from the first delivery**, not
  deferred with a later piece. It comes through the property
  sources and the credentials module (P13) — never a blueprint
  field — with the codex recipe's own root password as the codex
  machine's seeded default.
- **The dialect's `ready` field carries a sequence**, not a value:
  two screens answered in order before a prompt is waited for. The
  loop is unchanged — this sits in front of it — but it is the one
  place the OpenBSD dialect is structurally larger than DOS's.
- **What the API surface carries the credential as is a surface
  question this design leaves open** (S2, and S4 if the machine
  document ever names the account). `wait_ready(user=, password=)`
  is the obvious shape and is *not* settled here: it is the kind of
  call that earns its own round, and D113's `prompt=` precedent —
  the caller declares what the guest draws — is where that round
  starts.

**A guest that already boots to a shell needs none of this**, and
nothing above forbids one: a user whose own OpenBSD runs a console
shell meets the DOS-shaped path, because `ready` is a dialect field
and an installed system is free to differ from the codex machine.
## Output and values

The rows between the echo and the returned prompt, one screen
deep, F14's limit in force unchanged. The value channels are the
ones every platform has: a guest program writes to a drive and the
caller reads it on the host (P16's carve-out, D108 — Reliquary
reads no byte of it), and OpenBSD mounts a vvfat hard disk as
`msdos` through `mount_msdos(8)`, which is what makes a
directory-source media usable from this guest. The machine-variable
channel is a script's and is platform-neutral already.

## Proof

Integration, asked for by name as the DOS boots are:

0. **done** (2026-08-22, both passes). The install completes for
   real: the codex recipe's own answers carried a real autoinstall
   to `CONGRATULATIONS! Your OpenBSD install has been successfully
   completed!` in about eleven minutes, served from the run-scoped
   HTTP server and read throughout over the VNC plane. What it
   returned is folded above — the plane, the cursor cell, the dead
   exit-to-shell route, the login handshake, and the loader step the
   codex recipe gets wrong. The product is the disk (P20), so what
   is kept from the run is the installed machine;
1. a boot, `wait_ready`, `exec "uname -a"` reading back the kernel
   line, `exec "false", check=True` raising
   `command.signalled-failure`, `exec "nosuch"` raising the same
   (the `127` case), and a row slice that does not include the
   boot's output;
2. the agentless DOS suite passing byte for byte with DOS behind
   the seam — the dialect may not move a DOS reading by one row;
3. every touched norm tested against its own spelling (P24): the
   verbs' "DOS is the delivered workflow" clauses in `docs/spec/`
   amended with the delivery, and `docs/dos-automation.md` gaining
   an OpenBSD sibling or a platform section.
## The cut

Too large as one feature, and the cut is visible. At pledge F64
retires and each piece takes a fresh number; (b) references (a):

- **(a) the dialect seam** — DOS moved behind it, the registry in
  `_running_guest()`, the suite unchanged. No new behaviour on any
  surface; proof 2 alone.
- **(b) the OpenBSD dialect, readiness included**, proven against a
  machine installed by spike 0; the platform's `vnc` default; the
  recipe's loader-step fix; an `openbsd-verify` sibling of
  `freedos-verify`; the norms amended. Surfaces S1, S2 (`exec`,
  `wait_ready`, `check=` gain a platform with the same contract),
  S6 (the recipe), and S4 if the credential needs a name in the
  machine document.

**(c) is gone**, and its disappearance is the spike's doing: it held
"readiness that logs in," which the measurement moved into (b) by
killing the route that would have avoided it. A login handshake is
not separable from a dialect that cannot reach a prompt without one.
What (b) grew it must also carry — the credential surface question
above is the first thing its pledge round settles.

Spike 0 no longer precedes the pledge: it has run, and what it
returned is written into the sections above rather than left as a
condition on them.
## Out of scope, by the cut

ssh as a control plane (the recipe already allows root over ssh; a
native plane is P3's arc and F4's), guest-file verbs over it (the
same reason, and D108), `win9x` and `winnt` (no recipe, no text
console to bet on), any in-guest component, and the GUI era (F5).
