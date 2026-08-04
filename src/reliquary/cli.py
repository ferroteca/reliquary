# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Command-line parsing and dispatch."""

import argparse
import dataclasses
import getpass
import importlib.metadata
import json
import os
import sys
import textwrap
import traceback

try:
    _version = importlib.metadata.version("reliquary")
except importlib.metadata.PackageNotFoundError:
    _version = "unknown"

from .machine import (Machine, cursor_menu_select, screen_text,
                      screenshot, send_keys, send_text, wait_text)
from .home import (Context, DIRECTORIES, default_home_dir,
                   environment_variable)
# The codex family and the locate seam are the CLI's own (D87): no
# session veneer exists for them, so they take the invocation's
# Context directly.
from .library import (list_codex, locate_script, seed_blueprint,
                      seed_script)
from .errors import (PreflightError, ReliquaryError, StaticError,
                     UNEXPECTED, exit_code)
from .machines import read_vm_state, split_machine_id
from .credentials import CredentialError
from .progress import MODES as _PROGRESS_MODES
from .properties import is_secret
from .script_runner import _resolve_key
from .script_nodes import ScriptParseError
from .script_parser import load_script
from .session import Session


# Command words recognised when rewriting leading flags so that
# ``rlq --home-dir X list-machines`` and ``rlq list-machines --home-dir X``
# are identical without a parent-parser SUPPRESS twin.
_COMMANDS = frozenset({
    "create-machine", "start-machine", "stop-machine",
    "destroy-machine", "recreate-machine", "apply-blueprint",
    "get-machine-dir",
    "run-script", "fetch-media",
    "seed-blueprint", "seed-script", "new-blueprint",
    "delete-blueprint", "delete-script",
    "get-property", "set-property", "unset-property",
    "list-properties", "list-blueprints", "list-codex",
    "list-machines", "list-scripts", "list-media",
    "clean-media", "prune-media", "add-media",
    "insert-media", "eject-media", "set-boot-order",
    "get-machine-var", "wait-machine-var",
    "describe-drives", "refresh-drives",
    "put-file", "get-file",
    "list-files", "put-files", "get-files",
    "type", "enter", "press", "exec", "select", "screen", "wait",
    "screenshot", "hmp",
})

# Arity of every flag that may appear before the command word.
# Unknown leading tokens are left in place for argparse to reject.
_FLAG_ARITY = {
    "--home-dir": 1,
    "--blueprints-dir": 1,
    "--scripts-dir": 1,
    "--cache-dir": 1,
    "--media-dir": 1,
    "--machines-dir": 1,
    "--blueprint": 1,
    "--machine": 1,
    "--platform": 1,
    "--timeout": 1,
    "--interval": 1,
    "--display": 0,
    "--check": 0,
    "--secret": 0,
    "--json": 0,
    "--only": 0,
    "--name": 1,
    "--exclude": 1,
    "--property": 1,
    "--properties": 1,
    "--progress": 1,
    "--file": 1,
    "--dry-run": 0,
    "--backend": 1,
}


def _reorder_argv(argv):
    """Move leading flags to after the command word.

    Flags are declared once on each subparser; this rewrite makes
    position carry no meaning so the parent-parser SUPPRESS twin is
    unnecessary.

    An *unknown* leading flag has no arity to skip by, so its value
    (if it takes one) is an ordinary bare word. Stopping there would
    hand argparse the value as the command word and produce
    ``invalid choice: 'foo'`` — blaming the value and never naming
    the flag that is actually wrong. Once an unknown flag has been
    seen the scan therefore keeps looking for a real command word,
    so the reorder still happens and the subparser reports
    ``unrecognized arguments: --qemu foo``. The invocation is an
    error either way; this only decides which error it gets, and
    naming the unknown flag is the useful one. A bare word before
    any unknown flag still stops the scan, so a plain misspelled
    command is still reported as the invalid choice it is.
    """
    if not argv:
        return argv
    index = 0
    after_unknown = False
    while index < len(argv):
        arg = argv[index]
        if arg == "--":
            break
        if arg.startswith("-"):
            name, eq, _ = arg.partition("=")
            arity = _FLAG_ARITY.get(name)
            if arity is None:
                after_unknown = True
                index += 1
                continue
            if eq:
                index += 1
            else:
                index += 1 + arity
            continue
        if arg in _COMMANDS:
            if index == 0:
                return list(argv)
            leading = list(argv[:index])
            rest = list(argv[index:])
            return rest[:1] + leading + rest[1:]
        if after_unknown:
            index += 1          # the unknown flag's value; keep looking
            continue
        break
    return list(argv)


def _require_machine_selector(arguments, session):
    """Return a resolved machine id from selectors.

    Resolution runs through the invocation's session — the record
    built from the ``--*-dir`` flags, the environment, and the
    default home in main() — never through the process globals,
    which the CLI no longer drives (P26).
    """
    if not getattr(arguments, "blueprint", None) and not getattr(
            arguments, "machine", None):
        raise StaticError(
            "select a machine with --blueprint or --machine",
            rule_id="machine.no-selector")
    return session.resolve_machine(
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None),
    )


def _interaction_target(arguments, session):
    """Resolve the machine directory a guest-console command drives.

    The directory is the whole address: it is where the machine's
    recorded VM identity lives, and the adapter named there supplies
    the endpoint and verifies it. There is no port to pass — that is
    QEMU's own detail, on the far side of the adapter seam.
    """
    machine_id = _require_machine_selector(arguments, session)
    state = session.load_machine_state(machine_id)
    if state.get("phase") != "running":
        raise PreflightError(
            f"machine {machine_id} is not running "
            f"(phase: {state.get('phase')})",
            rule_id="machine.not-running")
    machine_home = session.machine_dir_path(machine_id)
    if read_vm_state(machine_home) is None:
        raise PreflightError(
            f"machine {machine_id} is running but has no "
            "recorded VM identity",
            rule_id="machine.no-vm-identity")
    return machine_home


# Every command takes the six directory flags, mirroring the API's
# shared keywords. Each names one working directory; the ones left
# unnamed derive (home.py), so `--home-dir` alone still places all
# six and a bare invocation places them under the default home.
_DIRECTORY_HELP = {
    "home": "reliquary home directory "
            "(default: Documents/reliquary)",
    "blueprints": "machine blueprints (default: <home>/blueprints)",
    "scripts": "automation scripts (default: <home>/scripts)",
    "cache": "regenerable cache root (default: <home>/cache)",
    "media": "cached media payloads (default: <cache>/media)",
    "machines": "machine materializations (default: <cache>/machines)",
}


