# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Assert the built artifacts carry what they must.

The wheel carries no suite, so nothing inside it checks itself. That
job lives here, and it is a better fit either way: this *names* what
has to be present rather than inferring it from a suite that happened
to pass.

The sdist does carry the suite (D105), and it is asserted in both
directions — present, because an sdist that cannot be verified is the
thing D105 refused, and whole, because setuptools' default sdist
rules ship top-level `tests/*.py` without the subdirectories under
them. A corpus that silently stopped shipping would leave a suite
that still passes.

What it guards is package data — the files setuptools ships only
because `[tool.setuptools.package-data]` says so, and which therefore
disappear silently when that list drifts. A missing `.lark` grammar
or `schemas/*.json` breaks an installed Reliquary at first use while
every source-tree test still passes.

Run it after `python -m build`:

    python tools/check_dist.py
"""

import os
import sys
import tarfile
import zipfile

# Package data the wheel must carry: without these an installed
# Reliquary fails at runtime, and no source-tree test would notice.
WHEEL_REQUIRED = (
    "reliquary/script_grammar.lark",
    "reliquary/schemas/blueprint-schema-v1.json",
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

# The sdist is the source package — the runtime and the suite that
# verifies it (D105). The suite's subdirectories are named one by one
# because that is the half a manifest drops silently: setuptools'
# default rules ship `tests/*.py` and none of the trees below, which
# leaves an archive whose suite passes while checking nothing it was
# written to check.
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

# What the source package does not carry, each for its own reason.
# `planning/` is maintainer governance (D96). `docs/` is the
# repository's prose, and README.md reaches a consumer through the
# distribution metadata without it. `tests/source_tree/` is the part
# of the suite that reads those two: shipped, it would sweep an
# absent tree and report success, so it is kept out where it cannot
# run at all rather than left to run hollow.
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
