# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Command-line parsing and dispatch."""

import argparse
import getpass
import importlib.metadata
import json
import os
import sys

try:
    _version = importlib.metadata.version("reliquary")
except importlib.metadata.PackageNotFoundError:
    _version = "unknown"

from qemu.qmp import ConnectError

from .interaction_agentless import AgentlessGuestExec
from .lifecycle import read_vm_state
from .machine import (Machine, cursor_menu_select, screen_text,
                      screenshot, send_keys, send_text, wait_text)
from .home import HOME_ASSETS, set_assets, set_cache, set_home
from .library import (list_blueprints, list_builtin_blueprints,
                      list_builtin_media, list_scripts, locate_blueprint,
                      locate_script, search_blueprints, seed_blueprint,
                      seed_script)
from . import blueprint as blueprint_mod
from .errors import ReliquaryError, UNEXPECTED, exit_code
from .machines import (apply_blueprint, create_machine, destroy_machine,
                       eject_media, get_file, get_machine_dir,
                       get_machine_var, insert_media,
                       list_machines, load_machine_state, machine_dir_path,
                       put_file, recreate_machine, resolve_machine,
                       set_boot_order, split_machine_id,
                       start_machine, stop_machine)
# Aliased on import: the twin is named for its command under the
# identity rule, and the builtin stays reachable here.
from .machines import exec as exec_guest
from .media import fetch_media, clean_media, list_media, prune_media
from .credentials import CredentialError
from .progress import MODES as _PROGRESS_MODES
from .properties import (get_property, has_credential, set_property,
                         unset_property, list_properties, is_secret)
from .script_runner import (ScriptRuntimeError, check_script,
                            run_script, _resolve_key)
from .script_nodes import ScriptParseError
from .script_parser import load_script


# Command words recognised when rewriting leading flags so that
# ``rlq --home X list-machines`` and ``rlq list-machines --home X``
# are identical without a parent-parser SUPPRESS twin.
_COMMANDS = frozenset({
    "create-machine", "start-machine", "stop-machine",
    "destroy-machine", "recreate-machine", "apply-blueprint",
    "get-machine-dir",
    "run-script", "check-script", "fetch-media",
    "seed-blueprint", "seed-script", "new-blueprint",
    "delete-blueprint", "search-blueprints",
    "get-property", "set-property", "unset-property",
    "list-properties", "list-blueprints",
    "list-machines", "list-scripts", "list-media",
    "clean-media", "prune-media", "add-media",
    "insert-media", "eject-media", "set-boot-order",
    "get-machine-var", "put-file", "get-file",
    "type", "enter", "press", "exec", "select", "screen", "wait",
    "screenshot", "hmp",
})

# Arity of every flag that may appear before the command word.
# Unknown leading tokens are left in place for argparse to reject.
_FLAG_ARITY = {
    "--home": 1,
    "--cache": 1,
    "--assets": 1,
    "--blueprint": 1,
    "--machine": 1,
    "--port": 1,
    "--platform": 1,
    "--timeout": 1,
    "--display": 0,
    "--builtin": 0,
    "--secret": 0,
    "--json": 0,
    "--only": 0,
    "--name": 1,
    "--exclude": 1,
    "--property": 1,
    "--properties": 1,
    "--progress": 1,
    "--file": 1,
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


def _require_machine_selector(arguments):
    """Return a resolved machine id from selectors.

    Relies on the process-global home/cache (set from --home/--cache
    in main() before dispatch) rather than threading arguments.home
    through — the CLI only ever drives the global default.
    """
    if not getattr(arguments, "blueprint", None) and not getattr(
            arguments, "machine", None):
        raise ValueError(
            "select a machine with --blueprint or --machine")
    return resolve_machine(
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None),
    )


def _interaction_target(arguments):
    """Resolve ``(port, machine directory)`` for a guest-console command.

    Cached machines are selected with ``--blueprint`` /
    ``--machine``; bare ``--port`` remains for the root-home path.
    The directory travels with the port because that is where the
    machine's recorded VM identity lives: without it the session
    could not be verified against the machine it claims to be, and
    every such command would fail closed.
    """
    if getattr(arguments, "blueprint", None) or getattr(
            arguments, "machine", None):
        machine_id = _require_machine_selector(arguments)
        state = load_machine_state(machine_id)
        if state.get("phase") != "running":
            raise ValueError(
                f"machine {machine_id} is not running "
                f"(phase: {state.get('phase')})")
        machine_home = machine_dir_path(machine_id)
        vm = read_vm_state(home=machine_home)
        if vm is None:
            raise ValueError(
                f"machine {machine_id} is running but has no recorded "
                "VM identity")
        return vm["port"], machine_home
    return getattr(arguments, "port", None), None


