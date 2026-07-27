# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the error taxonomy and its exit codes."""

import ast
import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import reliquary
from reliquary import cli, errors
from reliquary.binding import PropertyBindingError
from reliquary.credentials import CredentialError
from reliquary.errors import (InternalError, PreflightError, ReliquaryError,
                              RunCancelled, RunFailure, StaticError)
from reliquary.properties import PropertiesError
from reliquary.script_nodes import ScriptParseError
from reliquary.script_runner import ScriptPreflightError, ScriptRuntimeError


class TaxonomyTests(unittest.TestCase):
    """One root, four run-surface classes, one exit-code mapping."""

    def test_every_class_exits_by_its_tier(self):
        self.assertEqual(errors.exit_code(StaticError("x")), 2)
        self.assertEqual(errors.exit_code(PreflightError("x")), 3)
        self.assertEqual(errors.exit_code(RunFailure("x")), 4)
        self.assertEqual(errors.exit_code(RunCancelled("x")), 5)

    def test_the_root_catches_all_four(self):
        for error in (StaticError("a"), PreflightError("b"),
                      RunFailure("c"), RunCancelled("d")):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(ReliquaryError):
                    raise error

    def test_cancellation_is_not_a_failure(self):
        # "Neither success nor RUN FAILURE": a caller catching
        # RunFailure must not swallow a deliberate stop.
        self.assertNotIsInstance(RunCancelled("x"), RunFailure)

    def test_an_error_outside_the_taxonomy_exits_one(self):
        self.assertEqual(errors.exit_code(ValueError("x")),
                         errors.UNEXPECTED)
        self.assertEqual(errors.exit_code(ReliquaryError("x")),
                         errors.UNEXPECTED)

    def test_the_terminal_outcome_names_the_class(self):
        self.assertEqual(errors.outcome(None), "ok")
        self.assertEqual(errors.outcome(StaticError("x")), "static-error")
        self.assertEqual(errors.outcome(PreflightError("x")),
                         "preflight-error")
        self.assertEqual(errors.outcome(RunFailure("x")), "run-failure")
        self.assertEqual(errors.outcome(RunCancelled("x")), "cancelled")


class FoldedClassTests(unittest.TestCase):
    """The milestone-8 classes sit under the one root."""

    def test_every_deliberate_error_subclasses_the_root(self):
        for class_ in (PropertiesError, CredentialError,
                       PropertyBindingError, ScriptParseError,
                       ScriptRuntimeError, ScriptPreflightError):
            with self.subTest(class_=class_.__name__):
                self.assertTrue(issubclass(class_, ReliquaryError))

    def test_a_parse_error_is_the_static_tier(self):
        self.assertTrue(issubclass(ScriptParseError, StaticError))
        self.assertEqual(errors.exit_code(ScriptParseError(1, "bad")), 2)

    def test_binding_and_slot_preflight_are_the_preflight_tier(self):
        self.assertTrue(issubclass(PropertyBindingError, PreflightError))
        self.assertTrue(issubclass(ScriptPreflightError, PreflightError))
        self.assertEqual(errors.exit_code(PropertyBindingError("x")), 3)

    def test_a_runtime_error_is_the_run_failure_tier(self):
        self.assertTrue(issubclass(ScriptRuntimeError, RunFailure))
        self.assertEqual(errors.exit_code(ScriptRuntimeError("x")), 4)


