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
from .lifecycle import read_vm_state, stop as stop_legacy
from .machine import (Machine, cursor_menu_select, screen_text,
                      screenshot, send_keys, send_text, wait_text)
from .home import blueprints_dir, scripts_dir, set_home
from .library import (list_builtin_blueprints, seed_blueprint,
                      seed_media, seed_script)
from . import blueprint as blueprint_mod
from .machines import (create_machine, destroy_machine, eject_media,
                       insert_media, list_machines, load_machine_state,
                       machine_dir_path, resolve_machine,
                       set_boot_order, split_machine_id,
                       start_machine, stop_machine)
from .media import (fetch_media, clean_downloads, clean_media)
from .properties import (get_property, set_property, unset_property,
                         list_properties)
from .script_runner import (ScriptRuntimeError, check_script,
                            run_script, _resolve_key)
from .script_nodes import ScriptParseError
from .script_parser import load_script
from .workflows import _cli_machine_config, start as start_legacy


# Command words recognised when rewriting leading flags so that
# ``rlq --home X list-machines`` and ``rlq list-machines --home X``
# are identical without a parent-parser SUPPRESS twin.
_COMMANDS = frozenset({
    "create-machine", "start-machine", "stop-machine",
    "destroy-machine", "run-script", "check-script", "fetch-media",
    "seed-blueprint", "seed-media", "seed-script", "new-blueprint",
    "get-property", "set-property", "unset-property",
    "list-properties", "import-vm", "list-blueprints",
    "list-machines", "list-scripts", "clean-downloads",
    "clean-media", "insert-media", "eject-media", "set-boot-order",
    "type", "enter", "press", "exec", "select", "screen", "wait",
    "screenshot", "hmp",
})

