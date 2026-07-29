<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Pledged features

Large capability that is **pledged but not yet built**, each
carrying the work breakdown that delivers it. A feature arrives here
by being moved out of
[proposed/FEATURES.md](../proposed/FEATURES.md) — the move is the
pledge and the commit is its record ([README.md](../README.md))
— and leaves by being delivered, or by being **withdrawn** back to
that file when the pledge turns out to be one nobody meant (D44;
first used by D61).

Pledged is not scheduled: the numbered milestone arc ended with
milestone 9, so nothing below is queued or dated. The work items are
tasks like any other and answer to the same rules as
[TASKS.md](../TASKS.md); they sit with their feature rather than in
that queue because they are meaningless apart from it.

Each feature carries an **F-number** and must fit in **one sprint**
(D42; the rules are in [README.md](../README.md)). A feature too
large is cut on pledge, the split retiring the parent's number
for a fresh one per piece.

**This shelf emptied three times on 2026-07-27, by the two exits
it has.** F17 and F23 left by **delivery**, the ordinary one, and
their numbers retire with them (below). **F1 left by withdrawal**
(owner; D61) —
the first use of that exit, and the reverse of the move that is
supposed to fill this file. Nothing was rejected: the recorder's
design stands and its demand is live. What was wrong was the
pledge, which nobody ever made — the 2026-07-26 restructure housed
the feature here because its work items had nowhere else to live,
and D44's rename then converted what this shelf *claims*, from
agreement into a commitment to deliver, without re-testing its
occupants. **U6**, the use case F1 delivers, and **U2** left for
[proposed/USE-CASES.md](../proposed/USE-CASES.md) in the same
round; **U1** left upward, condensed and promoted to the current
list. D44 wrote the remedy — a pledge nobody means is withdrawn or
rejected, never left sitting — and this is its first use.

**It refilled and emptied again on 2026-07-28** (owner), with
**F2**, the backend adapter seam — pledged in the morning and
delivered the same day, so it joins F17 and F23 in leaving by the
ordinary exit rather than becoming the first entry to sit here.
Its demand, **U7**, was pledged in the same act
([USE-CASES.md](USE-CASES.md)) and had to be: F2 waited five days
for it, off the arc since 2026-07-23, and pledging a feature ahead
of the demand that justifies it is the error D61 undid. **U7 does
not travel with it**: the seam is what U7 needed built, and the
case itself is met only when a second adapter can materialize a
machine on the hypervisor a host actually provides. F2 was tested
against the size bound and pledged **whole**, so its number
retires unreused (D65) — the extraction was bounded by working
code and by a regression oracle, not by judgment about how much is
enough.

**It refilled again on 2026-07-29** (owner; D79) with **F24** and
**F25**, the two halves of `--dry-run` — and by the exit no feature
had used before. F11 was **cut on pledge**: too large for D42's
one-sprint bound, so its number retires unreused and a fresh one
comes to each piece, which is the rule this file's own preamble
states and the first occasion to apply it. D65 is the near miss —
F2 was weighed for the same cut a day earlier and pledged whole,
its pieces not being independently useful. These two are: each
lands coherently on its own, and neither waits on the other.

*(F17 — input pacing before guest input — delivered 2026-07-27,
so its number retires unreused. The `pacing` keyword, the
`statement > phase > header > built-in 0.1s` ladder, the
parse-time plan `check-script` reports, and the runtime pause are
recorded in [D60](../DECISIONS.md); the model is normative in
[script-spec.md](../../docs/spec/script-spec.md)'s Timing
section.)*

