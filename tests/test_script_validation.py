# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the static rules over the typed tree.

**Every rejection here is a case in one table, and the table is
parametrised over the rule it drives** (F58). Each case is a collected
node named for its rule and label, so a case is selected by name while
it is being fixed — `pytest tests/test_script_validation.py -k
V10-goto-undeclared` — and `test_every_enforced_rule_is_exercised`
walks `RULE_OF`'s whole range, so a rule added to the language with no
case is a **failing node** rather than an absence nobody counts. That
is why the table covers V1, V2, V4 and V12 too, whose deeper cases
live with the layers that raise them (`test_script_nodes` for the
lexer and block structure, `test_script_timing` for the placement
matrix and the cycle backstop): one case each here keeps the coverage
check total, with no second list of exemptions to keep in step.

A case that asserts more than its rule — a line number, a second
sentence in the message — keeps a function of its own below the table
and drives the same helper.
"""

import collections

import pytest

from reliquary.script_nodes import RULE_OF, ScriptParseError
from reliquary.script_parser import parse_script

_HEAD = "platform dos\n"

Case = collections.namedtuple("Case", "label rule message source")


def _rejects(source, message, rule):
    """Assert that a script fails, naming its problem and rule.

    ``rule`` is either the V-number a test was written against or the
    diagnostic's own dotted id — the V-numbers where a rule has
    several diagnostics and the test means any of them, the id where
    it means one exactly.

    Either way the assertion goes through the diagnostic's ``rule_id``
    rather than matching message text, which is stronger than the
    substring check it replaced: `"V1"` used to match a message that
    merely mentioned V12.
    """
    with pytest.raises(ScriptParseError) as caught:
        parse_script(source)
    error = caught.value
    assert message in error.message, source
    assert error.rule_id is not None, (
        f"expected {rule}, but this diagnostic carries no id yet")
    if rule in RULE_OF:
        assert error.rule_id == rule, source
    else:
        assert RULE_OF.get(error.rule_id) == rule, (
            f"{error.rule_id} enforces {RULE_OF.get(error.rule_id)}, "
            f"not {rule} (source: {source!r})")
    return error


def _reserved_phase(word):
    return Case(f"phase-named-{word}", "V5",
                f"a phase may not be a reserved node name: {word}",
                _HEAD + f"entry {word}\nphase {word} {{\n    finish\n}}\n")


CASES = (
    # The tiers below this module, one case each so the coverage
    # check over RULE_OF's range needs no exemption list. The cases
    # that work these rules properly live with the layer that raises
    # them.
    Case("unterminated-string", "V1", "unterminated string",
         _HEAD + 'wait "unclosed\n'),
    Case("modifier-not-allowed", "V2",
         "enter does not accept the modifier 'timeout'",
         _HEAD + 'enter "x" timeout=5m\n'),
    Case("duplicate-modifier", "V4", "duplicate modifier: timeout",
         _HEAD + "entry p\nphase p timeout=5m timeout=6m {\n"
         "    finish\n}\n"),
    Case("cycle-without-deadline", "V12", "the phase graph can cycle",
         _HEAD + "entry a\nphase a {\n    goto a\n}\n"),

    # V3 and V10: the two shapes, and what belongs to each.
    Case("entry-in-linear", "V3", "entry is invalid in a linear script",
         _HEAD + "entry somewhere\nstart\n"),
    Case("entry-missing", "V3", "declares the entry phase",
         _HEAD + "phase a {\n    finish\n}\n"),
    Case("entry-undeclared", "V10", "entry names an undeclared phase: b",
         _HEAD + "entry b\nphase a {\n    finish\n}\n"),
    Case("goto-undeclared", "V10",
         "goto names an undeclared phase: elsewhere",
         _HEAD + "entry a\nphase a {\n    goto elsewhere\n}\n"),
    Case("duplicate-phase", "V5", "duplicate phase: a",
         _HEAD + "entry a\nphase a {\n    finish\n}\n"
         "phase a {\n    finish\n}\n"),
    # script-spec.md, "Grammar": reserved node names cannot name
    # phases. The lexer makes a word a keyword only where a node may
    # start, so these parse cleanly and validation is what refuses
    # them.
    _reserved_phase("enter"),
    _reserved_phase("timeout"),
    _reserved_phase("phase"),
    _reserved_phase("goto"),
    _reserved_phase("set-boot"),
    Case("property-is-a-node-name", "V5",
         "a property key may not be a reserved node name: press",
         _HEAD + 'property text press\nwait "x"\n'),
    Case("finish-in-linear", "V10", "finish is invalid in a linear script",
         _HEAD + 'wait "x"\nfinish\n'),
    Case("goto-in-linear", "V10", "goto is invalid in a linear script",
         _HEAD + "goto a\n"),
    Case("transfer-in-a-linear-handler", "V10",
         "finish is invalid in a linear script",
         _HEAD + 'wait {\n    on "a" {\n        finish\n    }\n'
         '    on "b" {\n        press enter\n    }\n}\n'),

    # V9 and V11: sequential or reactive, and how each ends.
    Case("mixed-phase", "V9", "sequential or reactive, never both",
         _HEAD + "entry a\nphase a {\n    press enter\n"
         '    always "x" {\n        finish\n    }\n}\n'),
    Case("on-outside-branching-wait", "V9",
         "on is legal only inside a branching wait",
         _HEAD + 'entry a\nphase a {\n    on "x" {\n        finish\n'
         "    }\n}\n"),
    Case("always-outside-reactive-phase", "V9",
         "always is legal only directly inside a reactive phase",
         _HEAD + 'entry a\nphase a {\n    wait {\n'
         '        always "x" {\n            finish\n        }\n'
         '        on "y" {\n            finish\n        }\n    }\n}\n'),
    Case("phase-falls-through", "V11", "does not end in goto or finish",
         _HEAD + "entry a\nphase a {\n    press enter\n}\n"),
    Case("handler-falls-through", "V11", "does not end in goto or finish",
         _HEAD + "entry a\nphase a {\n    wait {\n"
         '        on "x" {\n            finish\n        }\n'
         '        on "y" {\n            press enter\n        }\n'
         "    }\n}\n"),
    Case("unreachable-statement", "V11",
         "unreachable statement: finish ends its statement list",
         _HEAD + "entry a\nphase a {\n    finish\n    press enter\n}\n"),

    # V8: what a branching wait is, and where it may stand.
    Case("too-few-handlers", "V8", "at least two handlers",
         _HEAD + 'wait {\n    on "x" {\n        press enter\n    }\n}\n'),
    Case("branching-condition", "V8", "carries no condition of its own",
         _HEAD + 'wait machine=stopped {\n'
         '    on "x" {\n        press enter\n    }\n'
         '    on "y" {\n        press enter\n    }\n}\n'),
    Case("branching-in-handler", "V8",
         "may not appear inside a handler body",
         _HEAD + 'wait {\n    on "x" {\n        wait {\n'
         '            on "y" {\n                press enter\n'
         "            }\n"
         '            on "z" {\n                press enter\n'
         "            }\n        }\n    }\n"
         '    on "w" {\n        press enter\n    }\n}\n'),
    Case("branching-in-standing-handler", "V8",
         "may not appear inside a handler body",
         _HEAD + "entry a\nphase a {\n"
         '    always "x" {\n        wait {\n'
         '            on "y" {\n                finish\n            }\n'
         '            on "z" {\n                finish\n            }\n'
         "        }\n    }\n}\n"),

    # V7: one condition, on a known channel, of the right kind.
    Case("two-conditions", "V7", "carries more than one condition",
         _HEAD + 'wait "x" machine=stopped\n'),
    Case("two-channels", "V7", "carries more than one condition",
         _HEAD + "wait machine=stopped machine=stopped\n"),
    Case("missing-condition", "V7", "wait requires a condition",
         _HEAD + "wait timeout=5m\n"),
    Case("bare-state-word", "V7", "machine state is spelled machine=stopped",
         _HEAD + "wait stopped\n"),
    Case("bare-word", "V7",
         "the screen is observed by a bare string or regex",
         _HEAD + "wait ready\n"),
    Case("screen-named", "V7", "the screen channel has no named spelling",
         _HEAD + 'wait screen="C:\\\\>"\n'),
    Case("unknown-channel", "V7", "unknown observation channel: serial",
         _HEAD + 'wait serial="login:"\n'),
    Case("machine-takes-a-state", "V7", "machine observes the state stopped",
         _HEAD + 'wait machine="stopped"\n'),
    Case("machine-state-is-closed", "V7",
         "machine observes the state stopped",
         _HEAD + "wait machine=running\n"),
    Case("handler-two-conditions", "V7",
         "on carries more than one condition",
         _HEAD + 'wait {\n    on "x" machine=stopped {\n'
         "        press enter\n    }\n"
         '    on "y" {\n        press enter\n    }\n}\n'),
    Case("handler-unknown-channel", "V7",
         "unknown observation channel: disk",
         _HEAD + "entry a\nphase a {\n"
         '    always disk=full {\n        finish\n    }\n}\n'),
    Case("handler-missing-condition", "V7", "always requires a condition",
         _HEAD + "entry a\nphase a {\n"
         "    always stable=1s {\n        finish\n    }\n}\n"),

    # V13: a watch pattern is non-empty, and a regex compiles. The
    # rule was specified when the surface was adopted and enforced by
    # nothing until the spec-inventory comparison found it. Each case
    # parsed cleanly before that: an empty pattern made a `wait` a
    # no-op that passed on its first sample, and a malformed regex
    # reached `re.search` in the sample loop, where it raised
    # `re.error` — exit 1, a fault outside the taxonomy, for a defect
    # the script text alone shows.
    Case("empty-string-pattern", "V13",
         "an empty watch pattern matches every screen",
         _HEAD + 'wait ""\n'),
    Case("empty-regex-pattern", "V13",
         "an empty watch pattern matches every screen",
         _HEAD + "wait //\n"),
    Case("uncompilable-regex", "V13", "the regex does not compile",
         _HEAD + "wait /a(b/\n"),
    Case("handler-uncompilable-regex", "V13",
         "the regex does not compile",
         _HEAD + 'wait {\n    on /x[/ {\n        press enter\n    }\n'
         '    on "y" {\n        press enter\n    }\n}\n'),
    Case("handler-empty-pattern", "V13", "an empty watch pattern",
         _HEAD + "entry a\nphase a {\n"
         '    always "" {\n        finish\n    }\n}\n'),

    # The HTTP declarations are static and legality-tier like the
    # rest, so they carry ids rather than a V-number of their own.
    Case("path-not-absolute", "http.path-not-absolute",
         "content path must begin with '/'",
         _HEAD + 'http {\n    content answer "answer.txt" """\n'
         '        one\n    """\n}\nstart\n'),
    Case("path-traversal", "http.path-traversal",
         "content path may not contain . or ..",
         _HEAD + 'http {\n    content answer "/../answer.txt" """\n'
         '        one\n    """\n}\nstart\n'),
    Case("duplicate-content-path", "http.duplicate-content-path",
         "duplicate content path: /answer.txt",
         _HEAD + 'http {\n    content answer "/answer.txt" """\n'
         '        one\n    """\n    content other "/answer.txt" """\n'
         '        two\n    """\n}\nstart\n'),
    Case("duplicate-content-name", "http.duplicate-content-name",
         "duplicate content name: answer",
         _HEAD + 'http {\n    content answer "/answer.txt" """\n'
         '        one\n    """\n    content answer "/other.txt" """\n'
         '        two\n    """\n}\nstart\n'),
    Case("duplicate-content-name-inline", "http.duplicate-content-name",
         "duplicate content name: answer",
         _HEAD + 'http start {\n    content answer "/answer.txt" """\n'
         '        one\n    """\n    content answer "/other.txt" """\n'
         '        two\n    """\n}\n'),
    Case("empty-body", "http.empty-body", "has an empty body",
         _HEAD + 'http {\n    content answer "/answer.txt" """\n'
         '    """\n}\nstart\n'),
    Case("port-range-inverted", "http.port-range-inverted",
         "port-min must be less than or equal to port-max",
         _HEAD + 'http port-min=9000 port-max=8000 {\n'
         '    content answer "/answer.txt" """\n        one\n    """\n'
         '}\nstart\n'),
    Case("port-out-of-range", "http.port-out-of-range",
         "port-min is not a TCP port",
         _HEAD + 'http port-min=70000 {\n'
         '    content answer "/answer.txt" """\n        one\n    """\n'
         '}\nstart\n'),
    Case("start-without-content", "http.start-without-content",
         "http start requires declared or inline content",
         _HEAD + "http start\n"),
    Case("unknown-action", "http.unknown-action",
         "http action must be start or stop",
         _HEAD + 'http {\n    content answer "/answer.txt" """\n'
         '        one\n    """\n}\nhttp begin\n'),
    Case("undeclared-content", "http.undeclared-content",
         "http start names undeclared content: missing",
         _HEAD + 'http {\n    content answer "/answer.txt" """\n'
         '        one\n    """\n}\nhttp start missing\n'),
    Case("stop-takes-nothing", "http.stop-takes-nothing",
         "http stop takes no content names",
         _HEAD + "http stop answer\n"),
    Case("property-rlq-namespace", "V5", "rlq namespace",
         _HEAD + "property rlq.http.url\nstart\n"),
    Case("property-reliquary-namespace", "V5", "reliquary namespace",
         _HEAD + "property reliquary.http.url\nstart\n"),
    Case("http-without-block", "V6",
         "rlq.http.* properties require an http block",
         _HEAD + 'enter "${rlq.http.url}/answer.txt"\n'),

    # V14: `press` uses the language's closed portable key set.
    Case("unknown-key-name", "V14", "'wingding' is not a portable key name",
         _HEAD + "press wingding\n"),
    Case("bare-character-key", "V14", "'c' is not a portable key name",
         _HEAD + "press c\n"),
    Case("empty-chord-member", "V14", "'' is not a portable key name",
         _HEAD + "press ctrl++c\n"),

    # A machine-variable key is the consumer's, but not reliquary's.
    Case("variable-rlq-namespace", "V5", "rlq namespace are reserved",
         _HEAD + 'set rlq.ready "yes"\n'),
    Case("variable-reliquary-namespace", "V5",
         "reliquary namespace are reserved",
         _HEAD + 'set reliquary "yes"\n'),
    Case("variable-reserved-in-a-handler", "V5",
         "rlq namespace are reserved",
         _HEAD + 'wait {\n    on "a" {\n        set rlq.x "1"\n'
         "        finish\n    }\n"
         '    on "b" {\n        finish\n    }\n}\n'),

    # The scoped machine-state change (F54). Each rule it carries is
    # an existing rule stretched, which is what the pledge weighed:
    # the head vocabulary is V14's closed-vocabulary rule, what a
    # block may hold is V2's signatures, one-scope-per-target is V9's
    # placement, distinct boot keys are V5's uniqueness, and the two
    # shapes never mixing is V10 — now decided here rather than by the
    # grammar, which can no longer see which shape a `with` opens.
    Case("scope-unknown-head", "V14", "with does not scope 'medium'",
         _HEAD + "with medium cdrom0 {\n    start\n}\n"),
    Case("scope-set-boot-as-a-head", "V14", "with does not scope 'set-boot'",
         _HEAD + "with set-boot cdrom0 {\n    start\n}\n"),
    Case("scope-insert-without-a-medium", "V2",
         "with insert takes a slot and a @media or $property reference",
         _HEAD + "with insert cdrom0 {\n    start\n}\n"),
    Case("scope-eject-takes-one-slot", "V2", "with eject takes one slot",
         _HEAD + "with eject cdrom0 cdrom1 {\n    start\n}\n"),
    Case("scope-wraps-a-statement-in-a-phased-script", "V2",
         "wraps phases, and this one holds the statement start",
         _HEAD + "entry a\nwith boot cdrom0 {\n    start\n}\n"
         "phase a {\n    finish\n}\n"),
    Case("scope-doubled-on-the-boot-order", "V9",
         "the boot order is already scoped by an enclosing with",
         _HEAD + "with boot cdrom0 {\n    with boot hdd0 {\n"
         "        start\n    }\n}\n"),
    Case("scope-doubled-on-one-slot", "V9",
         "cdrom0 is already scoped by an enclosing with",
         _HEAD + "with insert cdrom0 @disk {\n"
         "    with eject cdrom0 {\n        start\n    }\n}\n"),
    Case("scope-boot-names-one-drive-twice", "V5",
         "boot names one drive twice: cdrom0 and cdrom0",
         _HEAD + "with boot cdrom0 cdrom0 {\n    start\n}\n"),
    Case("scope-boot-names-one-drive-by-two-spellings", "V5",
         "boot names one drive twice: cdrom and cdrom0",
         _HEAD + "with boot cdrom cdrom0 {\n    start\n}\n"),
    Case("statement-outside-every-phase", "V10",
         "start is outside every phase",
         _HEAD + "entry a\nstart\nphase a {\n    finish\n}\n"),
)

