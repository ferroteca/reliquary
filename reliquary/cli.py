# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Command-line parsing and dispatch."""

import argparse
import importlib.metadata
import os
import sys

try:
    _version = importlib.metadata.version("reliquary")
except importlib.metadata.PackageNotFoundError:
    _version = "unknown"

from qemu.qmp import ConnectError

from .interaction_agentless import AgentlessGuestExec
from .lifecycle import stop as stop_legacy
from .machine import (Machine, cursor_menu_select, screen_text,
                      screenshot, send_keys, send_text, wait_text)
from .home import blueprints_dir, scripts_dir, set_home
from .library import list_builtin_blueprints, seed_blueprint
from . import blueprint as blueprint_mod
from .machines import (create_from_blueprint, destroy, list_machines,
                       resolve_machine, split_machine_id,
                       start as start_machine,
                       stop as stop_machine)
from .script_runner import ScriptRuntimeError, run_script
from .script import ScriptParseError, load_script
from .workflows import _cli_machine_config, start as start_legacy


def _cli_start_overrides(arguments):
    """CLI controls that override a loaded machine configuration."""
    overrides = {}
    if arguments.platform is not None:
        overrides["platform"] = arguments.platform
    if arguments.qemu is not None:
        overrides["qemu"] = arguments.qemu
    if getattr(arguments, "qemu_args", None):
        overrides["qemu_args"] = arguments.qemu_args
    return overrides


def _require_machine_selector(arguments):
    """Return a resolved machine id from global selectors."""
    if not arguments.blueprint and not arguments.machine:
        raise ValueError(
            "select a machine with --blueprint or --machine")
    return resolve_machine(
        machine=arguments.machine,
        blueprint=arguments.blueprint,
        home=arguments.home,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="rlq",
        description="OS installation scripting over QEMU guest "
                    "automation (DOS by default)")
    parser.add_argument(
        "--version", action="version",
        version="%(prog)s " + _version)
    parser.add_argument("--home", help="reliquary home directory (drives/, "
                        "screenshots/); default: $RELIQUARY_HOME, then "
                        "Documents/reliquary")
    parser.add_argument(
        "--blueprint",
        help="select a blueprint's sole machine, or combine with "
             "--machine <n>; names the blueprint for create / list")
    parser.add_argument(
        "--machine",
        help="select a machine by id (<blueprint>-<n>), unambiguous "
             "id prefix, or number with --blueprint")
    parser.add_argument("--port", type=int,
                        help="QMP port (legacy interaction commands; "
                             "new lifecycle stores port per machine)")
    parser.add_argument("--qemu", help="path to the QEMU binary (default: "
                        "$RELIQUARY_QEMU_HOME, then $QEMU_HOME, then PATH, "
                        "then well-known install locations)")
    parser.add_argument("--platform", default=None,
                        help="guest platform adapter (default: dos; other "
                             "platform workflows are not implemented yet)")
    parser.add_argument("--timeout", type=int, help="seconds to wait "
                        "(defaults: run 120, wait 60)")
    subcommands = parser.add_subparsers(dest="command", required=True)

    command = subcommands.add_parser(
        "create",
        help="materialize a machine from a blueprint")

    command = subcommands.add_parser(
        "start",
        help="start a machine (--blueprint/--machine, or legacy "
             "root-home machine.json)")
    # SUPPRESS keeps an omitted subcommand --home from clobbering the
    # already-parsed global --home in the shared namespace.
    command.add_argument("--home", default=argparse.SUPPRESS,
                         help="reliquary home directory")
    command.add_argument(
        "--blueprint", default=argparse.SUPPRESS,
        help="select a blueprint's sole machine, or combine with "
             "--machine <n>")
    command.add_argument(
        "--machine", default=argparse.SUPPRESS,
        help="select by id (<blueprint>-<n>), prefix, or number "
             "with --blueprint")
    command.add_argument("--display", action="store_true")
    command.add_argument(
        "qemu_args", nargs="*",
        help=argparse.SUPPRESS)

    command = subcommands.add_parser(
        "stop",
        help="stop a machine (--blueprint/--machine, or legacy "
             "root-home vm.json)")
    command.add_argument("--home", default=argparse.SUPPRESS,
                         help="reliquary home directory")
    command.add_argument(
        "--blueprint", default=argparse.SUPPRESS,
        help="select a blueprint's sole machine, or combine with "
             "--machine <n>")
    command.add_argument(
        "--machine", default=argparse.SUPPRESS,
        help="select by id (<blueprint>-<n>), prefix, or number "
             "with --blueprint")
    command = subcommands.add_parser(
        "destroy",
        help="delete a stopped machine "
             "(requires --blueprint or --machine)")
    command.add_argument("--home", default=argparse.SUPPRESS,
                         help="reliquary home directory")
    command.add_argument(
        "--blueprint", default=argparse.SUPPRESS,
        help="select a blueprint's sole machine, or combine with "
             "--machine <n>")
    command.add_argument(
        "--machine", default=argparse.SUPPRESS,
        help="select by id (<blueprint>-<n>), prefix, or number "
             "with --blueprint")

    command = subcommands.add_parser(
        "script",
        help="run a labeled .rlqs script against a machine "
             "(creates one when --blueprint has none)")
    command.add_argument(
        "label",
        help="blueprint scripts-map label, or bare script stem")
    command.add_argument(
        "--display", action="store_true",
        help="show the QEMU window during guest steps")

    list_command = subcommands.add_parser(
        "list", help="list blueprints or machines")
    list_sub = list_command.add_subparsers(dest="list_what", required=True)
    list_bps_parser = list_sub.add_parser(
        "blueprints", aliases=["blueprint"],
        help="list available blueprints")
    list_bps_parser.add_argument(
        "--builtin", action="store_true",
        help="list only built-in blueprints")
    list_machines_parser = list_sub.add_parser(
        "machines", aliases=["machine"],
        help="list materialized machines")
    list_machines_parser.add_argument(
        "--blueprint", dest="filter_blueprint",
        help="show only machines of this blueprint")
    list_scripts_parser = list_sub.add_parser(
        "scripts", aliases=["script"],
        help="list scripts (shared scripts/ by default; "
             "--blueprint lists a blueprint's own scripts)")
    list_scripts_parser.add_argument(
        "--blueprint", dest="list_scripts_blueprint",
        help="blueprint whose scripts to list (omit for shared "
             "scripts/)")

    command = subcommands.add_parser("type")
    command.add_argument("text")
    command = subcommands.add_parser("run")
    command.add_argument("dos_command")
    command = subcommands.add_parser("keys")
    command.add_argument("names", nargs="+")
    command = subcommands.add_parser("menu")
    command.add_argument("item")
    command.add_argument("--exclude", action="append", default=[],
                         metavar="TEXT",
                         help="never select rows containing TEXT "
                              "(repeatable)")
    subcommands.add_parser("text")
    command = subcommands.add_parser("wait")
    command.add_argument("pattern")
    command = subcommands.add_parser("screenshot")
    command.add_argument("name", nargs="?", default="screen")
    command = subcommands.add_parser("hmp")
    command.add_argument("line")

    arguments = parser.parse_args(argv)
    if arguments.home:
        set_home(arguments.home)
    try:
        return _dispatch(arguments)
    except (ConnectError, ConnectionError) as error:
        target = (f"127.0.0.1:{arguments.port}"
                  if arguments.port else "the active VM")
        print(f"reliquary: cannot reach QMP on {target}: {error}\n"
              "is the VM running? (rlq --blueprint NAME start)",
              file=sys.stderr)
        return 1
    except (ScriptRuntimeError, RuntimeError, TimeoutError,
            FileNotFoundError, NotImplementedError, ValueError,
            OSError) as error:
        print(f"reliquary: error: {error}", file=sys.stderr)
        return 1


