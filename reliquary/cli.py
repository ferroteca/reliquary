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
from .library import (list_builtin_blueprints, seed_blueprint,
                      seed_media, seed_script)
from . import blueprint as blueprint_mod
from .machines import (create_machine, destroy_machine, list_machines,
                       resolve_machine, split_machine_id,
                       start_machine,
                       stop_machine)
from .media import (fetch_media, clean_downloads, clean_media)
from .properties import (get_property, set_property, unset_property,
                         list_properties)
from .script_runner import (ScriptRuntimeError, check_script, run_script)
from .script_nodes import ScriptParseError
from .script_parser import load_script
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
    if not getattr(arguments, "blueprint", None) and not getattr(arguments, "machine", None):
        raise ValueError(
            "select a machine with --blueprint or --machine")
    return resolve_machine(
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None),
        home=getattr(arguments, "home", None),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="rlq",
        description="OS installation scripting over QEMU guest "
                    "automation (DOS by default)",
        conflict_handler="resolve")
    parser.add_argument(
        "--version", action="version",
        version="%(prog)s " + _version)

    # Global-ish flags that we want to accept before the subcommand
    parser.add_argument("--home", help=argparse.SUPPRESS)
    parser.add_argument("--blueprint", help=argparse.SUPPRESS)
    parser.add_argument("--machine", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--qemu", help=argparse.SUPPRESS)
    parser.add_argument("--platform", help=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=int, help=argparse.SUPPRESS)

    subcommands = parser.add_subparsers(dest="command", required=True)

    def add_common(cmd_parser):
        cmd_parser.add_argument(
            "--home", default=argparse.SUPPRESS,
            help="reliquary home directory")
        cmd_parser.add_argument(
            "--blueprint", default=argparse.SUPPRESS,
            help="select blueprint")
        cmd_parser.add_argument(
            "--machine", default=argparse.SUPPRESS,
            help="select machine")
        return cmd_parser

    # create-machine
    command = subcommands.add_parser(
        "create-machine",
        help="materialize a machine from a blueprint",
        conflict_handler="resolve")
    add_common(command)

    # start-machine
    command = subcommands.add_parser(
        "start-machine",
        help="start a machine",
        conflict_handler="resolve")
    add_common(command)
    command.add_argument("--display", action="store_true")
    command.add_argument("--port", type=int, default=argparse.SUPPRESS, help="QMP port")
    command.add_argument("--qemu", default=argparse.SUPPRESS, help="QEMU path")
    command.add_argument("--platform", default=argparse.SUPPRESS, help="guest platform")
    command.add_argument("qemu_args", nargs="*", help=argparse.SUPPRESS)

    # stop-machine
    command = subcommands.add_parser(
        "stop-machine",
        help="stop a machine",
        conflict_handler="resolve")
    add_common(command)
    command.add_argument("--port", type=int, default=argparse.SUPPRESS, help="QMP port")

    # destroy-machine
    command = subcommands.add_parser(
        "destroy-machine",
        help="delete a stopped machine",
        conflict_handler="resolve")
    add_common(command)

    # run-script
    command = subcommands.add_parser(
        "run-script",
        help="run a labeled .rlqs script",
        conflict_handler="resolve")
    add_common(command)
    command.add_argument("label", help="script label or stem")
    command.add_argument("--display", action="store_true")

    # check-script
    command = subcommands.add_parser(
        "check-script",
        help="check a script",
        conflict_handler="resolve")
    add_common(command)
    command.add_argument("name", help="script name")

    # fetch-media
    command = subcommands.add_parser(
        "fetch-media",
        help="fetch media",
        conflict_handler="resolve")
    add_common(command)
    command.add_argument("name", help="media name")

    # seed-*
    for kind in ["blueprint", "media", "script"]:
        command = subcommands.add_parser(
            f"seed-{kind}",
            help=f"copy built-in {kind} to home",
            conflict_handler="resolve")
        add_common(command)
        command.add_argument("name", help=f"built-in {kind} name")

    # new-blueprint
    command = subcommands.add_parser(
        "new-blueprint",
        help="create new blueprint",
        conflict_handler="resolve")
    add_common(command)
    command.add_argument("name", help="blueprint name")
    command.add_argument("--platform", help="guest platform")

    # property family
    command = subcommands.add_parser("get-property", help="get property",
                                     conflict_handler="resolve")
    add_common(command)
    command.add_argument("key")

    command = subcommands.add_parser("set-property", help="set property",
                                     conflict_handler="resolve")
    add_common(command)
    command.add_argument("key")
    command.add_argument("value")
    command.add_argument("--secret", action="store_true")

    command = subcommands.add_parser("unset-property", help="unset property",
                                     conflict_handler="resolve")
    add_common(command)
    command.add_argument("key")

    command = subcommands.add_parser("list-properties", help="list properties",
                                     conflict_handler="resolve")
    add_common(command)

    # import-vm
    command = subcommands.add_parser("import-vm", help="import VM",
                                     conflict_handler="resolve")
    add_common(command)
    command.add_argument("source")
    command.add_argument("--name", required=True)

    # list
    list_command = subcommands.add_parser("list", help="list things",
                                          conflict_handler="resolve")
    add_common(list_command)
    list_sub = list_command.add_subparsers(dest="list_what", required=True)

    list_bps = list_sub.add_parser("blueprints", aliases=["blueprint"],
                                   conflict_handler="resolve")
    list_bps.add_argument("--builtin", action="store_true")

    list_machines = list_sub.add_parser("machines", aliases=["machine"],
                                        conflict_handler="resolve")
    list_machines.add_argument("--blueprint", dest="filter_blueprint")

    list_scripts = list_sub.add_parser("scripts", aliases=["script"],
                                       conflict_handler="resolve")
    list_scripts.add_argument("--blueprint", dest="list_scripts_blueprint")

    # dashed list aliases
    command = subcommands.add_parser("list-blueprints", help=argparse.SUPPRESS,
                                     conflict_handler="resolve")
    add_common(command)
    command.add_argument("--builtin", action="store_true")

    command = subcommands.add_parser("list-machines", help=argparse.SUPPRESS,
                                     conflict_handler="resolve")
    add_common(command)
    command.add_argument("--blueprint", dest="filter_blueprint")

    command = subcommands.add_parser("list-scripts", help=argparse.SUPPRESS,
                                     conflict_handler="resolve")
    add_common(command)
    command.add_argument("--blueprint", dest="list_scripts_blueprint")

    # interaction
    command = subcommands.add_parser("type", conflict_handler="resolve")
    add_common(command)
    command.add_argument("text")
    command.add_argument("--port", type=int)

    command = subcommands.add_parser("run", conflict_handler="resolve")
    add_common(command)
    command.add_argument("dos_command")
    command.add_argument("--port", type=int)
    command.add_argument("--timeout", type=int)

    command = subcommands.add_parser("keys", conflict_handler="resolve")
    add_common(command)
    command.add_argument("names", nargs="+")
    command.add_argument("--port", type=int)

    command = subcommands.add_parser("menu", conflict_handler="resolve")
    add_common(command)
    command.add_argument("item")
    command.add_argument("--exclude", action="append", default=[])
    command.add_argument("--port", type=int)
    command.add_argument("--timeout", type=int)

    command = subcommands.add_parser("text", conflict_handler="resolve")
    add_common(command)
    command.add_argument("--port", type=int)
    command = subcommands.add_parser("wait", conflict_handler="resolve")
    add_common(command)
    command.add_argument("pattern")
    command.add_argument("--port", type=int)
    command.add_argument("--timeout", type=int)

    command = subcommands.add_parser("screenshot", conflict_handler="resolve")
    add_common(command)
    command.add_argument("name", nargs="?", default="screen")
    command.add_argument("--port", type=int)

    command = subcommands.add_parser("hmp", conflict_handler="resolve")
    add_common(command)
    command.add_argument("line")
    command.add_argument("--port", type=int)

    arguments = parser.parse_args(argv)
    if arguments.home:
        set_home(arguments.home)
    try:
        return _dispatch(arguments)
    except ScriptParseError as error:
        print(f"reliquary: error: {error}", file=sys.stderr)
        return 2
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
    blueprint_name = getattr(arguments, "blueprint", None)
    if not blueprint_name:
        raise ValueError("create-machine requires --blueprint")
    if getattr(arguments, "machine", None):
        raise ValueError(
            "create-machine allocates the machine number; "
            "do not pass --machine")
    machine_id = create_machine(
        blueprint_name, home=arguments.home)
    print(f"created machine {machine_id}")
    return 0


def _script(arguments):
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
    print(f"final script phase: {result.final_phase}")
    print(f"machine phase: {result.machine_phase}")
    print(f"run: {result.run_dir}")
    return 0


def _check_script(arguments):
    result = check_script(
        arguments.name,
        blueprint=getattr(arguments, "blueprint", None),
        machine=getattr(arguments, "machine", None),
        home=arguments.home,
    )
    print(result.report, end="")
    return 0


def _list_blueprints(arguments):
    if getattr(arguments, "builtin", False):
        names = list_builtin_blueprints()
        if not names:
            print("(no built-in blueprints)")
            return 0
        for name in names:
            print(name)
        return 0
    blueprints_path = blueprints_dir(arguments.home)
    names = []
    if os.path.exists(blueprints_path):
        names = sorted(
            entry[:-5] for entry in os.listdir(blueprints_path)
            if entry.endswith(".json"))
    if not names:
        print(f"(no blueprints in {blueprints_path})")
        return 0
    for name in names:
        print(name)
    return 0


def _list_machines(arguments):
    filter_blueprint = (
        getattr(arguments, "filter_blueprint", None)
        or getattr(arguments, "blueprint", None))
    machines = list_machines(
        home=arguments.home, blueprint=filter_blueprint)
    if not machines:
        if filter_blueprint:
            print(f"(no machines for blueprint {filter_blueprint})")
        else:
            print("(no machines)")
        return 0
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


def _description(script):
    """A script's description as one line of listing text."""
    if script.description is None:
        return "-"
    # A listing binds no properties, so any reference is shown as
    # the author wrote it.
    return script.description.spelling


def _list_scripts(arguments):
    blueprint_name = (getattr(arguments, "list_scripts_blueprint", None)
                      or getattr(arguments, "blueprint", None))
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
            [5] + [len(label) for label in scripts],
            default=5)
        print(f"{'LABEL':<{label_width}}  DESCRIPTION")
        for label, stem in scripts.items():
            script_path = os.path.join(scripts_dir(arguments.home),
                                       f"{stem}.rlqs")
            try:
                script = load_script(script_path)
            except (FileNotFoundError, ScriptParseError) as error:
                description = f"(error: {error})"
            else:
                description = _description(script)
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
            description = _description(script)
        print(f"{stem:<{label_width}}  {description}")
    return 0


