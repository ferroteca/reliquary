# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the composed blueprint document parser (document.py).

The conformance corpus
(``fixtures/conformance/blueprint/``, ``test_conformance_corpus.py``)
covers accept-versus-reject decisions across the whole rule surface.
These tests cover what a fixture cannot check: the *shape* parsing
produces. That means checking that a shorthand form (sugar) desugars
to the full form it stands for, that a machine's or media's identity
ends up where the data model says it should, and that when the parser
repairs a name, its warning message correctly says what it repaired.
"""

import json
import os
import warnings

import pytest

from reliquary import document
from reliquary.errors import StaticError
from reliquary.document import parse_document

SHA = "a" * 64


def _parse(value):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", document.BlueprintWarning)
        return parse_document(value)


@pytest.fixture
def root(tmp_path):
    return str(tmp_path)


def _load_file(root, value, name="b.rlqb"):
    path = os.path.join(root, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle)
    return document.load_document(path)


# Every mode in the parser's closed vocabulary parses.
#
# `_MATERIALIZE` is the closed set of modes an author may write, and
# each one must actually parse. If the parser rejected a mode that is
# in this set, that mode would be listed as legal but never usable.
# Whether the spec's table names the same modes is R5's audit
# (planning/RECURRING.md).

@pytest.mark.parametrize("mode", sorted(document._MATERIALIZE))
def test_every_declared_mode_parses(mode):
    spec = {"type": "media", "name": "m", "materialize": mode}
    # `new` is the one that forbids a location and needs
    # a size; the rest require a location.
    if mode == "new":
        spec["size"] = "20M"
    else:
        spec["location"] = "/tmp/payload.img"
    assert _parse([spec]).media["m"].materialize == mode


# The root's shape.

def test_root_array_of_specs():
    doc = _parse([
        {"type": "machine", "name": "rig", "platform": "dos",
         "devices": {"hdd0": "blank", "cdrom0": None}},
        {"type": "media", "name": "blank", "materialize": "new",
         "size": "20M"}])
    assert set(doc.machines) == {"rig"}
    assert set(doc.media) == {"blank"}
    machine = doc.machines["rig"]
    assert machine.drives["hdd0"].media == "blank"
    assert machine.drives["cdrom0"].media is None
    # The default boot best-guess: the slot-0 hard disk.
    assert machine.boot == ("hdd0",)


def test_lone_object_is_the_array_of_one():
    doc = _parse({"type": "machine", "name": "solo", "platform": "dos"})
    assert set(doc.machines) == {"solo"}


def test_untyped_lone_object_is_a_media_not_a_machine():
    """A lone untyped root object used to be read as a machine; that
    reading was retired along with the old machines/media sections."""
    doc = _parse({"name": "iso", "location": "payload.iso"})
    assert set(doc.media) == {"iso"}
    assert doc.machines == {}


def test_machine_vocabulary_without_a_type_says_did_you_mean():
    with pytest.raises(StaticError) as caught:
        parse_document({"name": "rig", "platform": "dos"})
    assert "did you mean" in str(caught.value).lower()
    assert "machine" in str(caught.value)


def test_bare_string_desugars_to_a_location():
    doc = _parse(["payload.iso"])
    media = doc.media["payload"]
    assert len(media.location) == 1
    assert media.location[0].kind == "local"
    assert media.location[0].local == "payload.iso"


def test_retired_section_names_itself():
    with pytest.raises(StaticError) as caught:
        parse_document({"machines": [{"name": "m", "platform": "dos"}]})
    assert "retired" in str(caught.value)


@pytest.mark.parametrize("retired", ["source", "archive"])
def test_retired_spec_type_names_itself(retired):
    with pytest.raises(StaticError) as caught:
        parse_document([{"type": retired, "name": "x"}])
    assert "retired" in str(caught.value)


# Identity: (name, type), and where a name comes from.

def test_machine_and_media_may_share_a_name():
    doc = _parse([
        {"type": "machine", "name": "dos622", "platform": "dos"},
        {"type": "media", "name": "dos622", "materialize": "new",
         "size": "1M"}])
    assert "dos622" in doc.machines
    assert "dos622" in doc.media


def test_name_derives_from_the_content_stem():
    doc = _parse([{"location": "D:/isos/win98se.iso"}])
    assert set(doc.media) == {"win98se"}


def test_leading_digit_derives_cleanly():
    """The media-name charter differs from the property-key charter in
    exactly this: it allows a leading digit."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        doc = parse_document([{"location": "https://x.test/86Box.zip",
                               "sha256": SHA}])
    assert set(doc.media) == {"86Box"}
    assert [w for w in caught
            if issubclass(w.category, document.BlueprintWarning)] == []