def _create(arguments):
    if not arguments.blueprint:
        raise ValueError("create requires --blueprint")
    if arguments.machine:
        raise ValueError(
            "create allocates the machine number; do not pass --machine")
    machine_id = create_from_blueprint(
        arguments.blueprint, home=arguments.home)
    print(f"created machine {machine_id}")
    return 0


def _script(arguments):
    if not arguments.blueprint and not arguments.machine:
        raise ValueError(
            "script requires --blueprint or --machine")
    try:
        result = run_script(
            arguments.label,
            blueprint=arguments.blueprint,
            machine=arguments.machine,
            home=arguments.home,
            display=arguments.display,
        )
    except KeyboardInterrupt:
        print("reliquary: interrupted", file=sys.stderr)
        return 130
    if result.created_machine:
        print(f"created machine {result.machine_id}")
    print(f"ran {os.path.basename(result.script_path)} "
          f"on machine {result.machine_id}")
    print(f"run: {result.run_dir}")
    return 0


def _list_blueprints(arguments):
    if getattr(arguments, "builtin", False):
        for name in list_builtin_blueprints():
            print(name)
        return 0
    blueprints_path = blueprints_dir(arguments.home)
    if not os.path.exists(blueprints_path):
        return 0
    for entry in sorted(os.listdir(blueprints_path)):
        if entry.endswith(".json"):
            print(entry[:-5])
    return 0


def _list_machines(arguments):
    filter_blueprint = (
        getattr(arguments, "filter_blueprint", None)
        or arguments.blueprint)
    machines = list_machines(
        home=arguments.home, blueprint=filter_blueprint)
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
    return 0


