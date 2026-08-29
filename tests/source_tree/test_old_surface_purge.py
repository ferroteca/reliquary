# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The old script syntax and retired CLI names do not survive anywhere live.

Milestone 4 task 11: a sweep of the whole tree. Historical records
(released CHANGELOG entries, DECISIONS, completed milestone notes) and
fixtures that deliberately test the old forms are allowed to still spell
them. Live code, tests, user docs, and shipped scripts are not.
"""

import io
import os
import re
import warnings
from contextlib import redirect_stderr, redirect_stdout

import pytest

import reliquary
from reliquary import document, json5reader
from reliquary import cli
from reliquary.script_nodes import ScriptParseError
from reliquary.script_parser import parse_script


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

# Retired CLI command words (exact argv tokens).
_OLD_CLI_COMMANDS = frozenset({
    "script", "keys", "menu", "text", "create", "destroy",
    "start", "stop", "list", "check-script",
    # The search family. Retired when each noun became a single
    # listing command instead: one listing per noun, with filtering
    # left to the shell and to --json (D88). `search-scripts` and
    # `search-media` never actually shipped, and are retired without
    # ever having been built — neither name is planned.
    "search-blueprints", "search-scripts", "search-media",
    # The drive report and the in-band file-transfer commands. Retired
    # once a machine's file content stopped being reliquary's concern
    # (D108). Reliquary declares a machine's drives and swaps their
    # media; what's inside a volume belongs to the caller, so there's
    # no drive letter to report and no file path to address.
    "describe-drives", "refresh-drives",
    "put-file", "get-file", "put-files", "get-files", "list-files",
})

# Retired public API names.
_OLD_API_NAMES = (
    "create_from_blueprint",
    "start_cached_machine",
    "stop_cached_machine",
    "final_state",
    "ExpectBranch",
    "State",
    "EmbeddedMedia",
    # The check family. Retired once `--dry-run` became the one way
    # to say "evaluate without doing" (F25). `check_key` went with
    # them: a public function that only checked a string, with no CLI
    # command of its own, was a leftover that violated P6, and this
    # cleanup removed it.
    "check_script",
    "ScriptCheck",
    "check_key",
    # The old two-directory model and the asset-root setting. Retired
    # once all six working directories became independently placeable.
    # `set_home` and `set_cache` are the old names for `set_home_dir`
    # and `set_cache_dir`. `set_assets` / `HOME_ASSETS` used to answer
    # two questions at once — where to put things, and whether to stay
    # hermetic — and the "where" half is now just the directory flags.
    # The "hermetic" half became `autoseed`, which D88 removed outright
    # rather than giving it a default: nothing resolves outside the
    # codex any more, so there's no longer a setting to have.
    "set_home",
    "set_cache",
    "set_assets",
    "HOME_ASSETS",
    "media_cache_dir",
    "machines_cache_dir",
    "set_autoseed",
    "autoseed",
    # The search family's API half, plus the codex-only listing that
    # the `--builtin` flag used to reach (D88). `search_blueprints`
    # covered two different sets of results through one function;
    # `list_builtin_media` listed components that can't be seeded on
    # their own anyway.
    "search_blueprints",
    "list_builtin_media",
    # The old module-level state. Retired once the session object
    # became the only way to talk to reliquary (P26). The directory
    # globals' setter functions, the environment-variable adoption,
    # and the "is this assigned" check are gone outright. The
    # resolvers, the directory-name vocabulary, the Documents lookup,
    # and the engine functions that had no session-method equivalent
    # also left the package root. (Every session method that does have
    # a same-named function at the package root is already checked
    # mechanically by test_command_manifest.py — a stray root-level
    # copy would show up there as an unclassified public name — so
    # those are not repeated in this list.)
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

# Live-tree paths scanned for retired spellings.
_SWEEP_ROOTS = (
    os.path.join("src", "reliquary"),
    "tests",
    "docs",
    "README.md",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "USE-CASES.md",
)

# Files allowed to quote the old surface on purpose.
_ALLOW_PATH_SUFFIXES = (
    # Negative tests: they check that the old spellings fail to parse.
    os.path.join("tests", "test_script_parser.py"),
    os.path.join("tests", "test_script_validation.py"),
    # Same reason: it checks that the retired `check-script` command
    # is gone, and it can't do that without naming it.
    os.path.join("tests", "test_dry_run.py"),
    # Same reason again, for D88's retirements. Each of these files
    # checks that a removed spelling stays removed — `--builtin`
    # rejected by the parser, `set_autoseed` absent from `home`, the
    # docs-coverage check's own record of commands that used to be
    # documented and no longer are — none of which can be written
    # without naming the thing that's gone.
    os.path.join("tests", "test_cli.py"),
    os.path.join("tests", "test_home.py"),
    os.path.join("tests", "test_library.py"),
    # This module itself names the forbidden spellings.
    os.path.join("tests", "source_tree", "test_old_surface_purge.py"),
    # The API spec's realignment section records a completed rename
    # and names the old spellings it replaced. That's historical
    # prose, not a surface anyone can actually reach: the names it
    # quotes are exactly the ones this module forbids, which is the
    # whole point of quoting them there.
    os.path.join("docs", "spec", "api.md"),
)

# Patterns that would mean live use of the old surface or a retired
# command. Each entry is (label, compiled regex).
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
    # D88's retirements. The word "autoseeding" is still allowed in
    # prose that records the deletion; the flag and the function are
    # not allowed anywhere live.
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
    # The pre-F22 directory flags and functions. Each pattern is
    # written to exclude the new spelling that contains it as a
    # substring, so `--home-dir` and `set_home_dir` pass while
    # `--home` and `set_home` do not.
    ("old --home flag", re.compile(r"--home(?!-dir)\b")),
    ("old --cache flag", re.compile(r"--cache(?!-dir)\b")),
    ("retired --assets flag", re.compile(r"--assets\b")),
    ("old set_home", re.compile(r"\bset_home(?!_dir)\b")),
    ("old set_cache", re.compile(r"\bset_cache(?!_dir)\b")),
    # P26's retirements: the old module-level state's spellings. The
    # `--*-dir` flags and the Context keywords are still allowed; the
    # setter functions and the environment-variable adoption are not.
    ("retired set_*_dir setter",
     re.compile(r"\bset_(?:home|blueprints|scripts|cache|media"
                r"|machines)_dir\b")),
    ("retired adopt_environment",
     re.compile(r"\badopt_environment\b")),
    ("retired set_assets", re.compile(r"\bset_assets\b")),
    ("retired HOME_ASSETS", re.compile(r"\bHOME_ASSETS\b")),
    ("old media_cache_dir", re.compile(r"\bmedia_cache_dir\b")),
    ("old machines_cache_dir", re.compile(r"\bmachines_cache_dir\b")),
)


def _allowed(path):
    rel = os.path.relpath(path, _REPO_ROOT)
    return any(rel.endswith(suffix) or rel == suffix
               for suffix in _ALLOW_PATH_SUFFIXES)


# Labels for patterns that match a *script statement* by anchoring to
# the start of a line. In markdown, these must only be checked inside
# fenced code blocks: prose text wraps across lines, and a sentence
# that happens to continue onto a new line starting with "boot order
# with the listed drive keys" is not actually the retired `boot` verb.
# The identifier patterns (not listed here) are still checked against
# the whole file, fenced or not.
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
        if not os.path.exists(path):
            # `os.walk` on a missing directory just yields nothing, so
            # a root that stopped existing would silently shrink the
            # sweep and still report success. This module only ever
            # runs from the repository itself (`tests/source_tree`),
            # where every root listed above is present.
            raise AssertionError(
                "sweep root %s does not exist; this module runs from "
                "the repository only" % root)
        if os.path.isfile(path):
            yield path
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [name for name in dirnames
                           if name not in {".venv", "__pycache__",
                                           "codex"}]
            # The package's codex scripts are shipped too — they're
            # walked explicitly below.
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


# The `.rlqm` media-definition file kind is retired everywhere in the
# tree.
#
# Media was folded into the composed `.rlqb` blueprint format in the
# 2026-07-23 media/composition round, so no `.rlqm` file should survive
# anywhere — not in the package, the shipped codex, the examples, or
# the fixtures. The word "rlqm" can still appear in historical records
# (CHANGELOG, DECISIONS, completed milestone notes) and in design prose
# that names the retired format by name — this check only guards
# against the actual *files* surviving, not the word.

_SKIP_DIRS = {".venv", ".git", "__pycache__", "build", "dist"}


def test_no_rlqm_files_survive():
    survivors = []
    for dirpath, dirnames, filenames in os.walk(_REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            if name.endswith(".rlqm"):
                survivors.append(
                    os.path.relpath(os.path.join(dirpath, name),
                                    _REPO_ROOT))
    assert survivors == [], (
        "the .rlqm media-definition file kind is retired; "
        "these files must be removed:\n" + "\n".join(survivors))


def test_no_authored_document_uses_the_retired_shape():
    """No authored file still uses the original four-component model.

    The plural root sections and the `source` / `archive` spec types
    were superseded by D22 before any of them ever shipped in an
    authored document. Every `.rlqb` file the repository carries —
    in the codex, the examples, the conformance corpus — follows the
    revised model, and the parser is what proves it: a leftover file
    using the old shape would fail to parse instead of silently being
    read as something else.
    """
    stale = []
    for dirpath, dirnames, filenames in os.walk(_REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        if os.path.basename(dirpath) == "invalid":
            continue  # fixtures that must fail, by design
        for name in filenames:
            if not name.endswith(".rlqb"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8") as handle:
                raw = json5reader.load(handle)
            if isinstance(raw, dict) and (
                    {"machines", "sources", "archives"} & set(raw)):
                stale.append(os.path.relpath(path, _REPO_ROOT))
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", document.BlueprintWarning)
                document.parse_document(raw)
    assert stale == [], (
        "these authored blueprints still use the retired "
        "four-component shape:\n" + "\n".join(stale))


# Retired package exports are gone entirely, not kept as aliases.

def test_old_api_names_absent():
    for name in _OLD_API_NAMES:
        assert not hasattr(reliquary, name), (
            f"reliquary still exports superseded name {name!r}")
        assert name not in reliquary.__all__


# Retired CLI command words are not registered.

def _registered_commands():
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            cli.main(["--help"])
        except SystemExit:
            pass
    help_text = stdout.getvalue() + stderr.getvalue()
    match = re.search(r"\{([^}]+)\}", help_text)
    assert match is not None, "cli --help lists no commands"
    return {part.strip() for part in match.group(1).split(",")}


def test_old_cli_commands_absent():
    survivors = sorted(_OLD_CLI_COMMANDS & _registered_commands())
    assert survivors == [], (
        f"superseded CLI commands still registered: {survivors}")


def test_the_record_management_family_is_absent():
    # D36: persistence moved to the asynchronous-runs backlog, and
    # the commands that managed it were removed along with it. There
    # is no compatibility shim for them.
    backlogged = {"list-runs", "run", "begin-run", "end-run"}
    survivors = sorted(backlogged & _registered_commands())
    assert survivors == [], (
        f"backlogged record commands still registered: {survivors}")


# A run returns its output directly and stores nothing on disk (D36).

def test_the_run_directory_helpers_are_gone():
    from reliquary import script_runner
    for name in ("_create_run_dir", "_start_transcript"):
        assert not hasattr(script_runner, name), (
            f"script_runner still carries {name!r}")


def test_the_run_result_carries_no_stored_location():
    fields = {field.name for field
              in reliquary.ScriptRun.__dataclass_fields__.values()}
    assert "run_dir" not in fields
    assert "events" in fields


# Scripts written in the old syntax are rejected outright — there is
# no compatibility bridge. Each old spelling gets its own test node,
# so if one of them stopped being rejected, the failing node would
# name exactly which one.

@pytest.mark.parametrize("source", [
    "platform dos\nstate ready {\n done\n}\n",
    "platform dos\nentry a\nphase a {\n    -> b\n}\n",
    "platform dos\nentry a\nphase a {\n    done\n}\n",
    'platform dos\nexpect "x" {\n}\n',
    'platform dos\nwait regex "x"\n',
    "platform dos\nwait stopped\n",
    "platform dos\nboot hdd0\n",
    'platform dos\ntype "A:" <enter>\n',
], ids=["state", "arrow", "done", "expect", "regex-keyword",
        "bare-stopped", "boot-verb", "key-token"])
def test_an_old_surface_sample_does_not_parse(source):
    with pytest.raises(ScriptParseError):
        parse_script(source)


# No live file keeps a retired spelling.

def test_live_tree_has_no_superseded_spellings():
    hits = []
    for path in _iter_sweep_files():
        if _allowed(path):
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except UnicodeDecodeError:
            continue
        # Python string and comment bodies that only appear as source
        # text inside the allowlisted negative tests are already
        # handled by the path allowlist above, so they aren't
        # special-cased again here.
        relative = os.path.relpath(path, _REPO_ROOT)
        fenced = _fenced_only(text) if path.endswith(".md") else text
        for label, pattern in _FORBIDDEN:
            haystack = (fenced if label in _SCRIPT_STATEMENT_LABELS
                        else text)
            for match in pattern.finditer(haystack):
                line = text.count("\n", 0, match.start()) + 1
                hits.append(
                    f"{relative}:{line}: {label}: {match.group(0)!r}")
    assert hits == [], (
        "superseded spellings survive in the live tree:\n"
        + "\n".join(hits))