def test_repair_names_both_the_derived_name_and_its_source():
    with pytest.warns(document.BlueprintWarning) as caught:
        doc = parse_document(
            [{"location": "https://x.test/FD 1.4 (final).zip",
              "sha256": SHA}])
    assert set(doc.media) == {"FD-1.4-final"}
    message = str(caught[0].message)
    assert "FD-1.4-final" in message
    assert "FD 1.4 (final).zip" in message


def test_in_file_duplicates_are_refused_even_when_identical():
    with pytest.raises(StaticError):
        parse_document([{"name": "x", "location": "p.iso"},
                        {"name": "x", "location": "p.iso"}])


def test_names_collide_case_insensitively():
    with pytest.raises(StaticError) as caught:
        parse_document([{"name": "FDBOOT", "location": "a.img"},
                        {"name": "fdboot", "location": "b.img"}])
    assert "case" in str(caught.value)


# The anonymous blank, and its named sibling.

def test_the_blank_is_in_no_namespace():
    doc = _parse([{"type": "machine", "name": "rig", "platform": "dos",
                   "devices": {"hdd0": {"size": "20M"}}}])
    assert doc.media == {}
    drive = doc.machines["rig"].drives["hdd0"]
    assert drive.media is None
    assert drive.inline is not None
    assert drive.inline.anonymous
    assert drive.inline.materialize == "new"
    assert drive.inline.size == "20M"


def test_a_named_inline_media_joins_the_catalog():
    doc = _parse([{"type": "machine", "name": "rig", "platform": "dos",
                   "devices": {"cdrom0": {"type": "media", "name": "cd",
                                          "location": "cd.iso"}}}])
    assert "cd" in doc.media
    assert doc.machines["rig"].drives["cdrom0"].media == "cd"


# Containment: `children` desugars to child-declares-parent.

def test_children_desugar_to_child_declares_parent():
    doc = _parse([{
        "name": "outer", "location": "https://x.test/outer.zip",
        "sha256": SHA,
        "children": [{"path": "cd.iso", "name": "cd"}, "floppy.img"]}])
    assert set(doc.media) == {"outer", "cd", "floppy"}
    for name, path in (("cd", "cd.iso"), ("floppy", "floppy.img")):
        rung = doc.media[name].location[0]
        assert rung.kind == "parent"
        assert rung.parent == "outer"
        assert rung.path == path


def test_the_two_spellings_produce_the_same_spec():
    """children is pure sugar: one semantic, two spellings."""
    batch = _parse([{"name": "outer", "location": "outer.zip",
                     "children": [{"path": "cd.iso", "name": "cd"}]}])
    child_side = _parse([
        {"name": "outer", "location": "outer.zip"},
        {"name": "cd", "location": "${media:outer/cd.iso}"}])
    assert batch.media["cd"] == child_side.media["cd"]


def test_nested_children_recurse():
    doc = _parse([{
        "name": "outer", "location": "outer.zip",
        "children": [{"path": "inner.zip", "name": "inner",
                      "children": ["deep.img"]}]}])
    assert set(doc.media) == {"outer", "inner", "deep"}
    assert doc.media["deep"].location[0].parent == "inner"


# Locations, and their desugarings.