def _list_scripts(arguments):
    blueprint_name = (getattr(arguments, "list_scripts_blueprint", None)
                      or arguments.blueprint)
    if blueprint_name:
        bp_path = os.path.join(blueprints_dir(arguments.home),
                               f"{blueprint_name}.json")
        if not os.path.exists(bp_path):
            seed_blueprint(blueprint_name, home=arguments.home)
        bp = blueprint_mod.load_blueprint(bp_path, home=arguments.home)
        scripts = bp.scripts
        if not scripts:
            print(f"(blueprint {blueprint_name} declares no scripts)")
            return 0
        label_width = max(
            [4] + [len(label) for label in scripts],
            default=4)
        print(f"{'NAME':<{label_width}}  DESCRIPTION")
        for label, stem in scripts.items():
            script_path = os.path.join(scripts_dir(arguments.home),
                                       f"{stem}.rlqs")
            try:
                script = load_script(script_path)
            except (FileNotFoundError, ScriptParseError) as error:
                description = f"(error: {error})"
            else:
                description = script.description or "-"
            print(f"{label:<{label_width}}  {description}")
        return 0
    _print_scripts_in_dir(scripts_dir(arguments.home))
    return 0


def _print_scripts_in_dir(scripts_path):
    if not os.path.isdir(scripts_path):
        print(f"(no scripts directory: {scripts_path})")
        return 0
    stems = sorted(
        entry[:-5] for entry in os.listdir(scripts_path)
        if entry.endswith(".rlqs")
    )
    if not stems:
        print(f"(no scripts in {scripts_path})")
        return 0
    label_width = max(
        [4] + [len(stem) for stem in stems],
        default=4)
    print(f"{'NAME':<{label_width}}  DESCRIPTION")
    for stem in stems:
        script_path = os.path.join(scripts_path, f"{stem}.rlqs")
        try:
            script = load_script(script_path)
        except (FileNotFoundError, ScriptParseError) as error:
            description = f"(error: {error})"
        else:
            description = script.description or "-"
        print(f"{stem:<{label_width}}  {description}")
    return 0


def _dispatch(arguments):
    platform = arguments.platform or "dos"
    if arguments.command == "create":
        return _create(arguments)
    if arguments.command == "script":
        return _script(arguments)
    if arguments.command == "list":
        if arguments.list_what in ("blueprints", "blueprint"):
            return _list_blueprints(arguments)
        if arguments.list_what in ("machines", "machine"):
            return _list_machines(arguments)
        if arguments.list_what in ("scripts", "script"):
            return _list_scripts(arguments)
        raise ValueError(f"unknown list target: {arguments.list_what}")
    if arguments.command == "start":
        if arguments.blueprint or arguments.machine:
            machine_id = _require_machine_selector(arguments)
            start_machine(
                machine_id, display=arguments.display,
                home=arguments.home)
            return 0
        # Legacy root-home start (MachineConfig / machine.json).
        config = _cli_machine_config(
            None, arguments.home,
            **_cli_start_overrides(arguments))
        start_legacy(
            config, display=arguments.display, port=arguments.port)
        return 0
    if arguments.command == "stop":
        if arguments.blueprint or arguments.machine:
            machine_id = _require_machine_selector(arguments)
            stop_machine(machine_id, home=arguments.home)
            return 0
        stop_legacy(arguments.port)
        return 0
    if arguments.command == "destroy":
        machine_id = _require_machine_selector(arguments)
        destroy(machine_id, home=arguments.home)
        print(f"destroyed machine {machine_id}")
        return 0
    if arguments.command == "type":
        send_text(arguments.text, arguments.port)
    elif arguments.command == "run":
        if platform != "dos":
            raise NotImplementedError("run requires platform='dos'")
        AgentlessGuestExec(Machine(arguments.port)).execute(
            arguments.dos_command, arguments.timeout or 120)
    elif arguments.command == "keys":
        send_keys([[key] for key in arguments.names], arguments.port)
    elif arguments.command == "menu":
        selected = cursor_menu_select(
            arguments.item, arguments.timeout or 30,
            arguments.exclude, arguments.port)
        print(f"selected: {selected}")
    elif arguments.command == "text":
        print("\n".join(screen_text(arguments.port)))
    elif arguments.command == "wait":
        wait_text(arguments.pattern, arguments.timeout or 60,
                  arguments.port)
        print("matched.")
    elif arguments.command == "screenshot":
        screenshot(arguments.name, arguments.port)
    elif arguments.command == "hmp":
        with Machine(arguments.port).qmp() as qmp:
            print(qmp.hmp(arguments.line))
    return 0
