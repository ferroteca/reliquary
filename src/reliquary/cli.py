# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Command-line parsing and dispatch."""

import argparse
import dataclasses
import getpass
import importlib.metadata
import json
import os
import re
import sys
import traceback

from rich import box
from rich.cells import cell_len
from rich.console import Console
from rich.table import Table

try:
    _version = importlib.metadata.version("reliquary")
except importlib.metadata.PackageNotFoundError:
    _version = "unknown"

from .machine_handle import (Machine, cursor_menu_select, screen_text,
                      screenshot, send_keys, send_text, wait_text)
from .home import (Context, DIRECTORIES, default_home_dir,
                   environment_variable)
# The codex functions and locate_script belong to the CLI alone
# (D87): there is no Session method wrapping them, so they take the
# invocation's Context directly instead of going through a Session.
from .library import (list_codex, locate_script, seed_blueprint,
                      seed_script)
from . import backends
from .errors import (InternalError, PreflightError, ReliquaryError,
                     StaticError, UNEXPECTED, WaitExpired, exit_code)
from .machines import read_vm_state
from .credentials import CredentialError
from .progress import MODES as _PROGRESS_MODES
from .properties import is_secret
from .script_runner import resolve_key
from .script_nodes import ScriptParseError
from .script_parser import load_script, parse_script
from .control_display import normalize_row
from .session import Session


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
    """Move any flags before the command word to after it.

    Each flag is declared once, on its subcommand's own parser, not
    on a shared parent parser. This function moves flags around so
    that their position on the command line doesn't matter — a flag
    written before the command word still reaches the right parser.

    An unknown flag before the command word has no known arity, so we
    don't know whether to skip a following value for it — its value
    (if it has one) just looks like an ordinary word. If we stopped
    scanning there, argparse would treat that value as the command
    word and report ``invalid choice: 'foo'``, blaming the value
    instead of naming the flag that's actually wrong. So once an
    unknown flag is seen, the scan keeps looking past it for the real
    command word; the reorder still happens, and the subparser then
    reports ``unrecognized arguments: --qemu foo`` instead, naming the
    flag. Either way the command is invalid — this only changes which
    error message the user sees, and naming the bad flag is the more
    useful one. A plain word seen before any unknown flag still stops
    the scan immediately, so a genuinely misspelled command name is
    still reported as an invalid choice, as it should be.
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
    """Resolve --blueprint/--machine to a machine id, or raise.

    Resolution goes through ``session`` — built in main() from the
    ``--*-dir`` flags, the environment, and the default home — never
    through any process-global state. The CLI doesn't use
    process-global state for this anymore (P26).
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
    """Resolve the machine directory a guest-console command should use.

    That directory is all the addressing info needed: it's where the
    machine's recorded VM identity lives, and the backend adapter
    named in that state supplies and verifies the actual connection
    endpoint. There's no port number to pass around here — that's a
    QEMU implementation detail handled inside the adapter.
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


# Every command accepts the same six directory flags, matching the
# API's shared keyword arguments. Each flag names one working
# directory; any left unnamed are derived from the others (see
# home.py), so passing just `--home-dir` still places all six, and
# running with no flags at all places them under the default home.
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
    _add_json(parser)
    return parser


def _add_json(parser):
    """Add the --json flag to a command parser."""
    parser.add_argument(
        "--json", action="store_true",
        help="print the command's result as one JSON document")
    return parser


def _invocation_context(arguments):
    """Build the one Context this invocation opens its session on.

    Flags take priority; for anything a flag didn't set, the
    environment variable is checked next; anything still unset falls
    back to the default home directory. That last fallback is what
    makes the "no home assigned" error unreachable from the command
    line: it fires whenever home is still unset at that point, not
    just when the user passed nothing at all, so
    ``rlq --cache-dir D:\\c list-machines`` still works, combining an
    explicit cache directory with a defaulted home.

    Reading environment variables happens only here, in the CLI —
    never inside the library itself: a program embedding reliquary as
    a library gets none of this unless it explicitly asks for it (see
    home.py). The selected properties file travels in the same
    Context record, alongside the six directories (P26): it comes
    from ``--properties``, then ``RELIQUARY_PROPERTIES``, then falls
    through to the home directory's own properties file if neither is
    set.
    """
    slots = {}
    for name in DIRECTORIES:
        value = getattr(arguments, "%s_dir" % name, None)
        if not value:
            value = os.environ.get(environment_variable(name))
        # RELIQUARY_HOME is the documented, current name for this
        # variable. Also accept the older name, RELIQUARY_HOME_DIR,
        # for users who still have it set, but only when RELIQUARY_HOME
        # itself isn't set.
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
    """Add --properties, letting a command use a file other than the home's."""
    parser.add_argument(
        "--properties", default=None, metavar="PATH",
        help="properties file to use instead of the home's "
             "(secrets scope to this path)")
    return parser