def test_every_string_form_has_one_object_desugaring():
    doc = _parse([
        {"name": "a", "location": "https://x.test/a.iso", "sha256": SHA},
        {"name": "b", "location": "b.iso"},
        {"name": "c", "location": "C:/isos/c.iso"},
        {"name": "d", "location": "${media:a}"},
        {"name": "e", "location": "${iso.path}"}])
    assert doc.media["a"].location[0].kind == "url"
    assert doc.media["b"].location[0].kind == "local"
    assert doc.media["c"].location[0].local == "C:/isos/c.iso"
    parent = doc.media["d"].location[0]
    assert (parent.kind, parent.parent, parent.path) == ("parent", "a", None)
    assert doc.media["e"].location[0].property_key == "iso.path"


def test_mirror_singleton_is_the_scalar():
    doc = _parse([{"name": "x", "sha256": SHA,
                   "location": ["https://a.test/p.iso"]}])
    assert len(doc.media["x"].location) == 1


def test_mirror_list_may_mix_schemes():
    doc = _parse([{"name": "x", "sha256": SHA,
                   "location": ["https://a.test/p.iso", "vendor/p.iso"]}])
    assert [rung.kind for rung in doc.media["x"].location] == [
        "url", "local"]


def test_inline_parent_registers_as_its_own_media():
    doc = _parse([{
        "name": "cd",
        "location": {"parent": {"name": "outer", "location": "outer.zip"},
                     "path": "cd.iso"}}])
    assert set(doc.media) == {"outer", "cd"}
    assert doc.media["cd"].location[0].parent == "outer"


# A relative ``local`` path is relative to the referencing file.
#
# ``load_document`` is the entry point with a file to anchor to, so it
# is where the authored spelling becomes absolute; a bare value parsed
# through ``parse_document`` has no file and keeps its paths as
# authored.

def test_a_relative_local_anchors_to_the_files_directory(root):
    doc = _load_file(root, [{"name": "iso",
                             "location": "../isos/x.iso"}])
    (rung,) = doc.media["iso"].location
    assert rung.local == os.path.normpath(
        os.path.join(root, "..", "isos", "x.iso"))
    assert os.path.isabs(rung.local)


def test_an_absolute_local_is_untouched(root):
    absolute = os.path.join(root, "elsewhere", "x.iso")
    doc = _load_file(root, [{"name": "iso", "location": absolute}])
    assert doc.media["iso"].location[0].local == absolute


def test_only_local_rungs_anchor_in_a_mirror_list(root):
    doc = _load_file(root, [{
        "name": "iso", "sha256": SHA,
        "location": ["https://x.test/p.iso", "vendor/p.iso"]}])
    url, local = doc.media["iso"].location
    assert url.url == "https://x.test/p.iso"
    assert local.local == os.path.join(root, "vendor", "p.iso")


def test_an_inline_drive_media_anchors(root):
    doc = _load_file(root, [{
        "type": "machine", "name": "rig", "platform": "dos",
        "devices": {"cdrom0": {"type": "media", "name": "cd",
                               "location": "cd.iso"}}}])
    anchored = os.path.join(root, "cd.iso")
    assert doc.media["cd"].location[0].local == anchored
    inline = doc.machines["rig"].drives["cdrom0"].inline
    assert inline.location[0].local == anchored


def test_a_bare_value_keeps_the_authored_spelling():
    doc = _parse([{"name": "iso", "location": "x.iso"}])
    assert doc.media["iso"].location[0].local == "x.iso"


# The reference grammar, closed at two productions.

def test_interpolation_defers_the_value():
    doc = _parse([{"type": "machine", "name": "rig", "platform": "dos",
                   "memory": "${rig.memory}"}])
    memory = doc.machines["rig"].memory
    assert isinstance(memory, document.Deferred)
    assert memory.references[0].target == "rig.memory"
    assert memory.references[0].qualifier is None