def _add_home(parser):
    for name in DIRECTORIES:
        parser.add_argument(
            "--%s-dir" % name, default=None, metavar="PATH",
            dest="%s_dir" % name, help=_DIRECTORY_HELP[name])
    parser.add_argument(
        "--json", action="store_true",
        help="print the command's result as one JSON document")
    return parser


def _invocation_context(arguments):
    """Build the one Context this invocation opens its session on.

    The order is the precedence: flags, then the environment for what
    no flag named, then the default home for what neither did. That
    last step is what makes the fail-closed error unreachable at the
    keyboard — one home assignment reaches all six through derivation
    — and it happens whenever the home is still unnamed, not only
    when nothing at all was given, so ``rlq --cache-dir D:\\c
    list-machines`` keeps working with an explicit cache over a
    defaulted home.

    Honouring the environment is the CLI's private construction step,
    never the library's: a program embedding Reliquary gets none of
    it unless it asks (home.py). The selected properties file rides
    in the same record (P26's cargo): ``--properties``, else
    ``RELIQUARY_PROPERTIES``, else the home's file by way of an
    empty slot.
    """
    slots = {}
    for name in DIRECTORIES:
        value = getattr(arguments, "%s_dir" % name, None)
        if not value:
            value = os.environ.get(environment_variable(name))
        # ``RELIQUARY_HOME`` is the documented spelling. Accept the
        # former mechanical spelling for existing CLI users only when
        # the primary spelling is absent.
        if not value and name == "home":
            value = os.environ.get("RELIQUARY_HOME_DIR")
        if value:
            slots["%s_dir" % name] = value
    defaulted = "home_dir" not in slots
    if defaulted:
        slots["home_dir"] = default_home_dir()
    properties_file = (getattr(arguments, "properties", None)
                       or os.environ.get("RELIQUARY_PROPERTIES") or None)
    context = Context(properties_file=properties_file, **slots)
    if defaulted:
        _narrate(f"using reliquary home: {context.home_dir}")
    return context


def _add_properties_file(parser):
    """The properties file a command maintains, replacing the home's."""
    parser.add_argument(
        "--properties", default=None, metavar="PATH",
        help="properties file to use instead of the home's "
             "(secrets scope to this path)")
    return parser


def _add_property_inputs(parser):
    """Property binding inputs for a run: --property and --properties."""
    parser.add_argument(
        "--property", action="append", default=None, metavar="KEY=VALUE",
        dest="property", help="bind a declared property (repeatable); "
        "never a secret -- argv is not a credential store")
    _add_properties_file(parser)
    return parser


def _explicit_properties(arguments):
    """Parse repeated --property KEY=VALUE into a mapping, or None."""
    pairs = getattr(arguments, "property", None)
    if not pairs:
        return None
    explicit = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise StaticError(
                f"--property expects KEY=VALUE, got: {pair!r}",
                rule_id="prop.flag-not-key-value")
        key = key.strip()
        if key in explicit:
            raise StaticError(
                f"--property {key} given more than once",
                rule_id="prop.flag-repeated")
        explicit[key] = value
    return explicit


def _expectations(arguments):
    """Parse repeated --expect KEY=VALUE into a mapping, or None.

    The same spelling as ``--property``, deliberately: one shape for
    "a key and a value on the command line" rather than a second
    mini-format for a reader to learn.
    """
    pairs = getattr(arguments, "expect", None)
    if not pairs:
        return None
    expected = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise StaticError(
                f"--expect expects KEY=VALUE, got: {pair!r}",
                rule_id="prop.flag-not-key-value")
        key = key.strip()
        if key in expected:
            raise StaticError(
                f"--expect {key} given more than once",
                rule_id="prop.flag-repeated")
        expected[key] = value
    return expected


def _emit(arguments, value, render):
    """Render a command result as JSON or human text.

    Under ``--json`` the twin's return ``value`` is printed as one
    JSON document on stdout (a void twin passes ``{}``); otherwise
    ``render()`` prints the human form. Returns exit code 0.

    The output discipline (docs/spec/cli.md): a result-bearing
    command's pretty stdout is exactly the human rendering of what
    its twin returns — the same value ``--json`` serializes — so it
    pipes clean with no flags. Narration around it, and every line of
    a void twin, belongs on stderr.
    """
    if getattr(arguments, "json", False):
        print(json.dumps(value, default=str))
    else:
        render()
    return 0


def _narrate(message):
    """Print narration — never a result — on stderr."""
    print(f"rlq: {message}", file=sys.stderr)


def _reject_stream_json(arguments, command):
    """Stream-bearing commands reject ``--json`` (they are event streams)."""
    if getattr(arguments, "json", False):
        raise StaticError(
            f"{command} is a stream, not a document; use "
            "--progress jsonl for machine-readable output",
            rule_id="progress.document-on-a-stream")


def _add_progress(parser):
    """The rendering selector on a stream-bearing command."""
    parser.add_argument(
        "--progress", choices=_PROGRESS_MODES, default="auto",
        help="live rendering: auto (tty detection), pretty, plain, or "
             "jsonl (the event stream on stdout, nothing else)")
    return parser


def _add_selectors(parser):
    _add_home(parser)
    parser.add_argument(
        "--blueprint", default=None,
        help="select a blueprint's sole machine")
    parser.add_argument(
        "--machine", default=None,
        help="select a machine by full id (<blueprint>-<n>)")
    return parser


_PROG_NAMES = ("rlq", "reliquary")


