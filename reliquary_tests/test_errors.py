# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the error taxonomy and its exit codes."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from reliquary import cli, errors
from reliquary.binding import PropertyBindingError
from reliquary.credentials import CredentialError
from reliquary.errors import (PreflightError, ReliquaryError, RunCancelled,
                              RunFailure, StaticError)
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


if __name__ == "__main__":
    unittest.main()
