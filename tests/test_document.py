# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the composed blueprint document parser (document.py).

The conformance corpus
(``fixtures/conformance/blueprint/``, ``test_conformance_corpus.py``)
covers accept-versus-reject across the whole rule surface. These tests
cover what a fixture cannot assert: the *shape* parsing produces — that
sugar desugars to the thing it claims to, that identity lands where the
model says, and that a repair says what it repaired.
"""

import os
import re
import tempfile
import unittest
import warnings

from reliquary import document
from reliquary.errors import StaticError
from reliquary.document import parse_document

SHA = "a" * 64
_MEDIA_SPEC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "spec", "media-spec.md")


def _parse(value):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", document.BlueprintWarning)
        return parse_document(value)


@unittest.skipUnless(os.path.isfile(_MEDIA_SPEC),
                     "the media spec is source-tree only")
class SpecifiedMaterializeModesTests(unittest.TestCase):
    """`materialize` accepts exactly the modes the spec tabulates.

    P24's inventory pass over media. `materialize` is a closed
    vocabulary the spec gives as a table and the parser gives as a
    set, which is the cheap comparison in its purest form — a mode
    in the table and not the set is a documented value the parser
    rejects; one in the set and not the table is undocumented
    behaviour.

    **What resisted mechanizing, named rather than skipped
    quietly**: the media *field* vocabulary. `_MEDIA_FIELDS` has
    eleven entries and media-spec.md gives seven of them their own
    `###` section; the other four — `type`, `children`,
    `description`, `notes` — belong to blueprint-model.md, which
    specifies them in prose rather than under headings. Comparing
    against the union would mean hardcoding which four live
    elsewhere, and a hardcoded exemption is the thing P24's clause
    warns about, so the field set stays uncompared until one of the
    two documents enumerates its own.
    """

    @staticmethod
    def _tabulated():
        with open(_MEDIA_SPEC, encoding="utf-8") as handle:
            text = handle.read()
        start = text.index("### `materialize`")
        table = text[start:text.index("### `size`", start)]
        return set(re.findall(r"^\| `([a-z]+)` \|", table, re.M))

    def test_the_table_and_the_parser_agree(self):
        self.assertEqual(
            self._tabulated(), document._MATERIALIZE,
            "the materialize modes docs/spec/media-spec.md tabulates "
            "are not the ones the parser accepts. It is a closed "
            "vocabulary: the table is what an author may write.")

    def test_every_tabulated_mode_parses(self):
        for mode in sorted(self._tabulated()):
            with self.subTest(materialize=mode):
                spec = {"type": "media", "name": "m", "materialize": mode}
                # `new` is the one that forbids a location and needs a
                # size; the rest require a location. The table's own
                # "needs" column is what says so.
                if mode == "new":
                    spec["size"] = "20M"
                else:
                    spec["location"] = "/tmp/payload.img"
                doc = _parse([spec])
                self.assertEqual(doc.media["m"].materialize, mode)


class RootShapeTests(unittest.TestCase):
    def test_root_array_of_specs(self):
        doc = _parse([
            {"type": "machine", "name": "rig", "platform": "dos",
             "drives": {"hdd0": "blank", "cdrom0": None}},
            {"type": "media", "name": "blank", "materialize": "new",
             "size": "20M"}])
        self.assertEqual(set(doc.machines), {"rig"})
        self.assertEqual(set(doc.media), {"blank"})
        machine = doc.machines["rig"]
        self.assertEqual(machine.drives["hdd0"].media, "blank")
        self.assertIsNone(machine.drives["cdrom0"].media)
        # The default boot best-guess: the slot-0 hard disk.
        self.assertEqual(machine.boot, ("hdd0",))

    def test_lone_object_is_the_array_of_one(self):
        doc = _parse({"type": "machine", "name": "solo", "platform": "dos"})
        self.assertEqual(set(doc.machines), {"solo"})

    def test_untyped_lone_object_is_a_media_not_a_machine(self):
        """The bare-root-machine reading retired with the sections."""
        doc = _parse({"name": "iso", "location": "payload.iso"})
        self.assertEqual(set(doc.media), {"iso"})
        self.assertEqual(doc.machines, {})

    def test_machine_vocabulary_without_a_type_says_did_you_mean(self):
        with self.assertRaises(StaticError) as caught:
            parse_document({"name": "rig", "platform": "dos"})
        self.assertIn("did you mean", str(caught.exception).lower())
        self.assertIn("machine", str(caught.exception))

    def test_bare_string_desugars_to_a_location(self):
        doc = _parse(["payload.iso"])
        media = doc.media["payload"]
        self.assertEqual(len(media.location), 1)
        self.assertEqual(media.location[0].kind, "local")
        self.assertEqual(media.location[0].local, "payload.iso")

    def test_retired_section_names_itself(self):
        with self.assertRaises(StaticError) as caught:
            parse_document({"machines": [{"name": "m", "platform": "dos"}]})
        self.assertIn("retired", str(caught.exception))

    def test_retired_spec_type_names_itself(self):
        for retired in ("source", "archive"):
            with self.subTest(type=retired):
                with self.assertRaises(StaticError) as caught:
                    parse_document([{"type": retired, "name": "x"}])
                self.assertIn("retired", str(caught.exception))


class IdentityTests(unittest.TestCase):
    def test_machine_and_media_may_share_a_name(self):
        doc = _parse([
            {"type": "machine", "name": "dos622", "platform": "dos"},
            {"type": "media", "name": "dos622", "materialize": "new",
             "size": "1M"}])
        self.assertIn("dos622", doc.machines)
        self.assertIn("dos622", doc.media)

    def test_name_derives_from_the_content_stem(self):
        doc = _parse([{"location": "D:/isos/win98se.iso"}])
        self.assertEqual(set(doc.media), {"win98se"})

    def test_leading_digit_derives_cleanly(self):
        """The charter splits from the property key by exactly this."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            doc = parse_document([{"location": "https://x.test/86Box.zip",
                                   "sha256": SHA}])
        self.assertEqual(set(doc.media), {"86Box"})
        self.assertEqual([w for w in caught
                          if issubclass(w.category, document.BlueprintWarning)],
                         [])

    def test_repair_names_both_the_derived_name_and_its_source(self):
        with self.assertWarns(document.BlueprintWarning) as caught:
            doc = parse_document(
                [{"location": "https://x.test/FD 1.4 (final).zip",
                  "sha256": SHA}])
        self.assertEqual(set(doc.media), {"FD-1.4-final"})
        message = str(caught.warning)
        self.assertIn("FD-1.4-final", message)
        self.assertIn("FD 1.4 (final).zip", message)

    def test_in_file_duplicates_are_refused_even_when_identical(self):
        with self.assertRaises(StaticError):
            parse_document([{"name": "x", "location": "p.iso"},
                            {"name": "x", "location": "p.iso"}])

    def test_names_collide_case_insensitively(self):
        with self.assertRaises(StaticError) as caught:
            parse_document([{"name": "FDBOOT", "location": "a.img"},
                            {"name": "fdboot", "location": "b.img"}])
        self.assertIn("case", str(caught.exception))