def _prog_name():
    """The invoked console-script name, falling back to ``rlq``.

    Both ``rlq`` and ``reliquary`` are registered entry points for
    the same command; help/usage text should reflect whichever the
    user actually typed rather than always naming one of them.
    """
    stem = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    return stem if stem in _PROG_NAMES else "rlq"


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = _reorder_argv(list(argv))

    parser = argparse.ArgumentParser(
        prog=_prog_name(),
        description="OS installation scripting over QEMU guest "
                    "automation (DOS by default)")
    parser.add_argument(
        "--version", action="version",
        version="%(prog)s " + _version)

    subcommands = parser.add_subparsers(dest="command", required=True)

    # create-machine
    command = subcommands.add_parser(
        "create-machine",
        help="materialize a machine from a blueprint")
    _add_home(command)
    _add_property_inputs(command)
    command.add_argument(
        "--blueprint", required=True,
        help="blueprint to materialize")
    command.add_argument(
        "--dry-run", action="store_true",
        help="report what a create would do and do none of it: "
             "nothing is seeded, fetched, locked or written")
    command.add_argument(
        "--backend", default=None,
        help="override the blueprint's backend: the named backend is "
             "pinned at assignment and must be available and capable. "
             "With --dry-run the question is whether the blueprint "
             "would work *there* — its capability decides and it "
             "need not be installed here, so absence is reported "
             "rather than raised")

    # start-machine
    command = subcommands.add_parser(
        "start-machine", help="start a machine")
    _add_selectors(command)
    command.add_argument("--display", action="store_true")

    # stop-machine
    command = subcommands.add_parser(
        "stop-machine", help="stop a machine")
    _add_selectors(command)

    # destroy-machine
    command = subcommands.add_parser(
        "destroy-machine", help="delete a stopped machine")
    _add_selectors(command)

    # recreate-machine
    command = subcommands.add_parser(
        "recreate-machine",
        help="destroy and recreate a machine under the same id")
    _add_selectors(command)
    _add_property_inputs(command)

    # apply-blueprint
    command = subcommands.add_parser(
        "apply-blueprint",
        help="adopt blueprint edits into a stopped machine")
    _add_selectors(command)
    _add_property_inputs(command)

    # get-machine-dir
    command = subcommands.add_parser(
        "get-machine-dir",
        help="print a machine's cache directory (out-of-band door)")
    _add_selectors(command)

    # run-script
    command = subcommands.add_parser(
        "run-script",
        help="run a labeled .rlqs script against a machine, streaming "
             "its progress and returning its output",
        # RawDescriptionHelpFormatter keeps these line breaks and adds
        # none, so the wrapping is written here rather than left to
        # argparse -- which would otherwise reflow the paragraphs into
        # single unreadable lines.
        description=(
            "Run a .rlqs script against a machine, streaming its\n"
            "progress and returning its output.\n"
            "\n"
            "LABEL is a name in the blueprint's `scripts` map, or a\n"
            "script's filename stem. The machine comes from --machine,\n"
            "or from --blueprint when that blueprint has exactly one\n"
            "machine; with --blueprint and no machine yet, one is\n"
            "created.\n"
            "\n"
            "Before the first guest input the script is checked from\n"
            "its text, the media and drives it names are resolved, and\n"
            "its declared properties are bound -- so a run never gets\n"
            "halfway before discovering a later statement is\n"
            "impossible. The machine is then brought to the state the\n"
            "script's `machine` header expects: a stopped machine is\n"
            "started when the script expects `running`, and a running\n"
            "one is refused when it expects `stopped`.\n"
            "\n"
            "The machine is left wherever the last executed statement\n"
            "put it, on success and on failure alike -- nothing is torn\n"
            "down implicitly, so a failed run can be inspected. The run\n"
            "stores nothing: its output is the event stream, live on\n"
            "stderr and gone when the run ends. Use --progress jsonl to\n"
            "keep it."),
        epilog=(
            "exit codes:\n"
            "  0  the script finished\n"
            "  2  the script is not legal (checked from its text)\n"
            "  3  preflight refused it (the machine, media, or "
            "properties)\n"
            "  4  the run failed (a clock expired, or a step could "
            "not be taken)\n"
            "  5  the run was cancelled at a boundary (Ctrl-C)"),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    _add_selectors(command)
    _add_property_inputs(command)
    _add_progress(command)
    command.add_argument("label", help="script label or stem")
    command.add_argument(
        "--display", action="store_true",
        help="show the backend's own display window while the script "
             "runs (input through it is invisible to reliquary)")
    command.add_argument(
        "--expect", action="append", default=None, metavar="KEY=VALUE",
        help="require the run to leave this machine variable at this "
             "value; a run that does not fails (exit 4). Repeatable")
    command.add_argument(
        "--dry-run", action="store_true",
        help="report what the run would do and run none of it: no "
             "machine is started and no statement reaches a guest. "
             "The only mode in which a selector is optional -- its "
             "presence chooses which tier is checked -- and the only "
             "one that answers to --json, a plan being a document "
             "rather than a stream")
    command.add_argument(
        "--record", default=None, metavar="PATH",
        help="record a screen transcript at PATH (.rlqt): every frame "
             "and carrier call, for debugging and corpus capture. "
             "Stops once a bound secret reaches the guest")

    # fetch-media
    command = subcommands.add_parser(
        "fetch-media", help="fetch media")
    _add_home(command)
    _add_progress(command)
    command.add_argument("name", help="media name")

    # seed-*
    for kind in ("blueprint", "script"):
        command = subcommands.add_parser(
            f"seed-{kind}",
            help=f"copy built-in {kind} to home")
        _add_home(command)
        command.add_argument("name", help=f"built-in {kind} name")
        command.add_argument(
            "--only", action="store_true",
            help="copy just this file, not its closure")

    # new-blueprint
    command = subcommands.add_parser(
        "new-blueprint", help="create new blueprint")
    _add_home(command)
    command.add_argument("name", help="blueprint name")
    command.add_argument("--platform", default=None,
                         help="guest platform")

    # delete-blueprint
    command = subcommands.add_parser(
        "delete-blueprint", help="delete a home blueprint file")
    _add_home(command)
    command.add_argument("name", help="blueprint name")

    # delete-script
    command = subcommands.add_parser(
        "delete-script", help="delete a home script file")
    _add_home(command)
    command.add_argument("name", help="script name")

    # property family
    command = subcommands.add_parser(
        "get-property", help="get a property")
    _add_home(command)
    _add_properties_file(command)
    command.add_argument("key")

    command = subcommands.add_parser(
        "set-property", help="set a property")
    _add_home(command)
    _add_properties_file(command)
    command.add_argument("key")
    command.add_argument(
        "value", nargs="?",
        help="the value (omitted with --secret, which never takes "
             "one on the command line)")
    command.add_argument(
        "--secret", action="store_true",
        help="store a secret: prompted without echo on a terminal, "
             "otherwise read from stdin")

    command = subcommands.add_parser(
        "unset-property", help="unset a property")
    _add_home(command)
    _add_properties_file(command)
    command.add_argument("key")

    command = subcommands.add_parser(
        "list-properties", help="list properties")
    _add_home(command)
    _add_properties_file(command)
    command.add_argument(
        "prefix", nargs="?",
        help="limit to this key and its dotted descendants")

    # list-*
    command = subcommands.add_parser(
        "list-blueprints", help="list your blueprint names")
    _add_home(command)

    command = subcommands.add_parser(
        "list-codex", help="list the built-in library's blueprints")
    _add_home(command)

    command = subcommands.add_parser(
        "list-machines", help="list materialized machines")
    _add_home(command)
    command.add_argument(
        "--blueprint", default=None,
        help="filter to one blueprint")

    command = subcommands.add_parser(
        "list-scripts", help="list script stems or labels")
    _add_selectors(command)

    command = subcommands.add_parser(
        "list-media", help="list your media item names")
    _add_home(command)

    # cache reclamation
    command = subcommands.add_parser(
        "clean-media", help="reclaim cached media payloads")
    _add_home(command)
    command.add_argument(
        "name", nargs="?",
        help="evict just this media (default: everything reclaimable)")

    command = subcommands.add_parser(
        "prune-media", help="drop cached payloads outside the closure")
    _add_home(command)
    command.add_argument(
        "--dry-run", action="store_true",
        help="report what would be pruned, without pruning it")

    command = subcommands.add_parser(
        "add-media", help="declare a media for a local file")
    _add_home(command)
    command.add_argument("name", help="the media name to declare")
    command.add_argument("file", help="the file it is located at")

    # state ops
    command = subcommands.add_parser(
        "insert-media", help="insert media into a drive slot")
    _add_selectors(command)
    command.add_argument("slot")
    command.add_argument(
        "media", nargs="?",
        help="a declared media name (omit with --file)")
    command.add_argument(
        "--file", default=None, metavar="PATH",
        help="mount this image in place instead: an anonymous local "
             "media, mutable and unverified, the caller's own")

    command = subcommands.add_parser(
        "eject-media", help="eject media from a drive slot")
    _add_selectors(command)
    command.add_argument("slot")

    command = subcommands.add_parser(
        "set-boot-order", help="set the machine boot order")
    _add_selectors(command)
    command.add_argument("keys", nargs="+")

    command = subcommands.add_parser(
        "get-machine-var",
        help="read a machine variable a script set")
    _add_selectors(command)
    command.add_argument("key", help="the variable's key")

    command = subcommands.add_parser(
        "wait-machine-var",
        help="wait for a machine variable another actor sets")
    _add_selectors(command)
    command.add_argument("key", help="the variable's key")
    command.add_argument(
        "value", nargs="?", default=None,
        help="the value to wait for; omitted, any value will do")
    command.add_argument("--timeout", type=float, default=None,
                         help="seconds to wait (default 120)")
    command.add_argument("--interval", type=float, default=None,
                         help="seconds between reads (default 1)")

    command = subcommands.add_parser(
        "describe-drives",
        help="report a machine's drives and what they hold")
    _add_selectors(command)

    command = subcommands.add_parser(
        "refresh-drives",
        help="re-read a stopped machine's disks into the drive record")
    _add_selectors(command)

    command = subcommands.add_parser(
        "put-file",
        help="copy a host file into a stopped machine's guest")
    _add_selectors(command)
    command.add_argument("source", help="the host file to place")
    command.add_argument(
        "destination",
        help=r"the guest address to place it at (e.g. A:\TEST.EXE)")

    command = subcommands.add_parser(
        "get-file",
        help="retrieve a file from a stopped machine's guest")
    _add_selectors(command)
    command.add_argument(
        "source", help=r"the guest address to read (e.g. A:\RESULT.TXT)")
    command.add_argument("destination", help="the host path to write")

    command = subcommands.add_parser(
        "list-files",
        help="list what a stopped machine's guest directory holds")
    _add_selectors(command)
    command.add_argument(
        "address", help=r"the guest directory to list (e.g. A:\ or A:\OUT)")
    command.add_argument(
        "--recursive", action="store_true",
        help="walk the tree instead of listing one directory level")

    command = subcommands.add_parser(
        "put-files",
        help="copy a host directory tree into a stopped machine's guest")
    _add_selectors(command)
    command.add_argument("source", help="the host directory to place")
    command.add_argument(
        "destination",
        help=r"the guest directory its contents land in (e.g. A:\)")

    command = subcommands.add_parser(
        "get-files",
        help="retrieve a directory tree from a stopped machine's guest")
    _add_selectors(command)
    command.add_argument(
        "source", help=r"the guest directory to read (e.g. A:\OUT)")
    command.add_argument(
        "destination", help="the host directory its contents land in")

    # guest-console family (script-language identity)
    command = subcommands.add_parser(
        "type", help="type text with no trailing Enter")
    _add_selectors(command)
    command.add_argument("text")

    command = subcommands.add_parser(
        "enter", help="type a line and press Enter")
    _add_selectors(command)
    command.add_argument("line")

    command = subcommands.add_parser(
        "press", help="send portable key names")
    _add_selectors(command)
    command.add_argument("names", nargs="+")

    command = subcommands.add_parser(
        "exec", help="enter a command and wait for the prompt")
    _add_selectors(command)
    command.add_argument("dos_command")
    command.add_argument("--timeout", type=int, default=None)
    command.add_argument(
        "--check", action="store_true",
        help="fail (exit 4) if the command signalled failure; the "
             "output is returned either way")

    command = subcommands.add_parser(
        "select", help="select a cursor-menu item")
    _add_selectors(command)
    command.add_argument("item")
    command.add_argument("--exclude", action="append", default=[])
    command.add_argument("--timeout", type=int, default=None)

    command = subcommands.add_parser(
        "screen", help="print the guest text screen")
    _add_selectors(command)

    command = subcommands.add_parser(
        "wait", help="wait until the screen matches a pattern")
    _add_selectors(command)
    command.add_argument("pattern")
    command.add_argument("--timeout", type=int, default=None)

    command = subcommands.add_parser(
        "screenshot", help="capture the guest framebuffer")
    _add_selectors(command)
    command.add_argument("name", nargs="?", default="screen")

    command = subcommands.add_parser(
        "hmp", help="send a QEMU human-monitor command")
    _add_selectors(command)
    command.add_argument("line")

    arguments = parser.parse_args(argv)
    context = _invocation_context(arguments)
    session = Session(context)
    try:
        try:
            return _dispatch(arguments, session, context)
        except ConnectionError as error:
            # An unreachable management endpoint is a machine rule, not
            # a fault: the command is legal and the VM is not there.
            # Converted rather than reported here, so the exit code
            # comes from the taxonomy like every other one.
            raise PreflightError(
                f"cannot reach the machine's backend: {error}\n"
                "  is the VM running? "
                "(rlq start-machine --blueprint NAME)",
                rule_id="machine.qmp-unreachable") from error
    except ReliquaryError as error:
        # The taxonomy is the exit codes: STATIC ERROR 2, PREFLIGHT
        # ERROR 3, RUN FAILURE 4, cancelled 5, an InternalError 1
        # (reliquary/errors.py). A run's own failure report already
        # reached the stream, so only the one-line diagnostic is
        # repeated here.
        print(f"rlq: {error}", file=sys.stderr)
        return exit_code(error)
    except KeyboardInterrupt:
        print("rlq: interrupted", file=sys.stderr)
        return 5
    except OSError as error:
        # The host refused something reliquary asked for correctly — a
        # permission, a full disk, a path that vanished under it. Not a
        # mistake the caller can restate and not an invariant of ours,
        # so it exits 1 wearing the host's own words.
        print(f"rlq: {error}", file=sys.stderr)
        return UNEXPECTED
    except Exception:
        # Exit 1 is contracted for a fault, so main() stays total and
        # returns it rather than letting the exception escape. What
        # changed is the *report*: the old clause named seven builtins
        # and printed one tidy line, which is how an ordinary mistake
        # raised as a `ValueError` came to look like a crash. Those are
        # all classes in the hierarchy now (D58), so anything reaching
        # here is a genuine bug and gets a traceback — a miss is meant
        # to be loud, not absorbed.
        traceback.print_exc()
        return UNEXPECTED


def _create(arguments, session):
    if getattr(arguments, "machine", None):
        raise StaticError(
            "create-machine allocates the machine number; "
            "do not pass --machine",
            rule_id="machine.selector-not-allowed")
    dry_run = getattr(arguments, "dry_run", False)
    result = session.create_machine(
        arguments.blueprint,
        dry_run=dry_run,
        backend=getattr(arguments, "backend", None),
        properties=_explicit_properties(arguments))
    if dry_run:
        # The twin returns a DryRun, so that is what --json prints;
        # the pretty form is its own report, which is the same
        # document rendered for a person.
        return _emit(arguments, dataclasses.asdict(result),
                     lambda: print(result.report, end=""))
    return _emit(arguments, result, lambda: print(result))


def _recreate_machine(arguments, session):
    machine_id = session.recreate_machine(
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None),
        properties=_explicit_properties(arguments))
    return _emit(arguments, machine_id, lambda: print(machine_id))


