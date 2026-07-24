# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Command-line parsing and dispatch."""

import argparse
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
from .machines import (apply_blueprint, create_machine, destroy_machine,
                       eject_media, get_machine_dir, insert_media,
                       list_machines, load_machine_state, machine_dir_path,
                       recreate_machine, resolve_machine,
                       set_boot_order, split_machine_id,
                       start_machine, stop_machine)
from .media import (add_media, fetch_media, clean_media, list_media,
                    prune_media)
from .properties import (get_property, set_property, unset_property,
                         list_properties)
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
    "list-properties", "import-vm", "list-blueprints",
    "list-machines", "list-scripts", "list-media",
    "clean-media", "prune-media", "add-media",
    "insert-media", "eject-media", "set-boot-order",
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
    "--qemu": 1,
    "--platform": 1,
    "--timeout": 1,
    "--display": 0,
    "--builtin": 0,
    "--secret": 0,
    "--json": 0,
    "--only": 0,
    "--name": 1,
    "--exclude": 1,
}


def _reorder_argv(argv):
    """Move leading flags to after the command word.

    Flags are declared once on each subparser; this rewrite makes
    position carry no meaning so the parent-parser SUPPRESS twin is
    unnecessary.
    """
    if not argv:
        return argv
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--":
            break
        if arg.startswith("-"):
            name, eq, _ = arg.partition("=")
            arity = _FLAG_ARITY.get(name)
            if arity is None:
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


def _interaction_port(arguments):
    """Resolve a QMP port from selectors or the legacy ``--port``.

    Cached machines are selected with ``--blueprint`` /
    ``--machine``; bare ``--port`` remains for the root-home path.
    """
    if getattr(arguments, "blueprint", None) or getattr(
            arguments, "machine", None):
        machine_id = _require_machine_selector(arguments)
        state = load_machine_state(machine_id)
        if state.get("phase") != "running":
            raise ValueError(
                f"machine {machine_id} is not running "
                f"(phase: {state.get('phase')})")
        vm = read_vm_state(home=machine_dir_path(machine_id))
        if vm is None:
            raise ValueError(
                f"machine {machine_id} is running but has no recorded "
                "VM identity")
        return vm["port"]
    return getattr(arguments, "port", None)


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


def _emit(arguments, value, render):
    """Render a command result as JSON or human text.

    Under ``--json`` the twin's return ``value`` is printed as one
    JSON document on stdout (a void twin passes ``{}``); otherwise
    ``render()`` prints the human form. Returns exit code 0.
    """
    if getattr(arguments, "json", False):
        print(json.dumps(value, default=str))
    else:
        render()
    return 0