#: Scripts the rules must let through, asserted by parsing alone.
#: The first four are D53's line: it refused reserving key names and
#: drive slots globally — syntax words are reserved, domain
#: vocabularies are not, which is the line Java and C# draw. So a
#: phase may still be named for a key or a slot, and `press enter`
#: still means the key.
ACCEPTS = (
    ("phase-named-for-a-slot",
     _HEAD + "entry cdrom0\nphase cdrom0 {\n    finish\n}\n"),
    ("phase-named-for-a-key",
     _HEAD + "entry esc\nphase esc {\n    finish\n}\n"),
    ("press-takes-a-key-name", _HEAD + "press enter\n"),
    ("screenshot-takes-a-name", _HEAD + "screenshot end\n"),
    ("an-ordinary-variable-key", _HEAD + 'set suite.result "PASS"\n'),
    # Scopes on different targets nest freely, and each shape wraps
    # its own units.
    ("a-scope-over-phases",
     _HEAD + "entry a\nwith boot cdrom0 {\n    phase a {\n"
     "        finish\n    }\n}\n"),
    ("a-scope-over-statements",
     _HEAD + "with insert cdrom0 @disk {\n    start\n}\n"),
    ("scopes-on-different-targets-nest",
     _HEAD + "with boot cdrom0 {\n    with insert cdrom0 @disk {\n"
     "        with eject floppy0 {\n            start\n        }\n"
     "    }\n}\n"),
    ("a-scope-beside-a-phase",
     _HEAD + "entry a\nwith boot cdrom0 {\n    phase a {\n"
     "        goto b\n    }\n}\nphase b {\n    finish\n}\n"),
    ("a-phase-named-with-is-still-refused-elsewhere",
     _HEAD + "entry withdraw\nphase withdraw {\n    finish\n}\n"),
)


