# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""CLI-API parity, checked against the rule that states it.

P24's inventory pass over the embedding API. The comparison the
other interfaces get -- what the spec enumerates against what the
code enumerates -- does not apply here, and the banner is why:
docs/spec/api.md declares itself "the end-goal design for
Reliquary's embedding API", so it deliberately names capability
that does not exist (`clone_machine`, `export_drive`,
`export_machine`, the pull-only handles). A document that does not
claim to describe today cannot be diffed against today, and
forcing it would only measure how much design is pending.

What *is* a claim about today is the rule that document states as
a Convention and AGENTS.md repeats as a required invariant: **the
twin-name identity rule** -- "the CLI command *is* the twin's
name, dash-separated", with "nothing CLI-only". That is checkable
against the two things the code enumerates itself, `cli._COMMANDS`
and the package's `__all__`, and it is the more valuable check:
parity is an invariant, where the inventory is only a document.

It found two divergences on 2026-07-27:

- `import-vm` shipped as a registered command whose handler was
  `raise NotImplementedError`, while the CLI spec described it
  working in present tense with a worked example, and both specs
  asserted an `import_vm` twin that did not exist. The command
  inventory test could not see it -- the command *word* was in
  both the spec and `_COMMANDS`, which is all that test compares.
  Retired with the rest of Machine mobility.
- `fetch_media` was imported into the package root but left out
  of `__all__`, so a headline twin was missing from the declared
  surface while its command shipped.

**The named gap** (P24's own clause, rather than a quiet
exemption): only one direction is tested. "No public capability
is unreachable from the CLI" is the rule's other half, and it has
no mechanical form -- `__all__` carries types, path helpers,
parsers, and lifecycle seams that are legitimately not commands,
so the reverse difference is a judgement per name and not a set
operation. Checking it would take a curated roster of
non-command surface, which is a design round, not a test.
"""

import os
import re
import unittest

import reliquary
from reliquary import cli

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_API_SPEC = os.path.join(_REPO_ROOT, "docs", "spec", "api.md")

_BACKTICKED = re.compile(r"`([^`]+)`")
_CONSOLE_ROW = re.compile(r"^\|\s*guest-console family\s*\(([^)]*)\)",
                          re.M)


def _console_family():
    """The CLI verbs api.md exempts from the twin-name rule.

    Read from the spec rather than listed here: the guest-console
    family is one of the rule's two named exceptions -- it "spells
    as the script language's verbs", its twins deferred to the
    control-plane design -- so which verbs are in it is the
    spec's answer to give, and a verb leaving the family should
    move this test with it.
    """
    row = _CONSOLE_ROW.search(_spec_text())
    if row is None:
        raise AssertionError(
            "docs/spec/api.md no longer has a guest-console family row; "
            "the parity test reads its exempt verbs from that row.")
    return set(_BACKTICKED.findall(row.group(1)))


def _spec_text():
    with open(_API_SPEC, encoding="utf-8") as handle:
        return handle.read()


@unittest.skipUnless(os.path.isfile(_API_SPEC),
                     "the API spec is source-tree only")
class TwinNameIdentityTests(unittest.TestCase):
    """Every command is its API twin's name, dash for underscore.

    The `run` family -- the rule's other named exception -- needs
    no handling here: it maps to the run handle's methods and
    ships no command at all (D35/D36 backlogged it), so nothing it
    covers is in `_COMMANDS` to exempt.
    """

    def _twins(self):
        """Each command owing a twin, with the name that twin has."""
        exempt = _console_family()
        return {command: command.replace("-", "_")
                for command in sorted(cli._COMMANDS)
                if command not in exempt}

    def test_every_command_has_an_api_twin(self):
        missing = sorted(
            command for command, twin in self._twins().items()
            if not hasattr(reliquary, twin))
        self.assertEqual(
            missing, [],
            f"{missing} are commands with no embedding-API twin. "
            "Nothing is CLI-only: every command maps one-to-one onto "
            "a public API call with the same semantics (AGENTS.md, "
            "CLI-API parity).")

    def test_every_twin_is_in_the_declared_surface(self):
        undeclared = sorted(
            twin for twin in self._twins().values()
            if hasattr(reliquary, twin)
            and twin not in reliquary.__all__)
        self.assertEqual(
            undeclared, [],
            f"{undeclared} are reachable but absent from __all__. The "
            "package root exposes the intended embedding surface, so "
            "a twin missing from it is a capability the API does not "
            "admit to having.")

    def test_the_exempt_verbs_are_all_commands(self):
        # The exemption is read from the spec, so it can go stale in
        # the other direction: a verb listed there and absent from
        # the CLI would silently widen what the rule skips.
        stray = sorted(_console_family() - set(cli._COMMANDS))
        self.assertEqual(
            stray, [],
            f"api.md exempts {stray} from the twin-name rule, and they "
            "are not commands. An exemption for something that does "
            "not exist can only hide a real one.")


if __name__ == "__main__":
    unittest.main()