def _get_machine_dir(arguments, session):
    machine_id = _require_machine_selector(arguments, session)
    path = session.get_machine_dir(machine=machine_id)
    return _emit(arguments, path, lambda: print(path))


def _apply_blueprint(arguments, session):
    machine_id = session.apply_blueprint(
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None),
        properties=_explicit_properties(arguments))
    return _emit(arguments, machine_id, lambda: print(machine_id))


def _script(arguments, session):
    """Run a script live and exit by outcome, or report a dry run.

    Stream-bearing: the run's output is the event stream, which
    ``--progress`` has already rendered — under ``jsonl`` onto stdout,
    terminal event last; under the human modes onto stderr, leaving
    stdout empty. Nothing is written to disk (D36), and nothing more
    is printed here: the outcome travels by exit code.

    ``--dry-run`` makes it the other thing entirely — a document
    rather than a stream — so the selector, the ``--json`` refusal
    and the printed result all change with it.
    """
    blueprint_name = getattr(arguments, "blueprint", None)
    machine_selector = getattr(arguments, "machine", None)
    dry_run = getattr(arguments, "dry_run", False)
    if not dry_run:
        # A run needs a machine to run against; a dry run does not,
        # and its selector chooses the tier instead (script-spec.md's
        # two checkable tiers, preserved by the respelling).
        _reject_stream_json(arguments, "run-script")
        if not blueprint_name and not machine_selector:
            raise StaticError(
                "run-script requires --blueprint or --machine",
                rule_id="machine.no-selector")
    result = session.run_script(
        arguments.label,
        blueprint=blueprint_name,
        machine=machine_selector,
        display=arguments.display,
        properties=_explicit_properties(arguments),
        progress=arguments.progress,
        dry_run=dry_run,
        expect=_expectations(arguments),
        record=getattr(arguments, "record", None),
    )
    if dry_run:
        # Under --dry-run the twin returns a document, so --json is
        # legal here and prints exactly that -- the same rule that
        # makes it illegal on a live run's event stream.
        return _emit(arguments, dataclasses.asdict(result),
                     lambda: print(result.report, end=""))
    return 0