def _add_home(parser):
    parser.add_argument("--home", default=None,
                        help="reliquary home directory")
    parser.add_argument("--cache", default=None,
                        help="cache directory (default: <home>/cache)")
    parser.add_argument(
        "--assets", default=None,
        help="project asset root (sole source; default: the home)")
    parser.add_argument(
        "--json", action="store_true",
        help="print the command's result as one JSON document")
    return parser


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
            raise ValueError(
                f"--property expects KEY=VALUE, got: {pair!r}")
        key = key.strip()
        if key in explicit:
            raise ValueError(f"--property {key} given more than once")
        explicit[key] = value
    return explicit


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
        raise ValueError(
            f"{command} is a stream, not a document; use "
            "--progress jsonl for machine-readable output")


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

    # check-script
    command = subcommands.add_parser(
        "check-script", help="check a script")
    _add_selectors(command)
    _add_property_inputs(command)
    command.add_argument("name", help="script name")

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

    # search-blueprints
    command = subcommands.add_parser(
        "search-blueprints",
        help="search codex and home blueprints")
    _add_home(command)
    command.add_argument("term", nargs="?", default="",
                         help="term matched against name/description/platform")

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
        "list-blueprints", help="list blueprint names")
    _add_home(command)
    command.add_argument("--builtin", action="store_true")

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
        "list-media", help="list media item names")
    _add_home(command)
    command.add_argument("--builtin", action="store_true")

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

    # guest-console family (script-language identity)
    command = subcommands.add_parser(
        "type", help="type text with no trailing Enter")
    _add_selectors(command)
    command.add_argument("text")
    command.add_argument("--port", type=int, default=None)

    command = subcommands.add_parser(
        "enter", help="type a line and press Enter")
    _add_selectors(command)
    command.add_argument("line")
    command.add_argument("--port", type=int, default=None)

    command = subcommands.add_parser(
        "press", help="send portable key names")
    _add_selectors(command)
    command.add_argument("names", nargs="+")
    command.add_argument("--port", type=int, default=None)

    command = subcommands.add_parser(
        "exec", help="enter a command and wait for the prompt")
    _add_selectors(command)
    command.add_argument("dos_command")
    command.add_argument("--port", type=int, default=None)
    command.add_argument("--timeout", type=int, default=None)
    command.add_argument("--platform", default=None)

    command = subcommands.add_parser(
        "select", help="select a cursor-menu item")
    _add_selectors(command)
    command.add_argument("item")
    command.add_argument("--exclude", action="append", default=[])
    command.add_argument("--port", type=int, default=None)
    command.add_argument("--timeout", type=int, default=None)

    command = subcommands.add_parser(
        "screen", help="print the guest text screen")
    _add_selectors(command)
    command.add_argument("--port", type=int, default=None)

    command = subcommands.add_parser(
        "wait", help="wait until the screen matches a pattern")
    _add_selectors(command)
    command.add_argument("pattern")
    command.add_argument("--port", type=int, default=None)
    command.add_argument("--timeout", type=int, default=None)

    command = subcommands.add_parser(
        "screenshot", help="capture the guest framebuffer")
    _add_selectors(command)
    command.add_argument("name", nargs="?", default="screen")
    command.add_argument("--port", type=int, default=None)

    command = subcommands.add_parser(
        "hmp", help="send a QEMU human-monitor command")
    _add_selectors(command)
    command.add_argument("line")
    command.add_argument("--port", type=int, default=None)

    arguments = parser.parse_args(argv)
    if arguments.home:
        set_home(arguments.home)
    if getattr(arguments, "cache", None):
        set_cache(arguments.cache)
    # The CLI always names an asset source: --assets selects a hermetic
    # project root, its absence selects home mode (canonical folders +
    # codex). The embedding API has no such default — it must name one.
    set_assets(getattr(arguments, "assets", None) or HOME_ASSETS)
    try:
        return _dispatch(arguments)
    except ReliquaryError as error:
        # The taxonomy is the exit codes: STATIC ERROR 2, PREFLIGHT
        # ERROR 3, RUN FAILURE 4, cancelled 5, everything else 1
        # (reliquary/errors.py). A run's own failure report already
        # reached the stream, so only the one-line diagnostic is
        # repeated here.
        print(f"rlq: {error}", file=sys.stderr)
        return exit_code(error)
    except (ConnectError, ConnectionError) as error:
        target = (f"127.0.0.1:{arguments.port}"
                  if getattr(arguments, "port", None)
                  else "the active VM")
        print(f"rlq: cannot reach QMP on {target}: {error}\n"
              "  is the VM running? "
              "(rlq start-machine --blueprint NAME)",
              file=sys.stderr)
        return UNEXPECTED
    except KeyboardInterrupt:
        print("rlq: interrupted", file=sys.stderr)
        return 5
    except (RuntimeError, TimeoutError, FileNotFoundError,
            NotImplementedError, ValueError, OSError, KeyError) as error:
        print(f"rlq: {error}", file=sys.stderr)
        return UNEXPECTED