def test_escape_yields_the_literal_text():
    """`\\${` means a literal `${`, so the parsed value carries it.

    The escape is consumed at parse: what reaches a guest config
    file is `${HOME}`, which is the whole point of having one.
    """
    doc = _parse([{"type": "machine", "name": "rig", "platform": "dos",
                   "parameters": {"p": "\\${HOME} is the guest's"}}])
    assert doc.machines["rig"].parameters["p"] == "${HOME} is the guest's"


def test_qualified_reference_carries_its_path():
    doc = _parse([{"name": "cd", "location": "${media:outer/a/b.iso}"}])
    rung = doc.media["cd"].location[0]
    assert (rung.parent, rung.path) == ("outer", "a/b.iso")


def test_the_closure_refuses_an_operator_that_passes_the_class():
    """P14's acceptance test, asserted on the message too.

    `${mem:-512M}` is built entirely from legal characters, so only
    the production can refuse it — and it must say why.
    """
    with pytest.raises(StaticError) as caught:
        parse_document([{"type": "machine", "name": "rig",
                         "platform": "dos", "memory": "${mem:-512M}"}])
    assert "qualifier" in str(caught.value)


@pytest.mark.parametrize("field,value", [("platform", "${p}"),
                                         ("backend", "${b}")])
def test_closed_vocabularies_refuse_references(field, value):
    spec = {"type": "machine", "name": "rig", "platform": "dos"}
    spec[field] = value
    with pytest.raises(StaticError) as caught:
        parse_document([spec])
    assert "closed vocabulary" in str(caught.value)


def test_identity_refuses_references():
    with pytest.raises(StaticError):
        parse_document([{"name": "${what}", "location": "p.iso"}])


# The media fields.

def test_size_without_a_location_is_a_blank():
    assert _parse([{"name": "blank", "size": "20M"}]).media[
        "blank"].materialize == "new"


def test_default_materialize_is_use():
    doc = _parse([{"name": "iso", "location": "https://x.test/a.iso",
                   "sha256": SHA}])
    assert doc.media["iso"].materialize == "use"


def test_a_blank_takes_no_location():
    with pytest.raises(StaticError):
        parse_document([{"name": "x", "materialize": "new",
                         "size": "20M", "location": "p.img"}])


def test_a_payload_mode_needs_a_location():
    with pytest.raises(StaticError):
        parse_document([{"name": "x", "materialize": "use"}])


def test_state_only_field_rejected():
    with pytest.raises(StaticError):
        parse_document([{"type": "machine", "name": "rig",
                         "platform": "dos", "id": "rig-0"}])


def test_hdd_null_rejected():
    with pytest.raises(StaticError):
        parse_document([{"type": "machine", "name": "rig",
                         "platform": "dos", "devices": {"hdd0": None}}])


# A blueprint diagnostic cites a line and column (D70).
#
# The two entry points differ on purpose: ``load_document`` has a file
# to point into and locates every diagnostic it raises;
# ``parse_document`` is handed a value that never had a position, and
# renders exactly as it did before positions existed.

def _diagnostic(root, text):
    """Parse ``text`` as a blueprint file, returning the diagnostic."""
    path = os.path.join(root, "located.rlqb")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    with pytest.raises(StaticError) as caught:
        document.load_document(path)
    return caught.value


def test_an_unknown_field_is_located_at_the_field(root):
    error = _diagnostic(
        root,
        '[\n'
        '  { "type": "machine", "name": "b", "platform": "dos",\n'
        '    "devices": { "hdd0": { "media": "d", "bogus": 1 } } }\n'
        ']\n')
    assert (error.line, error.column) == (3, 42)
    assert error.rule_id == "field.unknown"


def test_a_comment_above_the_error_shifts_nothing(root):
    """This guards a real bug: comments are blanked out (replaced with
    spaces) rather than removed, so the pass that locates each error
    still reads the same line and column numbers as the original
    file."""
    error = _diagnostic(
        root,
        '[\n'
        '  // a comment\n'
        '  /* and a\n'
        '     block one */\n'
        '  { "type": "machine", "name": "b", "platform": "linux" }\n'
        ']\n')
    assert error.line == 5


