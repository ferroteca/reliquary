<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Pledged use cases — awaiting delivery

> **Status:** use cases the project has **pledged** but does not
> yet meet. Work may be done from here; nothing here is a claim
> about the code.
>
> Three locations hold three states. A use case is drafted in
> [proposed/USE-CASES.md](../proposed/USE-CASES.md), moves here when
> it is pledged, and moves to root
> [USE-CASES.md](../../USE-CASES.md) when the code actually meets
> it. The root list is implemented-only — every entry there is met
> today, which is why it lives at the repository root — so
> pledge alone can never put an entry in it. All three share
> one global U-namespace; numbers are permanent, never reused, and
> no placeholder is left behind by any move — including the one
> that runs backwards. **A pledge the project does not mean is
> withdrawn** to `proposed/` or rejected outright, never left
> sitting (D44; first used by D61). Withdrawal costs the
> commitment and nothing else: the number, the text and every
> citation stand.
>
> The second move is **automatic on full delivery** (D34): whoever
> lands the work that fully meets a use case promotes it in the same
> change — adds it to the root list, deletes it here — rather than
> holding it for a separate sign-off. The moving commit is the whole
> record, and the delivery evidence belongs in its message; no
> [DECISIONS.md](../DECISIONS.md) entry marks a promotion (D63). *Full* delivery is the trigger: a use case
> whose work has partly landed stays here, since the root list is an
> implementation claim — unless the delivered part is a use case in
> its own right, in which case it is promoted under its own number
> and the remainder returns to `proposed/`. U5 did both in turn
> (D64).
>
> A use case in force is clarified, retired, or superseded — never
> changed in nature. One pledged here may still be reshaped, its
> number intact, with work already scheduled against it re-checked
> in the same edit. A proposal that dies at any point is recorded in
> [DECISIONS.md](../DECISIONS.md) and removed, triggering the planning
> sweep described in
> [proposed/USE-CASES.md](../proposed/USE-CASES.md); its U-number is
> the search key.

**U7 — Materialize on the hypervisor the host provides** — pledged
2026-07-28 (owner). Drafted 2026-07-23 by the mapping sweep, which
found the multi-backend pillar demand-free: no use case in force
named a hypervisor in any role, and the three non-substrate roles
that once did — export target (U1), import source (U2), guest-agent
vendor (U3) — have all since gone, widening the gap rather than
closing it. The pledge schedules the pair that left the numbered
arc on that lack: **F2**, the adapter seam, pledged in the same
act — and **delivered the same day**, so its number is retired and
the seam is built — and **F3**, the second backend, which followed
on its own move (2026-08-03) and was cut at pledge into **F50** /
**F51** / **F52** (D42), F3 retiring with the split; **F50**,
**F51**, and **F52** are delivered (VirtualBox lifecycle/VDI, the
shared fixed-font recognizer, and VirtualBox agentless display with
FreeDOS parity). U7's pledge was
necessary for both and sufficient for neither. **U7 stays here**:
the seam it demanded exists, but the case is met when a machine
materializes on the hypervisor a host actually provides, and two
of the four adapters are still stubs that claim no capability
(VMware and Hyper-V). What F2 delivered is what
U7 required, not what U7 asks for. The backend-adapter design (now
`design/backend-adapter.md`, its feature delivered) cites U7 from
here; F52 closed the VirtualBox half of the demand. **A second
delivery answered part of it and moved it
no closer** (2026-07-29; D80): `create-machine --dry-run --backend`
asks whether a blueprint would work on a named backend, capability
alone deciding, with nothing installed and nothing booted — U7's own
contract, checked statically. A static answer about a backend is not
a machine materialized on one, so the pledge stands exactly where it
did. Text verbatim as drafted:

