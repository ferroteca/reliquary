# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The one parametrisation helper every conformance corpus reads through.

A corpus is worth what its harness can prove ran, and a loop is worth
nothing on that measure. The blueprint corpus once ran against the
parser and **not** the schema while claiming the two cannot drift,
because 135 fixtures across two checks inside `subTest` is a run whose
halved form looks exactly like its whole one (D106).

The two functions here are the two halves of the fix:

- `parametrize` makes every fixture a **collected node named for its
  file**, so a check the harness stopped applying stops being counted,
  and a failing fixture is selected by name — `pytest
  tests/test_script_corpus.py -k v7-two-channels.rlqs`.
- `fixtures` **counts the bucket at collection**, so a corpus that
  stops loading is a collection error rather than a green run over
  nothing. An empty `parametrize` is one quiet skip, which is the same
  failure wearing a different hat.

One helper rather than one per corpus: the guarantee is a property of
the harness, not of a document format, and the third corpus (F43's)
inherits it by reading through the same two calls. A check over a
vocabulary the *package* declares — a schema's phase enum — is not a
corpus and parametrises directly; what belongs here is a directory of
fixture files.
"""

import glob
import os

import pytest


def fixtures(root, bucket, suffix, count):
    """The fixtures in one bucket, sorted, and there are `count` of them.

    Raised rather than asserted inside a test, because the count has to
    hold at **collection**: a bucket that lost its fixtures would
    otherwise take its assertions with it, and a check nothing collects
    reports nothing. A collection error names the module and stops the
    run; that is the whole point of pinning the number.
    """
    directory = os.path.join(root, bucket)
    paths = sorted(glob.glob(os.path.join(directory, f"*{suffix}")))
    if len(paths) != count:
        raise AssertionError(
            f"{directory} holds {len(paths)} `{suffix}` fixtures and "
            f"this harness is pinned to {count}. Adding or retiring a "
            "fixture updates the count here and the tally in the "
            "corpus README together — the pin is what stops a corpus "
            "that stopped loading from passing quietly.")
    return paths


def parametrize(paths, name="fixture"):
    """One collected node per fixture, named for its file."""
    return pytest.mark.parametrize(
        name, paths, ids=[os.path.basename(path) for path in paths])