#: The display D97 settled: a description is **never a column**. It
#: prints beneath its entry, indented clear of the names and wrapped
#: to a fixed width, and an entry without one contributes no line.
_DESCRIPTION_INDENT = "  "
_DESCRIPTION_WIDTH = 72


def _description_lines(text):
    """A description as its indented, wrapped display lines (D97)."""
    if not text or text == "-":
        return []
    return textwrap.wrap(
        text, width=_DESCRIPTION_WIDTH,
        initial_indent=_DESCRIPTION_INDENT,
        subsequent_indent=_DESCRIPTION_INDENT)


def _list_blueprints(arguments, session):
    rows = session.list_blueprints()

    def render():
        if not rows:
            print("(no blueprints)")
            return
        name_width = max([4] + [len(row["name"]) for row in rows])
        print(f"{'NAME':<{name_width}}  PATH")
        for row in rows:
            print(f"{row['name']:<{name_width}}  {row['path']}")
            for line in _description_lines(row["description"]):
                print(line)
    return _emit(arguments, rows, render)


def _list_codex(arguments):
    """The library's own listing — names to a person, records to --json.

    The description prints beneath its name, indented and wrapped
    (D97): the column D88 refused stays refused, and the field a
    person scans the library for is on the screen (U11).
    """
    rows = list_codex()

    def render():
        if not rows:
            print("(no built-in blueprints)")
            return
        for row in rows:
            print(row["name"])
            for line in _description_lines(row["description"]):
                print(line)
    return _emit(arguments, rows, render)


def _print_names(names, empty):
    if not names:
        print(empty)
        return
    for name in names:
        print(name)