> - **U7 — Materialize on the hypervisor the host provides.** A
>   blueprint and its scripts are written once; the hosts that
>   run them differ — a Windows laptop with Hyper-V already
>   enabled, a CI runner with only QEMU, a workstation with
>   VirtualBox. The machine materializes on whatever capable
>   backend the host offers, and the same blueprint and scripts
>   drive it there unchanged. Capability, not identity, is the
>   contract: a blueprint needing what a backend cannot give
>   fails closed naming the gap, never silently degrading;
>   declaring a `backend` explicitly is the exception, for when
>   the choice is the point. Without this, U4's journey breaks
>   at the second developer's host: a precisely shared
>   definition only helps if the machine can be built where
>   that developer is.

**U10 — The install is the thing under test** — pledged 2026-08-19
(owner). Drafted 2026-07-23: the control-plane arc's prose already
named install-testing ("os-autoinst-style, where the install is the
thing under test") but no numbered case owned it, and it is the use
that makes agentless operation permanently essential rather than a
bootstrap convenience. The pledge carries the citation it promised:
the arc's prose (ARCHITECTURE.md) and the two agentless-permanence
statements that derive from it — P2 (ARCHITECTURE.md) and G1
(docs/spec/script-spec.md) — now name U10. Nothing is built yet; the
case is met when a script can drive and observe an install run to a
pass/fail verdict with the machine discarded, purely agentlessly.
Text verbatim as drafted:

> - **U10 — The install is the thing under test.** An installer
>   or media maintainer runs an install to prove the install:
>   the screen is the assertion surface, the run record is the
>   verdict, and the machine is discarded. Agentless operation
>   is essential here, not a fallback — until the install
>   succeeds there is nothing in the guest to cooperate, and
>   the moments before an agent could exist are exactly the
>   ones under test. The same script observes a changed
>   installer honestly, failing with the screen it actually
>   saw.

**U25 — Automate a guest that paints in its own font** — pledged
2026-08-19 (owner). Drafted 2026-08-13, while fixing the fonts a
FreeDOS install is read through. The pledge cuts **F61** and **F62**
straight to [pledged/FEATURES.md](FEATURES.md) — F61 the authored
font and the statement that names it, F62 the DOS dump — and this
case is met when both land. It carries the citation the draft
promised on pledge: the display plane's own documentation now names
U25 wherever it says what the recognizer reads a screen through —
the text-screen contract
([design/backend-adapter.md](../design/backend-adapter.md)), the DOS
control plane's recognizer sentence
([design/guest-communication.md](../design/guest-communication.md)),
and the failure clause in
[docs/spec/script-spec.md](../../docs/spec/script-spec.md) that
already described this screen without owning it. The round's
settlements are **D109**.

**U27 was cut out of this case in the same act.** The draft named
two doors — a font **taken from the guest**, and a font **the author
supplies** where there is no moment to ask — and a journey states one
path, the fewest steps that reach the goal. Two doors to one goal is
a menu, which the landing bar sends to a guide; and the second door
is a goal someone pursues in its own right, which is where the
happy-path rule sends a deviation that is one. So it took a number
rather than a branch inside these steps. Neither half changed in
substance: **F61 delivers both**, and F62 is U25's alone.

**The gap is already load-bearing, and closed only by luck.** FreeDOS
does install a font — VirtualBox's BIOS applies its override table on
every text mode set, so a guest that merely set a mode would paint
the patched glyphs, and FreeDOS paints the unpatched ones. It is read
correctly because the font it installs happens to be byte-identical
to a bank VirtualBox stores. Nothing guarantees that for the next
guest.

**The guest is the only party that knows what it loaded**, and on DOS
it can be asked: `INT 10h AH=11h AL=30h` returns a pointer to the
live table, all 256 glyphs exactly, whatever was loaded. That is
guest-specific by nature — another platform has its own call and its
own dumper — so the dumper is Reliquary's platform workflow rather
than any one script's business, and it ships in the codex as F62.

**The bytes cross on a drive the author supplied**, which is the
shape D108 already settled for a file crossing the boundary: a
directory-source media attaches a host directory, the guest writes
`FONT.BIN` into it, and the author reads it off their own disk with
their own tools — Reliquary supplies the drive a file crosses on and
nothing inside it (**U14**). Two prices are accepted rather than
argued away. Directory-source drives are QEMU-only today, so the
*dump* is bound to QEMU while the asset it produces is portable to
every backend — the font is the guest's, not the host's, which is the
whole finding. And the file arrives after the machine stops, which an
authoring act performed once per guest font can afford. The
alternatives — a UART pointed at a host file, an image swapped live
and opened with the author's own tools — are recorded in **D109**
with what each cost.

**WEIGHED AND DECLINED: learning the font from pixels.** Render a
screen whose text the author states, cut it into cells, and record
each bitmap against its character. It needs no new channel and no
guest cooperation, and the recognizer would take the result as one
more bank — partial is enough, since unmatched glyphs fall through to
the host's. But it yields only the glyphs that appeared on one
screen, it asks the author to transcribe a framebuffer by eye, and
the artifact is worse for more work. It stays recorded because a
guest with no native door would leave it the only way — and note what
it is: a worse **capture route** to the same declared asset, not a
rival place to put one.

**The painting authority changes mid-boot, and only the script knows
when.** The BIOS paints with the bank it patched at the mode set;
then the guest takes control and paints with its own. So the font is
named **positionally** — from here forward, try this first, the rest
behind it — the shape U24's `boot` settled for drive order: name what
comes first and let the remainder follow. Saying it also **narrows**,
which is the part that is easy to miss: every additional bank is one
more chance for a near-match to beat the true glyph, so naming the
font in force corrects priority rather than adding to a pile. That is
why F61 makes the recognizer's order a real priority rather than the
tie-break it is today (D109). Text as pledged:

> - **U25 — Automate a guest that paints in its own font.** A script
>   waits for text the author can plainly see on the screen, and the
>   wait never matches. The guest has loaded a face of its own — a
>   prepared codepage, a localized shell — and the screen is being
>   read against the fonts the *host's* hypervisor installed, which
>   do not include it; the run ends at a timeout saying how much of
>   the screen could not be read. The guest is the only party that
>   knows what it loaded, and wherever a script can reach a prompt it
>   can be asked: the face comes out of the running guest, is kept as
>   an asset of its own, and is named from the point in the run where
>   the guest takes the screen over — the firmware painted the
>   earlier screens, and painted them in a different face. From there
>   the wait matches the text that was on the screen all along, and
>   the guest automates on any host that will run it (U7).
>
>   Precondition: an installed machine (U12), and the dumper copied
>   out of the library — `rlq seed-script freedos-dump-font` (U11).
>
>   1. **Give the machine somewhere to put the dump.** In the
>      blueprint, a drive whose media is a host directory — the drive
>      the file crosses on, with nothing of Reliquary's inside it
>      (U14) — and `rlq apply-blueprint --blueprint <name>`, which is
>      what hands the stopped machine a drive its blueprint gained.
>   2. **Ask the guest for the font it loaded.** `rlq run-script
>      freedos-dump-font --blueprint <name>` (*requires F62*): it
>      boots to a prompt, reads the live glyph table, writes it to
>      that drive as `FONT.BIN`, and powers the machine off. The 4096
>      bytes are in the author's own directory when the run returns.
>   3. **Declare what the bytes cannot say.** `guest.rlqf` in the
>      fonts directory — the cell size, and the codepage the bank's
>      indices mean — with the dumped file beside it as `guest.bin`
>      (*requires F61*).
>   4. **Name it where the guest takes the screen over.** In the
>      script, `font @guest` at the phase that follows the guest's
>      own font load (*requires F61*): the font named is tried first
>      and the host's follow.
>   5. **Run the script.** `rlq run-script <script> --blueprint
>      <name>`.