def _add_property_inputs(parser):
    """Add the property-binding flags for a run: --property and --properties."""
    parser.add_argument(
        "--property", action="append", default=None, metavar="KEY=VALUE",
        dest="property", help="bind a declared property (repeatable); "
        "never a secret -- argv is not a credential store")
    _add_properties_file(parser)
    return parser


def _explicit_properties(arguments):
    """Parse the repeated --property KEY=VALUE flags into a dict, or None."""
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
    """Parse the repeated --expect KEY=VALUE flags into a dict, or None.

    Uses the same KEY=VALUE syntax as --property, deliberately: one
    format for "a key and a value on the command line" is easier to
    learn than a second, slightly different one.
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
    """Print a command's result as JSON or as human-readable text.

    Under ``--json``, ``value`` (the underlying Session method's
    return value) is printed as one JSON document on stdout — a
    command with no real return value passes ``{}``. Otherwise,
    ``render()`` is called to print the human-readable form. Always
    returns exit code 0.

    Per the output rules in docs/spec/cli.md: a command's normal
    stdout output is exactly the human-readable rendering of the same
    value that ``--json`` would print, so it can be piped without any
    extra flags. Anything else — narration, or every line printed by
    a command with no real return value — goes to stderr instead.
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
    """Raise if --json was passed to a command whose output is an event stream."""
    if getattr(arguments, "json", False):
        raise StaticError(
            f"{command} is a stream, not a document; use "
            "--progress jsonl for machine-readable output",
            rule_id="progress.document-on-a-stream")


def _add_progress(parser):
    """Add --progress to a command whose output is a live event stream."""
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
    """Return the console-script name the user actually typed, or "rlq".

    ``rlq`` and ``reliquary`` are both registered as entry points for
    this same command, so help and usage text should show whichever
    one the user actually ran, instead of always naming one of them.
    """
    stem = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    return stem if stem in _PROG_NAMES else "rlq"


def _add_machine_commands(subcommands):
    """Register the machine lifecycle."""
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

    # restart-machine
    command = subcommands.add_parser(
        "restart-machine", help="stop a machine if running, then start it")
    _add_selectors(command)
    command.add_argument("--display", action="store_true")
    command.add_argument(
        "machine_id", nargs="?", default=None,
        help="machine id for 'restart-machine <id>' (short for --machine)")

    # stop-machine
    command = subcommands.add_parser(
        "stop-machine", help="stop a machine")
    _add_selectors(command)
    command.add_argument(
        "machine_id", nargs="?", default=None,
        help="machine id for 'stop-machine <id>' (short for --machine)")

    # destroy-machine
    command = subcommands.add_parser(
        "destroy-machine", help="stop a running machine, then delete it")
    _add_selectors(command)
    command.add_argument(
        "machine_id", nargs="?", default=None,
        help="machine id for 'destroy-machine <id>' (short for --machine)")

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


def _add_script_commands(subcommands):
    """Register running a script."""
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


def _add_media_commands(subcommands):
    """Register fetching media."""
    # fetch-media
    command = subcommands.add_parser(
        "fetch-media", help="fetch media")
    _add_home(command)
    _add_progress(command)
    command.add_argument("name", help="media name")


def _add_authoring_commands(subcommands):
    """Register seeding and authoring the files a user owns."""
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


def _add_property_commands(subcommands):
    """Register the property family."""
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


def _add_listing_commands(subcommands):
    """Register the list family."""
    # list-*
    command = subcommands.add_parser(
        "list-backends", help="list discovered backend installations")
    _add_json(command)

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


def _add_cache_commands(subcommands):
    """Register cache reclamation, and declaring a local media."""
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


def _add_state_commands(subcommands):
    """Register persistent machine-state operations."""
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