@pytest.mark.parametrize(
    "case", CASES, ids=[f"{case.rule}-{case.label}" for case in CASES])
def test_a_case_is_rejected_by_the_rule_it_names(case):
    _rejects(case.source, case.message, case.rule)


@pytest.mark.parametrize(
    "source", [source for _, source in ACCEPTS],
    ids=[label for label, _ in ACCEPTS])
def test_an_accepted_script_parses(source):
    parse_script(source)


@pytest.mark.parametrize(
    "rule", sorted({rule for rule in RULE_OF.values() if rule}))
def test_every_enforced_rule_is_exercised(rule):
    """Rule coverage, one collected node per rule.

    `RULE_OF`'s range is the static tier's rule universe. A rule no
    case drives is enforcement nothing exercises — the V13 class,
    which reached the guest loop as an untyped fault because nothing
    had ever driven the rule it violated. The corpus asserts the same
    property over fixtures (`test_script_corpus`); this is the unit
    half, and it fails as a **named missing rule** rather than as a
    count nobody reads.
    """
    driven = {RULE_OF[case.rule] if case.rule in RULE_OF else case.rule
              for case in CASES}
    assert rule in driven, (
        f"{rule} is enforced and no case in CASES drives it. Add one "
        "— a rejection nothing drives is enforcement only by reading "
        "the code.")


