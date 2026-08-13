# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The property binding pipeline (milestone 8, T3).

Order: --property, blueprint parameter, environment, properties file,
interactive ask. The declared derivation (T4) slots between file and
ask later. Spec: docs/spec/script-spec.md, "The property
sources".
"""

import os

import pytest

from reliquary import binding, credentials, properties
from reliquary import facts as facts_module
from reliquary.binding import (PropertyBindingError, bind_properties,
                               describe_sources)
from reliquary.script_parser import parse_script
from reliquary.script_validation import validate
from tests.test_credentials import FakeStore


def script(text):
    return parse_script(text)


@pytest.fixture
def home(tmp_path):
    """A temp home with the credential store faked out."""
    previous = credentials._set_provider(FakeStore())
    yield str(tmp_path)
    credentials._set_provider(previous)


@pytest.fixture
def store():
    """The fake store itself, where a test inspects what was written."""
    fake = FakeStore()
    previous = credentials._set_provider(fake)
    yield fake
    credentials._set_provider(previous)


@pytest.fixture
def facts(monkeypatch):
    """Route `rlq.*` facts through a controlled table.

    So no test depends on the host account.
    """
    table = {}
    monkeypatch.setattr(facts_module, "resolve", table.get)
    monkeypatch.setattr(facts_module, "is_fact",
                        lambda key: key in table or key.startswith("rlq."))
    return table


def _env(monkeypatch, **values):
    for name, value in values.items():
        monkeypatch.setenv(name, value)


# The source order.

def test_flag_beats_every_other_source(home, monkeypatch):
    properties.set_property("owner", "from-file", context=home)
    _env(monkeypatch, RELIQUARY_PROPERTY_OWNER="from-env")
    bound = bind_properties(script("property owner\n"), context=home,
                            explicit={"owner": "from-flag"},
                            parameters={"owner": "from-parameter"})
    assert bound.values["owner"] == "from-flag"
    assert bound.sources["owner"] == binding.FLAG


def test_parameter_beats_env_and_file(home, monkeypatch):
    properties.set_property("owner", "from-file", context=home)
    _env(monkeypatch, RELIQUARY_PROPERTY_OWNER="from-env")
    bound = bind_properties(script("property owner\n"), context=home,
                            parameters={"owner": "from-parameter"})
    assert bound.values["owner"] == "from-parameter"
    assert bound.sources["owner"] == binding.PARAMETER


def test_env_beats_file(home, monkeypatch):
    properties.set_property("owner", "from-file", context=home)
    _env(monkeypatch, RELIQUARY_PROPERTY_OWNER="from-env")
    bound = bind_properties(script("property owner\n"), context=home)
    assert bound.values["owner"] == "from-env"
    assert bound.sources["owner"] == binding.ENVIRONMENT


def test_file_answers_when_nothing_above_does(home):
    properties.set_property("owner", "from-file", context=home)
    bound = bind_properties(script("property owner\n"), context=home)
    assert bound.values["owner"] == "from-file"
    assert bound.sources["owner"] == binding.FILE


def test_ask_is_last_and_only_when_offered(home):
    asked = []

    def asker(key, prompt, secret):
        asked.append((key, prompt, secret))
        return "from-ask"

    bound = bind_properties(script('property owner prompt="Owner"\n'),
                            context=home, asker=asker)
    assert bound.values["owner"] == "from-ask"
    assert bound.sources["owner"] == binding.ASK
    assert asked == [("owner", "Owner", False)]


def test_noninteractive_unbound_fails_closed(home):
    with pytest.raises(PropertyBindingError) as caught:
        bind_properties(script("property owner\n"), context=home,
                        asker=None)
    assert "owner" in str(caught.value)


# A parameter may redirect to another key.

def test_redirect_resolves_target_through_lower_sources(home):
    properties.set_property("company.key", "resolved", context=home)
    bound = bind_properties(
        script("property install-key\n"),
        parameters={"install-key": {"property": "company.key"}},
        context=home)
    assert bound.values["install-key"] == "resolved"
    assert bound.sources["install-key"] == (
        f"{binding.PARAMETER} -> {binding.FILE}")


def test_redirect_does_not_fall_back_to_the_declared_key(home):
    # The declared key has a file value, but a redirect replaces
    # its resolution entirely -- the target, unanswered, reaches
    # the ask, not the declared key's own file entry.
    properties.set_property("install-key", "declared-file", context=home)
    asked = []

    def asker(key, prompt, secret):
        asked.append(key)
        return "from-ask"

    bound = bind_properties(
        script("property install-key\n"),
        parameters={"install-key": {"property": "missing.key"}},
        context=home, asker=asker)
    assert bound.values["install-key"] == "from-ask"
    assert asked == ["install-key"]


def test_redirect_reads_env_of_the_target(home, monkeypatch):
    _env(monkeypatch, RELIQUARY_PROPERTY_COMPANY_KEY="from-env")
    bound = bind_properties(
        script("property install-key\n"),
        parameters={"install-key": {"property": "company.key"}},
        context=home)
    assert bound.values["install-key"] == "from-env"
    assert bound.sources["install-key"] == (
        f"{binding.PARAMETER} -> {binding.ENVIRONMENT}")


# Secrets, and what each kind may bind from.

def test_secret_binds_from_the_credential_store(store, tmp_path):
    home = str(tmp_path)
    properties.set_property("pw", "hunter2", secret=True, context=home)
    bound = bind_properties(script("property secret pw\n"), context=home)
    assert bound.values["pw"] == "hunter2"
    assert bound.secret_keys == frozenset({"pw"})
    assert bound.secret_values() == {"hunter2"}


def test_secret_cannot_come_from_a_flag(home):
    with pytest.raises(PropertyBindingError) as caught:
        bind_properties(script("property secret pw\n"),
                        explicit={"pw": "hunter2"}, context=home)
    assert "not" in str(caught.value).lower()


def test_secret_may_come_from_the_environment(home, monkeypatch):
    _env(monkeypatch, RELIQUARY_PROPERTY_PW="from-env")
    bound = bind_properties(script("property secret pw\n"), context=home)
    assert bound.values["pw"] == "from-env"


def test_text_declaration_finding_a_secret_is_an_error(home):
    properties.set_property("pw", "hunter2", secret=True, context=home)
    with pytest.raises(PropertyBindingError) as caught:
        bind_properties(script("property pw\n"), context=home)
    assert "secret" in str(caught.value)


def test_secret_declaration_finding_ordinary_is_an_error(home):
    properties.set_property("pw", "plain", context=home)
    with pytest.raises(PropertyBindingError) as caught:
        bind_properties(script("property secret pw\n"), context=home)
    assert "ordinary" in str(caught.value)


def test_secret_marker_without_a_credential_fails_closed(home):
    path = properties._properties_path(context=home)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("pw = @secret\n")
    with pytest.raises(PropertyBindingError) as caught:
        bind_properties(script("property secret pw\n"), context=home)
    assert "credential" in str(caught.value)


# How a key is spelled in the environment.

def test_dots_and_dashes_map_to_underscores(home, monkeypatch):
    _env(monkeypatch,
         RELIQUARY_PROPERTY_PRODUCTS_WINDOWS_98_INSTALL_KEY="k")
    bound = bind_properties(
        script("property products.windows-98.install-key\n"), context=home)
    assert bound.values["products.windows-98.install-key"] == "k"


def test_colliding_keys_fail_before_the_run(home):
    with pytest.raises(PropertyBindingError) as caught:
        bind_properties(script("property a.b\nproperty a-b\n"),
                        context=home)
    message = str(caught.value)
    assert "a.b" in message
    assert "a-b" in message


def test_undeclared_explicit_key_is_rejected(home):
    with pytest.raises(PropertyBindingError) as caught:
        bind_properties(script("property owner\n"),
                        explicit={"stranger": "x"}, context=home)
    assert "stranger" in str(caught.value)


# The declared derivation tier, between the file and the ask.

def test_a_literal_default_answers(home, facts):
    bound = bind_properties(script('property owner default="guest"\n'),
                            context=home)
    assert bound.values["owner"] == "guest"
    assert bound.sources["owner"] == binding.DERIVATION


def test_a_fact_default_answers_when_available(home, facts):
    facts["rlq.host.username"] = "ada"
    bound = bind_properties(
        script('property owner default="${rlq.host.username}"\n'),
        context=home)
    assert bound.values["owner"] == "ada"
    assert bound.sources["owner"] == binding.DERIVATION


def test_an_unavailable_fact_falls_through_to_the_next_candidate(home,
                                                                 facts):
    facts["rlq.host.full-name"] = None  # empty, unanswerable
    bound = bind_properties(
        script('property owner default="${rlq.host.full-name}" '
               'default="fallback"\n'),
        context=home)
    assert bound.values["owner"] == "fallback"


def test_a_curated_fact_prefers_itself_over_a_raw_fallback(home, facts):
    facts["rlq.host.full-name"] = "Ada Lovelace"
    facts["rlq.env.FULLNAME"] = "ada-env"
    bound = bind_properties(
        script('property owner default="${rlq.host.full-name}" '
               'default="${rlq.env.FULLNAME}"\n'),
        context=home)
    assert bound.values["owner"] == "Ada Lovelace"


def test_a_derivation_falls_to_the_ask_when_no_candidate_answers(home,
                                                                 facts):
    facts["rlq.host.full-name"] = None
    bound = bind_properties(
        script('property owner default="${rlq.host.full-name}"\n'),
        context=home, asker=lambda key, prompt, secret: "asked")
    assert bound.values["owner"] == "asked"
    assert bound.sources["owner"] == binding.ASK


def test_an_outer_source_still_beats_the_derivation(home, facts):
    bound = bind_properties(script('property owner default="guest"\n'),
                            context=home, explicit={"owner": "explicit"})
    assert bound.values["owner"] == "explicit"
    assert bound.sources["owner"] == binding.FLAG


def test_a_derivation_references_another_bound_property(home, facts):
    properties.set_property("company", "Acme", context=home)
    bound = bind_properties(
        script('property company\n'
               'property banner default="Welcome to ${company}"\n'),
        context=home)
    assert bound.values["banner"] == "Welcome to Acme"


def test_referents_bind_first_regardless_of_declaration_order(home, facts):
    # `banner` is declared before the `company` it references.
    properties.set_property("company", "Acme", context=home)
    bound = bind_properties(
        script('property banner default="Welcome to ${company}"\n'
               'property company\n'),
        context=home)
    assert bound.values["banner"] == "Welcome to Acme"


def test_a_composed_default_needs_every_reference(home, facts):
    facts["rlq.host.username"] = "ada"
    # The second reference is empty, so the whole candidate is
    # unanswerable and the literal fallback wins.
    facts["rlq.env.TEAM"] = None
    bound = bind_properties(
        script('property tag default="${rlq.host.username}-${rlq.env.TEAM}" '
               'default="anon"\n'),
        context=home)
    assert bound.values["tag"] == "anon"


# The static derivation rules (V5, V6).

def test_secret_with_default_is_rejected():
    with pytest.raises(Exception) as caught:
        validate(script('property secret pw default="x"\n'))
    assert "secret" in str(caught.value)


def test_a_literal_before_another_candidate_is_dead():
    with pytest.raises(Exception) as caught:
        validate(script('property owner default="here" '
                        'default="${rlq.host.username}"\n'))
    assert "dead" in str(caught.value)


def test_a_reference_to_an_undeclared_key_is_rejected():
    with pytest.raises(Exception) as caught:
        validate(script('property owner default="${nobody}"\n'))
    assert "nobody" in str(caught.value)


def test_a_reference_to_a_secret_is_rejected():
    with pytest.raises(Exception) as caught:
        validate(script('property secret pw\n'
                        'property owner default="${pw}"\n'))
    assert "secret" in str(caught.value)


def test_a_cycle_among_derivations_is_rejected():
    with pytest.raises(Exception) as caught:
        validate(script('property a default="${b}"\n'
                        'property b default="${a}"\n'))
    assert "cycle" in str(caught.value)


def test_an_rlq_fact_reference_is_accepted():
    validate(script('property owner default="${rlq.host.username}"\n'))
    validate(script('property owner default="${rlq.env.USER}"\n'))


# The dry twin: which source would answer, without binding.

def test_reports_each_source_without_prompting_or_values(home, monkeypatch):
    properties.set_property("from-file", "v", context=home)
    _env(monkeypatch, RELIQUARY_PROPERTY_FROM_ENV="v")
    sources = describe_sources(
        script("property from-flag\n"
               "property from-param\n"
               "property from-env\n"
               "property from-file\n"
               "property will-ask\n"),
        explicit={"from-flag": "v"},
        parameters={"from-param": "v"},
        context=home)
    assert sources == {
        "from-flag": binding.FLAG,
        "from-param": binding.PARAMETER,
        "from-env": binding.ENVIRONMENT,
        "from-file": binding.FILE,
        "will-ask": binding.ASK,
    }


def test_dry_run_never_reads_a_secret_value(home):
    # A marker present, credential absent: dry mode names the file
    # as the source without fetching (nothing to fetch here).
    path = properties._properties_path(context=home)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("pw = @secret\n")
    sources = describe_sources(script("property secret pw\n"),
                               context=home)
    assert sources == {"pw": binding.FILE}