def _reject_stream_json(arguments, command):
    """Stream-bearing commands reject ``--json`` (they are event streams)."""
    if getattr(arguments, "json", False):
        raise ValueError(
            f"{command} is a stream, not a document; use "
            "--progress jsonl for machine-readable output")


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

    # apply-blueprint
    command = subcommands.add_parser(
        "apply-blueprint",
        help="adopt blueprint edits into a stopped machine")
    _add_selectors(command)

    # get-machine-dir
    command = subcommands.add_parser(
        "get-machine-dir",
        help="print a machine's cache directory (out-of-band door)")
    _add_selectors(command)

    # run-script
    command = subcommands.add_parser(
        "run-script", help="run a labeled .rlqs script")
    _add_selectors(command)
    command.add_argument("label", help="script label or stem")
    command.add_argument("--display", action="store_true")

    # check-script
    command = subcommands.add_parser(
        "check-script", help="check a script")
    _add_selectors(command)
    command.add_argument("name", help="script name")

    # fetch-media
    command = subcommands.add_parser(
        "fetch-media", help="fetch media")
    _add_home(command)
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
    command.add_argument("key")

    command = subcommands.add_parser(
        "set-property", help="set a property")
    _add_home(command)
    command.add_argument("key")
    command.add_argument("value")
    command.add_argument("--secret", action="store_true")

    command = subcommands.add_parser(
        "unset-property", help="unset a property")
    _add_home(command)
    command.add_argument("key")

    command = subcommands.add_parser(
        "list-properties", help="list properties")
    _add_home(command)

    # import-vm
    command = subcommands.add_parser(
        "import-vm", help="import a VM as a blueprint")
    _add_home(command)
    command.add_argument("source")
    command.add_argument("--name", required=True)

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
        "add-media", help="supply a payload nothing can locate")
    _add_home(command)
    command.add_argument("name", help="the media the file supplies")
    command.add_argument("file", help="the payload file")

    # state ops
    command = subcommands.add_parser(
        "insert-media", help="insert media into a drive slot")
    _add_selectors(command)
    command.add_argument("slot")
    command.add_argument("media")

    command = subcommands.add_parser(
        "eject-media", help="eject media from a drive slot")
    _add_selectors(command)
    command.add_argument("slot")

    command = subcommands.add_parser(
        "set-boot-order", help="set the machine boot order")
    _add_selectors(command)
    command.add_argument("keys", nargs="+")

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
    except ScriptParseError as error:
        print(f"reliquary: error: {error}", file=sys.stderr)
        return 2
    except (ConnectError, ConnectionError) as error:
        target = (f"127.0.0.1:{arguments.port}"
                  if getattr(arguments, "port", None)
                  else "the active VM")
        print(f"reliquary: cannot reach QMP on {target}: {error}\n"
              "is the VM running? "
              "(rlq start-machine --blueprint NAME)",
              file=sys.stderr)
        return 1
    except (ScriptRuntimeError, RuntimeError, TimeoutError,
            FileNotFoundError, NotImplementedError, ValueError,
            OSError, KeyError) as error:
        print(f"reliquary: error: {error}", file=sys.stderr)
        return 1


def _create(arguments):
    if getattr(arguments, "machine", None):
        raise ValueError(
            "create-machine allocates the machine number; "
            "do not pass --machine")
    machine_id = create_machine(arguments.blueprint)
    return _emit(arguments, machine_id,
                 lambda: print(f"created machine {machine_id}"))


def _recreate_machine(arguments):
    machine_id = recreate_machine(
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None))
    return _emit(arguments, machine_id,
                 lambda: print(f"recreated machine {machine_id}"))


def _get_machine_dir(arguments):
    machine_id = _require_machine_selector(arguments)
    path = get_machine_dir(machine=machine_id)
    return _emit(arguments, path, lambda: print(path))


def _apply_blueprint(arguments):
    machine_id = apply_blueprint(
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None))
    return _emit(arguments, machine_id,
                 lambda: print(f"applied blueprint to machine {machine_id}"))


def _script(arguments):
    _reject_stream_json(arguments, "run-script")
    blueprint_name = getattr(arguments, "blueprint", None)
    machine_selector = getattr(arguments, "machine", None)
    if not blueprint_name and not machine_selector:
        raise ValueError(
            "run-script requires --blueprint or --machine")
    try:
        result = run_script(
            arguments.label,
            blueprint=blueprint_name,
            machine=machine_selector,
            display=arguments.display,
        )
    except KeyboardInterrupt:
        print("reliquary: interrupted", file=sys.stderr)
        return 130
    if result.created_machine:
        print(f"created machine {result.machine_id}")
    print(f"ran {os.path.basename(result.script_path)} "
          f"on machine {result.machine_id}")
    print(f"final script phase: {result.final_phase}")
    print(f"machine phase: {result.machine_phase}")
    print(f"run: {result.run_dir}")
    return 0


