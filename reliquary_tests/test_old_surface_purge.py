# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The old script surface and superseded CLI names do not survive.

Milestone 4 task 11: a whole-tree sweep. Historical records
(released CHANGELOG, DECISIONS, completed ROADMAP notes) and
intentional negative / regression fixtures may still spell the old
forms; live code, tests, user docs, and shipped scripts must not.
"""

import io
import os
import re
import unittest
from contextlib import redirect_stderr, redirect_stdout

import reliquary
from reliquary import cli
from reliquary.script_nodes import ScriptParseError
from reliquary.script_parser import parse_script


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Superseded CLI command words (exact argv tokens).
_OLD_CLI_COMMANDS = frozenset({
    "script", "keys", "menu", "text", "create", "destroy",
    "start", "stop", "list",
})

# Superseded public API names.
_OLD_API_NAMES = (
    "create_from_blueprint",
    "start_cached_machine",
    "stop_cached_machine",
    "final_state",
    "ExpectBranch",
    "State",
    "EmbeddedMedia",
)

# Live-tree paths scanned for superseded spellings.
_SWEEP_ROOTS = (
    "reliquary",
    "reliquary_tests",
    "docs",
    "README.md",
    "AGENTS.md",
    "planning/examples",
)

# Files that may quote the old surface deliberately.
_ALLOW_PATH_SUFFIXES = (
    # Negative tests: old spellings must fail to parse.
    os.path.join("reliquary_tests", "test_script_parser.py"),
    os.path.join("reliquary_tests", "test_script_validation.py"),
    # This module names the forbidden spellings.
    os.path.join("reliquary_tests", "test_old_surface_purge.py"),
)

# Patterns that would be live old-surface / superseded-command use.
# Each is (name, compiled regex).
_FORBIDDEN = (
    ("create_from_blueprint",
     re.compile(r"\bcreate_from_blueprint\b")),
    ("start_cached_machine",
     re.compile(r"\bstart_cached_machine\b")),
    ("stop_cached_machine",
     re.compile(r"\bstop_cached_machine\b")),
    ("ScriptRun.final_state",
     re.compile(r"\bfinal_state\b")),
    ("ExpectBranch",
     re.compile(r"\bExpectBranch\b")),
    ("rlq script",
     re.compile(r"\brlq\s+script\b")),
    ("nested list machines",
     re.compile(r"\blist\s+machines\b")),
    ("nested list blueprints",
     re.compile(r"\blist\s+blueprints\b")),
    ("nested list scripts",
     re.compile(r"\blist\s+scripts\b")),
    ("rlq keys",
     re.compile(r"\brlq\s+keys\b")),
    ("rlq menu",
     re.compile(r"\brlq\s+menu\b")),
    ("rlq text",
     re.compile(r"\brlq\s+text\b")),
    ("old state keyword",
     re.compile(r"(?m)^\s*state\s+\w+\s*\{")),
    ("old arrow goto",
     re.compile(r"(?m)^\s*->\s+\w+\s*$")),
    ("old done terminator",
     re.compile(r"(?m)^\s*done\s*$")),
    ("old expect",
     re.compile(r"(?m)^\s*expect\s+")),
    ("bare wait stopped",
     re.compile(r"(?m)^\s*wait\s+stopped\s*$")),
    ("old boot verb",
     re.compile(r"(?m)^\s*boot\s+[a-zA-Z_]")),
    ("old key token",
     re.compile(r"<enter>|<esc>|<ret>|<tab>|<space>")),
)


def _allowed(path):
    rel = os.path.relpath(path, _REPO_ROOT)
    return any(rel.endswith(suffix) or rel == suffix
               for suffix in _ALLOW_PATH_SUFFIXES)


def _iter_sweep_files():
    for root in _SWEEP_ROOTS:
        path = os.path.join(_REPO_ROOT, root)
        if os.path.isfile(path):
            yield path
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [name for name in dirnames
                           if name not in {".venv", "__pycache__",
                                           "codex"}]
            # Ship the package's codex scripts too — walk them
            # explicitly below.
            for name in filenames:
                if name.endswith((
                        ".py", ".md", ".rlqs", ".lark", ".json")):
                    yield os.path.join(dirpath, name)
    codex = os.path.join(_REPO_ROOT, "reliquary", "codex")
    if os.path.isdir(codex):
        for dirpath, _, filenames in os.walk(codex):
            for name in filenames:
                if name.endswith((".rlqs", ".json", ".md")):
                    yield os.path.join(dirpath, name)


class RetiredMediaDefinitionTests(unittest.TestCase):
    """The `.rlqm` media-definition file kind is retired tree-wide.

    Media folded into the composed `.rlqb` blueprint (the 2026-07-23
    media/composition round); no `.rlqm` file survives anywhere in the
    package, the shipped codex, the examples, or the fixtures. The
    string may still appear in historical records (CHANGELOG,
    DECISIONS, completed ROADMAP notes) and design prose that names the
    retired format — this guards the *files*, not the spelling.
    """

    def test_no_rlqm_files_survive(self):
        survivors = []
        skip_dirs = {".venv", ".git", "__pycache__", "build", "dist"}
        for dirpath, dirnames, filenames in os.walk(_REPO_ROOT):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for name in filenames:
                if name.endswith(".rlqm"):
                    survivors.append(
                        os.path.relpath(os.path.join(dirpath, name),
                                        _REPO_ROOT))
        self.assertEqual(
            survivors, [],
            "the .rlqm media-definition file kind is retired; "
            "these files must be removed:\n" + "\n".join(survivors))


class OldApiNamesAbsentTests(unittest.TestCase):
    """Superseded package exports are gone, not aliased."""

    def test_old_api_names_absent(self):
        for name in _OLD_API_NAMES:
            self.assertFalse(
                hasattr(reliquary, name),
                f"reliquary still exports superseded name {name!r}")
            self.assertNotIn(name, reliquary.__all__)


class OldCliCommandsAbsentTests(unittest.TestCase):
    """Superseded CLI command words are not registered."""

    def test_old_cli_commands_absent(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                cli.main(["--help"])
            except SystemExit:
                pass
        help_text = stdout.getvalue() + stderr.getvalue()
        match = re.search(r"\{([^}]+)\}", help_text)
        self.assertIsNotNone(match, "cli --help lists no commands")
        commands = {part.strip() for part in match.group(1).split(",")}
        survivors = sorted(_OLD_CLI_COMMANDS & commands)
        self.assertEqual(
            survivors, [],
            f"superseded CLI commands still registered: {survivors}")


class OldScriptSurfaceRejectedTests(unittest.TestCase):
    """Old-surface documents fail closed — no bridge."""

    def test_old_surface_samples_do_not_parse(self):
        samples = (
            "platform dos\nstate ready {\n done\n}\n",
            "platform dos\nentry a\nphase a {\n    -> b\n}\n",
            "platform dos\nentry a\nphase a {\n    done\n}\n",
            'platform dos\nexpect "x" {\n}\n',
            'platform dos\nwait regex "x"\n',
            "platform dos\nwait stopped\n",
            "platform dos\nboot hdd0\n",
            'platform dos\ntype "A:" <enter>\n',
        )
        for source in samples:
            with self.subTest(source=source.splitlines()[1]):
                with self.assertRaises(ScriptParseError):
                    parse_script(source)


class LiveTreePurgeTests(unittest.TestCase):
    """No live path keeps a superseded spelling."""

    def test_live_tree_has_no_superseded_spellings(self):
        hits = []
        for path in _iter_sweep_files():
            if _allowed(path):
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
            except UnicodeDecodeError:
                continue
            # Skip Python string/comment bodies that only appear in
            # AST-string form inside allowlisted negative tests —
            # already handled by path allowlist.
            relative = os.path.relpath(path, _REPO_ROOT)
            for label, pattern in _FORBIDDEN:
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    hits.append(
                        f"{relative}:{line}: {label}: "
                        f"{match.group(0)!r}")
        self.assertEqual(
            hits, [],
            "superseded spellings survive in the live tree:\n"
            + "\n".join(hits))


if __name__ == "__main__":
    unittest.main()