def _create(arguments):
    if getattr(arguments, "machine", None):
        raise ValueError(
            "create-machine allocates the machine number; "
            "do not pass --machine")
    machine_id = create_machine(
        arguments.blueprint,
        properties=_explicit_properties(arguments),
        properties_file=_properties_file(arguments))
    return _emit(arguments, machine_id, lambda: print(machine_id))


def _recreate_machine(arguments):
    machine_id = recreate_machine(
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None),
        properties=_explicit_properties(arguments),
        properties_file=_properties_file(arguments))
    return _emit(arguments, machine_id, lambda: print(machine_id))


def _get_machine_dir(arguments):
    machine_id = _require_machine_selector(arguments)
    path = get_machine_dir(machine=machine_id)
    return _emit(arguments, path, lambda: print(path))


def _apply_blueprint(arguments):
    machine_id = apply_blueprint(
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None),
        properties=_explicit_properties(arguments),
        properties_file=_properties_file(arguments))
    return _emit(arguments, machine_id, lambda: print(machine_id))


def _script(arguments):
    """Run a script live and exit by outcome.

    Stream-bearing: the run's output is the event stream, which
    ``--progress`` has already rendered — under ``jsonl`` onto stdout,
    terminal event last; under the human modes onto stderr, leaving
    stdout empty. Nothing is written to disk (D36), and nothing more
    is printed here: the outcome travels by exit code.
    """
    _reject_stream_json(arguments, "run-script")
    blueprint_name = getattr(arguments, "blueprint", None)
    machine_selector = getattr(arguments, "machine", None)
    if not blueprint_name and not machine_selector:
        raise ValueError(
            "run-script requires --blueprint or --machine")
    run_script(
        arguments.label,
        blueprint=blueprint_name,
        machine=machine_selector,
        display=arguments.display,
        properties=_explicit_properties(arguments),
        properties_file=_properties_file(arguments),
        progress=arguments.progress,
    )
    return 0


def _check_script(arguments):
    result = check_script(
        arguments.name,
        blueprint=getattr(arguments, "blueprint", None),
        machine=getattr(arguments, "machine", None),
        properties=_explicit_properties(arguments),
        properties_file=_properties_file(arguments),
    )
    return _emit(
        arguments,
        {"report": result.report,
         "property_sources": result.property_sources},
        lambda: print(result.report, end=""))


def _list_blueprints(arguments):
    if getattr(arguments, "builtin", False):
        names = list(list_builtin_blueprints())

        def render_builtin():
            if not names:
                print("(no built-in blueprints)")
                return
            for name in names:
                print(name)
        return _emit(arguments, names, render_builtin)
    rows = list_blueprints()

    def render():
        if not rows:
            print("(no blueprints)")
            return
        name_width = max([4] + [len(row["name"]) for row in rows])
        print(f"{'NAME':<{name_width}}  PATH")
        for row in rows:
            print(f"{row['name']:<{name_width}}  {row['path']}")
    return _emit(arguments, rows, render)


