<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Script authoring by recording

> **Status:** this is the settled design for U6's authoring recorder
> (planning/proposed/USE-CASES.md U6; owner rounds, 2026-07-21 — the
> decisions behind it are recorded in planning/DECISIONS.md).
> **Nothing here is pledged.** The recorder is feature **F1** in
> planning/proposed/FEATURES.md, which lists its deliverables and how
> they'll be split up when it's pledged. This design document moved
> along with F1 when both were withdrawn from `pledged/` (D61,
> 2026-07-27). The design itself is settled and stands as written —
> what's unpledged is only when it gets built, not what it looks
> like.

The authoring recorder exists to serve U6: a person performs a task
once, in a console session Reliquary is watching, and Reliquary
drafts the script plus captures the landmark image assets needed to
reproduce that task later. Here is the settled design:

**Recording requires Reliquary itself to be the console the person
types into.** Input typed directly into a backend's own display
window never passes through Reliquary at all and can't be recorded.
So recording instead happens inside a viewer Reliquary owns, running
over the `vnc` control plane, where every keystroke, click, and media
swap is actually observable. This viewer is a real piece of software
that has to be built, and it's a prerequisite for recording on every
backend — including QEMU.

**The first capture produces a draft; the author tailors it by
hand.** Each input event splits the session's timeline into steps:
the stable screen that appeared right before an input becomes the
proposed wait condition (a VGA text match in text mode, a landmark
image in GUI mode), the input itself becomes the proposed action, and
however long the recorder actually observed the guest taking becomes
a proposed, generously padded timeout. Anything the recorder can't
know on its own — which features of a screen are actually
load-bearing, how long a step can honestly be expected to take — it
flags with a generated comment in the draft rather than guessing
silently. Text-mode capture comes first and needs no new language
feature to support it. GUI capture rides on the existing
landmark/click work, and a click's screen position seeds where its
matching landmark image comes from. The draft itself is ordinary
script text. By default it's self-contained — landmark images travel
as embedded, resolve-in-place blocks (docs/spec/landmarks.md) — with
the option to factor them out into separate catalog files instead.
Once written, it belongs to the user from then on, the same way
`import-vm`'s output does.

**Re-recording works together with hand-tailoring, using playback to
find the right spot.** Any customization the author made by hand has
to survive a later re-capture, so a later recording session never
regenerates the script from scratch and never text-merges into it.
Instead, Reliquary plays back the user's already-tailored script to
carry the machine forward to the point that needs to change — either
a breakpoint the author set, or the exact statement where the script
now fails because the guest has changed — and the person then takes
over the console, demonstrates the new behavior, and hands control
back. The recorder then produces a *fragment*: new waits, actions,
and image assets, anchored at that specific phase and statement of
the user's own script. Because this anchor point comes from actually
running the script, not from comparing it against some stored
original copy, this process works no matter how heavily the script
has been tailored — there's no pristine draft kept around anywhere,
and no merge step happens. (This mirrors a concept from os-autoinst's
interactive mode — only the concept is borrowed, per AGENTS.md, not
any of its code.)

**There are two separate kinds of update, each writing to disk in a
different way.** When a step is unchanged but its screen now looks
different, that's an *asset refresh*: it produces a new landmark
image variant and never touches the script file at all. The numbered
variant naming scheme (`<name>.<n>.png`, placed beside wherever the
landmark is declared — beside the script itself for an embedded
landmark; docs/spec/landmarks.md) means a refresh only ever creates a
new file, it never rewrites an existing one. When a step is new or
has actually changed, that's a *step capture*: the resulting fragment
is written out beside the script, for the author to manually splice
into their editor. An explicit, opt-in `apply` step can instead
perform that insertion automatically, surgically, at the anchor
point, without touching any other byte of the file — this is a named
exception within the same family as installing an embedded
definition. Either way, every update this process makes is
purely additive: nothing Reliquary has already written ever gets
rewritten.

**This reuses machinery that already exists for other purposes.**
Running to a specific point, breakpoints, and letting a human take
over control are all runner features that are also useful for
ordinary debugging — "take over from here" is a natural next command
to suggest in a failure report, independent of recording. Handover
events — control passing back and forth between the script and a
human — join the run-events stream as their own event kind, so a
recording session ends up as a single run record with a mix of
automated and human-driven steps. The `record` family of commands
lands on both the CLI and the embedding API together, keeping the two
in step with each other. Blueprints themselves are untouched by any
of this: a recording session runs on an ordinary machine, and media
swaps already use the existing `insert`/`eject` mechanism.