def _fetch_media(arguments):
    fetch_media(arguments.name, home=arguments.home)
    print(f"fetched {arguments.name}")
    return 0


def _seed_blueprint(arguments):
    if seed_blueprint(arguments.name, home=arguments.home):
        print(f"seeded blueprint {arguments.name}")
    else:
        print(f"blueprint {arguments.name} already exists or not found")
    return 0


def _seed_media(arguments):
    if seed_media(arguments.name, home=arguments.home):
        print(f"seeded media {arguments.name}")
    else:
        print(f"media {arguments.name} already exists or not found")
    return 0


def _seed_script(arguments):
    if seed_script(arguments.name, home=arguments.home):
        print(f"seeded script {arguments.name}")
    else:
        print(f"script {arguments.name} already exists or not found")
    return 0


def _new_blueprint(arguments):
    path = blueprint_mod.new_blueprint(
        arguments.name, platform=arguments.platform or "dos",
        home=arguments.home)
    print(f"created blueprint {arguments.name} at {path}")
    return 0


def _get_property(arguments):
    value = get_property(arguments.key, home=arguments.home)
    if value is not None:
        print(value)
    return 0


def _set_property(arguments):
    set_property(
        arguments.key, arguments.value, secret=arguments.secret,
        home=arguments.home)
    return 0