def _list_media(arguments, session):
    names = session.list_media()
    return _emit(arguments, names,
                 lambda: _print_names(names, "(no media)"))


def _list_machines(arguments, session):
    filter_blueprint = getattr(arguments, "blueprint", None)
    machines = session.list_machines(blueprint=filter_blueprint)
    return _emit(arguments, machines,
                 lambda: _render_machines(machines, filter_blueprint))


def _render_machines(machines, filter_blueprint):
    if not machines:
        if filter_blueprint:
            print(f"(no machines for blueprint {filter_blueprint})")
        else:
            print("(no machines)")
        return
    bp_width = max(
        [9] + [len(state.get("blueprint") or "-")
                for state in machines],
        default=9)
    num_width = max(
        [6] + [len(str(split_machine_id(state["id"])[1]))
                for state in machines
                if split_machine_id(state["id"]) is not None],
        default=6)
    print(f"{'BLUEPRINT':<{bp_width}}  {'NUMBER':>{num_width}}  "
          f"{'PHASE':<8}  BACKEND")
    for state in machines:
        blueprint = state.get("blueprint") or "-"
        parsed = split_machine_id(state["id"])
        number = str(parsed[1]) if parsed else "-"
        phase = state.get("phase") or "?"
        backend = state.get("backend") or "qemu"
        print(f"{blueprint:<{bp_width}}  {number:>{num_width}}  "
              f"{phase:<8}  {backend}")


def _description(script):
    """A script's description as one line of listing text."""
    if script.description is None:
        return "-"
    # A listing binds no properties, so any reference is shown as
    # the author wrote it.
    return script.description.spelling


def _script_description(script_path):
    try:
        return _description(load_script(script_path))
    except (FileNotFoundError, ScriptParseError) as error:
        return f"(error: {error})"


def _script_description_by_stem(stem, context):
    """A script's one-line description, resolved through the seam."""
    try:
        return _script_description(locate_script(stem, context))
    except FileNotFoundError as error:
        return f"(error: {error})"


def _list_scripts(arguments, session, context):
    blueprint_name = getattr(arguments, "blueprint", None)
    if blueprint_name:
        namespace = session.load_namespace()
        machine_component = namespace.machines.get(blueprint_name)
        scripts = dict(machine_component.scripts) if machine_component else {}
        rows = [
            {"label": label, "stem": stem,
             "description": _script_description_by_stem(stem, context)}
            for label, stem in scripts.items()]

        def render_labels():
            if not rows:
                print(f"(blueprint {blueprint_name} declares no scripts)")
                return
            width = max([5] + [len(row["label"]) for row in rows])
            print(f"{'LABEL':<{width}}  STEM")
            for row in rows:
                print(f"{row['label']:<{width}}  {row['stem']}")
                for line in _description_lines(row["description"]):
                    print(line)
        return _emit(arguments, rows, render_labels)

    rows = [{"name": row["name"], "path": row["path"],
             "description": _script_description(row["path"])}
            for row in session.list_scripts()]

    def render_dir():
        if not rows:
            print("(no scripts)")
            return
        width = max([4] + [len(row["name"]) for row in rows])
        print(f"{'NAME':<{width}}  PATH")
        for row in rows:
            print(f"{row['name']:<{width}}  {row['path']}")
            for line in _description_lines(row["description"]):
                print(line)
    return _emit(arguments, rows, render_dir)


def _fetch_media(arguments, session):
    """Fetch a media live; the transfer events are the output."""
    _reject_stream_json(arguments, "fetch-media")
    session.fetch_media(arguments.name, progress=arguments.progress)
    return 0


def _seed(arguments, seeder, kind, context):
    seeded = seeder(arguments.name, context,
                    only=getattr(arguments, "only", False))
    message = (f"seeded {kind} {arguments.name}" if seeded
               else f"{kind} {arguments.name} already exists or not found")
    return _emit(arguments, seeded, lambda: _narrate(message))


def _seed_blueprint(arguments, context):
    return _seed(arguments, seed_blueprint, "blueprint", context)


def _seed_script(arguments, context):
    return _seed(arguments, seed_script, "script", context)


def _new_blueprint(arguments, session):
    path = session.new_blueprint(
        arguments.name, platform=arguments.platform or "dos")
    return _emit(arguments, path, lambda: print(path))


def _delete_blueprint(arguments, session):
    path = session.delete_blueprint(arguments.name)
    return _emit(arguments, path, lambda: print(path))


def _delete_script(arguments, session):
    path = session.delete_script(arguments.name)
    return _emit(arguments, path, lambda: print(path))


def _property_text(value):
    """Render one property value for a human. Secrets show their kind."""
    return "@secret" if is_secret(value) else value


def _warn_missing_credentials(session, keys):
    """Warn on stderr for secrets whose credential is absent.

    The *result* is the properties projection — a secret is its
    marker, on stdout, identical under ``--json``. Whether the host
    store actually holds the value is a diagnostic about the host,
    so it goes to stderr as a warning and never changes the result.
    """
    try:
        missing = [key for key in keys
                   if not session.has_credential(key)]
    except CredentialError as error:
        print(f"reliquary: warning: {error}", file=sys.stderr)
        return
    for key in missing:
        print(f"reliquary: warning: {key} is marked secret but has no "
              f"credential on this host; set it with "
              f"'rlq set-property {key} --secret'", file=sys.stderr)


def _read_secret_value(key):
    """Read a secret from the entry channel the context provides.

    On a terminal, a no-echo prompt; otherwise stdin to EOF with one
    trailing newline stripped, so a program can pipe the value in and
    the CLI stays a complete binding. There is deliberately no
    command-line argument: argv reaches process listings and shell
    history, which are not credential stores.
    """
    if sys.stdin.isatty() and sys.stderr.isatty():
        value = getpass.getpass(f"value for {key}: ", stream=sys.stderr)
    else:
        value = sys.stdin.read()
        if value.endswith("\n"):
            value = value[:-1]
        if value.endswith("\r"):
            value = value[:-1]
    if not value:
        raise PreflightError(
            f"no value supplied for the secret {key!r}",
            rule_id="prop.secret-not-supplied")
    return value


def _get_property(arguments, session):
    value = session.get_property(arguments.key)
    if is_secret(value):
        _warn_missing_credentials(session, [arguments.key])

    def render():
        if value is not None:
            print(_property_text(value))
    return _emit(arguments, value, render)