class AnonymousBlankTests(unittest.TestCase):
    def test_the_blank_is_in_no_namespace(self):
        doc = _parse([{"type": "machine", "name": "rig", "platform": "dos",
                       "drives": {"hdd0": {"size": "20M"}}}])
        self.assertEqual(doc.media, {})
        drive = doc.machines["rig"].drives["hdd0"]
        self.assertIsNone(drive.media)
        self.assertIsNotNone(drive.inline)
        self.assertTrue(drive.inline.anonymous)
        self.assertEqual(drive.inline.materialize, "new")
        self.assertEqual(drive.inline.size, "20M")

    def test_a_named_inline_media_joins_the_catalog(self):
        doc = _parse([{"type": "machine", "name": "rig", "platform": "dos",
                       "drives": {"cdrom0": {"type": "media", "name": "cd",
                                             "location": "cd.iso"}}}])
        self.assertIn("cd", doc.media)
        self.assertEqual(doc.machines["rig"].drives["cdrom0"].media, "cd")


class ContainmentTests(unittest.TestCase):
    def test_children_desugar_to_child_declares_parent(self):
        doc = _parse([{
            "name": "outer", "location": "https://x.test/outer.zip",
            "sha256": SHA,
            "children": [{"path": "cd.iso", "name": "cd"},
                         "floppy.img"]}])
        self.assertEqual(set(doc.media), {"outer", "cd", "floppy"})
        for name, path in (("cd", "cd.iso"), ("floppy", "floppy.img")):
            rung = doc.media[name].location[0]
            self.assertEqual(rung.kind, "parent")
            self.assertEqual(rung.parent, "outer")
            self.assertEqual(rung.path, path)

    def test_the_two_spellings_produce_the_same_spec(self):
        """children is pure sugar: one semantic, two spellings."""
        batch = _parse([{"name": "outer", "location": "outer.zip",
                         "children": [{"path": "cd.iso", "name": "cd"}]}])
        child_side = _parse([
            {"name": "outer", "location": "outer.zip"},
            {"name": "cd", "location": "${media:outer/cd.iso}"}])
        self.assertEqual(batch.media["cd"], child_side.media["cd"])

    def test_nested_children_recurse(self):
        doc = _parse([{
            "name": "outer", "location": "outer.zip",
            "children": [{"path": "inner.zip", "name": "inner",
                          "children": ["deep.img"]}]}])
        self.assertEqual(set(doc.media), {"outer", "inner", "deep"})
        self.assertEqual(doc.media["deep"].location[0].parent, "inner")