*(F23 — in-band listing and whole-tree file transfer — delivered
2026-07-27, the same day it was pledged, so its number retires
unreused. `list-files` / `get-files` / `put-files` and their
twins ship with one guest-terms address vocabulary shared with
`put-file` / `get-file`, a drive root sayable as `A:\`, a flat
listing document whose addresses feed straight back to the file
verbs, and a required `get-files` destination; the round is
[D62](../DECISIONS.md) and the surface is normative in
[cli.md](../../docs/spec/cli.md)'s in-band section.*

***P16 was armed by the same change***, which is the whole point
of the feature: it moved to the standing list with its residue —
an image drive has no in-band route — filed as a defect under
[TASKS.md](../TASKS.md), per D34 and D48.)*

*(F2 — the backend adapter seam — delivered 2026-07-28, the day it
was pledged, so its number retires unreused. One adapter API now
carries every backend operation
([design/backend-adapter.md](../design/backend-adapter.md), which
travelled out of `pledged/design/` with the delivery and records
the signatures it said it would): QEMU's half is
`reliquary/backend_qemu.py` and nothing above the seam names QEMU,
qcow2, QMP or a port; the agentless display console is
`reliquary/control_display.py`, reading the portable text-screen
contract rather than VGA bytes; assignment walks the D66 priority
order at materialization and takes the first backend both
available and capable, naming the backend and the requirement when
none is; VirtualBox, VMware Workstation and Hyper-V ship as stubs
that probe honestly and claim nothing; and the recorded VM
identity generalized to `{backend, backend-id, token, endpoint}`.
The oracle it was pledged against — the FreeDOS install script
passing unchanged — is the opt-in integration test, which is
unchanged by the extraction. The round is
[D67](../DECISIONS.md).*

***The three stubs are not a second backend.*** U7 stays pledged
and F3 stays proposed: what is delivered is the seam U7 demanded,
not the capability, and the order's tail remains intent recorded
(D66).)*

## F24 — `create-machine --dry-run`

> **Pledged 2026-07-29** (owner), cut from **F11** with
> [F25](#f25--run-script---dry-run-and-the-end-of-the-check-family);
> the parent's number retires unreused (D42, D79). Serves **U7**
> ([USE-CASES.md](USE-CASES.md)) through the portability reading
> below, and **P11**, which is what a backend-aware validation
> reports. F11's banner cited U7 as a draft; it was pledged
> 2026-07-28 (D65). **This feature carries no decide-first** —
> D79 settled every one it arrived with.

THE RULE, shared with F25 and the whole of why the two are one
semantic: *a dry run performs every step that costs nothing and
commits nothing, stops at the first step that would, and reports
what it would have done.* Two invariants carry it. It **leaves no
state behind** — no machine directory, no `machine.json`, no
fetched payload, no started process; a step that cannot be
evaluated without committing is reported unevaluated rather than
performed. And its **return describes the run, never impersonating
the run's output**, which is the line F25's exclusion draws.

**This is the gap, and filling it is the point.** Scripts can be
checked today; machines cannot, so there is no way to ask "is this
blueprint sound, and what would it build?" without building it.

Evaluate: blueprint parse, namespace resolution, reference closure,
drive and medium compatibility, backend capability, slot limits,
the machine id that would be allocated, and each drive's resolved
plan — `new` (size), `use` (which location, cached or not),
`difference` / `copy` (over which base). Stop before the machine
directory, `machine.json`, `create_hdd_image`, and any fetch.

MEDIA RESOLVES AND NEVER FETCHES, resolution and acquisition being
different costs. Report each medium as cached, would-download (with
size and sha256), local-present, or local-missing: a missing
*local* file is an error a dry run can and should catch, and a
not-yet-downloaded remote is not. A later `--dry-run=verify` that
additionally hashes what is already cached is the check people want
before a long install — noted, not proposed, and its own interface
change when someone wants it. `--dry-run` is a **boolean** here and
binds as one (P7); a value vocabulary is what that later form would
have to argue for.

**IT MUST NOT PROMPT, AND TODAY'S CREATE DOES.** `create_machine`
binds every `${key}` a media location references through
`binding.bind_keys(…, asker=console_asker())`, which asks. The dry
run needs the *describe* treatment instead — naming each key's
supplying source without binding it, which `binding.describe_sources`
already does for the script side and `check-script` already
promises. That is the one piece of real machinery this feature adds
beyond splitting evaluation from commitment.

**`--backend` IS A QUESTION, NOT A CONFIGURATION** (D79), and it is
new surface: the only `--backend` in the tree today is
`new-blueprint`'s scaffold field. It is **legal only with
`--dry-run`**, where it names the backend to validate against and
materializes nothing — so `rlq create-machine --blueprint NAME
--dry-run --backend vmware` answers "would this blueprint work over
there?" with nothing installed and nothing booted. That is the U7
contract — capability, not identity, failing closed by name
(P11) — checked statically, out of machinery that already exists.
It is confined to `--dry-run` because P10 gives the blueprint
authority over what a machine *is*: a flag that changed the
assigned backend at materialization would put that configuration
outside the blueprint, which is a different feature needing a
different argument. Note the combination that is *not* simulation:
`--dry-run --backend simulator` validates against the simulator's
capabilities and stops; running simulated means dropping
`--dry-run` and keeping the backend. Worth a line of help text,
because the mistake is natural.

SURFACE, both presentations together (P6):

    rlq create-machine --blueprint NAME --dry-run [--backend NAME]

    create_machine(name, *, dry_run=False, backend=None, ...)
        -> str | DryRun

**A distinct return type is the point.** A `dry_run=True` call must
not return something a caller can mistake for the real return: a
machine id naming no machine, or `None`, makes misuse a confusing
failure three layers down, where a `DryRun` object makes it a
`TypeError` at the call site. `dry_run` is already the project's
word (`prune_media`, D22), so this is consistency rather than
overloading, and it is **per-call only** — no `set_dry_run()`, no
`Context(dry_run=…)`, an ambient mode being how a dry run gets left
on.

This half needs no output-discipline work: `create-machine` is
already a result-bearing `--json` command, so the `DryRun` document
lands in the machinery that is there. F25 is where that costs
something.

Work items:

1. Split evaluation from commitment in `machines.create` — every
   check the create path already makes, reached without the
   directory, the state file, the image work or the allocation.
2. The `DryRun` return type and its `--json` document, defined
   once and shared with F25's script variant.
3. Media resolved and never fetched, reporting the four states,
   with a missing local file an error.
4. Location properties described rather than bound, so nothing
   prompts.
5. `--backend` under `--dry-run` only, and the help text naming the
   simulation mistake.
6. The surface landed on both presentations, `cli.md` and `api.md`
   with it, and tests asserting the two invariants directly: no
   state behind, and the return not the run's.

## F25 — `run-script --dry-run`, and the end of the check family

> **Pledged 2026-07-29** (owner), cut from **F11** with
> [F24](#f24--create-machine---dry-run); the parent's number
> retires unreused (D42, D79). Serves **P6** — it retires the
> second spelling of one semantic — and **P9**, which deletes the
> old spelling rather than aliasing it. **No use-case impact**:
> `check-script` ships, and this is a better spelling for it, which
> is the first triage bullet of
> [INTERFACES.md](../INTERFACES.md). **This feature carries no
> decide-first** — D79 settled every one it arrived with.

**`run-script --dry-run` is what `check-script` already is.**
Everything `ScriptCheck` returns — script path, timing plan,
resolved machine, property sources, printable report — is a dry run
of a script. Evaluate parse, static checks, property binding
(naming unbound keys and their sources), referenced media and
landmarks, the timing plan, and the machine selector resolving to a
real machine; stop before starting the machine and before any
statement reaches a guest. F24 states the rule both halves share.

THE CHECK INVENTORY — three public names carrying the word, and
they are not one thing:

| name | disposition |
|---|---|
| `check_script()` | becomes `run_script(dry_run=True)` |
| `ScriptCheck` | becomes `DryRun` |
| `check_key()` | goes private — a different species |

`check_key(key)` validates a property key and returns it. There is
no operation to dry-run: it is a predicate on a string, like
`str.isidentifier()`, and folding it into `--dry-run` would be
forcing it. **It goes private** (D79), which is the tidier of the
two dispositions F11 offered and the one that closes something —
it is exported from `reliquary/__init__.py`, appears in no `api.md`
parity row and has no CLI twin, so it is a standing P6 residue
today. Privacy closes it; `validate_key()` would keep it open and
owe a CLI twin for a string predicate. P9 deletes the old spelling
rather than aliasing it.

THREE SURFACE COLLISIONS, all settled in D79 and none of them
visible until the shipped commands were read side by side. This is
what makes the respelling more than a rename, and it is why this
half — not F24's — is where the surface work is.

- **A dry run is a document, not a stream, and the flip is
  forced.** `run-script` rejects `--json` today, naming
  `--progress jsonl`: a live run is an event stream. Under
  `--dry-run` the twin returns a `DryRun`, and `cli.md`'s own rule
  is that `--json` prints *exactly what the API twin returns* — so
  `--json` becomes legal and `--progress` has no stream to render.
  `--progress` and `--display` are refused under `--dry-run` rather
  than accepted and ignored (P11: say what cannot be done).
- **The selector relaxes, and the two modes survive.**
  `run-script` requires `--blueprint` or `--machine`;
  `check-script` does not, and `script-spec.md` makes the
  selector-less mode normative — "exactly two modes, one per
  checkable tier". So under `--dry-run` the selector is optional
  and its presence chooses the tier: without one, every legality
  rule; with one, the machine rules as well. Merged without this,
  the respelling silently deletes a specified mode.
- **One positional, one name.** `check_script`'s first parameter is
  `name` and `run_script`'s is `label`; the merged verb keeps
  `label`, resolving label-first then bare stem exactly as D8 item
  7 settled — that resolution survives the rename intact.

THE REPORT COVERS THE WHOLE SCRIPT AND SAYS WHAT IT COULD NOT REACH
(D79). Conditions and handlers depend on guest state, so a plan can
only ever be a plan — the report states the limit outright
(`3 statements not statically reachable`) rather than implying a
completeness it cannot have, which is P11 at the report level.
Reporting only the statically decidable part was declined: a reader
cannot tell what was omitted, and the counts stop describing the
script the caller wrote.

SURFACE, both presentations together (P6):

    rlq run-script LABEL --dry-run [--blueprint NAME | --machine ID]

    run_script(label, *, dry_run=False, ...) -> ScriptRun | DryRun

WHAT IS DELIBERATELY EXCLUDED — mocked statement results, so
control flow could execute. That is where the feature would change
species, and the tell is sharp: **a dry run's output is *about* the
run — a plan, a report, a verdict; a fake backend's output is *of*
the run.** Once output is *of* the run, three obligations follow
that a flag is a poor place to carry: somewhere to declare the
responses, a way to distinguish simulated output from real, and a
guarantee it cannot be switched on by accident. The accident is
concrete for any caller that parses guest output — a misconfigured
run reports every guest test passing having booted nothing. A plan
can never be mistaken that way; fabricated output can.
**[F12](../proposed/FEATURES.md) is where that belongs, and the two
are documented in the same breath**: the first reading of
`--dry-run`, including by this project's own author, is "simulate
the run", so the fix is making the fake backends easy to find
rather than making the validator into one.

Work items:

1. `run_script(dry_run=True)` absorbing `check_script`'s body, and
   `ScriptCheck` becoming the `DryRun` F24 defines.
2. `--dry-run` on `run-script`: the selector optional and choosing
   the tier, `--json` legal, `--progress` and `--display` refused.
3. The report naming what it could not statically reach.
4. `check_key` private, out of `__init__.py` and out of
   `api-reference.md`.
5. `check-script` deleted — the subcommand, the twin, and every
   mention across `cli.md`, `api.md`, `script-spec.md`,
   `script-properties.md`, `http-serve.md`, the two references,
   `README.md` and `AGENTS.md`. P9 leaves no alias behind.
6. The CHANGELOG line, under the unreleased section, naming the
   deleted spelling — this is a rename users hit.