# What a case cannot say: a line number, or a second sentence.

def test_goto_undeclared_names_the_line_it_stands_on():
    error = _rejects(_HEAD + "entry a\nphase a {\n    goto elsewhere\n}\n",
                     "goto names an undeclared phase: elsewhere", "V10")
    assert error.line == 4


def test_a_mixed_phase_names_the_line_the_handler_opens_on():
    error = _rejects(
        _HEAD + "entry a\nphase a {\n    press enter\n"
        '    always "x" {\n        finish\n    }\n}\n',
        "sequential or reactive, never both", "V9")
    assert error.line == 5


def test_a_falling_phase_names_its_closing_line():
    error = _rejects(_HEAD + "entry a\nphase a {\n    press enter\n}\n",
                     "does not end in goto or finish", "V11")
    assert error.line == 4


def test_an_unreachable_statement_names_its_own_line():
    error = _rejects(
        _HEAD + "entry a\nphase a {\n    finish\n    press enter\n}\n",
        "unreachable statement: finish ends its statement list", "V11")
    assert error.line == 5


def test_a_bare_state_word_says_what_it_is_not():
    error = _rejects(_HEAD + "wait stopped\n",
                     "machine state is spelled machine=stopped", "V7")
    assert "'stopped' is not a condition" in error.message