class LocationTests(unittest.TestCase):
    def test_every_string_form_has_one_object_desugaring(self):
        doc = _parse([
            {"name": "a", "location": "https://x.test/a.iso", "sha256": SHA},
            {"name": "b", "location": "b.iso"},
            {"name": "c", "location": "C:/isos/c.iso"},
            {"name": "d", "location": "${media:a}"},
            {"name": "e", "location": "${iso.path}"}])
        self.assertEqual(doc.media["a"].location[0].kind, "url")
        self.assertEqual(doc.media["b"].location[0].kind, "local")
        self.assertEqual(doc.media["c"].location[0].local, "C:/isos/c.iso")
        parent = doc.media["d"].location[0]
        self.assertEqual((parent.kind, parent.parent, parent.path),
                         ("parent", "a", None))
        self.assertEqual(doc.media["e"].location[0].property_key, "iso.path")

    def test_mirror_singleton_is_the_scalar(self):
        doc = _parse([{"name": "x", "sha256": SHA,
                       "location": ["https://a.test/p.iso"]}])
        self.assertEqual(len(doc.media["x"].location), 1)

    def test_mirror_list_may_mix_schemes(self):
        doc = _parse([{"name": "x", "sha256": SHA,
                       "location": ["https://a.test/p.iso", "vendor/p.iso"]}])
        kinds = [rung.kind for rung in doc.media["x"].location]
        self.assertEqual(kinds, ["url", "local"])

    def test_inline_parent_registers_as_its_own_media(self):
        doc = _parse([{
            "name": "cd",
            "location": {"parent": {"name": "outer", "location": "outer.zip"},
                         "path": "cd.iso"}}])
        self.assertEqual(set(doc.media), {"outer", "cd"})
        self.assertEqual(doc.media["cd"].location[0].parent, "outer")


class ReferenceTests(unittest.TestCase):
    def test_interpolation_defers_the_value(self):
        doc = _parse([{"type": "machine", "name": "rig", "platform": "dos",
                       "memory": "${rig.memory}"}])
        memory = doc.machines["rig"].memory
        self.assertIsInstance(memory, document.Deferred)
        self.assertEqual(memory.references[0].target, "rig.memory")
        self.assertIsNone(memory.references[0].qualifier)

    def test_escape_yields_the_literal_text(self):
        """`\\${` means a literal `${`, so the parsed value carries it.

        The escape is consumed at parse: what reaches a guest config
        file is `${HOME}`, which is the whole point of having one.
        """
        doc = _parse([{"type": "machine", "name": "rig", "platform": "dos",
                       "parameters": {"p": "\\${HOME} is the guest's"}}])
        self.assertEqual(doc.machines["rig"].parameters["p"],
                         "${HOME} is the guest's")

    def test_qualified_reference_carries_its_path(self):
        doc = _parse([{"name": "cd", "location": "${media:outer/a/b.iso}"}])
        rung = doc.media["cd"].location[0]
        self.assertEqual((rung.parent, rung.path), ("outer", "a/b.iso"))

    def test_the_closure_refuses_an_operator_that_passes_the_class(self):
        """P14's acceptance test, asserted on the message too.

        `${mem:-512M}` is built entirely from legal characters, so only
        the production can refuse it — and it must say why.
        """
        with self.assertRaises(StaticError) as caught:
            parse_document([{"type": "machine", "name": "rig",
                             "platform": "dos", "memory": "${mem:-512M}"}])
        self.assertIn("qualifier", str(caught.exception))

    def test_closed_vocabularies_refuse_references(self):
        for field, value in (("platform", "${p}"), ("backend", "${b}")):
            with self.subTest(field=field):
                spec = {"type": "machine", "name": "rig", "platform": "dos"}
                spec[field] = value
                with self.assertRaises(StaticError) as caught:
                    parse_document([spec])
                self.assertIn("closed vocabulary", str(caught.exception))

    def test_identity_refuses_references(self):
        with self.assertRaises(StaticError):
            parse_document([{"name": "${what}", "location": "p.iso"}])


