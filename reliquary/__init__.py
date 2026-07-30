# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""OS installation scripting over agentless QEMU guest automation."""

from .blueprint import add_media, delete_blueprint, new_blueprint
from .cli import main
from .document import (BlueprintError, Document, load_document,
                       parse_document)
from .home import (DIRECTORIES, Context, blueprints_dir,
                   cache_dir, default_home_dir, documents_dir, home_dir,
                   machines_dir, media_dir, scripts_dir,
                   set_blueprints_dir, set_cache_dir, set_home_dir,
                   set_machines_dir, set_media_dir, set_scripts_dir)
from .interaction import GuestExec
from .interaction_agentless import AgentlessGuestExec
from .backends import PRIORITY as BACKEND_PRIORITY
from .backends import (Availability, BackendAdapter, Capabilities,
                       adapter, discover)
# The codex verbs are not here: `seed-blueprint`, `seed-script` and
# `list-codex` are CLI-only (D87). A library that changes in a point
# release is not something a program may bind against, so reaching it
# is a human act.
from .library import list_blueprints, list_scripts
from .machine import (Machine, cursor_menu_select, screen_text,
                      screenshot, send_keys, send_text, wait_text)
from .errors import (InternalError, PreflightError, ReliquaryError,
                     RunCancelled, RunFailure, StaticError)
from .events import Event, EventStream
from .machines import (DryRun, apply_blueprint, create, create_machine,
                       describe_drives,
                       destroy_machine, eject_media, get_file, get_files,
                       get_machine_dir, get_machine_var,
                       insert_media, list_files, list_machines,
                       refresh_drives,
                       load_machine_state,
                       machine_dir_path, mark_stopped,
                       put_file, put_files, recreate_machine, resolve_machine,
                       set_boot_order, set_machine_var, start_machine,
                       stop_machine)
# The one-shot member of the run family; named for its command under
# the twin-name identity rule (the builtin stays reachable as
# ``builtins.exec``).
from .machines import exec  # noqa: A001
from .media import fetch_media, clean_media, list_media, prune_media
from .resolve import load_namespace
from .binding import (BoundProperties, PropertyBindingError,
                      bind_properties, describe_sources)
from .credentials import CredentialError
from .properties import (PropertiesError, get_property,
                         has_credential, is_secret, list_properties,
                         secret_marker, set_property, unset_property)
from .script_nodes import ScriptParseError
from .script_parser import (Condition, Handler, Phase, Property, Script,
                            Statement, load_script, parse_script)
from .script_runner import (ScriptRun, ScriptRuntimeError,
                            execute_script, run_script)

__all__ = [
    "Condition",
    "Document",
    "Event",
    "EventStream",
    "Handler",
    "Machine",
    "Script",
    "ScriptParseError",
    "ScriptRun",
    "ScriptRuntimeError",
    "BlueprintError",
    "BoundProperties",
    "CredentialError",
    "InternalError",
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
    "Availability",
    "BACKEND_PRIORITY",
    "BackendAdapter",
    "Capabilities",
    "Context",
    "DIRECTORIES",
    "DryRun",
    "GuestExec",
    "adapter",
    "discover",
    "apply_blueprint",
    "create",
    "create_machine",
    "cursor_menu_select",
    "delete_blueprint",
    "describe_drives",
    "destroy_machine",
    "eject_media",
    "exec",
    "get_file",
    "get_files",
    "get_machine_dir",
    "get_machine_var",
    "insert_media",
    "list_files",
    "put_file",
    "put_files",
    "refresh_drives",
    "set_machine_var",
    "blueprints_dir",
    "cache_dir",
    "bind_properties",
    "describe_sources",
    "has_credential",
    "is_secret",
    "secret_marker",
    "add_media",
    "clean_media",
    "documents_dir",
    "fetch_media",
    "get_property",
    "home_dir",
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
    "machines_dir",
    "main",
    "mark_stopped",
    "media_dir",
    "new_blueprint",
    "parse_document",
    "prune_media",
    "parse_script",
    "recreate_machine",
    "resolve_machine",
    "screen_text",
    "screenshot",
    "scripts_dir",
    "send_keys",
    "send_text",
    "default_home_dir",
    "set_blueprints_dir",
    "set_boot_order",
    "set_cache_dir",
    "set_home_dir",
    "set_machines_dir",
    "set_media_dir",
    "set_scripts_dir",
    "set_property",
    "start_machine",
    "stop_machine",
    "unset_property",
    "wait_text",
    "execute_script",
    "run_script",
]