def test_a_malformed_regex_names_the_syntax_it_was_read_as():
    error = _rejects(_HEAD + "wait /a(b/\n", "the regex does not compile",
                     "V13")
    assert "Python's re syntax" in error.message
    assert error.line == 2


# What the rules let through, beyond parsing.

def test_a_linear_script_needs_no_terminator():
    script = parse_script(_HEAD + 'wait "C:\\\\>"\nscreenshot booted\n')
    assert [s.verb for s in script.statements] == ["wait", "screenshot"]


def test_a_branching_wait_terminates_when_every_handler_does():
    script = parse_script(
        _HEAD + "entry a\ndeadline 10m\nphase a {\n    wait {\n"
        '        on "x" {\n            finish\n        }\n'
        '        on "y" {\n            goto a\n        }\n    }\n}\n')
    assert script.phases[0].statements[0].verb == "wait"


def test_a_reactive_phase_needs_no_terminator():
    script = parse_script(
        _HEAD + "entry a\ndeadline 10m\nphase a {\n"
        '    always "x" {\n        press enter\n    }\n}\n')
    assert len(script.phases[0].handlers) == 1


def test_an_empty_handler_body_is_not_a_shape_error():
    # The grammar requires a statement in a handler body; the
    # explicit no-action branch is the spec's, not V8's.
    with pytest.raises(ScriptParseError):
        parse_script(
            _HEAD + 'wait {\n    on "x" {\n    }\n'
            '    on "y" {\n        press enter\n    }\n}\n')


