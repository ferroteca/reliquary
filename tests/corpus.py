# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The one parametrization helper every conformance corpus uses.

A corpus test is only as good as what the test runner can show
actually ran, and a `subTest` loop cannot show that. The blueprint
corpus once checked fixtures against the parser only, not the schema,
while claiming the two could not drift — because with 135 fixtures
and two checks running inside one `subTest`, dropping one of the
checks left the test report looking exactly like running both (D106).

The two functions here fix that, in two parts:

- `parametrize` turns every fixture into its own collected test,
  named after its file. If the harness stops running a check on a
  fixture, that fixture stops being counted, and a failing fixture
  can be selected by name — `pytest
  tests/test_script_corpus.py -k v7-two-channels.rlqs`.
- `fixtures` counts the files in a bucket at collection time, so a
  corpus that stops loading its fixtures shows up as a collection
  error, not as a run that passes because it silently ran nothing. An
  empty `parametrize` is the same failure, just now caught instead of
  passed over.

There is one helper here instead of one per corpus, because this
guarantee belongs to the test harness, not to any one document
format — the third corpus (F43's) gets it for free by calling the
same two functions. A check against a vocabulary the package itself
declares — such as a schema's phase enum — is not a corpus, and
parametrizes directly; what belongs here is a directory of fixture
files.
"""

import glob
import os

import pytest


def fixtures(root, bucket, suffix, count):
    """The fixtures in one bucket, sorted; asserts there are exactly
    `count` of them.

    This raises instead of using an `assert` inside a test, because
    the count has to be checked at collection time: if a bucket lost
    its fixtures, a test-level assertion would be lost along with
    them, since a test that collects nothing reports nothing. A
    collection error, by contrast, names the module and stops the
    run — that is the point of pinning the number here.
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
