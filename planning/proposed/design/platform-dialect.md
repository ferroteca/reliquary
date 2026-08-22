<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The platform dialect: a second agentless workflow behind one loop

> **Status:** the design for **F64** (planning/proposed/FEATURES.md,
> the OpenBSD platform workflow) — owner round, 2026-08-22.
> **Nothing here is pledged.** F64 carries the demand and the cut;
> this document holds the shape the cut delivers, so the pledge
> round starts from it rather than from the entry's prose. Spike 0
> — the OpenBSD recipe completing for real — precedes the pledge,
> and two clauses below are marked as what it measures.

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
| `prompt_shape` | `^[A-Z]:(\\[^>]*)?>$` — needed so `CD` can change the prompt's *text* and still complete | a row ending in `# ` or `$ ` after a non-blank head; `ksh`'s prompt does not change on `cd`, so the shape is only the standard-readiness door, and D113's `prompt=` carries over for a redrawn one |
| `probe` | `IF ERRORLEVEL 1 ECHO RLQ-EXEC-FAILED` | `test $? -ne 0 && echo RLQ-EXEC-FAILED` — its own line, read through the same echo discipline; `$?` is the previous line's status in `ksh`, and is `127` for a command the shell could not find, so the DOS probe's stated gap (`COMMAND.COM` leaves ERRORLEVEL alone) does not exist here (P11, stated either way) |
| `sentinel` | `RLQ-EXEC-FAILED` | the same word: it is text Reliquary composed and reads back (G2, P18), and one spelling keeps the rule ids the two probes share |
| `ready` | a settled prompt on the bottom row | a settled prompt on the bottom row — **because the codex machine boots to one** (below); a guest that boots to `login:` is route (1)'s, delivered when asked |
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

## The transport is the one already built

OpenBSD amd64 booted by BIOS on QEMU's `-vga std` takes its console
on `vga(4)` in text mode — `wscons` over an 80×25 VGA text screen —
so the agentless plane applies unchanged: QMP `send-key` in, text
memory at `0xb8000` out, `screendump` for pictures; the VNC plane
with the fixed-font recognizer is the equally agentless fallback
should the console ever leave text mode (F63). **Spike 0 measures
this**: the console's mode after first boot, and whether the
recognizer reads the console font if the VNC plane is needed. If
the console is a framebuffer the VNC plane is the route and the bet
holds; if the recognizer cannot read it, that is the stop, and F64
shrinks to recording why.

## Readiness: the codex machine boots to a prompt

DOS boots to a prompt; OpenBSD boots to `login:`. F64 weighed two
routes — readiness logging in, or the recipe arranging a root shell
on the console — and recommended the second for the codex machine.
**The design takes the second by its cheapest mechanism, which
neither route as written named**: the installer's own exit to a
shell, with the installed filesystem still mounted.

After `CONGRATULATIONS! Your OpenBSD install has been successfully
completed!` the installer asks `Exit to (S)hell, (H)alt or
(R)eboot?` Under autoinstall the answer comes from the response
file like every other, so the recipe's `install.conf` gains one
line —

```
Exit to (S)hell, (H)alt or (R)eboot = shell
```

— and the recipe, at the installer's `#` prompt with the target at
`/mnt`, runs one edit and reboots:

```rlqs
wait "CONGRATULATIONS! Your OpenBSD install has been successfully completed!"
wait /^# $/
enter "sed -i 's|/usr/libexec/getty Pc|/bin/ksh|' /mnt/etc/ttys"
wait /^# $/
enter "reboot"
```

`ttyC0 "/bin/ksh" vt220 on secure` is the long-standing console
trick: `init` runs the shell as root on the console, the machine
boots to `openbsd# `, and readiness is DOS-shaped — a settled
prompt on the bottom row, no credential anywhere in the transport,
no new verb, four statements the language already has. **Spike 0
measures the two facts this rests on**: that autoinstall honours
the exit-to-shell answer rather than rebooting on its own, and that
the edited `ttys` line yields an interactive shell on `ttyC0` at
boot.

What this makes of the codex machine is stated rather than hidden:
a test fixture with a root shell on its console, not a system that
logs in. That is what P1's ephemeral reading prefers for a rig, and
it is the codex's business to say so in the recipe's comments,
because a user seeding the recipe for a system of their own wants
the line gone. **Route (1) — `wait_ready` recognizing `login:`,
typing a user, answering `Password:` from the property sources and
the credentials module (P13), and waiting for the prompt — stays
the general mechanism** for exactly that user's OpenBSD, delivered
when one asks: it is the only piece that touches a transport, and
it is the last of the cut.

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

0. the install completing for real — a 700 MB ISO and a 45-minute
   deadline, paid once, the product being the disk (P20) — and the
   console mode and the two readiness facts above measured on it;
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
retires and each piece takes a fresh number; (b) references (a),
(c) references (b):

- **(a) the dialect seam** — DOS moved behind it, the registry in
  `_running_guest()`, the suite unchanged. No new behaviour on any
  surface; proof 2 alone.
- **(b) the OpenBSD dialect and the recipe's exit-to-shell
  change**, proven against a machine installed by spike 0; an
  `openbsd-verify` sibling of `freedos-verify`; the norms amended.
  Surfaces S1, S2 (`exec`, `wait_ready`, `check=` gain a platform
  with the same contract) and S6 (the recipe).
- **(c) readiness that logs in** — route (1), if and when a user's
  own OpenBSD asks for it. The one piece that adds to S4 (a
  credential parameter, if the machine document needs one) and to
  the transport.

Spike 0 precedes the pledge of any of them: a recipe that has never
completed is not a foundation anything may be pledged on.

## Out of scope, by the cut

ssh as a control plane (the recipe already allows root over ssh; a
native plane is P3's arc and F4's), guest-file verbs over it (the
same reason, and D108), `win9x` and `winnt` (no recipe, no text
console to bet on), any in-guest component, and the GUI era (F5).