def test_a_handler_names_a_non_default_channel():
    script = parse_script(
        _HEAD + "entry a\ndeadline 10m\nphase a {\n    wait timeout=5m {\n"
        '        on "Press a key..." {\n            press enter\n'
        "        }\n"
        "        on machine=stopped {\n            goto a\n        }\n"
        "    }\n    finish\n}\n")
    handlers = script.phases[0].statements[0].handlers
    assert [h.condition.channel for h in handlers] == ["screen", "machine"]


def test_the_screen_and_machine_channels_validate():
    script = parse_script(
        _HEAD + 'wait "C:\\\\>"\nwait /[0-9]+ files/\n'
        "wait machine=stopped timeout=2m\n")
    assert [(s.condition.channel, s.condition.kind)
            for s in script.statements] == [
        ("screen", "text"), ("screen", "regex"), ("machine", "state")]


def test_an_interpolation_alone_is_a_pattern():
    # `${key}` is text the run binds, so the authored pattern
    # is not empty even though it carries no literal character.
    script = parse_script(_HEAD + 'property text target\nwait "${target}"\n')
    assert script.statements[0].condition.kind == "text"


def test_a_machine_state_carries_no_pattern_rule():
    script = parse_script(_HEAD + "wait machine=stopped\n")
    assert script.statements[0].condition.value == "stopped"


def test_every_portable_key_name_is_valid():
    names = (
        "enter esc tab space backspace up down left right insert delete "
        "home end pageup pagedown f1 f2 f3 f4 f5 f6 f7 f8 f9 f10 f11 "
        "f12 ctrl alt shift"
    )
    script = parse_script(_HEAD + "press " + names + "\n")
    assert script.statements[0].arguments == tuple(names.split())


def test_a_chord_may_contain_a_printable_character():
    script = parse_script(_HEAD + "press ctrl+c ctrl+alt+delete\n")
    assert script.statements[0].arguments == ("ctrl+c", "ctrl+alt+delete")


def test_http_stop_is_allowed_without_declared_content():
    script = parse_script(_HEAD + "http stop\n")
    assert script.statements[0].arguments == ("stop",)


def test_http_start_can_define_inline_content_without_declaration():
    script = parse_script(
        _HEAD + 'http start {\n    content answer "/answer.txt" """\n'
        '        one\n    """\n}\n'
        'enter "${rlq.http.url}/answer.txt"\n')
    assert script.statements[0].contents[0].name == "answer"


def test_http_start_can_redefine_declared_content_inline():
    script = parse_script(
        _HEAD + 'http {\n    content answer "/answer.txt" """\n'
        '        one\n    """\n}\n'
        'http start {\n    content answer "/answer.txt" """\n'
        '        two\n    """\n}\n')
    assert script.statements[0].contents[0].body.text == "two\n"


def test_a_static_error_renders_its_source_line():
    """A static error carries the same context as a parse error."""
    with pytest.raises(ScriptParseError) as caught:
        parse_script(_HEAD + "wait stopped\n", path="verify.rlqs")
    rendered = str(caught.value)
    assert "verify.rlqs:2:6: error:" in rendered
    assert "wait stopped" in rendered
    assert "^" in rendered
