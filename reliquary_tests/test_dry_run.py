# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The dry run: what a create would do, having done none of it.

Two invariants carry the feature and both are asserted directly
here, because everything else it reports is only worth having if
they hold: it **leaves no state behind**, and its **return is not
the run's**. The rest of the module checks that what it predicts is
what a create then does — the only claim that makes a plan worth
reading.
"""

import contextlib
import dataclasses
import hashlib
import json
import os
import tempfile
import unittest

from reliquary import backends
from reliquary.backends import Capabilities
from reliquary.errors import PreflightError, StaticError
from reliquary.home import Context
from reliquary.machines import DryRun, create_machine, load_machine_state
from reliquary_tests import fake_backend


class _DryCase(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        self.iso_path = os.path.join(self.home, "live.iso")
        with open(self.iso_path, "wb") as handle:
            handle.write(b"ISO-CONTENT")
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.backend = stack.enter_context(fake_backend.installed())
        self.stack = stack

    # -- fixtures -------------------------------------------------

    def _write(self, name, machine, media=None):
        specs = [dict(machine, type="machine", name=name)]
        specs.extend(dict(spec, type="media") for spec in (media or ()))
        bpdir = os.path.join(self.home, "blueprints")
        os.makedirs(bpdir, exist_ok=True)
        with open(os.path.join(bpdir, f"{name}.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump(specs, handle)

    def _livecd(self):
        return {"name": "livecd", "materialize": "use",
                "read-only": True, "location": {"local": self.iso_path}}

    #: The payload the remote media pins, and its hash. A create for
    #: real is given this in the cache, so it is a cache hit rather
    #: than a download; a dry run with an empty cache still reports
    #: `would-download`, which is the state under test.
    TOOLS = b"TOOLS-PAYLOAD"
    TOOLS_SHA = hashlib.sha256(TOOLS).hexdigest()

    def _remote(self):
        return {"name": "tools", "materialize": "use",
                "sha256": self.TOOLS_SHA,
                "location": "https://example.invalid/tools.img"}

    def _cache_tools(self):
        """Put the pinned payload in the cache, so a create hits it."""
        cache = os.path.join(self.home, "cache", "media")
        os.makedirs(cache, exist_ok=True)
        with open(os.path.join(cache, "tools.img"), "wb") as handle:
            handle.write(self.TOOLS)

    def _media(self, result, name):
        for entry in result.plan["media"]:
            if entry["name"] == name:
                return entry
        raise AssertionError(f"no media entry for {name!r} in "
                             f"{result.plan['media']}")

    def _mixed(self):
        """A machine touching every materialization path at once."""
        return {
            "platform": "dos",
            "drives": {
                "hdd0": {"type": "media", "size": "20M"},
                "cdrom0": "livecd",
                "floppy0": "tools",
                "floppy1": None,
            },
        }

    def _tree(self):
        """Every path under the home, relative and sorted."""
        found = []
        for root, dirs, files in os.walk(self.home):
            for name in list(dirs) + list(files):
                found.append(os.path.relpath(
                    os.path.join(root, name), self.home))
        return sorted(found)

    def _dry(self, name="demo", **kwargs):
        return create_machine(name, context=self.home, dry_run=True,
                              **kwargs)


class LeavesNoStateTests(_DryCase):
    """The first invariant, asserted against the disk itself."""

    def test_a_dry_run_writes_nothing_at_all(self):
        self._write("demo", self._mixed(),
                    [self._livecd(), self._remote()])
        before = self._tree()
        result = self._dry()
        self.assertEqual(before, self._tree())
        # Named individually too: the tree comparison would pass if
        # the walk itself were broken, and these are the four things
        # a create writes.
        for leftover in ("cache", os.path.join("cache", "machines"),
                         os.path.join("cache", "media"),
                         os.path.join("cache", "machines", ".locks")):
            self.assertFalse(
                os.path.exists(os.path.join(self.home, leftover)),
                f"a dry run created {leftover}")
        self.assertEqual(result.plan["machine"], "demo-0")

    def test_it_materializes_no_image(self):
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        self._dry()
        self.assertEqual([], self.backend.images)

    def test_a_codex_blueprint_is_read_where_it_lies(self):
        # create_machine seeds a codex blueprint into the home on
        # first reference; a dry run must not, a seeded file being
        # state left behind. The home here has no blueprints at all.
        context = Context(home_dir=self.home, autoseed=True)
        result = create_machine("freedos", context=context, dry_run=True)
        self.assertEqual("freedos-0", result.plan["machine"])
        self.assertFalse(
            os.path.exists(os.path.join(self.home, "blueprints")),
            "a dry run seeded the codex blueprint")
        self.assertEqual(["live.iso"], self._tree())

    def test_nothing_is_hashed(self):
        # `cached` says the file is there, not that it is the right
        # one: verifying what is cached is a later --dry-run=verify,
        # and hashing a LiveCD is not a step that costs nothing.
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        cache = os.path.join(self.home, "cache", "media")
        os.makedirs(cache)
        with open(os.path.join(cache, "tools.img"), "wb") as handle:
            handle.write(b"NOT-THE-PINNED-PAYLOAD")
        entry = self._media(self._dry(), "tools")
        self.assertEqual("cached", entry["state"])


class ReturnIsNotTheRunsTests(_DryCase):
    """The second invariant: no caller can mistake one for the other."""

    def test_a_dry_create_returns_a_dry_run_not_a_machine_id(self):
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        result = self._dry()
        self.assertIsInstance(result, DryRun)
        self.assertNotIsInstance(result, str)
        self.assertEqual("create-machine", result.operation)

    def test_a_real_create_still_returns_the_id(self):
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        self._cache_tools()
        with _no_network():
            machine_id = create_machine("demo", context=self.home)
        self.assertEqual("demo-0", machine_id)

    def test_the_document_serializes_whole(self):
        # --json prints exactly what the twin returns, so the twin's
        # return has to survive json.dumps with nothing dropped.
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        document = dataclasses.asdict(self._dry())
        round_tripped = json.loads(json.dumps(document))
        self.assertEqual(document["plan"]["machine"],
                         round_tripped["plan"]["machine"])
        self.assertIn("nothing was created.", round_tripped["report"])


class PredictsTheCreateTests(_DryCase):
    """A plan is worth reading only if the create then matches it."""

    def test_the_plan_is_what_the_create_writes(self):
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        plan = self._dry().plan
        self._cache_tools()
        with _no_network():
            machine_id = create_machine("demo", context=self.home)
        state = load_machine_state(machine_id, self.home)

        self.assertEqual(plan["machine"], machine_id)
        self.assertEqual(plan["backend"], state["backend"])
        self.assertEqual(plan["platform"], state["platform"])
        self.assertEqual(plan["memory"], state["memory"])
        self.assertEqual(plan["cpus"], state["cpus"])
        self.assertEqual(plan["boot"], state["boot"])
        self.assertEqual(plan["control-planes"], state["control-planes"])

        predicted = {drive["key"]: drive for drive in plan["drives"]}
        self.assertEqual(sorted(predicted), sorted(state["drives"]))
        for key, built in state["drives"].items():
            for field in ("medium", "slot", "controller", "media",
                          "materialize", "size", "path"):
                if field not in built:
                    continue
                self.assertEqual(
                    built[field], predicted[key].get(field),
                    f"drive {key} field {field} was mispredicted")

    def test_the_predicted_number_is_the_lowest_free(self):
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        self._cache_tools()
        with _no_network():
            create_machine("demo", context=self.home)
        plan = self._dry().plan
        self.assertEqual("demo-1", plan["machine"])
        self.assertEqual("lowest free", plan["machine-number"])

    def test_a_pinned_number_that_exists_is_refused(self):
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        self._cache_tools()
        with _no_network():
            create_machine("demo", context=self.home)
        with self.assertRaises(PreflightError) as caught:
            self._dry(number=0)
        self.assertEqual("machine.already-exists", caught.exception.rule_id)


class MediaResidencyTests(_DryCase):
    """Resolved, never fetched — and each state named honestly."""

    def test_a_local_payload_is_present_where_it_lies(self):
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        entry = self._media(self._dry(), "livecd")
        self.assertEqual("local-present", entry["state"])
        self.assertEqual(self.iso_path, entry["path"])
        self.assertEqual(len(b"ISO-CONTENT"), entry["size"])

    def test_an_uncached_remote_would_download(self):
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        entry = self._media(self._dry(), "tools")
        self.assertEqual("would-download", entry["state"])
        self.assertEqual("https://example.invalid/tools.img",
                         entry["source"])
        self.assertEqual(self.TOOLS_SHA, entry["sha256"])
        # No byte total: nothing on this host knows one, and a total
        # appears only where something does.
        self.assertNotIn("size", entry)

    def test_a_missing_local_payload_refuses_naming_every_one(self):
        gone = os.path.join(self.home, "gone.img")
        away = os.path.join(self.home, "away.img")
        self._write("demo", {
            "platform": "dos",
            "drives": {"hdd0": "one", "floppy0": "two"},
        }, [
            {"name": "one", "materialize": "use",
             "location": {"local": gone}},
            {"name": "two", "materialize": "use",
             "location": {"local": away}},
        ])
        with self.assertRaises(PreflightError) as caught:
            self._dry()
        message = str(caught.exception)
        self.assertEqual("media.file-missing", caught.exception.rule_id)
        # Both at once: a validator that stops at the first fault
        # costs a fix-and-rerun for each of them.
        self.assertIn("'one'", message)
        self.assertIn("'two'", message)

    def test_a_container_child_names_the_download_behind_it(self):
        self._write("demo", {
            "platform": "dos",
            "drives": {"cdrom0": "inner"},
        }, [
            {"name": "outer", "sha256": "1" * 64,
             "location": "https://example.invalid/bundle.zip",
             "children": [{"type": "media", "name": "inner",
                           "path": "DISC.iso", "read-only": True,
                           "sha256": "2" * 64}]},
        ])
        plan = self._dry().plan
        states = {entry["name"]: entry["state"] for entry in plan["media"]}
        self.assertEqual("would-extract", states["inner"])
        self.assertEqual("would-download", states["outer"])

    def test_a_cached_container_hides_the_download_behind_it(self):
        # The closure `prune` reclaims by: a container is fetched only
        # while its child is missing, so a cached child reports no
        # download at all.
        self._write("demo", {
            "platform": "dos",
            "drives": {"cdrom0": "inner"},
        }, [
            {"name": "outer", "sha256": "1" * 64,
             "location": "https://example.invalid/bundle.zip",
             "children": [{"type": "media", "name": "inner",
                           "path": "DISC.iso", "read-only": True,
                           "sha256": "2" * 64}]},
        ])
        cache = os.path.join(self.home, "cache", "media")
        os.makedirs(cache)
        with open(os.path.join(cache, "inner.iso"), "wb") as handle:
            handle.write(b"DISC")
        names = [entry["name"] for entry in self._dry().plan["media"]]
        self.assertEqual(["inner"], names)


class NeverPromptsTests(_DryCase):
    """A location nothing answers is reported, never asked for."""

    def test_an_unbound_location_is_reported_unevaluated(self):
        self._write("demo", {
            "platform": "dos",
            "drives": {"cdrom0": "vendor"},
        }, [
            {"name": "vendor", "materialize": "use", "read-only": True,
             "location": "${license-iso}"},
        ])
        plan = self._dry().plan
        entry, = plan["media"]
        self.assertEqual("unbound", entry["state"])
        self.assertEqual(["license-iso"], entry["needs"])
        self.assertIsNone(entry["path"])
        # And the report says what a real create would have done
        # about it, which is ask.
        self.assertEqual("interactive ask", plan["properties"]["license-iso"])

    def test_a_bound_location_resolves_all_the_way(self):
        self._write("demo", {
            "platform": "dos",
            "drives": {"cdrom0": "vendor"},
        }, [
            {"name": "vendor", "materialize": "use", "read-only": True,
             "location": "${license-iso}"},
        ])
        plan = self._dry(
            properties={"license-iso": self.iso_path}).plan
        entry, = plan["media"]
        self.assertEqual("local-present", entry["state"])
        self.assertEqual(self.iso_path, entry["path"])
        self.assertEqual("--property", plan["properties"]["license-iso"])


class BackendQuestionTests(_DryCase):
    """--backend asks about another host, so only capability decides."""

    def _install(self, name, *, available, capabilities=None):
        return self.stack.enter_context(fake_backend.installed(
            name=name, available=available, capabilities=capabilities))

    def test_an_absent_but_capable_backend_answers_yes(self):
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        self._install("vmware", available=False)
        plan = self._dry(backend="vmware").plan
        self.assertEqual("vmware", plan["backend"])
        self.assertEqual("--backend", plan["backend-source"])
        self.assertFalse(plan["backend-available"])
        self.assertIn("no vmware on this host", plan["backend-detail"])

    def test_an_incapable_backend_is_refused_by_name(self):
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        self._install("vmware", available=True,
                      capabilities=Capabilities(backend="vmware"))
        with self.assertRaises(PreflightError) as caught:
            self._dry(backend="vmware")
        self.assertEqual("machine.backend-incapable",
                         caught.exception.rule_id)
        self.assertIn("cdrom drives", str(caught.exception))

    def test_an_unknown_backend_is_refused(self):
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        with self.assertRaises(StaticError) as caught:
            self._dry(backend="parallels")
        self.assertEqual("machine.backend-unknown", caught.exception.rule_id)

    def test_backend_without_dry_run_is_refused(self):
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        with self.assertRaises(StaticError) as caught:
            create_machine("demo", context=self.home, backend="vmware")
        self.assertEqual("machine.backend-outside-dry-run",
                         caught.exception.rule_id)

    def test_without_the_flag_assignment_still_needs_availability(self):
        # The question changes with the flag and not without it: an
        # ordinary dry run reports what *this* host would do.
        self._write("demo", self._mixed(), [self._livecd(),
                                            self._remote()])
        self.backend.available = False
        with self.assertRaises(PreflightError) as caught:
            self._dry()
        self.assertEqual("machine.no-capable-backend",
                         caught.exception.rule_id)

    def test_a_declared_backend_is_named_as_the_source(self):
        machine = dict(self._mixed(), backend="qemu")
        self._write("demo", machine, [self._livecd(), self._remote()])
        self.assertEqual("declared", self._dry().plan["backend-source"])


class EvaluateTests(unittest.TestCase):
    """The judgment assignment is built from, on its own."""

    def test_it_reports_both_answers_separately(self):
        requirements = backends.Requirements(media=("cdrom",))
        with fake_backend.installed(name="vmware", available=False):
            verdict = backends.evaluate("vmware", requirements)
        self.assertFalse(verdict.available)
        self.assertEqual((), verdict.unmet)

    def test_an_available_backend_can_still_be_unmet(self):
        requirements = backends.Requirements(controllers=("scsi",))
        with fake_backend.installed(name="vmware", available=True):
            verdict = backends.evaluate("vmware", requirements)
        self.assertTrue(verdict.available)
        self.assertEqual(("controller 'scsi'",), verdict.unmet)


def _no_network():
    """A real create in these tests must never reach the network.

    Every fixture with a remote media pairs it with a cached payload
    or is not created for real; this makes a slip loud rather than
    slow.
    """
    import unittest.mock as mock
    return mock.patch("reliquary.acquire._download",
                      side_effect=AssertionError(
                          "a test create tried to download"))


if __name__ == "__main__":
    unittest.main()
