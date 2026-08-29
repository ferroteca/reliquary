# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""OS installation scripting over agentless QEMU guest automation.

``Session`` is the one way to interact with reliquary's working
directories, machine state, and media state (P26): every such call
goes through a :class:`Session`, opened on at least a home directory.
Besides ``Session``, this module exports the types, the error
classes, the ``Context`` record a ``Session`` is opened on,
``default_home_dir()``, and the standalone parsing functions — those
are pure functions that take input and return output with no
directory lookups, so a tool using them never has to invent a home
directory just to parse a string. Two groups of functions are
exported directly, by name, rather than through ``Session``: the
guest-console functions (``Machine`` and its related functions, which
address one machine's own directory directly — giving these a
``Session``-based interface is left for the control-plane design), and
the backend discovery functions, which are read-only. The codex
functions (for the built-in blueprint library) are available only
from the CLI (D87) and are not exported here at all.
"""

from .session import Session
from .cli import main
from .home import Context, default_home_dir
from .document import (BlueprintError, Document, load_document,
                       parse_document)
from .interaction import GuestExec
from .interaction_agentless import AgentlessGuestExec
from .backends import PRIORITY as BACKEND_PRIORITY
from .backends import (Availability, BackendAdapter, Capabilities,
                       adapter, discover)
from .machine_handle import (Machine, cursor_menu_select, screen_text,
                      screenshot, send_keys, send_text, wait_text)
from .errors import (InternalError, PreflightError, ReliquaryError,
                     RunCancelled, RunFailure, StaticError,
                     UnreadableScreen, WaitExpired)
from .events import Event, EventStream
from .machines import DryRun
from .binding import BoundProperties, PropertyBindingError
from .credentials import CredentialError
from .properties import PropertiesError, is_secret, secret_marker
from .script_nodes import ScriptParseError
from .script_parser import (Condition, Handler, Phase, Property, Script,
                            Statement, load_script, parse_script)
from .script_runner import ScriptRun, ScriptRuntimeError

__all__ = [
    "Session",
    "AgentlessGuestExec",
    "Availability",
    "BACKEND_PRIORITY",
    "BackendAdapter",
    "BlueprintError",
    "BoundProperties",
    "Capabilities",
    "Condition",
    "Context",
    "CredentialError",
    "Document",
    "DryRun",
    "Event",
    "EventStream",
    "GuestExec",
    "Handler",
    "InternalError",
    "Machine",
    "Phase",
    "PreflightError",
    "PropertiesError",
    "Property",
    "PropertyBindingError",
    "ReliquaryError",
    "RunCancelled",
    "RunFailure",
    "Script",
    "ScriptParseError",
    "ScriptRun",
    "ScriptRuntimeError",
    "StaticError",
    "Statement",
    "UnreadableScreen",
    "WaitExpired",
    "adapter",
    "cursor_menu_select",
    "default_home_dir",
    "discover",
    "is_secret",
    "load_document",
    "load_script",
    "main",
    "parse_document",
    "parse_script",
    "screen_text",
    "screenshot",
    "secret_marker",
    "send_keys",
    "send_text",
    "wait_text",
]
