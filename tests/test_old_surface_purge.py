# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The old script surface and superseded CLI names do not survive.

Milestone 4 task 11: a whole-tree sweep. Historical records
(released CHANGELOG, DECISIONS, completed milestone notes) and
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
    "start", "stop", "list", "check-script",
    # The search family, retired when the noun became the set: a
    # listing per noun, and filtering left to the shell and to --json
    # (D88). `search-scripts` and `search-media` never shipped and
    # are retired unbuilt, so neither is planned under either name.
    "search-blueprints", "search-scripts", "search-media",
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
    # The check family, retired when `--dry-run` became the one
    # spelling of "evaluate without doing" (F25). `check_key` went
    # with them: a public predicate on a string with no CLI twin was
    # a standing P6 residue, and privacy closed it.
    "check_script",
    "ScriptCheck",
    "check_key",
    # The two-directory model and the asset-root knob, retired when
    # all six working directories became placeable. `set_home` and
    # `set_cache` are the old spellings of `set_home_dir` /
    # `set_cache_dir`; `set_assets` / `HOME_ASSETS` answered
    # placement and hermeticity with one word, and the placement half
    # is now the directory flags. The hermeticity half became
    # `autoseed`, which D88 deleted outright rather than defaulting:
    # nothing resolves out of the codex, so there is no axis to set.
    "set_home",
    "set_cache",
    "set_assets",
    "HOME_ASSETS",
    "media_cache_dir",
    "machines_cache_dir",
    "set_autoseed",
    "autoseed",
    # The search family's API half, and the codex-mode listing the
    # `--builtin` flag reached (D88). `search_blueprints` spanned two
    # sets in one verb; `list_builtin_media` enumerated components
    # that cannot be seeded on their own.
    "search_blueprints",
    "list_builtin_media",
    # The module-level carrier, retired when the session became the
    # only door (P26). The directory globals' setters, the
    # environment adoption and the assignment probe are deleted
    # outright; the resolvers, the directory vocabulary, the
    # Documents lookup and the non-twin engine doors left the
    # package root (every session-method twin's root spelling is
    # policed mechanically by test_command_manifest.py — a root
    # twin would be an unclassified public name — so the twins
    # are not repeated here).
    "set_home_dir",
    "set_blueprints_dir",
    "set_scripts_dir",
    "set_cache_dir",
    "set_media_dir",
    "set_machines_dir",
    "adopt_environment",
    "is_assigned",
    "home_dir",
    "blueprints_dir",
    "scripts_dir",
    "cache_dir",
    "media_dir",
    "machines_dir",
    "DIRECTORIES",
    "documents_dir",
    "create",
    "execute_script",
    "load_namespace",
    "bind_properties",
    "describe_sources",
    "resolve_machine",
    "load_machine_state",
    "machine_dir_path",
    "mark_stopped",
    "has_credential",
)

# Live-tree paths scanned for superseded spellings.
_SWEEP_ROOTS = (
    os.path.join("src", "reliquary"),
    "tests",
    "docs",
    "README.md",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "USE-CASES.md",
)

# Files that may quote the old surface deliberately.
_ALLOW_PATH_SUFFIXES = (
    # Negative tests: old spellings must fail to parse.
    os.path.join("tests", "test_script_parser.py"),
    os.path.join("tests", "test_script_validation.py"),
    # Same rationale: it asserts the retired `check-script` command
    # is gone, which it cannot do without naming it.
    os.path.join("tests", "test_dry_run.py"),
    # And the same again for D88's retirements. Each of these asserts
    # a deleted spelling stays deleted — `--builtin` refused by the
    # parser, `set_autoseed` absent from `home`, the docs-coverage
    # check's own record of commands once specified and absent — none
    # of which can be written without naming what is gone.
    os.path.join("tests", "test_cli.py"),
    os.path.join("tests", "test_home.py"),
    os.path.join("tests", "test_library.py"),
    # This module names the forbidden spellings.
    os.path.join("tests", "test_old_surface_purge.py"),
    # The API spec's realignment section records a completed rename
    # and names the spellings it replaced. Historical prose, not a
    # surface anyone can reach: the names it quotes are exactly the
    # ones this module forbids, which is the point of quoting them.
    os.path.join("docs", "spec", "api.md"),
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
    ("check_script",
     re.compile(r"\bcheck_script\b")),
    ("ScriptCheck",
     re.compile(r"\bScriptCheck\b")),
    ("public check_key",
     re.compile(r"(?<!_)\bcheck_key\b")),
    ("rlq check-script",
     re.compile(r"\bcheck-script\b")),
    # D88's retirements. The word "autoseeding" survives in prose that
    # records the deletion; the flag and the function may not.
    ("--autoseed flag",
     re.compile(r"--(?:no-)?autoseed\b")),
    ("set_autoseed",
     re.compile(r"\bset_autoseed\b")),
    ("Context(autoseed=)",
     re.compile(r"\bautoseed\s*=")),
    ("--builtin flag",
     re.compile(r"--builtin\b")),
    ("list_builtin_media",
     re.compile(r"\blist_builtin_media\b")),
    ("rlq search-blueprints",
     re.compile(r"\bsearch[-_]blueprints\b")),
    ("search-scripts / search-media",
     re.compile(r"\bsearch[-_](?:scripts|media)\b")),
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
    # The pre-F22 directory surface. Each pattern excludes the new
    # spelling that contains it, so `--home-dir` and `set_home_dir`
    # read clean while `--home` and `set_home` do not.
    ("old --home flag", re.compile(r"--home(?!-dir)\b")),
    ("old --cache flag", re.compile(r"--cache(?!-dir)\b")),
    ("retired --assets flag", re.compile(r"--assets\b")),
    ("old set_home", re.compile(r"\bset_home(?!_dir)\b")),
    ("old set_cache", re.compile(r"\bset_cache(?!_dir)\b")),
    # P26's retirements: the module-level carrier's spellings. The
    # `--*-dir` flags and the Context keywords survive; the setter
    # functions and the environment adoption do not.
    ("retired set_*_dir setter",
     re.compile(r"\bset_(?:home|blueprints|scripts|cache|media"
                r"|machines)_dir\b")),
    ("retired adopt_environment",
     re.compile(r"\badopt_environment\b")),
    ("retired set_assets", re.compile(r"\bset_assets\b")),
    ("retired HOME_ASSETS", re.compile(r"\bHOME_ASSETS\b")),
    ("old media_cache_dir", re.compile(r"\bmedia_cache_dir\b")),
    ("old machines_cache_dir", re.compile(r"\bmachines_cache_dir\b")),
    ("old RELIQUARY_HOME", re.compile(r"\bRELIQUARY_HOME(?!_DIR)\b")),
)