def _unset_property(arguments):
    unset_property(arguments.key, home=arguments.home)
    return 0


def _list_properties(arguments):
    properties = list_properties(home=arguments.home)
    if not properties:
        return 0
    key_width = max(len(key) for key in properties)
    for key, value in sorted(properties.items()):
        print(f"{key:<{key_width}}  {value}")
    return 0


def _import_vm(arguments):
    raise NotImplementedError("import-vm is not yet implemented")


def _dispatch(arguments):
    platform = getattr(arguments, "platform", None) or "dos"
    port = getattr(arguments, "port", None)
    timeout = getattr(arguments, "timeout", None)
    home = getattr(arguments, "home", None)
    blueprint = getattr(arguments, "blueprint", None)
    machine = getattr(arguments, "machine", None)

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
    if arguments.command == "seed-media":
        return _seed_media(arguments)
    if arguments.command == "seed-script":
        return _seed_script(arguments)
    if arguments.command == "new-blueprint":
        return _new_blueprint(arguments)
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
    if arguments.command in ("list-blueprints", "list-machines", "list-scripts"):
        arguments.list_what = arguments.command.split("-")[1]
        if arguments.list_what == "blueprints":
            return _list_blueprints(arguments)
        if arguments.list_what == "machines":
            return _list_machines(arguments)
        if arguments.list_what == "scripts":
            return _list_scripts(arguments)
    if arguments.command == "list":
        if arguments.list_what in ("blueprints", "blueprint"):
            return _list_blueprints(arguments)
        if arguments.list_what in ("machines", "machine"):
            return _list_machines(arguments)
        if arguments.list_what in ("scripts", "script"):
            return _list_scripts(arguments)
        raise ValueError(f"unknown list target: {arguments.list_what}")
    if arguments.command == "start-machine":
        if blueprint or machine:
            machine_id = _require_machine_selector(arguments)
            start_machine(
                machine_id, display=getattr(arguments, "display", False),
                home=home)
            return 0
        # Legacy root-home start (MachineConfig / machine.json).
        config = _cli_machine_config(
            None, home,
            **_cli_start_overrides(arguments))
        start_legacy(
            config, display=getattr(arguments, "display", False), port=port)
        return 0
    if arguments.command == "stop-machine":
        if blueprint or machine:
            machine_id = _require_machine_selector(arguments)
            stop_machine(machine_id, home=home)
            return 0
        stop_legacy(port)
        return 0
    if arguments.command == "destroy-machine":
        machine_id = _require_machine_selector(arguments)
        destroy_machine(machine_id, home=home)
        print(f"destroyed machine {machine_id}")
        return 0
    if arguments.command == "type":
        send_text(arguments.text, port)
    elif arguments.command == "run":
        if platform != "dos":
            raise NotImplementedError("run requires platform='dos'")
        AgentlessGuestExec(Machine(port)).execute(
            arguments.dos_command, timeout or 120)
    elif arguments.command == "keys":
        send_keys([[key] for key in arguments.names], port)
    elif arguments.command == "menu":
        selected = cursor_menu_select(
            arguments.item, timeout or 30,
            getattr(arguments, "exclude", []), port)
        print(f"selected: {selected}")
    elif arguments.command == "text":
        print("\n".join(screen_text(port)))
    elif arguments.command == "wait":
        wait_text(arguments.pattern, timeout or 60,
                  port)
        print("matched.")
    elif arguments.command == "screenshot":
        screenshot(arguments.name, port)
    elif arguments.command == "hmp":
        with Machine(port).qmp() as qmp:
            print(qmp.hmp(arguments.line))
    return 0