def _add_console_commands(subcommands):
    """Register the guest-console family (script-language identity)."""
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
        "wait-ready", help="wait until the guest is at a prompt")
    _add_selectors(command)
    command.add_argument("--timeout", type=float, default=None,
                         help="seconds to wait (default 90)")
    command.add_argument(
        "--prompt", default=None,
        help="the exact bottom-row text a customized prompt draws; "
             "the standard DOS prompt is always recognized")

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
        "wait", help="wait for a condition, in the script language's "
                     "spellings")
    _add_selectors(command)
    command.add_argument(
        "condition",
        help="bare text (a normalized literal), /regex/, or "
             "machine=stopped — the language's spelling less the quotes "
             "the shell consumed")
    command.add_argument("--timeout", type=int, default=None)

    command = subcommands.add_parser(
        "screenshot", help="capture the guest framebuffer")
    _add_selectors(command)
    command.add_argument("name", nargs="?", default="screen")

    command = subcommands.add_parser(
        "hmp", help="send a QEMU human-monitor command")
    _add_selectors(command)
    command.add_argument("line")

    command = subcommands.add_parser(
        "guest-agent-ping",
        help="confirm the QEMU guest agent is alive on its channel")
    _add_selectors(command)
    command.add_argument("--timeout", type=float, default=None)

    command = subcommands.add_parser(
        "guest-agent-exec",
        help="run one executable through the QEMU guest agent")
    _add_selectors(command)
    command.add_argument("path", help="the executable's path in the guest")
    command.add_argument("exec_args", nargs="*", metavar="arg")
    command.add_argument("--timeout", type=float, default=None)


def _build_parser():
    """Build the whole CLI: the root parser, and every command it registers.

    Returns ``(parser, commands)`` — the parser to run an invocation
    with, and the set of command-word strings it recognizes. The
    command set is read directly off the built parser rather than
    typed out again by hand, so `_COMMANDS` below never has to be kept
    in sync with the actual registrations manually.

    The order the `_add_*_commands` functions are called in below is
    the order commands appear in `--help` output, so reordering a call
    reorders the listing. The groupings follow how this module has
    always been organized rather than some new category scheme, which
    is why `fetch-media` sits alone between the script and authoring
    groups, and `add-media` sits with cache reclamation instead of
    with the other media commands.
    """
    parser = argparse.ArgumentParser(
        prog=_prog_name(),
        description="OS installation scripting over QEMU guest "
                    "automation (DOS by default)")
    parser.add_argument(
        "--version", action="version",
        version="%(prog)s " + _version)

    subcommands = parser.add_subparsers(dest="command", required=True)
    _add_machine_commands(subcommands)
    _add_script_commands(subcommands)
    _add_media_commands(subcommands)
    _add_authoring_commands(subcommands)
    _add_property_commands(subcommands)
    _add_listing_commands(subcommands)
    _add_cache_commands(subcommands)
    _add_state_commands(subcommands)
    _add_console_commands(subcommands)
    return parser, frozenset(subcommands.choices)


