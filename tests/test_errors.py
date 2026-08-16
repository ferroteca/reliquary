# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the error taxonomy and its exit codes."""

import ast
import contextlib
import io
import json
import os
from unittest import mock

import pytest

import reliquary
from reliquary import cli, errors
from reliquary.binding import PropertyBindingError
from reliquary.credentials import CredentialError
from reliquary.errors import (InternalError, PreflightError, ReliquaryError,
                              RunCancelled, RunFailure, StaticError)
from reliquary.properties import PropertiesError
from reliquary.script_nodes import ScriptParseError
from reliquary.script_runner import ScriptPreflightError, ScriptRuntimeError

_PACKAGE = os.path.dirname(os.path.abspath(reliquary.__file__))


def _modules():
    """Every package module, as (relative path, parsed tree)."""
    for folder, _dirs, names in os.walk(_PACKAGE):
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            path = os.path.join(folder, name)
            with open(path, encoding="utf-8") as handle:
                yield (os.path.relpath(path, _PACKAGE),
                       ast.parse(handle.read(), filename=path))


# One root, four run-surface classes, one exit-code mapping.

def test_every_class_exits_by_its_tier():
    assert errors.exit_code(StaticError("x")) == 2
    assert errors.exit_code(PreflightError("x")) == 3
    assert errors.exit_code(RunFailure("x")) == 4
    assert errors.exit_code(RunCancelled("x")) == 5


@pytest.mark.parametrize("class_", [StaticError, PreflightError,
                                    RunFailure, RunCancelled],
                         ids=lambda c: c.__name__)
def test_the_root_catches_all_four(class_):
    with pytest.raises(ReliquaryError):
        raise class_("x")


def test_cancellation_is_not_a_failure():
    # "Neither success nor RUN FAILURE": a caller catching
    # RunFailure must not swallow a deliberate stop.
    assert not isinstance(RunCancelled("x"), RunFailure)


def test_an_error_outside_the_taxonomy_exits_one():
    assert errors.exit_code(ValueError("x")) == errors.UNEXPECTED
    assert errors.exit_code(ReliquaryError("x")) == errors.UNEXPECTED


def test_the_terminal_outcome_names_the_class():
    assert errors.outcome(None) == "ok"
    assert errors.outcome(StaticError("x")) == "static-error"
    assert errors.outcome(PreflightError("x")) == "preflight-error"
    assert errors.outcome(RunFailure("x")) == "run-failure"
    assert errors.outcome(RunCancelled("x")) == "cancelled"


# The milestone-8 classes sit under the one root.

@pytest.mark.parametrize("class_", [PropertiesError, CredentialError,
                                    PropertyBindingError, ScriptParseError,
                                    ScriptRuntimeError,
                                    ScriptPreflightError],
                         ids=lambda c: c.__name__)
def test_every_deliberate_error_subclasses_the_root(class_):
    assert issubclass(class_, ReliquaryError)


def test_a_parse_error_is_the_static_tier():
    assert issubclass(ScriptParseError, StaticError)
    assert errors.exit_code(ScriptParseError(1, "bad")) == 2


def test_binding_and_slot_preflight_are_the_preflight_tier():
    assert issubclass(PropertyBindingError, PreflightError)
    assert issubclass(ScriptPreflightError, PreflightError)
    assert errors.exit_code(PropertyBindingError("x")) == 3


def test_a_runtime_error_is_the_run_failure_tier():
    assert issubclass(ScriptRuntimeError, RunFailure)
    assert errors.exit_code(ScriptRuntimeError("x")) == 4


# The CLI's exit codes are the taxonomy, not an everything-is-1.

@pytest.fixture
def home(tmp_path):
    home = str(tmp_path)
    os.makedirs(os.path.join(home, "blueprints"))
    os.makedirs(os.path.join(home, "scripts"))
    return home


@pytest.fixture
def scripted_home(home):
    """A home holding one plain blueprint, for the run-script arm."""
    with open(os.path.join(home, "blueprints", "plain.rlqb"), "w",
              encoding="utf-8") as handle:
        json.dump({"type": "machine", "name": "plain", "platform": "dos"},
                  handle)
    return home


def _run_raising(home, error):
    stderr = io.StringIO()
    with mock.patch("reliquary.session.Session.run_script",
                    side_effect=error), \
            contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(stderr):
        code = cli.main([
            "--home-dir", home, "--blueprint", "plain",
            "run-script", "install",
        ])
    return code, stderr.getvalue()