def _print_names(names, empty):
    if not names:
        print(empty)
        return
    for name in names:
        print(name)


def _list_media(arguments):
    if getattr(arguments, "builtin", False):
        names = list(list_builtin_media())
        return _emit(arguments, names,
                     lambda: _print_names(names, "(no built-in media)"))
    names = list_media()
    return _emit(arguments, names,
                 lambda: _print_names(names, "(no media)"))


def _list_machines(arguments):
    filter_blueprint = getattr(arguments, "blueprint", None)
    machines = list_machines(blueprint=filter_blueprint)
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


def _script_description_by_stem(stem):
    """A script's one-line description, resolved through the seam."""
    try:
        return _script_description(locate_script(stem))
    except FileNotFoundError as error:
        return f"(error: {error})"


def _list_scripts(arguments):
    blueprint_name = getattr(arguments, "blueprint", None)
    if blueprint_name:
        from .resolve import load_namespace
        machine_component = load_namespace().machines.get(blueprint_name)
        scripts = dict(machine_component.scripts) if machine_component else {}
        rows = [
            {"label": label, "stem": stem,
             "description": _script_description_by_stem(stem)}
            for label, stem in scripts.items()]

        def render_labels():
            if not rows:
                print(f"(blueprint {blueprint_name} declares no scripts)")
                return
            width = max([5] + [len(row["label"]) for row in rows])
            print(f"{'LABEL':<{width}}  DESCRIPTION")
            for row in rows:
                print(f"{row['label']:<{width}}  {row['description']}")
        return _emit(arguments, rows, render_labels)

    rows = [{"name": row["name"],
             "description": _script_description(row["path"])}
            for row in list_scripts()]

    def render_dir():
        if not rows:
            print("(no scripts)")
            return
        width = max([4] + [len(row["name"]) for row in rows])
        print(f"{'NAME':<{width}}  DESCRIPTION")
        for row in rows:
            print(f"{row['name']:<{width}}  {row['description']}")
    return _emit(arguments, rows, render_dir)


def _fetch_media(arguments):
    """Fetch a media live; the transfer events are the output."""
    _reject_stream_json(arguments, "fetch-media")
    fetch_media(arguments.name, progress=arguments.progress)
    return 0


def _seed(arguments, seeder, kind):
    seeded = seeder(arguments.name, only=getattr(arguments, "only", False))
    message = (f"seeded {kind} {arguments.name}" if seeded
               else f"{kind} {arguments.name} already exists or not found")
    return _emit(arguments, seeded, lambda: _narrate(message))


def _seed_blueprint(arguments):
    return _seed(arguments, seed_blueprint, "blueprint")


def _seed_script(arguments):
    return _seed(arguments, seed_script, "script")


def _search_blueprints(arguments):
    rows = search_blueprints(arguments.term)

    def render():
        if not rows:
            print("(no matching blueprints)")
            return
        name_width = max([4] + [len(row["name"]) for row in rows])
        prov_width = max([10] + [len(row["provenance"]) for row in rows])
        print(f"{'NAME':<{name_width}}  {'PROVENANCE':<{prov_width}}  "
              f"{'PLATFORM':<8}  DESCRIPTION")
        for row in rows:
            platform = row["platform"] or "-"
            description = row["description"] or "-"
            print(f"{row['name']:<{name_width}}  "
                  f"{row['provenance']:<{prov_width}}  "
                  f"{platform:<8}  {description}")
    return _emit(arguments, rows, render)


def _new_blueprint(arguments):
    path = blueprint_mod.new_blueprint(
        arguments.name, platform=arguments.platform or "dos")
    return _emit(arguments, path, lambda: print(path))


def _delete_blueprint(arguments):
    path = blueprint_mod.delete_blueprint(arguments.name)
    return _emit(arguments, path, lambda: print(path))


def _property_text(value):
    """Render one property value for a human. Secrets show their kind."""
    return "@secret" if is_secret(value) else value


def _properties_file(arguments):
    return getattr(arguments, "properties", None)


def _warn_missing_credentials(arguments, keys):
    """Warn on stderr for secrets whose credential is absent.

    The *result* is the properties projection — a secret is its
    marker, on stdout, identical under ``--json``. Whether the host
    store actually holds the value is a diagnostic about the host,
    so it goes to stderr as a warning and never changes the result.
    """
    try:
        missing = [key for key in keys
                   if not has_credential(
                       key, properties_file=_properties_file(arguments))]
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
        raise ValueError(f"no value supplied for the secret {key!r}")
    return value