# The set of command words _reorder_argv() looks for when rewriting
# leading flags, so that ``rlq --home-dir X list-machines`` and
# ``rlq list-machines --home-dir X`` behave identically. This set is
# computed by building a throwaway parser once at import time rather
# than typed out by hand, so it can never drift out of sync with the
# commands actually registered. main() builds its own separate parser
# for the real run, so _prog_name() still reads sys.argv[0] when the
# command actually runs, not when this module is first imported.
_COMMANDS = _build_parser()[1]


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = _reorder_argv(list(argv))

    parser, _commands = _build_parser()
    arguments = parser.parse_args(argv)
    context = _invocation_context(arguments)
    session = Session(context)
    try:
        try:
            return _dispatch(arguments, session, context)
        except ConnectionError as error:
            # An unreachable management endpoint means the command was
            # legal but the VM isn't actually there — that's a
            # PreflightError, not an internal fault. Converting it to
            # a PreflightError here, rather than reporting the raw
            # ConnectionError, is what makes the exit code come from
            # the normal error-class-to-exit-code mapping like every
            # other error.
            raise PreflightError(
                f"cannot reach the machine's backend: {error}\n"
                "  is the VM running? "
                "(rlq start-machine --blueprint NAME)",
                rule_id="machine.qmp-unreachable") from error
    except ReliquaryError as error:
        # See reliquary/errors.py for the exit codes: StaticError is
        # 2, PreflightError is 3, RunFailure is 4, cancelled is 5, and
        # InternalError is 1. A run's own failure is already reported
        # in the event stream, so only this one-line summary is
        # printed here, not the full report again.
        print(f"rlq: {error}", file=sys.stderr)
        return exit_code(error)
    except KeyboardInterrupt:
        print("rlq: interrupted", file=sys.stderr)
        return 5
    except OSError as error:
        # The host refused to do something reliquary correctly asked
        # for — a permission error, a full disk, a path that vanished
        # underneath it. This isn't a mistake the caller can fix by
        # rephrasing the command, and it isn't a bug in reliquary
        # either, so it exits 1, printing the host's own error message.
        print(f"rlq: {error}", file=sys.stderr)
        return UNEXPECTED
    except Exception:
        # Exit code 1 is reserved for reliquary's own faults, so
        # main() catches everything here rather than letting an
        # exception crash the process, and still returns 1. What
        # changed from an earlier version of this code: it used to
        # list specific built-in exception types (like ValueError) and
        # print just one tidy line for them, which made an ordinary
        # user mistake that happened to raise a plain ValueError look
        # like an internal crash. Those cases are now all proper
        # reliquary error classes (D58), so anything that still
        # reaches this bare except really is an unexpected bug, and
        # gets a full traceback printed — a bug here should be loud,
        # not hidden behind a tidy one-liner.
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
        # session.create_machine() returns a DryRun object here, so
        # that's what --json prints (as a dict); result.report is the
        # same information rendered as text for a person to read.
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
    """Run a script live and exit with its outcome, or report a dry run.

    A live run's output is the event stream, and ``--progress`` has
    already rendered it: under ``jsonl`` it goes to stdout, with the
    terminal event printed last; under the human modes it goes to
    stderr, leaving stdout empty. Nothing is written to disk (D36),
    and nothing extra is printed here — the outcome is reported only
    through the exit code.

    ``--dry-run`` makes this something else entirely: instead of a
    live event stream, it produces one document. That changes which
    selector is required, whether ``--json`` is allowed, and what
    gets printed.
    """
    blueprint_name = getattr(arguments, "blueprint", None)
    machine_selector = getattr(arguments, "machine", None)
    dry_run = getattr(arguments, "dry_run", False)
    if not dry_run:
        # A live run needs a machine to run against; a dry run does
        # not, since its selector just picks which of the two checks
        # (blueprint or machine) to run instead (the two checkable
        # tiers from script-spec.md).
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
        # Under --dry-run, session.run_script() returns a document
        # rather than a stream, so --json is allowed here and prints
        # exactly that document -- the same rule that makes --json
        # rejected on a live run's event stream.
        return _emit(arguments, dataclasses.asdict(result),
                     lambda: print(result.report, end=""))
    return 0


def _table_box(encoding):
    """Choose table border characters the console's encoding can display."""
    normalized = (encoding or "").lower().replace("_", "").replace("-", "")
    return box.ROUNDED if normalized.startswith("utf") else box.ASCII


def _print_table(columns, rows):
    """Print a compact, colorful table that wraps long cells.

    Rich measures column widths in terminal cells, not Python
    characters, and wraps any value that doesn't fit — including a
    long description, inside its own cell. When stdout isn't a
    terminal (piped, captured, or running under the test suite), the
    width is fixed at 80 instead of reading the actual terminal's
    width, because that width belongs to whatever terminal happens to
    be running the command, not to the stdout stream we're writing
    to — reading it would make piped output and test assertions
    depend on the size of whoever's terminal window happened to run
    them.
    """
    force_width = None if sys.stdout.isatty() else 80
    console = Console(file=sys.stdout, highlight=False,
                      width=force_width)
    headings = tuple(columns)
    gutter = 2 * (len(headings) - 1)
    available = max(sum(cell_len(heading) for heading in headings),
                    console.width - gutter - 2)
    desired = [max(cell_len(heading),
                   *(cell_len(str(row[index])) for row in rows))
               for index, heading in enumerate(headings)]
    widths = [cell_len(heading) for heading in headings]
    remaining = available - sum(widths)
    while remaining and any(width < wanted
                            for width, wanted in zip(widths, desired)):
        for index, wanted in enumerate(desired):
            if remaining == 0:
                break
            if widths[index] < wanted:
                widths[index] += 1
                remaining -= 1

    def table(*, header):
        result = Table(box=_table_box(console.encoding),
                       border_style="bright_blue",
                       header_style="bold bright_cyan", pad_edge=False,
                       padding=(0, 1), collapse_padding=True,
                       show_header=header, show_lines=True)
        for heading, width in zip(headings, widths):
            result.add_column(heading, width=width, overflow="fold")
        return result

    result = table(header=True)
    for index, row in enumerate(rows):
        result.add_row(*(str(value) for value in row),
                       style="bright_white" if index % 2 else "white")
    console.print(result)