def test_a_static_error_exits_two(scripted_home):
    code, text = _run_raising(scripted_home,
                              ScriptParseError(3, "bad token"))
    assert code == 2
    assert "bad token" in text


def test_a_preflight_error_exits_three(scripted_home):
    code, text = _run_raising(
        scripted_home, PropertyBindingError("no value for owner"))
    assert code == 3
    assert "no value for owner" in text


def test_a_run_failure_exits_four(scripted_home):
    code, _text = _run_raising(
        scripted_home, ScriptRuntimeError("the guest never answered"))
    assert code == 4


def test_a_cancelled_run_exits_five(scripted_home):
    code, text = _run_raising(scripted_home,
                              RunCancelled("the run was cancelled"))
    assert code == 5
    assert "cancelled" in text


def test_an_unexpected_fault_exits_one(scripted_home):
    code, _text = _run_raising(scripted_home,
                               RuntimeError("something else entirely"))
    assert code == 1


def test_an_internal_error_exits_one(scripted_home):
    # The other population of exit 1: deliberate, in the hierarchy,
    # and still a fault — no user input reaches it, so there is
    # nothing for a caller to restate.
    code, text = _run_raising(
        scripted_home, InternalError("phase 'wat' is unrecognized"))
    assert code == 1
    assert "unrecognized" in text


# The five mistakes that exited 1, measured end to end (D58).
#
# Every row of the defect's table, driven through `cli.main` rather
# than asserted against a class — the exit code is what a CLI-driving
# program sees (U9), and it was the exit code that was wrong while the
# taxonomy underneath was right all along.

def _cli(home, *argv):
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(err):
        code = cli.main(["--home-dir", home, *argv])
    return code, err.getvalue()


def _write_blueprint(home, name, text):
    path = os.path.join(home, "blueprints", f"{name}.rlqb")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def test_a_media_that_does_not_exist_is_preflight(home):
    code, text = _cli(home, "fetch-media", "no-such-media")
    assert code == 3
    assert "no-such-media" in text


def test_a_blueprint_that_does_not_exist_is_preflight(home):
    code, text = _cli(home, "create-machine", "--blueprint", "no-such-bp")
    assert code == 3
    assert "no-such-bp" in text


def test_a_machine_that_does_not_exist_is_preflight(home):
    code, text = _cli(home, "start-machine", "--machine", "no-such-0")
    assert code == 3
    assert "no-such-0" in text


def test_a_script_label_that_does_not_exist_is_preflight(home):
    _write_blueprint(home, "plain", json.dumps(
        {"type": "machine", "name": "plain", "platform": "dos"}))
    code, text = _cli(home, "--blueprint", "plain", "run-script",
                      "no-such-script", "--dry-run")
    assert code == 3
    assert "no-such-script" in text


def test_malformed_blueprint_json_is_static(home):
    # The text alone settles it, and the author wrote the text.
    _write_blueprint(home, "broken", '[{"type": "machine", "name": ,}]')
    code, text = _cli(home, "create-machine", "--blueprint", "broken")
    assert code == 2
    assert "line" in text


# No deliberate raise in the package is a bare builtin.
#
# `except ReliquaryError` is documented as the catch-all, which only
# holds if every deliberate raise is in the hierarchy — so the rule is
# asserted structurally rather than left to review. A builtin escaping
# this way is exactly how an ordinary mistake came to report as
# reliquary's own fault: the CLI had a clause naming seven of them and
# printed exit 1.

#: Builtins a deliberate raise may never use again.
FORBIDDEN = {
    "ValueError", "KeyError", "RuntimeError", "FileNotFoundError",
    "FileExistsError", "TypeError", "OSError", "LookupError",
    "TimeoutError", "IndexError", "AttributeError", "Exception",
    "ArithmeticError", "BufferError", "EOFError", "ImportError",
    "MemoryError", "NameError", "OverflowError", "ReferenceError",
    "StopIteration", "SyntaxError", "SystemError", "UnicodeError",
    "ZeroDivisionError",
}


def _raise_sites():
    """Yield (module, line, raised name, node) for every raise."""
    for module, tree in _modules():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            raised = node.exc
            if isinstance(raised, ast.Call):
                raised = raised.func
            if isinstance(raised, ast.Name):
                yield module, node.lineno, raised.id, node


def test_no_deliberate_raise_uses_a_forbidden_builtin():
    offenders = [f"{module}:{line}: raise {name}"
                 for module, line, name, _node in _raise_sites()
                 if name in FORBIDDEN]
    assert offenders == [], "\n".join(offenders)