def _get_property(arguments):
    value = get_property(
        arguments.key, properties_file=_properties_file(arguments))
    if is_secret(value):
        _warn_missing_credentials(arguments, [arguments.key])

    def render():
        if value is not None:
            print(_property_text(value))
    return _emit(arguments, value, render)


def _set_property(arguments):
    if arguments.secret:
        if arguments.value is not None:
            raise ValueError(
                "set-property --secret takes no value argument: "
                "process listings and shell history are not "
                "credential stores; it prompts on a terminal and "
                "reads stdin otherwise")
        value = _read_secret_value(arguments.key)
    else:
        if arguments.value is None:
            raise ValueError(
                "set-property needs a value (or --secret)")
        value = arguments.value
    set_property(arguments.key, value, secret=arguments.secret,
                 properties_file=_properties_file(arguments))
    return _emit(arguments, {}, lambda: None)


def _unset_property(arguments):
    unset_property(
        arguments.key, properties_file=_properties_file(arguments))
    return _emit(arguments, {}, lambda: None)


def _list_properties(arguments):
    properties = list_properties(
        getattr(arguments, "prefix", None),
        properties_file=_properties_file(arguments))
    secrets = [key for key, value in properties.items() if is_secret(value)]
    if secrets:
        _warn_missing_credentials(arguments, secrets)

    def render():
        if not properties:
            return
        key_width = max(len(key) for key in properties)
        for key, value in properties.items():
            print(f"{key:<{key_width}}  {_property_text(value)}")
    return _emit(arguments, properties, render)


def _clean_media(arguments):
    reclaimed = clean_media(getattr(arguments, "name", None))
    return _emit(
        arguments, reclaimed,
        lambda: _print_names(reclaimed, "(nothing to reclaim)"))


def _prune_media(arguments):
    pruned = prune_media(dry_run=arguments.dry_run)
    verb = "would prune" if arguments.dry_run else "pruned"
    return _emit(
        arguments, pruned,
        lambda: _print_names(pruned, f"({verb} nothing)"))


def _add_media(arguments):
    path = blueprint_mod.add_media(arguments.name, arguments.file)
    return _emit(arguments, path, lambda: print(path))


def _insert_media(arguments):
    machine_id = _require_machine_selector(arguments)
    file = getattr(arguments, "file", None)
    insert_media(machine_id, arguments.slot, arguments.media, file=file)
    what = file if file else arguments.media
    return _emit(
        arguments, {},
        lambda: _narrate(f"inserted {what} into {arguments.slot} "
                         f"on {machine_id}"))


def _get_machine_var(arguments):
    value = get_machine_var(
        arguments.key,
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None))
    return _emit(arguments, value,
                 lambda: None if value is None else print(value))


def _put_file(arguments):
    address = put_file(
        arguments.source, arguments.destination,
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None))
    return _emit(arguments, address, lambda: print(address))


def _get_file(arguments):
    path = get_file(
        arguments.source, arguments.destination,
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None))
    return _emit(arguments, path, lambda: print(path))


def _eject_media(arguments):
    machine_id = _require_machine_selector(arguments)
    eject_media(machine_id, arguments.slot)
    return _emit(
        arguments, {},
        lambda: _narrate(f"ejected {arguments.slot} on {machine_id}"))


def _set_boot_order(arguments):
    machine_id = _require_machine_selector(arguments)
    set_boot_order(machine_id, arguments.keys)
    return _emit(
        arguments, {},
        lambda: _narrate(f"boot order on {machine_id}: "
                         f"{' '.join(arguments.keys)}"))