def test_the_rendering_cites_the_file_and_shows_the_source(root):
    error = _diagnostic(
        root,
        '[\n'
        '  { "type": "machine", "name": "b", "platform": "linux" }\n'
        ']\n')
    rendered = str(error).split("\n")
    assert ".rlqb:2:37: error: platform must be one of" in rendered[0]
    assert "(value.not-in-vocabulary)" in rendered[0]
    assert rendered[1] == ('2 |   { "type": "machine", "name": "b", '
                           '"platform": "linux" }')
    assert rendered[2].rstrip() == " " * (4 + 36) + "^"


def test_an_array_element_is_located_at_the_element(root):
    error = _diagnostic(
        root,
        '[\n'
        '  { "type": "machine", "name": "b", "platform": "dos",\n'
        '    "devices": { "hdd0": "d" },\n'
        '    "boot": ["hdd0",\n'
        '             "cdrom0"] }\n'
        ']\n')
    assert (error.line, error.column) == (5, 14)
    assert error.rule_id == "drive.boot-undeclared"


def test_a_value_handed_in_directly_is_unlocated():
    with pytest.raises(StaticError) as caught:
        parse_document([{"type": "machine", "name": "b",
                         "platform": "linux"}])
    assert caught.value.line is None
    assert str(caught.value) == (
        "platform must be one of dos, openbsd, win9x, winnt, "
        "got: 'linux'")


def test_the_breadcrumb_is_unchanged_by_locating(root):
    """Position was the gap; the wording was not, and did not move."""
    error = _diagnostic(
        root,
        '[\n'
        '  { "name": "m", "location": "${mem:-512M}" }\n'
        ']\n')
    assert "spec.location: unknown reference qualifier 'mem'" in str(error)


# Network devices (D120): an attachment (nat/bridged), never a
# chipset. Shorthand desugars the same way a bare drive medium does.

def _machine_with_network(network):
    return _parse([{"type": "machine", "name": "rig", "platform": "dos",
                    "devices": network}]).machines["rig"]


def test_a_bare_attachment_name_is_shorthand():
    machine = _machine_with_network({"net0": "nat"})
    net0 = machine.network["net0"]
    assert (net0.attachment, net0.interface) == ("nat", None)


def test_bridged_desugars_the_same_way():
    machine = _machine_with_network({"net0": "bridged"})
    assert machine.network["net0"].attachment == "bridged"


def test_the_object_form_carries_an_explicit_interface():
    machine = _machine_with_network(
        {"net0": {"attachment": "bridged", "interface": "eth0"}})
    net0 = machine.network["net0"]
    assert (net0.attachment, net0.interface) == ("bridged", "eth0")


def test_an_interface_may_be_a_property_reference():
    machine = _machine_with_network(
        {"net0": {"attachment": "bridged", "interface": "${host-nic}"}})
    interface = machine.network["net0"].interface
    assert isinstance(interface, document.Deferred)
    assert interface.references[0].target == "host-nic"


# The NIC model override (D122): omitted, it's platform-resolved
# (never authored); named, it's a closed vocabulary checked the same
# way the attachment is.

def test_a_model_may_be_named_explicitly():
    machine = _machine_with_network(
        {"net0": {"attachment": "nat", "model": "ne2k"}})
    assert machine.network["net0"].model == "ne2k"


def test_a_model_is_optional():
    machine = _machine_with_network({"net0": "nat"})
    assert machine.network["net0"].model is None


def test_a_model_is_valid_on_either_attachment():
    machine = _machine_with_network(
        {"net0": {"attachment": "bridged", "model": "pcnet"}})
    assert machine.network["net0"].model == "pcnet"


def test_an_unknown_model_is_refused():
    with pytest.raises(StaticError) as caught:
        _machine_with_network({"net0": {"attachment": "nat",
                                        "model": "e1000"}})
    assert caught.value.rule_id == "value.not-in-vocabulary"


