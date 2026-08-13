# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""OS installation scripting over agentless QEMU guest automation.

The session is the only door (P26): all consumer interaction with
ambient state — whatever resolves a working directory, touches
machine or media state, or reads ambient configuration — passes
through a :class:`Session`, opened on at minimum a home directory.
What the root exports beside it is the vocabulary: the types, the
errors, the ``Context`` record the session is opened on,
``default_home_dir()``, and the free parsers — pure
data-in/data-out work, so tooling never invents a home to parse a
string. Two families stay module-level by name: the guest-console
family (the carrier stratum — ``Machine`` and its functions
address a machine's own directory, their session respell deferred
to the control-plane design), and the backend seam's read-only
vocabulary. The codex verbs are CLI-only (D87) and appear on no
surface here.
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
