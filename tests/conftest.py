# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The integration tier's selection, and the home it runs in.

The FreeDOS runs use a pytest marker instead of `skipUnless`, to tell
a deliberately skipped test apart from an accidental one (D106).
`skipUnless` reported the same "s" for a broken environment as it did
for a test that was never meant to run in this configuration, so the
suite used to assert an exact skip count just to tell the two apart.
With the marker, the integration tier is deselected by default, so a
default run has zero skips — any skip that does show up is a real
defect, not something to explain away.

`--integration` is a command-line option rather than an environment
variable, because whether to run the integration tier is a property
of this run, not of the host machine: the option shows up in
`--help`, a misspelled one is an error under `--strict-config`, and
it leaves nothing behind in the shell after the run finishes. Where
the run stores its files stays an environment variable —
`RELIQUARY_INTEGRATION_HOME`, read by `integration_home` below —
because a media cache worth reusing needs to outlive any one command
line.
"""

import os
import tempfile

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--integration", action="store_true", default=False,
        help="also run the integration tier: the FreeDOS install and "
             "verify runs against a live hypervisor, which need the "
             "backend on PATH and the network on a cold home")


def pytest_collection_modifyitems(config, items):
    """Deselect the integration tier unless it was asked for.

    Deselected rather than skipped: a deselected test simply is not
    part of this run, so it produces no skip report that could be
    misread as a tolerated failure.
    """
    if config.getoption("--integration"):
        return
    selected = []
    deselected = []
    for item in items:
        if item.get_closest_marker("integration") is None:
            selected.append(item)
        else:
            deselected.append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected


@pytest.fixture
def integration_home():
    """The home an integration run works in.

    `RELIQUARY_INTEGRATION_HOME` names an absolute home to reuse, so
    the LiveCD media cache survives reruns; it is created if absent
    and left behind. Otherwise a temporary home is created and removed
    with the test. Give the two backends *separate* reuse homes — the
    same machine id cannot span them.
    """
    reuse = os.environ.get("RELIQUARY_INTEGRATION_HOME", "").strip()
    if reuse:
        home = os.path.abspath(reuse)
        os.makedirs(home, exist_ok=True)
        yield home
        return
    with tempfile.TemporaryDirectory(
            prefix="reliquary-integration-") as home:
        yield home
