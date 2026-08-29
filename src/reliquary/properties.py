# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The user properties file.

`<reliquary_home>/user.properties` is a flat, user-owned file of
`key = value` lines. A person edits it directly, and Reliquary only
ever changes the one line a command names — every comment, blank
line, and ordering choice elsewhere in the file is left exactly as
it was. That is why the format is line-based instead of JSON. The
normative spec is docs/spec/script-properties.md.

Despite the familiar extension this is deliberately not the Java
properties format: no unicode escapes, no line continuations, no
quoting. A value is the trimmed remainder of its line, verbatim.

Secret values never live in this file. A secret property's line
carries the `@secret` marker, and its actual value belongs in the
host credential store, which lands with the store itself (milestone
8, T2 in planning/TASKS.md). Until then, trying to set a secret
fails with an error rather than writing a value into a file that
must never hold it.
"""

import os
import re
import tempfile

from . import credentials
from .errors import StaticError
from .home import Context, home_dir

_SEGMENT = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
_RESERVED = ("rlq", "reliquary")
_SECRET_TOKEN = "@secret"

class PropertiesError(StaticError):
    """A malformed properties file, key, or value.

    A STATIC ERROR (exit code 2): the file's own text decides every
    one of these problems, and the person who wrote that text caused
    them. It subclasses the root error class directly, the way it did
    back when the four error classes lined up with stages of a script
    run; D58 made those four classes apply everywhere, not just to
    scripts, and a properties file counts as authored input the same
    way a script does.
    """

def secret_marker():
    """Return the marker value shown in place of a secret property's
    real value."""
    return {"secret": True}

def is_secret(value):
    """Return True if a returned value is the secret marker."""
    return isinstance(value, dict) and value.get("secret") is True

def _properties_path(context=None, properties_file=None):
    """Return the path of the selected properties file.

    Passing an explicit `properties_file` replaces the home
    directory's file rather than adding to it, so pointing it at a
    project's own file makes a run self-contained regardless of the
    environment it runs in. A `Context` object carrying a
    `properties_file` field is used the same way when no argument is
    given — `Context` is the object the session passes down through
    its calls, carrying settings like this one (P26). The CLI's
    `--properties` flag and the `RELIQUARY_PROPERTIES` environment
    variable both end up setting that `Context` field, when the CLI
    builds its `Context`; this function itself never reads
    environment variables.
    """
    if properties_file is None and isinstance(context, Context):
        properties_file = context.properties_file
    if properties_file is not None:
        return os.path.abspath(properties_file)
    return os.path.join(home_dir(context), "user.properties")

def _check_key(key):
    """Validate a property key, returning it.

    Keys are dot-separated segments of ASCII letters, digits, `_`
    and `-`, each starting with a letter, and the `rlq` and
    `reliquary` namespaces are reserved for Reliquary's own facts.
    """
    if not isinstance(key, str) or not key:
        raise PropertiesError("a property key is required",
                              rule_id="name.property-empty")
    segments = key.split(".")
    for segment in segments:
        if not _SEGMENT.match(segment):
            raise PropertiesError(
                f"invalid property key {key!r}: each segment starts "
                "with a letter and continues with letters, digits, "
                "'_' or '-'",
                rule_id="name.property-charter")
    if segments[0] in _RESERVED:
        raise PropertiesError(
            f"invalid property key {key!r}: the {segments[0]!r} "
            "namespace is reserved for Reliquary's own facts",
            rule_id="name.property-reserved-namespace")
    return key

def _decode(text, path, number):
    """Decode a value as written, or raise naming file and line."""
    if text == _SECRET_TOKEN:
        return secret_marker()
    if text.startswith("@@"):
        return text[1:]
    if text.startswith("@"):
        raise PropertiesError(
            f"{path}:{number}: {text!r} is not a known value kind; "
            "a leading '@' is reserved (write '@@' for a literal "
            "'@')", rule_id="prop.value-reserved-sigil")
    return text

def _encode(value):
    """Render a value as the file writes it."""
    if is_secret(value):
        return _SECRET_TOKEN
    if not isinstance(value, str):
        raise PropertiesError(
            "a property value must be text; every ordinary value "
            "is a string and the declaration provides the type",
            rule_id="prop.value-not-text")
    if value != value.strip():
        raise PropertiesError(
            f"a property value may not lead or trail with "
            f"whitespace: {value!r} would not read back as written "
            "(the format has no quoting)",
            rule_id="prop.value-untrimmed")
    if "\n" in value or "\r" in value:
        raise PropertiesError(
            "a property value is one line; it may not contain a "
            "line break", rule_id="prop.value-multiline")
    if value.startswith("@"):
        return "@" + value
    return value

class _File:
    """A parsed properties file that remembers how it was written."""

    def __init__(self, path, lines, entries, ending="\n"):
        self.path = path
        self.lines = lines
        self.entries = entries
        self.ending = ending

    def value(self, key):
        entry = self.entries.get(key)
        return None if entry is None else entry[1]

    def projection(self):
        return {key: value for key, (_, value) in self.entries.items()}

    def set(self, key, value):
        """Rewrite or append the one line this key owns."""
        line = f"{key} = {_encode(value)}"
        entry = self.entries.get(key)
        if entry is None:
            self.lines.append(line)
            index = len(self.lines) - 1
        else:
            index = entry[0]
            self.lines[index] = line
        self.entries[key] = (index, value)

    def unset(self, key):
        """Delete the one line this key owns, if it has one."""
        entry = self.entries.pop(key, None)
        if entry is None:
            return False
        index = entry[0]
        del self.lines[index]
        self.entries = {
            other: ((position - 1) if position > index else position, value)
            for other, (position, value) in self.entries.items()}
        return True

    def save(self):
        """Write the file atomically, creating its directory."""
        directory = os.path.dirname(self.path)
        os.makedirs(directory, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=directory,
            prefix=".user.properties.", delete=False)
        try:
            with handle:
                for line in self.lines:
                    handle.write(line + self.ending)
            os.replace(handle.name, self.path)
        except BaseException:
            try:
                os.unlink(handle.name)
            except OSError:
                pass
            raise

def _read(path):
    """Parse the properties file, or raise naming path and line.

    A file that does not parse is never partly rewritten: every
    caller reads the whole file before it edits a line of it.
    """
    lines = []
    entries = {}
    ending = os.linesep if os.linesep in ("\n", "\r\n") else "\n"
    if os.path.exists(path):
        try:
            # newline="" keeps the file's own line endings visible, so a
            # hand-edited CRLF file is not silently rewritten as LF.
            with open(path, "r", encoding="utf-8", newline="") as handle:
                text = handle.read()
        except UnicodeDecodeError as error:
            raise PropertiesError(
                f"{path}: the properties file is not UTF-8",
                rule_id="prop.file-not-utf8") from error
        if text:
            ending = "\r\n" if "\r\n" in text else "\n"
        lines = [line.rstrip("\r") for line in text.split("\n")]
        # A file's final newline terminates its last line rather than
        # starting an empty one; save() writes one back.
        if lines and lines[-1] == "":
            lines.pop()
    for index, line in enumerate(lines):
        number = index + 1
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, written = line.partition("=")
        if not separator:
            raise PropertiesError(
                f"{path}:{number}: expected 'key = value', a comment, "
                "or a blank line",
                rule_id="prop.file-line-malformed")
        key = key.strip()
        try:
            _check_key(key)
        except PropertiesError as error:
            # The rules for a valid key are the same no matter where
            # the key came from, so the same rule_id is reused here;
            # only the file and line number are added.
            raise PropertiesError(f"{path}:{number}: {error}",
                                  rule_id=error.rule_id) from error
        if key in entries:
            first = entries[key][0] + 1
            raise PropertiesError(
                f"{path}:{number}: duplicate property {key!r}, first "
                f"defined on line {first}",
                rule_id="name.duplicate-property")
        entries[key] = (index, _decode(written.strip(), path, number))
    return _File(path, lines, entries, ending)

def get_property(key, context=None, properties_file=None):
    """Return the named property's value, or None if it has none.

    A secret returns its marker, never its value — exactly what
    the `--json` rendering serializes. Whether its credential is
    actually present is `has_credential`'s question, kept separate
    so reading a property never depends on reaching the store.
    """
    _check_key(key)
    return _read(_properties_path(context, properties_file)).value(key)

def has_credential(key, context=None, properties_file=None):
    """Return True when this key's secret credential is present.

    Read-only: it never stores or removes anything.
    """
    _check_key(key)
    path = _properties_path(context, properties_file)
    return credentials.has_secret(credentials.scope_for(path), key)

def get_secret(key, context=None, properties_file=None):
    """Return a secret's plaintext value, or None if it has none.

    This is the only function that returns a stored secret's actual
    value, used for binding it into a run. It is deliberately not
    exposed to the CLI: `get-property` and `list-properties` reveal
    only the marker.
    """
    _check_key(key)
    path = _properties_path(context, properties_file)
    return credentials.read_secret(credentials.scope_for(path), key)

def _refuse_orphan(path, key):
    """Refuse to overwrite a credential that has no marker line for it.

    `set_property` stores the credential before it writes the marker
    line, so a credential with no marker means a previous secret set
    was interrupted partway through. Overwriting it would silently
    discard a secret the user believes is already stored, so this
    makes the caller ask for the cleanup explicitly instead.
    """
    try:
        present = credentials.has_secret(credentials.scope_for(path), key)
    except credentials.CredentialError:
        # If the credential store can't even answer, skip this check
        # — an unavailable store must not block setting an ordinary
        # (non-secret) value.
        return
    if present:
        raise PropertiesError(
            f"an orphaned credential exists for {key!r} (stored, but "
            f"no marker in {path} — an interrupted secret set); run "
            f"'rlq unset-property {key}' to clear it first",
            rule_id="prop.orphaned-credential")

def set_property(key, value, secret=False, context=None,
                 properties_file=None):
    """Create or replace a property, preserving the rest of the file.

    Changing a property between ordinary and secret requires calling
    `unset_property` first, so a secret can never be downgraded to a
    plaintext value by a single command.

    A secret's value is stored in the host credential store first,
    and only afterward is its marker written to the file. That order
    means an interruption can leave an orphaned credential (which is
    detected and reported), but never a marker pointing at a
    credential that isn't actually there.
    """
    _check_key(key)
    path = _properties_path(context, properties_file)
    properties = _read(path)
    current = properties.value(key)
    if secret:
        if not isinstance(value, str) or not value:
            raise PropertiesError(
                "a secret needs a non-empty value",
                rule_id="prop.secret-empty")
        if current is not None and not is_secret(current):
            raise PropertiesError(
                f"{key!r} is an ordinary property; unset it first "
                "to store a secret under that key",
                rule_id="prop.kind-change-on-set")
        credentials.store_secret(credentials.scope_for(path), key, value)
        properties.set(key, secret_marker())
        properties.save()
        return
    if is_secret(current):
        raise PropertiesError(
            f"{key!r} is a secret property; unset it first to store "
            "an ordinary value under that key",
            rule_id="prop.kind-change-on-set")
    if current is None:
        _refuse_orphan(path, key)
    properties.set(key, value)
    properties.save()

def unset_property(key, context=None, properties_file=None):
    """Remove a property: its marker line and its credential alike.

    The marker line is deleted first, then the credential, so an
    interruption leaves an orphaned credential rather than a marker
    pointing at nothing. Calling unset on a key with no marker line
    still clears any orphaned credential left for it — that is how an
    orphaned credential gets cleaned up.
    """
    _check_key(key)
    path = _properties_path(context, properties_file)
    properties = _read(path)
    current = properties.value(key)
    was_secret = is_secret(current)
    if properties.unset(key):
        properties.save()
    if current is not None and not was_secret:
        # An ordinary property and an orphaned credential can't both
        # exist for the same key — set_property already refuses to
        # create an ordinary value over an orphaned credential — so
        # there's nothing to check in the credential store here.
        return
    try:
        credentials.delete_secret(credentials.scope_for(path), key)
    except credentials.CredentialError:
        # Removing an ordinary property must still succeed even if
        # this host has no working credential store; removing a
        # secret must not.
        if was_secret:
            raise

def list_properties(prefix=None, context=None, properties_file=None):
    """Return the properties as a dict mapping key to value or marker.

    A prefix selects that key and its dotted descendants — it works
    like a namespace, not like a plain string match.
    """
    path = _properties_path(context, properties_file)
    properties = _read(path).projection()
    if prefix is None:
        return dict(sorted(properties.items()))
    _check_key(prefix)
    selected = {
        key: value for key, value in properties.items()
        if key == prefix or key.startswith(prefix + ".")}
    return dict(sorted(selected.items()))