def _list_blueprints(arguments, session):
    rows = session.list_blueprints()

    def render():
        if not rows:
            print("(no blueprints)")
            return
        if any(row["description"] for row in rows):
            _print_table(("NAME", "PATH", "DESCRIPTION"),
                         [(row["name"], row["path"],
                           row["description"] or "") for row in rows])
        else:
            _print_table(("NAME", "PATH"),
                         [(row["name"], row["path"]) for row in rows])
    return _emit(arguments, rows, render)


def _list_codex(arguments):
    """List the built-in library's blueprints: names for a person, records for --json.

    Each blueprint's description is shown in the same row, wrapping
    to fit the terminal as needed.
    """
    rows = list_codex()

    def render():
        if not rows:
            print("(no built-in blueprints)")
            return
        _print_table(("NAME", "DESCRIPTION"),
                     [(row["name"], row["description"] or "")
                      for row in rows])
    return _emit(arguments, rows, render)


def _print_names(names, empty):
    if not names:
        print(empty)
        return
    for name in names:
        print(name)


def _list_backends(arguments):
    """List the backends discovered on this host; excludes any not available."""
    rows = [
        {"backend": probe.backend, "home": probe.home}
        for probe in backends.discover()
        if probe.available
    ]

    def render():
        if not rows:
            print("(no backends discovered)")
            return
        _print_table(("BACKEND", "HOME"),
                     [(row["backend"], row["home"]) for row in rows])

    return _emit(arguments, rows, render)


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
    rows = []
    for state in machines:
        phase = state.get("phase") or "?"
        backend = state.get("backend") or "qemu"
        rows.append((state["id"], phase, backend))
    _print_table(("ID", "PHASE", "BACKEND"), rows)


def _description(script):
    """Return a script's description as one line of listing text."""
    if script.description is None:
        return ""
    # Listing a script doesn't bind any properties, so any
    # ${property} reference in the description is shown exactly as
    # the author wrote it, not with a value filled in.
    return script.description.spelling


def _script_description(script_path):
    try:
        return _description(load_script(script_path))
    except (FileNotFoundError, ScriptParseError) as error:
        return f"(error: {error})"


def _script_description_by_stem(stem, context):
    """Return a script's one-line description, resolved by its filename stem."""
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
            if any(row["description"] for row in rows):
                _print_table(("LABEL", "STEM", "DESCRIPTION"),
                             [(row["label"], row["stem"],
                               row["description"]) for row in rows])
            else:
                _print_table(("LABEL", "STEM"),
                             [(row["label"], row["stem"]) for row in rows])
        return _emit(arguments, rows, render_labels)

    rows = [{"name": row["name"], "path": row["path"],
             "description": _script_description(row["path"])}
            for row in session.list_scripts()]

    def render_dir():
        if not rows:
            print("(no scripts)")
            return
        if any(row["description"] for row in rows):
            _print_table(("NAME", "PATH", "DESCRIPTION"),
                         [(row["name"], row["path"], row["description"])
                          for row in rows])
        else:
            _print_table(("NAME", "PATH"),
                         [(row["name"], row["path"]) for row in rows])
    return _emit(arguments, rows, render_dir)


def _fetch_media(arguments, session):
    """Fetch one media item; the transfer events printed live are the output."""
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
    """Render one property value for a human; a secret shows as "@secret"."""
    return "@secret" if is_secret(value) else value