# Arity of every flag that may appear before the command word.
# Unknown leading tokens are left in place for argparse to reject.
_FLAG_ARITY = {
    "--home": 1,
    "--blueprint": 1,
    "--machine": 1,
    "--port": 1,
    "--qemu": 1,
    "--platform": 1,
    "--timeout": 1,
    "--display": 0,
    "--builtin": 0,
    "--secret": 0,
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
    """Return a resolved machine id from selectors."""
    if not getattr(arguments, "blueprint", None) and not getattr(
            arguments, "machine", None):
        raise ValueError(
            "select a machine with --blueprint or --machine")
    return resolve_machine(
        machine=getattr(arguments, "machine", None),
        blueprint=getattr(arguments, "blueprint", None),
        home=getattr(arguments, "home", None),
    )


def _interaction_port(arguments):
    """Resolve a QMP port from selectors or the legacy ``--port``.

    Cached machines are selected with ``--blueprint`` /
    ``--machine``; bare ``--port`` remains for the root-home path.
    """
    if getattr(arguments, "blueprint", None) or getattr(
            arguments, "machine", None):
        machine_id = _require_machine_selector(arguments)
        state = load_machine_state(machine_id, arguments.home)
        if state.get("phase") != "running":
            raise ValueError(
                f"machine {machine_id} is not running "
                f"(phase: {state.get('phase')})")
        vm = read_vm_state(home=machine_dir_path(
            machine_id, arguments.home))
        if vm is None:
            raise ValueError(
                f"machine {machine_id} is running but has no "
                "vm.json")
        return vm["port"]
    return getattr(arguments, "port", None)


def _add_home(parser):
    parser.add_argument("--home", default=None,
                        help="reliquary home directory")
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


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = _reorder_argv(list(argv))

    parser = argparse.ArgumentParser(
        prog="rlq",
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
    command.add_argument("--port", type=int, default=None,
                         help="QMP port (legacy root-home start)")
    command.add_argument("--qemu", default=None, help="QEMU path")
    command.add_argument("--platform", default=None,
                         help="guest platform")
    command.add_argument("qemu_args", nargs="*",
                         help=argparse.SUPPRESS)

    # stop-machine
    command = subcommands.add_parser(
        "stop-machine", help="stop a machine")
    _add_selectors(command)
    command.add_argument("--port", type=int, default=None,
                         help="QMP port (legacy root-home stop)")

    # destroy-machine
    command = subcommands.add_parser(
        "destroy-machine", help="delete a stopped machine")
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
    for kind in ("blueprint", "media", "script"):
        command = subcommands.add_parser(
            f"seed-{kind}",
            help=f"copy built-in {kind} to home")
        _add_home(command)
        command.add_argument("name", help=f"built-in {kind} name")

    # new-blueprint
    command = subcommands.add_parser(
        "new-blueprint", help="create new blueprint")
    _add_home(command)
    command.add_argument("name", help="blueprint name")
    command.add_argument("--platform", default=None,
                         help="guest platform")

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

    # clean-*
    command = subcommands.add_parser(
        "clean-downloads", help="reclaim cached source archives")
    _add_home(command)

    command = subcommands.add_parser(
        "clean-media", help="reclaim cached media payloads")
    _add_home(command)

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
    machine_id = create_machine(
        arguments.blueprint, home=arguments.home)
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
    filter_blueprint = getattr(arguments, "blueprint", None)
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
    blueprint_name = getattr(arguments, "blueprint", None)
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


def _clean_downloads(arguments):
    clean_downloads(home=arguments.home)
    print("cleaned downloads cache")
    return 0


def _clean_media(arguments):
    clean_media(home=arguments.home)
    print("cleaned media cache")
    return 0


def _insert_media(arguments):
    machine_id = _require_machine_selector(arguments)
    insert_media(machine_id, arguments.slot, arguments.media,
                 home=arguments.home)
    print(f"inserted {arguments.media} into {arguments.slot} "
          f"on {machine_id}")
    return 0


def _eject_media(arguments):
    machine_id = _require_machine_selector(arguments)
    eject_media(machine_id, arguments.slot, home=arguments.home)
    print(f"ejected {arguments.slot} on {machine_id}")
    return 0


def _set_boot_order(arguments):
    machine_id = _require_machine_selector(arguments)
    set_boot_order(machine_id, arguments.keys, home=arguments.home)
    print(f"boot order on {machine_id}: {' '.join(arguments.keys)}")
    return 0


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
    if arguments.command == "list-blueprints":
        return _list_blueprints(arguments)
    if arguments.command == "list-machines":
        return _list_machines(arguments)
    if arguments.command == "list-scripts":
        return _list_scripts(arguments)
    if arguments.command == "clean-downloads":
        return _clean_downloads(arguments)
    if arguments.command == "clean-media":
        return _clean_media(arguments)
    if arguments.command == "insert-media":
        return _insert_media(arguments)
    if arguments.command == "eject-media":
        return _eject_media(arguments)
    if arguments.command == "set-boot-order":
        return _set_boot_order(arguments)
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
            config, display=getattr(arguments, "display", False),
            port=port)
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

    interaction_port = _interaction_port(arguments)
    if arguments.command == "type":
        send_text(arguments.text, enter=False, port=interaction_port)
    elif arguments.command == "enter":
        send_text(arguments.line, enter=True, port=interaction_port)
    elif arguments.command == "press":
        combos = [_resolve_key(name) for name in arguments.names]
        send_keys(combos, interaction_port)
    elif arguments.command == "exec":
        if platform != "dos":
            raise NotImplementedError("exec requires platform='dos'")
        AgentlessGuestExec(Machine(interaction_port)).execute(
            arguments.dos_command, timeout or 120)
    elif arguments.command == "select":
        selected = cursor_menu_select(
            arguments.item, timeout or 30,
            getattr(arguments, "exclude", []), interaction_port)
        print(f"selected: {selected}")
    elif arguments.command == "screen":
        print("\n".join(screen_text(interaction_port)))
    elif arguments.command == "wait":
        wait_text(arguments.pattern, timeout or 60,
                  interaction_port)
        print("matched.")
    elif arguments.command == "screenshot":
        screenshot(arguments.name, interaction_port)
    elif arguments.command == "hmp":
        with Machine(interaction_port).qmp() as qmp:
            print(qmp.hmp(arguments.line))
    return 0