def test_an_interface_on_nat_is_refused():
    with pytest.raises(StaticError) as caught:
        _machine_with_network(
            {"net0": {"attachment": "nat", "interface": "eth0"}})
    assert caught.value.rule_id == "network.interface-on-nat"


def test_an_unknown_attachment_is_refused():
    with pytest.raises(StaticError) as caught:
        _machine_with_network({"net0": "dhcp"})
    assert caught.value.rule_id == "value.not-in-vocabulary"


def test_a_network_object_with_unknown_keys_is_refused():
    with pytest.raises(StaticError) as caught:
        _machine_with_network({"net0": {"attachment": "nat", "bogus": 1}})
    assert caught.value.rule_id == "field.unknown"


def test_a_network_object_without_attachment_is_refused():
    with pytest.raises(StaticError) as caught:
        _machine_with_network({"net0": {"interface": "eth0"}})
    assert caught.value.rule_id == "network.without-attachment"


def test_net_slots_run_zero_to_three():
    machine = _machine_with_network({"net3": "nat"})
    assert machine.network["net3"].attachment == "nat"
    with pytest.raises(StaticError) as caught:
        _machine_with_network({"net4": "nat"})
    assert caught.value.rule_id == "device.slot-out-of-range"


def test_an_invalid_network_key_is_refused():
    with pytest.raises(StaticError) as caught:
        _machine_with_network({"eth0": "nat"})
    assert caught.value.rule_id == "device.key-invalid"


def test_a_machine_with_no_network_declares_none():
    machine = _machine_with_network({})
    assert machine.network == {}


def test_drives_and_nics_share_one_devices_map():
    doc = _parse([{"type": "machine", "name": "rig", "platform": "dos",
                   "devices": {"hdd0": "blank", "net0": "nat"}}])
    machine = doc.machines["rig"]
    assert set(machine.devices) == {"hdd0", "net0"}
    assert set(machine.drives) == {"hdd0"}
    assert set(machine.network) == {"net0"}


def test_boot_refuses_a_network_slot():
    with pytest.raises(StaticError) as caught:
        _parse([{"type": "machine", "name": "rig", "platform": "dos",
                 "devices": {"net0": "nat"}, "boot": ["net0"]}])
    assert caught.value.rule_id == "drive.boot-undeclared"


# Share devices (F68): a host directory presented to the guest. Value
# forms mirror a drive's — a media name, an object, or an inline media
# — minus `null`, since an empty share means nothing.

def _machine_with_shares(shares):
    return _parse([{"type": "machine", "name": "rig", "platform": "dos",
                    "devices": shares}]).machines["rig"]


def test_a_bare_media_name_is_shorthand_for_a_share():
    machine = _machine_with_shares({"share0": "hostdir"})
    share0 = machine.shares["share0"]
    assert (share0.media, share0.model) == ("hostdir", None)


def test_a_share_object_carries_an_explicit_model():
    machine = _machine_with_shares(
        {"share0": {"media": "hostdir", "model": "vvfat"}})
    assert machine.shares["share0"].model == "vvfat"


def test_a_share_model_is_optional():
    machine = _machine_with_shares({"share0": "hostdir"})
    assert machine.shares["share0"].model is None


def test_every_share_model_is_accepted_by_the_parser():
    # The parser accepts the whole vocabulary (D122); whether a given
    # model actually renders is a capability question, judged later.
    for model in ("vvfat", "9p", "virtio-fs"):
        machine = _machine_with_shares(
            {"share0": {"media": "hostdir", "model": model}})
        assert machine.shares["share0"].model == model


def test_an_unknown_share_model_is_refused():
    with pytest.raises(StaticError) as caught:
        _machine_with_shares(
            {"share0": {"media": "hostdir", "model": "hgfs"}})
    assert caught.value.rule_id == "value.not-in-vocabulary"