class CliExitCodeTests(unittest.TestCase):
    """The CLI's exit codes are the taxonomy, not an everything-is-1."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        os.makedirs(os.path.join(self.home, "blueprints"))
        os.makedirs(os.path.join(self.home, "scripts"))
        with open(os.path.join(self.home, "blueprints", "plain.rlqb"),
                  "w", encoding="utf-8") as handle:
            json.dump(
                {"type": "machine", "name": "plain", "platform": "dos"},
                handle)

    def _run(self, error):
        stderr = io.StringIO()
        with mock.patch("reliquary.cli.run_script", side_effect=error), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(stderr):
            code = cli.main([
                "--home", self.home, "--blueprint", "plain",
                "run-script", "install",
            ])
        return code, stderr.getvalue()

    def test_a_static_error_exits_two(self):
        code, text = self._run(ScriptParseError(3, "bad token"))
        self.assertEqual(code, 2)
        self.assertIn("bad token", text)

    def test_a_preflight_error_exits_three(self):
        code, text = self._run(PropertyBindingError("no value for owner"))
        self.assertEqual(code, 3)
        self.assertIn("no value for owner", text)

    def test_a_run_failure_exits_four(self):
        code, _ = self._run(ScriptRuntimeError("the guest never answered"))
        self.assertEqual(code, 4)

    def test_a_cancelled_run_exits_five(self):
        code, text = self._run(RunCancelled("the run was cancelled"))
        self.assertEqual(code, 5)
        self.assertIn("cancelled", text)

    def test_an_unexpected_fault_exits_one(self):
        code, _ = self._run(RuntimeError("something else entirely"))
        self.assertEqual(code, 1)

    def test_an_internal_error_exits_one(self):
        # The other population of exit 1: deliberate, in the hierarchy,
        # and still a fault — no user input reaches it, so there is
        # nothing for a caller to restate.
        code, text = self._run(InternalError("phase 'wat' is unrecognized"))
        self.assertEqual(code, 1)
        self.assertIn("unrecognized", text)


class OrdinaryMistakesAreNotFaultsTests(unittest.TestCase):
    """The five mistakes that exited 1, measured end to end (D58).

    Every row of the defect's table, driven through `cli.main` rather
    than asserted against a class — the exit code is what a
    CLI-driving program sees (U9), and it was the exit code that was
    wrong while the taxonomy underneath was right all along.
    """

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        os.makedirs(os.path.join(self.home, "blueprints"))
        os.makedirs(os.path.join(self.home, "scripts"))

    def _write(self, name, text):
        path = os.path.join(self.home, "blueprints", f"{name}.rlqb")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def _run(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(err):
            code = cli.main(["--home", self.home, *argv])
        return code, err.getvalue()

    def test_a_media_that_does_not_exist_is_preflight(self):
        code, text = self._run("fetch-media", "no-such-media")
        self.assertEqual(code, 3)
        self.assertIn("no-such-media", text)

    def test_a_blueprint_that_does_not_exist_is_preflight(self):
        code, text = self._run("create-machine", "--blueprint", "no-such-bp")
        self.assertEqual(code, 3)
        self.assertIn("no-such-bp", text)

    def test_a_machine_that_does_not_exist_is_preflight(self):
        code, text = self._run("start-machine", "--machine", "no-such-0")
        self.assertEqual(code, 3)
        self.assertIn("no-such-0", text)

    def test_a_script_label_that_does_not_exist_is_preflight(self):
        self._write("plain", json.dumps(
            {"type": "machine", "name": "plain", "platform": "dos"}))
        code, text = self._run(
            "--blueprint", "plain", "check-script", "no-such-script")
        self.assertEqual(code, 3)
        self.assertIn("no-such-script", text)

    def test_malformed_blueprint_json_is_static(self):
        # The text alone settles it, and the author wrote the text.
        self._write("broken", '[{"type": "machine", "name": ,}]')
        code, text = self._run("create-machine", "--blueprint", "broken")
        self.assertEqual(code, 2)
        self.assertIn("line", text)


class DeliberateRaisesStayInTheHierarchyTests(unittest.TestCase):
    """No deliberate raise in the package is a bare builtin.

    `except ReliquaryError` is documented as the catch-all, which only
    holds if every deliberate raise is in the hierarchy — so the rule
    is asserted structurally rather than left to review. A builtin
    escaping this way is exactly how an ordinary mistake came to
    report as reliquary's own fault: the CLI had a clause naming seven
    of them and printed exit 1.
    """

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

    def _sites(self):
        """Yield (module, line, raised name) for every raise statement."""
        root = os.path.dirname(os.path.abspath(reliquary.__file__))
        for folder, _dirs, names in os.walk(root):
            for name in sorted(names):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), filename=path)
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Raise) or node.exc is None:
                        continue
                    raised = node.exc
                    if isinstance(raised, ast.Call):
                        raised = raised.func
                    if isinstance(raised, ast.Name):
                        yield (os.path.relpath(path, root), node.lineno,
                               raised.id, node)

    def test_no_deliberate_raise_uses_a_forbidden_builtin(self):
        offenders = []
        for module, line, name, node in self._sites():
            if name not in self.FORBIDDEN:
                continue
            offenders.append(f"{module}:{line}: raise {name}")
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_the_one_permitted_builtin_is_the_abstract_method_idiom(self):
        """`raise NotImplementedError` survives only argument-less.

        An abstract method's stub is an invariant the language
        enforces, not a report to a caller. Given an argument it is a
        message someone reads, which makes it a capability gap — a
        PREFLIGHT ERROR, since the request is legal and this build
        does not satisfy it.
        """
        wrong = []
        for module, line, name, node in self._sites():
            if name != "NotImplementedError":
                continue
            if isinstance(node.exc, ast.Call) and (node.exc.args
                                                   or node.exc.keywords):
                wrong.append(f"{module}:{line}")
        self.assertEqual(wrong, [], "\n".join(wrong))


class GeneralizedClassesTests(unittest.TestCase):
    """The four classes describe every surface, not only a run (D58)."""

    def test_a_properties_file_is_authored_input(self):
        self.assertTrue(issubclass(PropertiesError, StaticError))
        self.assertEqual(errors.exit_code(PropertiesError("bad key")), 2)

    def test_an_unreachable_credential_store_is_a_world_condition(self):
        self.assertTrue(issubclass(CredentialError, PreflightError))
        self.assertEqual(errors.exit_code(CredentialError("no store")), 3)

    def test_an_internal_error_is_in_the_hierarchy_and_still_exits_one(self):
        self.assertTrue(issubclass(InternalError, ReliquaryError))
        self.assertEqual(errors.exit_code(InternalError("x")),
                         errors.UNEXPECTED)

    def test_an_internal_error_is_none_of_the_four(self):
        for class_ in (StaticError, PreflightError, RunFailure,
                       RunCancelled):
            with self.subTest(class_=class_.__name__):
                self.assertNotIsInstance(InternalError("x"), class_)


if __name__ == "__main__":
    unittest.main()
