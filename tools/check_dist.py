# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Check that the built wheel and sdist carry what they must.

The wheel ships no test suite, so nothing inside the wheel checks
itself. That check lives here instead, and it fits better here
anyway: this file states directly what has to be present, rather than
trusting a test suite that happened to pass.

The sdist does carry the test suite (D105), and this checks it two
ways: that the suite is present at all — an sdist whose suite can't
be verified is exactly what D105 ruled out — and that it is complete,
because setuptools' default sdist rules ship the top-level
`tests/*.py` files but drop the subdirectories under them. If the
fixture corpus silently stopped shipping, the suite inside the sdist
would still pass, having nothing left to check.

What this checks is package data: files that setuptools ships only
because `[tool.setuptools.package-data]` lists them, and which
therefore vanish silently the moment that list falls out of date. A
missing `.lark` grammar file or a missing `schemas/*.json` file
breaks an installed copy of Reliquary the first time it runs, even
though every test in the source tree still passes.

Run it after `python -m build`:

    python tools/check_dist.py
"""

import os
import sys
import tarfile
import zipfile

# Files the wheel must carry. Without these, an installed copy of
# Reliquary fails at runtime, and no test running from the source
# tree would catch it.
WHEEL_REQUIRED = (
    "reliquary/script_grammar.lark",
    "reliquary/schemas/blueprint-schema-v1.json",
    "reliquary/schemas/landmark-schema-v1.json",
    "reliquary/schemas/machine-state.schema.json",
    "reliquary/fonts/cp437_8x16.bin",
    "reliquary/codex/codex.json",
)

# Prefixes the wheel must carry at least one file under.
WHEEL_REQUIRED_TREES = (
    "reliquary/codex/blueprints/",
    "reliquary/codex/scripts/",
)

# The wheel is the runtime: the suite is not in it.
WHEEL_FORBIDDEN_TREES = ("tests/",)

# The sdist is the source package: the runtime plus the test suite
# that verifies it (D105). Each subdirectory of the suite is listed
# by name here because that's the half setuptools drops silently by
# default — its default sdist rules ship the top-level `tests/*.py`
# files but none of the trees below them, leaving an archive whose
# suite passes while checking nothing it was written to check.
SDIST_REQUIRED_TREES = (
    "tests/",
    "tests/fixtures/conformance/blueprint/valid/",
    "tests/fixtures/conformance/blueprint/invalid/",
    "tests/fixtures/conformance/blueprint/invalid-at-resolution/",
    "tests/fixtures/conformance/script/valid/",
    "tests/fixtures/conformance/script/invalid/",
    "tests/fixtures/conformance/script/invalid-at-preflight/",
    "tests/fixtures/conformance/transcript/",
    "tests/fixtures/text_recognize/",
)

# What the sdist must not carry, each left out for its own reason.
# `planning/` is maintainer governance (D96), not something a
# consumer needs. `docs/` is the repository's own prose — a consumer
# gets what they need from README.md, which reaches them through the
# distribution metadata regardless. `tests/source_tree/` is the part
# of the suite that checks `planning/` and `docs/` exist: shipped in
# the sdist, where those two are missing, it would just find nothing
# there and report success, so it is left out entirely rather than
# left in to pass without checking anything real.
SDIST_FORBIDDEN_TREES = ("planning/", "docs/", "tests/source_tree/")


def _wheel_names(path):
    with zipfile.ZipFile(path) as archive:
        return [name for name in archive.namelist()
                if not name.endswith("/")]


def _sdist_names(path):
    with tarfile.open(path) as archive:
        return [member.name.split("/", 1)[1]
                for member in archive.getmembers()
                if member.isfile() and "/" in member.name]


def _one(directory, suffix):
    found = sorted(name for name in os.listdir(directory)
                   if name.endswith(suffix))
    if len(found) != 1:
        raise SystemExit(
            "expected exactly one %s in %s, found %d: %s"
            % (suffix, directory, len(found), found or "none"))
    return os.path.join(directory, found[0])


def main(directory="dist"):
    if not os.path.isdir(directory):
        raise SystemExit("no %s/ directory; run `python -m build` first"
                         % directory)
    wheel = _one(directory, ".whl")
    sdist = _one(directory, ".tar.gz")
    names = {"wheel": _wheel_names(wheel), "sdist": _sdist_names(sdist)}

    problems = []
    for required in WHEEL_REQUIRED:
        if required not in names["wheel"]:
            problems.append("wheel is missing %s" % required)
    for tree in WHEEL_REQUIRED_TREES:
        if not any(n.startswith(tree) for n in names["wheel"]):
            problems.append("wheel carries nothing under %s" % tree)
    for tree in WHEEL_FORBIDDEN_TREES:
        carried = [n for n in names["wheel"] if n.startswith(tree)]
        if carried:
            problems.append(
                "wheel carries %d files under %s, which no artifact ships"
                % (len(carried), tree))
    for tree in SDIST_REQUIRED_TREES:
        if not any(n.startswith(tree) for n in names["sdist"]):
            problems.append("sdist carries nothing under %s" % tree)
    for tree in SDIST_FORBIDDEN_TREES:
        carried = [n for n in names["sdist"] if n.startswith(tree)]
        if carried:
            problems.append(
                "sdist carries %d files under %s, which no artifact ships"
                % (len(carried), tree))

    print("wheel: %s (%d files)" % (os.path.basename(wheel),
                                    len(names["wheel"])))
    print("sdist: %s (%d files)" % (os.path.basename(sdist),
                                    len(names["sdist"])))
    if problems:
        print("\nFAILED:")
        for problem in problems:
            print("  " + problem)
        return 1
    print("\nOK: both artifacts carry what they must")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