class MediaFieldTests(unittest.TestCase):
    def test_size_without_a_location_is_a_blank(self):
        doc = _parse([{"name": "blank", "size": "20M"}])
        self.assertEqual(doc.media["blank"].materialize, "new")

    def test_default_materialize_is_use(self):
        doc = _parse([{"name": "iso", "location": "https://x.test/a.iso",
                       "sha256": SHA}])
        self.assertEqual(doc.media["iso"].materialize, "use")

    def test_a_blank_takes_no_location(self):
        with self.assertRaises(StaticError):
            parse_document([{"name": "x", "materialize": "new",
                             "size": "20M", "location": "p.img"}])

    def test_a_payload_mode_needs_a_location(self):
        with self.assertRaises(StaticError):
            parse_document([{"name": "x", "materialize": "use"}])

    def test_state_only_field_rejected(self):
        with self.assertRaises(StaticError):
            parse_document([{"type": "machine", "name": "rig",
                             "platform": "dos", "id": "rig-0"}])

    def test_hdd_null_rejected(self):
        with self.assertRaises(StaticError):
            parse_document([{"type": "machine", "name": "rig",
                             "platform": "dos", "drives": {"hdd0": None}}])


class LocatedDiagnosticTests(unittest.TestCase):
    """A blueprint diagnostic cites a line and column (D70).

    The two entry points differ on purpose: ``load_document`` has a file
    to point into and locates every diagnostic it raises;
    ``parse_document`` is handed a value that never had a position, and
    renders exactly as it did before positions existed.
    """

    def _load(self, text):
        """Parse ``text`` as a blueprint file, returning the diagnostic."""
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".rlqb", delete=False, encoding="utf-8")
        try:
            handle.write(text)
            handle.close()
            with self.assertRaises(StaticError) as caught:
                document.load_document(handle.name)
        finally:
            os.unlink(handle.name)
        return caught.exception

    def test_an_unknown_field_is_located_at_the_field(self):
        error = self._load(
            '[\n'
            '  { "type": "machine", "name": "b", "platform": "dos",\n'
            '    "drives": { "hdd0": { "media": "d", "bogus": 1 } } }\n'
            ']\n')
        self.assertEqual((error.line, error.column), (3, 41))
        self.assertEqual(error.rule_id, "field.unknown")

    def test_a_comment_above_the_error_shifts_nothing(self):
        """The gap this closed was structural, and this is why: comments
        are blanked rather than removed, so the second pass reads the
        original file's coordinates."""
        error = self._load(
            '[\n'
            '  // a comment\n'
            '  /* and a\n'
            '     block one */\n'
            '  { "type": "machine", "name": "b", "platform": "linux" }\n'
            ']\n')
        self.assertEqual(error.line, 5)

    def test_the_rendering_cites_the_file_and_shows_the_source(self):
        error = self._load(
            '[\n'
            '  { "type": "machine", "name": "b", "platform": "linux" }\n'
            ']\n')
        rendered = str(error).split("\n")
        self.assertIn(".rlqb:2:37: error: platform must be one of",
                      rendered[0])
        self.assertIn("(value.not-in-vocabulary)", rendered[0])
        self.assertEqual(rendered[1],
                         '2 |   { "type": "machine", "name": "b", '
                         '"platform": "linux" }')
        self.assertEqual(rendered[2].rstrip(), " " * (4 + 36) + "^")

    def test_an_array_element_is_located_at_the_element(self):
        error = self._load(
            '[\n'
            '  { "type": "machine", "name": "b", "platform": "dos",\n'
            '    "drives": { "hdd0": "d" },\n'
            '    "boot": ["hdd0",\n'
            '             "cdrom0"] }\n'
            ']\n')
        self.assertEqual((error.line, error.column), (5, 14))
        self.assertEqual(error.rule_id, "drive.boot-undeclared")

    def test_a_value_handed_in_directly_is_unlocated(self):
        with self.assertRaises(StaticError) as caught:
            parse_document([{"type": "machine", "name": "b",
                             "platform": "linux"}])
        error = caught.exception
        self.assertIsNone(error.line)
        self.assertEqual(
            str(error),
            "platform must be one of dos, openbsd, win9x, winnt, "
            "got: 'linux'")

    def test_the_breadcrumb_is_unchanged_by_locating(self):
        """Position was the gap; the wording was not, and did not move."""
        error = self._load(
            '[\n'
            '  { "name": "m", "location": "${mem:-512M}" }\n'
            ']\n')
        self.assertIn("spec.location: unknown reference qualifier 'mem'",
                      str(error))


if __name__ == "__main__":
    unittest.main()