def _dispatch(arguments):
    platform = getattr(arguments, "platform", None) or "dos"
    timeout = getattr(arguments, "timeout", None)

    if arguments.command == "create-machine":
        return _create(arguments)
    if arguments.command == "run-script":
        return _script(arguments)
    if arguments.command == "check-script":
        return _check_script(arguments)
    if arguments.command == "fetch-media":
        return _fetch_media(arguments)
    if arguments.command == "seed-blueprint":
        return _seed_blueprint(arguments)
    if arguments.command == "seed-script":
        return _seed_script(arguments)
    if arguments.command == "search-blueprints":
        return _search_blueprints(arguments)
    if arguments.command == "new-blueprint":
        return _new_blueprint(arguments)
    if arguments.command == "delete-blueprint":
        return _delete_blueprint(arguments)
    if arguments.command == "get-property":
        return _get_property(arguments)
    if arguments.command == "set-property":
        return _set_property(arguments)
    if arguments.command == "unset-property":
        return _unset_property(arguments)
    if arguments.command == "list-properties":
        return _list_properties(arguments)
    if arguments.command == "list-blueprints":
        return _list_blueprints(arguments)
    if arguments.command == "list-machines":
        return _list_machines(arguments)
    if arguments.command == "list-scripts":
        return _list_scripts(arguments)
    if arguments.command == "list-media":
        return _list_media(arguments)
    if arguments.command == "clean-media":
        return _clean_media(arguments)
    if arguments.command == "prune-media":
        return _prune_media(arguments)
    if arguments.command == "add-media":
        return _add_media(arguments)
    if arguments.command == "insert-media":
        return _insert_media(arguments)
    if arguments.command == "eject-media":
        return _eject_media(arguments)
    if arguments.command == "set-boot-order":
        return _set_boot_order(arguments)
    if arguments.command == "get-machine-var":
        return _get_machine_var(arguments)
    if arguments.command == "put-file":
        return _put_file(arguments)
    if arguments.command == "get-file":
        return _get_file(arguments)
    if arguments.command == "start-machine":
        machine_id = _require_machine_selector(arguments)
        started_port = start_machine(
            machine_id, display=getattr(arguments, "display", False))
        return _emit(arguments, started_port, lambda: print(started_port))
    if arguments.command == "stop-machine":
        machine_id = _require_machine_selector(arguments)
        stop_machine(machine_id)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "destroy-machine":
        machine_id = _require_machine_selector(arguments)
        destroy_machine(machine_id)
        return _emit(arguments, {},
                     lambda: _narrate(f"destroyed machine {machine_id}"))
    if arguments.command == "recreate-machine":
        return _recreate_machine(arguments)
    if arguments.command == "apply-blueprint":
        return _apply_blueprint(arguments)
    if arguments.command == "get-machine-dir":
        return _get_machine_dir(arguments)

    port, machine_home = _interaction_target(arguments)
    if arguments.command == "type":
        send_text(arguments.text, enter=False, port=port, home=machine_home)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "enter":
        send_text(arguments.line, enter=True, port=port, home=machine_home)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "press":
        combos = [_resolve_key(name) for name in arguments.names]
        send_keys(combos, port, home=machine_home)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "exec":
        if getattr(arguments, "machine", None) or getattr(
                arguments, "blueprint", None):
            # The twin resolves the selector, the platform, and the
            # VM identity itself, and returns the command's output.
            rows = exec_guest(
                arguments.dos_command,
                machine=getattr(arguments, "machine", None),
                blueprint=getattr(arguments, "blueprint", None),
                timeout=timeout or 120)
        else:
            if platform != "dos":
                raise NotImplementedError("exec requires platform='dos'")
            rows = AgentlessGuestExec(Machine(port, machine_home)).execute(
                arguments.dos_command, timeout or 120)
        rows = list(rows or ())
        return _emit(arguments, rows, lambda: print("\n".join(rows)))
    if arguments.command == "select":
        selected = cursor_menu_select(
            arguments.item, timeout or 30,
            getattr(arguments, "exclude", []), port, home=machine_home)
        return _emit(arguments, selected, lambda: print(selected))
    if arguments.command == "screen":
        rows = screen_text(port, home=machine_home)
        return _emit(arguments, rows, lambda: print("\n".join(rows)))
    if arguments.command == "wait":
        wait_text(arguments.pattern, timeout or 60, port, home=machine_home)
        return _emit(arguments, {}, lambda: _narrate("matched"))
    if arguments.command == "screenshot":
        screenshot(arguments.name, port, machine_home)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "hmp":
        with Machine(port, machine_home).qmp() as qmp:
            output = qmp.hmp(arguments.line)
        return _emit(arguments, output, lambda: print(output))
    return 0