def _check_script(arguments):
    result = check_script(
        arguments.name,
        blueprint=getattr(arguments, "blueprint", None),
        machine=getattr(arguments, "machine", None),
    )
    return _emit(arguments, {"report": result.report},
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
    _reject_stream_json(arguments, "fetch-media")
    fetch_media(arguments.name)
    print(f"fetched {arguments.name}")
    return 0


def _seed(arguments, seeder, kind):
    seeded = seeder(arguments.name, only=getattr(arguments, "only", False))
    message = (f"seeded {kind} {arguments.name}" if seeded
               else f"{kind} {arguments.name} already exists or not found")
    return _emit(arguments, seeded, lambda: print(message))


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
    return _emit(arguments, path,
                 lambda: print(f"created blueprint {arguments.name} "
                               f"at {path}"))


def _delete_blueprint(arguments):
    path = blueprint_mod.delete_blueprint(arguments.name)
    return _emit(
        arguments, path,
        lambda: print(f"deleted blueprint {arguments.name} ({path})"))


def _get_property(arguments):
    value = get_property(arguments.key)

    def render():
        if value is not None:
            print(value)
    return _emit(arguments, value, render)


def _set_property(arguments):
    set_property(arguments.key, arguments.value, secret=arguments.secret)
    return _emit(arguments, {}, lambda: None)


def _unset_property(arguments):
    unset_property(arguments.key)
    return _emit(arguments, {}, lambda: None)


def _list_properties(arguments):
    properties = list_properties()

    def render():
        if not properties:
            return
        key_width = max(len(key) for key in properties)
        for key, value in sorted(properties.items()):
            print(f"{key:<{key_width}}  {value}")
    return _emit(arguments, properties, render)


def _import_vm(arguments):
    raise NotImplementedError("import-vm is not yet implemented")


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
    path = add_media(arguments.name, arguments.file)
    return _emit(
        arguments, path,
        lambda: print(f"supplied {arguments.name} ({path})"))


def _insert_media(arguments):
    machine_id = _require_machine_selector(arguments)
    insert_media(machine_id, arguments.slot, arguments.media)
    return _emit(
        arguments, {},
        lambda: print(f"inserted {arguments.media} into {arguments.slot} "
                      f"on {machine_id}"))


def _eject_media(arguments):
    machine_id = _require_machine_selector(arguments)
    eject_media(machine_id, arguments.slot)
    return _emit(arguments, {},
                 lambda: print(f"ejected {arguments.slot} on {machine_id}"))


def _set_boot_order(arguments):
    machine_id = _require_machine_selector(arguments)
    set_boot_order(machine_id, arguments.keys)
    return _emit(
        arguments, {},
        lambda: print(f"boot order on {machine_id}: "
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
    if arguments.command == "import-vm":
        return _import_vm(arguments)
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
    if arguments.command == "start-machine":
        machine_id = _require_machine_selector(arguments)
        started_port = start_machine(
            machine_id, display=getattr(arguments, "display", False))
        return _emit(arguments, started_port, lambda: None)
    if arguments.command == "stop-machine":
        machine_id = _require_machine_selector(arguments)
        stop_machine(machine_id)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "destroy-machine":
        machine_id = _require_machine_selector(arguments)
        destroy_machine(machine_id)
        return _emit(arguments, {},
                     lambda: print(f"destroyed machine {machine_id}"))
    if arguments.command == "recreate-machine":
        return _recreate_machine(arguments)
    if arguments.command == "apply-blueprint":
        return _apply_blueprint(arguments)
    if arguments.command == "get-machine-dir":
        return _get_machine_dir(arguments)

    interaction_port = _interaction_port(arguments)
    if arguments.command == "type":
        send_text(arguments.text, enter=False, port=interaction_port)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "enter":
        send_text(arguments.line, enter=True, port=interaction_port)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "press":
        combos = [_resolve_key(name) for name in arguments.names]
        send_keys(combos, interaction_port)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "exec":
        if platform != "dos":
            raise NotImplementedError("exec requires platform='dos'")
        AgentlessGuestExec(Machine(interaction_port)).execute(
            arguments.dos_command, timeout or 120)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "select":
        selected = cursor_menu_select(
            arguments.item, timeout or 30,
            getattr(arguments, "exclude", []), interaction_port)
        return _emit(arguments, selected,
                     lambda: print(f"selected: {selected}"))
    if arguments.command == "screen":
        rows = screen_text(interaction_port)
        return _emit(arguments, rows, lambda: print("\n".join(rows)))
    if arguments.command == "wait":
        wait_text(arguments.pattern, timeout or 60, interaction_port)
        return _emit(arguments, {}, lambda: print("matched."))
    if arguments.command == "screenshot":
        screenshot(arguments.name, interaction_port)
        return _emit(arguments, {}, lambda: None)
    if arguments.command == "hmp":
        with Machine(interaction_port).qmp() as qmp:
            output = qmp.hmp(arguments.line)
        return _emit(arguments, output, lambda: print(output))
    return 0
