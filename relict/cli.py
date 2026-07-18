# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Command-line parsing and dispatch."""

import argparse
import sys

from qemu.qmp import ConnectError

from .home import set_home
from .workflows import _cli_machine_config
from .interaction_agentless import (AgentlessGuestExec, screen_text,
                                    send_keys, send_text, wait_screen)
from .lifecycle import stop
from .machine import Machine, screenshot
from .platform_dos import download
from .workflows import start


def _cli_start_overrides(arguments):
    """CLI controls that override a loaded machine configuration."""
    overrides = {}
    if arguments.platform is not None:
        overrides["platform"] = arguments.platform
    if arguments.qemu is not None:
        overrides["qemu"] = arguments.qemu
    if arguments.qemu_args:
        overrides["qemu_args"] = arguments.qemu_args
    return overrides


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="relict", description="QEMU guest automation harness "
                                   "(DOS by default)")
    parser.add_argument("--home", help="relict home directory (drives/, "
                        "screenshots/); default: $RELICT_HOME, then "
                        "Documents/relict")
    parser.add_argument("--port", type=int,
                        help="QMP port (start: choose one automatically; "
                             "other commands: use the active VM)")
    parser.add_argument("--qemu", help="path to the QEMU binary (default: "
                        "$RELICT_QEMU_HOME, then $QEMU_HOME, then PATH, "
                        "then well-known install locations)")
    parser.add_argument("--platform", default=None,
                        help="guest platform adapter (default: dos; other "
                             "platform workflows are not implemented yet)")
    parser.add_argument("--timeout", type=int, help="seconds to wait "
                        "(defaults: boot-to-dos 90, run 120, wait 60)")
    parser.add_argument("--machine", help="path to machine.json configuration "
                        "file (default: <home>/machine.json if present)")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("download")
    command = subcommands.add_parser("start")
    command.add_argument("--display", action="store_true")
    command.add_argument("qemu_args", nargs="*")
    subcommands.add_parser("stop")
    subcommands.add_parser("boot-to-dos")
    command = subcommands.add_parser("type")
    command.add_argument("text")
    command = subcommands.add_parser("run")
    command.add_argument("dos_command")
    command = subcommands.add_parser("keys")
    command.add_argument("names", nargs="+")
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
        print(f"relict: cannot reach QMP on {target}: {error}\n"
              "is the VM running? (relict start)", file=sys.stderr)
        return 1
    except (RuntimeError, TimeoutError, FileNotFoundError,
            NotImplementedError, ValueError, OSError) as error:
        print(f"relict: error: {error}", file=sys.stderr)
        return 1


def _dispatch(arguments):
    platform = arguments.platform or "dos"
    if arguments.command == "download":
        if platform != "dos":
            raise NotImplementedError(
                f"platform {platform!r} provisioning is not "
                "implemented")
        download()
    elif arguments.command == "start":
        config = _cli_machine_config(
            arguments.machine, arguments.home,
            **_cli_start_overrides(arguments))
        start(config, display=arguments.display, port=arguments.port)
    elif arguments.command == "stop":
        stop(arguments.port)
    elif arguments.command == "boot-to-dos":
        if platform != "dos":
            raise NotImplementedError(
                "boot-to-dos requires platform='dos'")
        AgentlessGuestExec(Machine(arguments.port)).wait_ready(
            arguments.timeout or 90)
    elif arguments.command == "type":
        send_text(arguments.text, arguments.port)
    elif arguments.command == "run":
        if platform != "dos":
            raise NotImplementedError("run requires platform='dos'")
        AgentlessGuestExec(Machine(arguments.port)).execute(
            arguments.dos_command, arguments.timeout or 120)
    elif arguments.command == "keys":
        send_keys([[key] for key in arguments.names], arguments.port)
    elif arguments.command == "text":
        print("\n".join(screen_text(arguments.port)))
    elif arguments.command == "wait":
        wait_screen(arguments.pattern, arguments.timeout or 60,
                    arguments.port)
        print("matched.")
    elif arguments.command == "screenshot":
        screenshot(arguments.name, arguments.port)
    elif arguments.command == "hmp":
        with Machine(arguments.port).qmp() as qmp:
            print(qmp.hmp(arguments.line))
    return 0