def _warn_missing_credentials(session, keys):
    """Print a stderr warning for each secret whose credential is missing.

    The command's actual result is the properties list — a secret
    always shows up as its marker on stdout, whether or not
    ``--json`` is used. Whether the host's credential store actually
    holds the value is a separate fact about the host, so it's
    reported as a warning on stderr and never changes the result
    itself.
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
    """Read a secret value, prompting on a terminal or reading stdin otherwise.

    On a terminal, this shows a prompt that doesn't echo what's
    typed. Otherwise, it reads all of stdin until EOF and strips one
    trailing newline, so a program can pipe the value in. There is
    deliberately no way to pass the secret as a command-line argument:
    command-line arguments show up in process listings and shell
    history, neither of which is a safe place to store a credential.
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
        _print_table(("KEY", "VALUE"),
                     [(key, _property_text(value))
                      for key, value in properties.items()])
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
    """Wait for a variable another actor sets, then print it.

    No special handling is needed if the wait times out: the
    underlying call raises ``WaitExpired``, which is a
    ``RunFailure``, so it's reported through the normal error
    handling as exit code 4 — the work that was asked for didn't
    happen. Raising a plain built-in exception here instead would
    have exited with code 1, wrongly claiming it was reliquary's own
    fault rather than an ordinary timeout (D90).

    Only the flags the caller actually passed are forwarded to
    session.wait_machine_var(), so its own default values stay in one
    place — its own signature — instead of being duplicated here.
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


def _wait_condition(text):
    """Parse one `wait` condition using the script language's own parser.

    The CLI defines no condition grammar of its own (S1): ``text`` is
    handed to :func:`parse_script` as the one-statement script
    ``wait <text>``, so its accepted spellings are exactly the script
    language's, by construction (D116). The shell has already
    stripped the script language's own quotes from a plain word, so
    plain text (with no leading quote, slash, or ``machine=``) is
    treated as a literal string and re-quoted here before parsing —
    its backslashes and quote characters escaped the way the script
    language escapes them, with a ``${key}`` reference left alone to
    mean whatever the script language says it means. Text that
    already carries its own quotes, a ``/regex/``, or
    ``machine=stopped`` is passed through to the parser exactly as
    written.

    Returns a ``(channel, pattern)`` tuple: ``("machine", None)`` for
    the machine channel, or ``("screen", regex)`` otherwise — where a
    literal string condition is converted to its normalized,
    regex-escaped text (matching the spec's rule that a literal
    matches as a normalized substring of a normalized screen row).
    """
    spelled = text
    if not (text.startswith('"') or text.startswith("/")
            or text.startswith("machine=")):
        spelled = '"' + (text.replace("\\", "\\\\")
                         .replace('"', '\\"')) + '"'
    try:
        script = parse_script(f"wait {spelled}", path="<wait>")
    except ScriptParseError as error:
        raise StaticError(
            f"not a wait condition: {text!r} — bare text, /regex/, or "
            f"machine=stopped ({error})",
            rule_id="condition.unparsable") from error
    condition = script.statements[0].conditions[0]
    if condition.channel == "machine":
        return "machine", None
    if condition.kind == "regex":
        return "screen", condition.value
    literal = condition.value
    if literal.interpolated:
        raise StaticError(
            f"a property reference in a wait condition is a script's: "
            f"{text!r}", rule_id="condition.property-reference")
    return "screen", re.escape(normalize_row(literal.text))


def _wait(arguments, session, timeout):
    """Implement the CLI's `wait` command: one condition, either channel.

    The machine channel succeeds even if the machine has already
    stopped by the time the command runs — a `wait` started a moment
    too late by the shell is treated as satisfied, not refused. After
    confirming the VM is gone, this also updates the machine's
    recorded phase to match, the same way the script runtime does
    after making the same observation (D116).
    """
    channel, pattern = _wait_condition(arguments.condition)
    if channel == "machine":
        machine_id = _require_machine_selector(arguments, session)
        state = session.load_machine_state(machine_id)
        if state.get("phase") == "running":
            Machine(session.machine_dir_path(machine_id)).wait_stopped(
                timeout)
            session.mark_stopped(machine_id)
        return _emit(arguments, {}, lambda: _narrate("stopped"))
    machine_home = _interaction_target(arguments, session)
    try:
        wait_text(pattern, timeout, home=machine_home)
    except WaitExpired as expired:
        # wait_text() names the regex pattern it searched for in its
        # error message, but the user typed a condition string, not a
        # regex, so the error message should name what they typed.
        raise WaitExpired(
            str(expired).replace(pattern, arguments.condition, 1),
            rule_id=expired.rule_id) from expired
    return _emit(arguments, {}, lambda: _narrate("matched"))


def _wait_ready(arguments, session):
    """Wait until the guest finishes booting and is ready for commands.

    This command has no real return value: which prompt the guest
    reached is reported as narration on stderr (printed by the
    adapter), the same way `wait`'s "matched" message is, and
    `--json` just prints `{}`. If the wait times out,
    session.wait_ready() raises ``WaitExpired``, reported as the usual
    exit code 4 (D90). Only the flags the caller actually passed are
    forwarded, so session.wait_ready()'s own defaults stay in one
    place.
    """
    keywords = {}
    if getattr(arguments, "timeout", None) is not None:
        keywords["timeout"] = arguments.timeout
    if getattr(arguments, "prompt", None) is not None:
        keywords["prompt"] = arguments.prompt
    session.wait_ready(
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None),
        **keywords)
    return _emit(arguments, {}, lambda: None)


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
    """Route one parsed command-line invocation to the right handler function.

    ``session`` carries the resolved working directories (P26).
    ``context`` is that same underlying record, passed directly to
    the codex functions and to locate_script — the CLI-only
    capabilities that have no Session method wrapping them (D87).
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
    if arguments.command == "list-backends":
        return _list_backends(arguments)
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
    if arguments.command == "start-machine":
        machine_id = _require_machine_selector(arguments, session)
        started = session.start_machine(
            machine_id, display=getattr(arguments, "display", False))
        return _emit(arguments, started, lambda: print(started))
    if arguments.command == "restart-machine":
        pos_id = getattr(arguments, "machine_id", None)
        if pos_id:
            machine_id = session.resolve_machine(machine=pos_id)
        else:
            machine_id = _require_machine_selector(arguments, session)
        started = session.restart_machine(
            machine_id, display=getattr(arguments, "display", False))
        return _emit(arguments, started, lambda: print(started))
    if arguments.command == "stop-machine":
        pos_id = getattr(arguments, "machine_id", None)
        if pos_id:
            machine_id = session.resolve_machine(machine=pos_id)
        else:
            machine_id = _require_machine_selector(arguments, session)
        session.stop_machine(machine_id)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "destroy-machine":
        pos_id = getattr(arguments, "machine_id", None)
        if pos_id:
            machine_id = session.resolve_machine(machine=pos_id)
        else:
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

    if arguments.command == "wait":
        # _wait() resolves its own machine target rather than using
        # _interaction_target() below, because the machine channel
        # needs to succeed on a machine that has already stopped, and
        # _interaction_target()'s running-machine check would reject
        # that.
        return _wait(arguments, session, timeout or 60)
    machine_home = _interaction_target(arguments, session)
    if arguments.command == "type":
        send_text(arguments.text, enter=False, home=machine_home)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "enter":
        send_text(arguments.line, enter=True, home=machine_home)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "press":
        combos = [resolve_key(name) for name in arguments.names]
        send_keys(combos, home=machine_home)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "wait-ready":
        return _wait_ready(arguments, session)
    if arguments.command == "exec":
        # session.exec() resolves the machine selector, the guest
        # platform, and the VM identity itself, and returns the
        # command's output.
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
    if arguments.command == "screenshot":
        screenshot(arguments.name, machine_home)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "hmp":
        with Machine(machine_home).qmp() as qmp:
            output = qmp.hmp(arguments.line)
        return _emit(arguments, output, lambda: print(output))
    if arguments.command == "guest-agent-ping":
        with Machine(machine_home).guest_agent() as agent:
            agent.ping(timeout=timeout)
        return _emit(arguments, {},
                     lambda: _narrate("guest agent is alive"))
    if arguments.command == "guest-agent-exec":
        with Machine(machine_home).guest_agent() as agent:
            result = agent.run(arguments.path, arguments.exec_args,
                               timeout=timeout)
        value = {"exit-code": result.exit_code, "signal": result.signal,
                 "stdout": result.stdout, "stderr": result.stderr}

        def _render_exec():
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
        return _emit(arguments, value, _render_exec)
    # A command that's registered with argparse but has no matching
    # `if` branch above ends up here. Just returning 0 in that case
    # would report success for work that was never actually done,
    # which is the one bug in this file that would give a wrong
    # answer instead of just being inconvenient. The list of commands
    # is currently kept in three separate places, and only one of
    # them is checked against the argparse registrations
    # automatically, so this gap is real until that's fixed (T17).
    raise InternalError(
        f"the CLI registers {arguments.command!r} and routes it "
        "nowhere: a registered command with no dispatch arm would "
        "otherwise report success for work it never did")
