# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""OS installation scripting over agentless QEMU guest automation."""

from .blueprint import delete_blueprint, new_blueprint
from .cli import main
from .document import Document, load_document, parse_document
from .home import (HOME_ASSETS, Context,
                   blueprints_dir, cache_dir, documents_dir, home,
                   machines_cache_dir, media_cache_dir,
                   scripts_dir, set_assets, set_cache, set_home)
from .interaction import GuestExec
from .interaction_agentless import AgentlessGuestExec
from .lifecycle import (Qmp, create_hdd_image, find_qemu, find_qemu_img,
                        stop)
from .library import (list_blueprints, list_scripts, search_blueprints,
                     seed_blueprint, seed_script)
from .machine import (Machine, cursor_menu_select, screen_text,
                      screenshot, send_keys, send_text, wait_text)
from .errors import (PreflightError, ReliquaryError, RunCancelled,
                     RunFailure, StaticError)
from .events import Event, EventStream
from .machines import (apply_blueprint, create, create_machine,
                       destroy_machine, eject_media, get_file,
                       get_machine_dir, get_machine_var,
                       insert_media, list_machines, load_machine_state,
                       machine_dir_path, machine_drive_args, mark_stopped,
                       put_file, recreate_machine, resolve_machine,
                       set_boot_order, set_machine_var, start_machine,
                       stop_machine)
# The one-shot member of the run family; named for its command under
# the twin-name identity rule (the builtin stays reachable as
# ``builtins.exec``).
from .machines import exec  # noqa: A001
from .media import (add_media, fetch_media, clean_media, list_media,
                    prune_media)
from .resolve import load_namespace
from .binding import (BoundProperties, PropertyBindingError,
                      bind_properties, describe_sources)
from .credentials import CredentialError
from .properties import (PropertiesError, check_key, get_property,
                         has_credential, is_secret, list_properties,
                         secret_marker, set_property, unset_property)
from .script_nodes import ScriptParseError
from .script_parser import (Condition, Handler, Phase, Property, Script,
                            Statement, load_script, parse_script)
from .script_runner import (ScriptCheck, ScriptRun, ScriptRuntimeError,
                            check_script, execute_script, run_script)

__all__ = [
    "Condition",
    "Document",
    "Event",
    "EventStream",
    "Handler",
    "Machine",
    "Qmp",
    "Script",
    "ScriptCheck",
    "ScriptParseError",
    "ScriptRun",
    "ScriptRuntimeError",
    "BoundProperties",
    "CredentialError",
    "PreflightError",
    "PropertiesError",
    "PropertyBindingError",
    "ReliquaryError",
    "RunCancelled",
    "RunFailure",
    "StaticError",
    "Phase",
    "Property",
    "Statement",
    "AgentlessGuestExec",
    "Context",
    "HOME_ASSETS",
    "GuestExec",
    "apply_blueprint",
    "create",
    "create_hdd_image",
    "create_machine",
    "cursor_menu_select",
    "delete_blueprint",
    "destroy_machine",
    "eject_media",
    "exec",
    "get_file",
    "get_machine_dir",
    "get_machine_var",
    "insert_media",
    "put_file",
    "set_machine_var",
    "blueprints_dir",
    "cache_dir",
    "bind_properties",
    "check_key",
    "describe_sources",
    "has_credential",
    "is_secret",
    "secret_marker",
    "add_media",
    "clean_media",
    "documents_dir",
    "find_qemu",
    "find_qemu_img",
    "get_property",
    "home",
    "list_blueprints",
    "list_machines",
    "list_media",
    "list_properties",
    "list_scripts",
    "load_document",
    "load_namespace",
    "load_script",
    "load_machine_state",
    "machine_dir_path",
    "machine_drive_args",
    "machines_cache_dir",
    "main",
    "mark_stopped",
    "media_cache_dir",
    "new_blueprint",
    "parse_document",
    "prune_media",
    "parse_script",
    "recreate_machine",
    "resolve_machine",
    "screen_text",
    "screenshot",
    "scripts_dir",
    "search_blueprints",
    "seed_blueprint",
    "seed_script",
    "send_keys",
    "send_text",
    "set_assets",
    "set_boot_order",
    "set_cache",
    "set_home",
    "set_property",
    "start_machine",
    "stop",
    "stop_machine",
    "unset_property",
    "wait_text",
    "execute_script",
    "check_script",
    "run_script",
]