def _set_property(arguments, session):
    if arguments.secret:
        if arguments.value is not None:
            raise StaticError(
                "set-property --secret takes no value argument: "
                "process listings and shell history are not "
                "credential stores; it prompts on a terminal and "
                "reads stdin otherwise",
                rule_id="prop.set-secret-takes-no-value")
        value = _read_secret_value(arguments.key)
    else:
        if arguments.value is None:
            raise StaticError(
                "set-property needs a value (or --secret)",
                rule_id="prop.set-needs-a-value")
        value = arguments.value
    session.set_property(arguments.key, value, secret=arguments.secret)
    return _emit(arguments, {}, lambda: None)


def _unset_property(arguments, session):
    session.unset_property(arguments.key)
    return _emit(arguments, {}, lambda: None)


def _list_properties(arguments, session):
    properties = session.list_properties(
        getattr(arguments, "prefix", None))
    secrets = [key for key, value in properties.items() if is_secret(value)]
    if secrets:
        _warn_missing_credentials(session, secrets)

    def render():
        if not properties:
            return
        key_width = max(len(key) for key in properties)
        for key, value in properties.items():
            print(f"{key:<{key_width}}  {_property_text(value)}")
    return _emit(arguments, properties, render)


def _clean_media(arguments, session):
    reclaimed = session.clean_media(getattr(arguments, "name", None))
    return _emit(
        arguments, reclaimed,
        lambda: _print_names(reclaimed, "(nothing to reclaim)"))


def _prune_media(arguments, session):
    pruned = session.prune_media(dry_run=arguments.dry_run)
    verb = "would prune" if arguments.dry_run else "pruned"
    return _emit(
        arguments, pruned,
        lambda: _print_names(pruned, f"({verb} nothing)"))


def _add_media(arguments, session):
    path = session.add_media(arguments.name, arguments.file)
    return _emit(arguments, path, lambda: print(path))


def _insert_media(arguments, session):
    machine_id = _require_machine_selector(arguments, session)
    file = getattr(arguments, "file", None)
    session.insert_media(machine_id, arguments.slot, arguments.media,
                         file=file)
    what = file if file else arguments.media
    return _emit(
        arguments, {},
        lambda: _narrate(f"inserted {what} into {arguments.slot} "
                         f"on {machine_id}"))


def _get_machine_var(arguments, session):
    value = session.get_machine_var(
        arguments.key,
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None))
    return _emit(arguments, value,
                 lambda: None if value is None else print(value))


def _wait_machine_var(arguments, session):
    """Wait for a variable another actor sets, and print it.

    No special handling for an expired wait: the twin raises
    ``WaitExpired``, which is a ``RunFailure``, so the ordinary
    taxonomy arm reports it as exit 4 — the work asked for did not
    happen. A bare builtin here would have exited 1 and claimed
    reliquary's own fault (D90).

    Only the flags the caller actually gave are forwarded, so the
    twin's defaults stay the twin's and are documented in one place.
    """
    keywords = {}
    if getattr(arguments, "timeout", None) is not None:
        keywords["timeout"] = arguments.timeout
    if getattr(arguments, "interval", None) is not None:
        keywords["interval"] = arguments.interval
    value = session.wait_machine_var(
        arguments.key, arguments.value,
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None),
        **keywords)
    return _emit(arguments, value, lambda: print(value))


def _describe_drives(arguments, session):
    report = session.describe_drives(
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None))
    return _emit(arguments, report, lambda: _render_drive_report(report))


def _refresh_drives(arguments, session):
    report = session.refresh_drives(
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None))
    return _emit(arguments, report, lambda: _render_drive_report(report))


def _render_drive_report(report):
    """The drive report's human rendering; ``--json`` is the record."""
    recorded = "  (recorded)" if report.get("recorded") else ""
    print(f"{report['machine']}  blueprint {report['blueprint']}  "
          f"{report['platform']}  {report['phase']}{recorded}")
    for drive in report.get("drives") or []:
        media = drive.get("media") or "(empty)"
        mode = drive.get("materialize") or "-"
        line = (f"{drive['key']}  {drive['medium']} slot "
                f"{drive['slot']}  {media}  {mode}")
        record = drive.get("geometry")
        if record is None:
            print(line)
            continue
        unread = record.get("unread")
        if unread is not None:
            print(line)
            print(f"  unread — {unread['id']}: {unread['reason']}")
            continue
        volumes = record.get("volumes") or []
        plural = "" if len(volumes) == 1 else "s"
        backing = record.get("backing") or "-"
        read_at = record.get("read-at") or "-"
        print(f"{line}  {backing}  {len(volumes)} volume{plural}  "
              f"read {read_at}")
        for entry in record.get("partitions") or []:
            logical = " logical" if entry.get("logical") else ""
            print(f"  partition {entry['number']}: type "
                  f"0x{entry['type']:02X} {entry['declares']}"
                  f"{logical}  {entry['size']} bytes")
        for volume in volumes:
            parts = [f"  [{volume['index']}]"]
            if volume.get("filesystem"):
                parts.append(volume["filesystem"])
            if volume.get("label"):
                parts.append(f"label {volume['label']}")
            if volume.get("size") is not None:
                parts.append(f"{volume['size']} bytes")
            if volume.get("heads"):
                parts.append(f"heads {volume['heads']}")
            if volume.get("sectors-per-track"):
                parts.append(
                    f"sectors/track {volume['sectors-per-track']}")
            if len(parts) == 1:
                parts.append("(composed by the backend at attach)")
            print("  ".join(parts))
    mapping = report.get("mapping") or {}
    unmapped = mapping.get("unmapped")
    if unmapped is not None:
        print(f"mapping: {unmapped['reason']}")
        return
    for letter, placed in (mapping.get("letters") or {}).items():
        print(f"{letter}: {placed['drive']} [{placed['volume']}]")
    for entry in mapping.get("undetermined") or []:
        print(f"?: {entry['drive']} — {entry['id']}: {entry['reason']}")


def _put_file(arguments, session):
    address = session.put_file(
        arguments.source, arguments.destination,
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None))
    return _emit(arguments, address, lambda: print(address))


def _get_file(arguments, session):
    path = session.get_file(
        arguments.source, arguments.destination,
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None))
    return _emit(arguments, path, lambda: print(path))