def _allowed(path):
    rel = os.path.relpath(path, _REPO_ROOT)
    return any(rel.endswith(suffix) or rel == suffix
               for suffix in _ALLOW_PATH_SUFFIXES)


# Patterns that match a *script statement* by anchoring to the start
# of a line. In markdown they must be applied only inside fenced code
# blocks: prose wraps, and a sentence continuing onto a line that
# happens to begin "boot order with the listed drive keys" is not the
# retired `boot` verb. Identifier patterns stay whole-file.
_SCRIPT_STATEMENT_LABELS = frozenset({
    "old state keyword",
    "old arrow goto",
    "old done terminator",
    "old expect",
    "bare wait stopped",
    "old boot verb",
})


def _fenced_only(text):
    """Blank every line outside a fenced block, keeping line numbers."""
    kept = []
    inside = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            inside = not inside
            kept.append("")
            continue
        kept.append(line if inside else "")
    return "\n".join(kept)


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
    codex = os.path.join(_REPO_ROOT, "src", "reliquary", "codex")
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
    DECISIONS, completed milestone notes) and design prose that names the
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

    def test_no_authored_document_uses_the_retired_shape(self):
        """The first-round four-component model leaves no authored file.

        The plural root sections and the `source` / `archive` spec
        types were superseded by D22 before any of them shipped in an
        authored document. Every `.rlqb` the repository carries — the
        codex, the examples, the conformance corpus — speaks the
        revised model, and the parser is what proves it: a survivor
        would fail to parse rather than quietly mean something else.
        """
        import warnings

        from reliquary import document, jsonc

        skip_dirs = {".venv", ".git", "__pycache__", "build", "dist"}
        stale = []
        for dirpath, dirnames, filenames in os.walk(_REPO_ROOT):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            if os.path.basename(dirpath) == "invalid":
                continue  # fixtures that must fail, by design
            for name in filenames:
                if not name.endswith(".rlqb"):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as handle:
                    raw = jsonc.load(handle)
                if isinstance(raw, dict) and (
                        {"machines", "sources", "archives"} & set(raw)):
                    stale.append(os.path.relpath(path, _REPO_ROOT))
                    continue
                with warnings.catch_warnings():
                    warnings.simplefilter(
                        "ignore", document.BlueprintWarning)
                    document.parse_document(raw)
        self.assertEqual(
            stale, [],
            "these authored blueprints still use the retired "
            "four-component shape:\n" + "\n".join(stale))


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

    def _commands(self):
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
        return {part.strip() for part in match.group(1).split(",")}

    def test_old_cli_commands_absent(self):
        survivors = sorted(_OLD_CLI_COMMANDS & self._commands())
        self.assertEqual(
            survivors, [],
            f"superseded CLI commands still registered: {survivors}")

    def test_the_record_management_family_is_absent(self):
        # D36: persistence went to the asynchronous-runs backlog, and
        # the verbs that managed it went with it. No shims.
        backlogged = {"list-runs", "run", "begin-run", "end-run"}
        survivors = sorted(backlogged & self._commands())
        self.assertEqual(
            survivors, [],
            f"backlogged record commands still registered: {survivors}")


class RunPersistenceAbsentTests(unittest.TestCase):
    """The run returns its output and stores nothing (D36)."""

    def test_the_run_directory_helpers_are_gone(self):
        from reliquary import script_runner
        for name in ("_create_run_dir", "_start_transcript"):
            self.assertFalse(
                hasattr(script_runner, name),
                f"script_runner still carries {name!r}")

    def test_the_run_result_carries_no_stored_location(self):
        self.assertNotIn(
            "run_dir",
            {field.name for field
             in reliquary.ScriptRun.__dataclass_fields__.values()})
        self.assertIn(
            "events",
            {field.name for field
             in reliquary.ScriptRun.__dataclass_fields__.values()})


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
            fenced = _fenced_only(text) if path.endswith(".md") else text
            for label, pattern in _FORBIDDEN:
                haystack = (fenced if label in _SCRIPT_STATEMENT_LABELS
                            else text)
                for match in pattern.finditer(haystack):
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