def test_a_share_may_disable_itself():
    machine = _machine_with_shares(
        {"share0": {"media": "hostdir", "enabled": False}})
    assert machine.shares["share0"].enabled is False


def test_a_share_object_with_unknown_keys_is_treated_as_inline_media():
    # Mirrors _drive()'s dispatch: fields beyond model/enabled mean
    # this is an inline media spec, not a bare media reference.
    machine = _machine_with_shares(
        {"share0": {"location": "./hostdir"}})
    share0 = machine.shares["share0"]
    assert share0.inline is not None
    assert share0.inline.location[0].local == "./hostdir"


def test_an_inline_share_composes_with_model():
    # F72: a share's path and its model in one object — model and
    # enabled are pulled off first, so they compose with an inline
    # media spec instead of forcing a promotion to a named media.
    machine = _machine_with_shares(
        {"share0": {"location": "./hostdir", "model": "9p"}})
    share0 = machine.shares["share0"]
    assert share0.model == "9p"
    assert share0.inline is not None
    assert share0.inline.location[0].local == "./hostdir"


def test_an_inline_share_composes_with_model_and_enabled():
    machine = _machine_with_shares(
        {"share0": {"location": "./hostdir", "model": "9p",
                    "enabled": False}})
    share0 = machine.shares["share0"]
    assert (share0.model, share0.enabled) == ("9p", False)
    assert share0.inline is not None
    assert share0.inline.location[0].local == "./hostdir"


def test_a_named_share_still_composes_with_model_and_enabled():
    # {media, model, enabled} kept working unchanged (F72 is a strict
    # widening of the inline form, not a redefinition of this one).
    machine = _machine_with_shares(
        {"share0": {"media": "hostdir", "model": "9p", "enabled": False}})
    share0 = machine.shares["share0"]
    assert (share0.media, share0.model, share0.enabled) == \
        ("hostdir", "9p", False)


def test_a_share_path_key_is_still_refused():
    # DECLINED in F72: a `path` key next to model would work, but adds
    # a second spelling for where a payload comes from. `location` is
    # the only one.
    with pytest.raises(StaticError) as caught:
        _machine_with_shares(
            {"share0": {"path": "./hostdir", "model": "9p"}})
    assert caught.value.rule_id == "field.unknown"


def test_a_share_object_without_media_is_refused():
    with pytest.raises(StaticError) as caught:
        _machine_with_shares({"share0": {"model": "vvfat"}})
    assert caught.value.rule_id == "share.without-media"


def test_a_null_share_is_refused():
    with pytest.raises(StaticError) as caught:
        _machine_with_shares({"share0": None})
    assert caught.value.rule_id == "share.null-not-allowed"


def test_share_slots_run_zero_to_three():
    machine = _machine_with_shares({"share3": "hostdir"})
    assert machine.shares["share3"].media == "hostdir"
    with pytest.raises(StaticError) as caught:
        _machine_with_shares({"share4": "hostdir"})
    assert caught.value.rule_id == "device.slot-out-of-range"


def test_a_machine_with_no_shares_declares_none():
    machine = _machine_with_shares({})
    assert machine.shares == {}


def test_drives_nics_and_shares_share_one_devices_map():
    doc = _parse([{"type": "machine", "name": "rig", "platform": "dos",
                   "devices": {"hdd0": "blank", "net0": "nat",
                               "share0": "hostdir"}}])
    machine = doc.machines["rig"]
    assert set(machine.devices) == {"hdd0", "net0", "share0"}
    assert set(machine.drives) == {"hdd0"}
    assert set(machine.network) == {"net0"}
    assert set(machine.shares) == {"share0"}


def test_boot_refuses_a_share_slot():
    with pytest.raises(StaticError) as caught:
        _parse([{"type": "machine", "name": "rig", "platform": "dos",
                 "devices": {"share0": "hostdir"}, "boot": ["share0"]}])
    assert caught.value.rule_id == "drive.boot-undeclared"