def _list_files(arguments, session):
    entries = session.list_files(
        arguments.address, recursive=arguments.recursive,
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None))

    def render():
        if not entries:
            print("(no files)")
            return
        width = max(len(str(entry["size"] if entry["size"] is not None
                            else "<DIR>")) for entry in entries)
        for entry in entries:
            size = entry["size"]
            size = "<DIR>" if size is None else str(size)
            print(f"{size:>{width}}  {entry['address']}")
    return _emit(arguments, entries, render)


def _put_files(arguments, session):
    addresses = session.put_files(
        arguments.source, arguments.destination,
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None))
    return _emit(arguments, addresses,
                 lambda: _print_names(addresses, "(no files)"))


def _get_files(arguments, session):
    paths = session.get_files(
        arguments.source, arguments.destination,
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None))
    return _emit(arguments, paths,
                 lambda: _print_names(paths, "(no files)"))


def _eject_media(arguments, session):
    machine_id = _require_machine_selector(arguments, session)
    session.eject_media(machine_id, arguments.slot)
    return _emit(
        arguments, {},
        lambda: _narrate(f"ejected {arguments.slot} on {machine_id}"))


def _set_boot_order(arguments, session):
    machine_id = _require_machine_selector(arguments, session)
    session.set_boot_order(machine_id, arguments.keys)
    return _emit(
        arguments, {},
        lambda: _narrate(f"boot order on {machine_id}: "
                         f"{' '.join(arguments.keys)}"))


def _dispatch(arguments, session, context):
    """Route one parsed invocation onto the session it opened.

    ``session`` carries the ambient state (P26); ``context`` is the
    same record, handed directly to the codex family and the locate
    seam — the CLI-only capabilities no veneer covers (D87).
    """
    timeout = getattr(arguments, "timeout", None)

    if arguments.command == "create-machine":
        return _create(arguments, session)
    if arguments.command == "run-script":
        return _script(arguments, session)
    if arguments.command == "fetch-media":
        return _fetch_media(arguments, session)
    if arguments.command == "seed-blueprint":
        return _seed_blueprint(arguments, context)
    if arguments.command == "seed-script":
        return _seed_script(arguments, context)
    if arguments.command == "new-blueprint":
        return _new_blueprint(arguments, session)
    if arguments.command == "delete-blueprint":
        return _delete_blueprint(arguments, session)
    if arguments.command == "delete-script":
        return _delete_script(arguments, session)
    if arguments.command == "get-property":
        return _get_property(arguments, session)
    if arguments.command == "set-property":
        return _set_property(arguments, session)
    if arguments.command == "unset-property":
        return _unset_property(arguments, session)
    if arguments.command == "list-properties":
        return _list_properties(arguments, session)
    if arguments.command == "list-blueprints":
        return _list_blueprints(arguments, session)
    if arguments.command == "list-codex":
        return _list_codex(arguments)
    if arguments.command == "list-machines":
        return _list_machines(arguments, session)
    if arguments.command == "list-scripts":
        return _list_scripts(arguments, session, context)
    if arguments.command == "list-media":
        return _list_media(arguments, session)
    if arguments.command == "clean-media":
        return _clean_media(arguments, session)
    if arguments.command == "prune-media":
        return _prune_media(arguments, session)
    if arguments.command == "add-media":
        return _add_media(arguments, session)
    if arguments.command == "insert-media":
        return _insert_media(arguments, session)
    if arguments.command == "eject-media":
        return _eject_media(arguments, session)
    if arguments.command == "set-boot-order":
        return _set_boot_order(arguments, session)
    if arguments.command == "get-machine-var":
        return _get_machine_var(arguments, session)
    if arguments.command == "wait-machine-var":
        return _wait_machine_var(arguments, session)
    if arguments.command == "describe-drives":
        return _describe_drives(arguments, session)
    if arguments.command == "refresh-drives":
        return _refresh_drives(arguments, session)
    if arguments.command == "put-file":
        return _put_file(arguments, session)
    if arguments.command == "get-file":
        return _get_file(arguments, session)
    if arguments.command == "list-files":
        return _list_files(arguments, session)
    if arguments.command == "put-files":
        return _put_files(arguments, session)
    if arguments.command == "get-files":
        return _get_files(arguments, session)
    if arguments.command == "start-machine":
        machine_id = _require_machine_selector(arguments, session)
        started = session.start_machine(
            machine_id, display=getattr(arguments, "display", False))
        return _emit(arguments, started, lambda: print(started))
    if arguments.command == "stop-machine":
        machine_id = _require_machine_selector(arguments, session)
        session.stop_machine(machine_id)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "destroy-machine":
        machine_id = _require_machine_selector(arguments, session)
        session.destroy_machine(machine_id)
        return _emit(arguments, {},
                     lambda: _narrate(f"destroyed machine {machine_id}"))
    if arguments.command == "recreate-machine":
        return _recreate_machine(arguments, session)
    if arguments.command == "apply-blueprint":
        return _apply_blueprint(arguments, session)
    if arguments.command == "get-machine-dir":
        return _get_machine_dir(arguments, session)

    machine_home = _interaction_target(arguments, session)
    if arguments.command == "type":
        send_text(arguments.text, enter=False, home=machine_home)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "enter":
        send_text(arguments.line, enter=True, home=machine_home)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "press":
        combos = [_resolve_key(name) for name in arguments.names]
        send_keys(combos, home=machine_home)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "exec":
        # The twin resolves the selector, the platform, and the VM
        # identity itself, and returns the command's output.
        rows = session.exec(
            arguments.dos_command,
            machine=getattr(arguments, "machine", None),
            blueprint=getattr(arguments, "blueprint", None),
            timeout=timeout or 120,
            check=getattr(arguments, "check", False))
        rows = list(rows or ())
        return _emit(arguments, rows, lambda: print("\n".join(rows)))
    if arguments.command == "select":
        selected = cursor_menu_select(
            arguments.item, timeout or 30,
            getattr(arguments, "exclude", []), home=machine_home)
        return _emit(arguments, selected, lambda: print(selected))
    if arguments.command == "screen":
        rows = screen_text(home=machine_home)
        return _emit(arguments, rows, lambda: print("\n".join(rows)))
    if arguments.command == "wait":
        wait_text(arguments.pattern, timeout or 60, home=machine_home)
        return _emit(arguments, {}, lambda: _narrate("matched"))
    if arguments.command == "screenshot":
        screenshot(arguments.name, machine_home)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "hmp":
        with Machine(machine_home).qmp() as qmp:
            output = qmp.hmp(arguments.line)
        return _emit(arguments, output, lambda: print(output))
    return 0
