# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The integration tier's selection, and the home it runs in.

**A marker states a deliberate tier where a skip states an accident**
(D106). The two FreeDOS runs were gated by `RELIQUARY_INTEGRATION` and
a `skipUnless`, which reported the same "s" a broken environment would
have — so the suite carried an asserted skip *count* to say which of
the two it was. The marker says it instead: the tier is **deselected**
by default and the default run skips nothing at all, so a surviving
skip is a defect with nothing to hide behind.

`--integration` is an option rather than an environment variable
because it is a property of the run being asked for, not of the host:
the option appears in `--help`, an unreadable one is an error under
`--strict-config`, and nothing about it survives in a shell after the
run. What stays environmental is where the run puts its files —
`RELIQUARY_INTEGRATION_HOME`, read by `integration_home` below, since
a media cache worth reusing outlives any one command line.
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

    Deselected rather than skipped: a deselected test is one this run
    was never for, and it leaves no report to read as a failure that
    was tolerated.
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