def test_the_one_permitted_builtin_is_the_abstract_method_idiom():
    """`raise NotImplementedError` survives only argument-less.

    An abstract method's stub is an invariant the language
    enforces, not a report to a caller. Given an argument it is a
    message someone reads, which makes it a capability gap — a
    PREFLIGHT ERROR, since the request is legal and this build
    does not satisfy it.
    """
    wrong = [f"{module}:{line}"
             for module, line, name, node in _raise_sites()
             if name == "NotImplementedError"
             and isinstance(node.exc, ast.Call)
             and (node.exc.args or node.exc.keywords)]
    assert wrong == [], "\n".join(wrong)


# `script-spec.md` requires an id of every diagnostic (D55).
#
# The requirement had been read as the script surface's, because the
# error classes were read as tiers of a script run. D58 generalized the
# classes and the requirement travelled with them, which took the
# population from 30 to 288. It reads zero now, and this is what keeps
# it there: the next diagnostic added without an id fails here rather
# than being noticed later by a measurement.
#
# The corpora assert that the *right* id fires for a given input; this
# asserts only that one exists, which is the part a corpus cannot cover
# for surfaces it has no fixtures for.

#: Classes that name no rule, and why.
#:
#: `InternalError` is a fault — no user input reaches it, so there is
#: no rule a caller could act on. `RunCancelled` is not an error at all
#: but an outcome. `_PropertyUnbound` is a private signal the statement
#: dispatcher always catches and restates. `_Unreadable` is the same idiom in the JSON5
#: position scanner: it means "stop recording positions here", is
#: caught by the scan that started it, and reports to nobody — the
#: document itself has already been judged by `json5.loads`. A bare
#: `NotImplementedError` is the abstract-method idiom, an invariant the
#: language enforces rather than a report to anyone.
EXEMPT = {"InternalError", "RunCancelled", "_PropertyUnbound",
          "_Unreadable", "NotImplementedError"}

#: Helpers that *return* a diagnostic for a caller to raise. The id
#: lives at the construction, so the raise site has none to give —
#: which is why a sweep over `raise` statements alone would miss them,
#: and did until this test was written.
RETURNING = {"_startup_error", "_unbound_failure", "_chaining_failure",
             "_unbound", "_diagnose", "_error", "_expired",
             "_unassigned", "_not_running"}


def test_every_deliberate_raise_names_a_rule():
    bare = []
    for module, tree in _modules():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            if not isinstance(node.exc, ast.Call):
                continue    # `raise` of a name built elsewhere
            func = node.exc.func
            label = (getattr(func, "id", None)
                     or getattr(func, "attr", None))
            if label is None or label in EXEMPT or label in RETURNING:
                continue
            if any(k.arg == "rule_id" for k in node.exc.keywords):
                continue
            bare.append(f"{module}:{node.lineno}: raise {label}")
    assert bare == [], "\n".join(
        ["these diagnostics name no rule. Give each a rule_id whose "
         "prefix is its subject, reusing an id where the rule already "
         "has one:"] + bare)


def test_the_returning_helpers_name_a_rule_where_they_build_it():
    """The exemption above is narrow, and asserted in both directions.

    A helper that returns a diagnostic is exempt at the raise site
    precisely because the id belongs at the construction. If one
    stopped setting an id there, the exemption would hide it.
    """
    found = {}
    for _module, tree in _modules():
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name not in RETURNING:
                continue
            named = any(isinstance(inner, ast.keyword)
                        and inner.arg == "rule_id"
                        for inner in ast.walk(node))
            found[node.name] = found.get(node.name, False) or named
    assert sorted(name for name, named in found.items() if not named) == [], (
        "these helpers build a diagnostic and set no rule_id, while "
        "their raise sites are exempt on the grounds that they do.")


# The four classes describe every surface, not only a run (D58).

def test_a_properties_file_is_authored_input():
    assert issubclass(PropertiesError, StaticError)
    assert errors.exit_code(PropertiesError("bad key")) == 2


def test_an_unreachable_credential_store_is_a_world_condition():
    assert issubclass(CredentialError, PreflightError)
    assert errors.exit_code(CredentialError("no store")) == 3


def test_an_internal_error_is_in_the_hierarchy_and_still_exits_one():
    assert issubclass(InternalError, ReliquaryError)
    assert errors.exit_code(InternalError("x")) == errors.UNEXPECTED


@pytest.mark.parametrize("class_", [StaticError, PreflightError,
                                    RunFailure, RunCancelled],
                         ids=lambda c: c.__name__)
def test_an_internal_error_is_none_of_the_four(class_):
    assert not isinstance(InternalError("x"), class_)
