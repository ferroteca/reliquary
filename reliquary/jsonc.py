# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""JSON with Comments (JSONC) reader.

Implements RFC 8259 + // and /* */ comments + trailing commas.
Comments are replaced by spaces to preserve line and column numbers.
"""

import json
import re

from .errors import StaticError

def loads(s):
    """Load JSONC string.

    A document that does not parse is a STATIC ERROR: the text alone
    settles it, and the caller wrote the text. ``JSONDecodeError``
    would otherwise escape as a bare ``ValueError`` and report as
    reliquary's own fault (exit 1) rather than the author's mistake.
    Its message carries the line and column, so it is kept verbatim.
    """
    # 1. Replace comments with spaces of the same length
    # This keeps line/column numbers exact for the JSON parser if it reports them.
    # Note: we must be careful not to replace comments inside strings.
    
    # Regex for JSON strings, // comments, and /* */ comments
    # Strings: " ( [^"\\] | \\. )* "
    # // comments: // [^\n]*
    # /* */ comments: /\* .*? \*/
    pattern = re.compile(
        r'("(?:[^"\\]|\\.)*")|'      # Group 1: Strings
        r'(//[^\n]*)|'               # Group 2: // comments
        r'(/\*.*?\*/)',              # Group 3: /* */ comments
        re.DOTALL
    )
    
    def replace(match):
        if match.group(1):
            return match.group(1) # Keep strings as is
        return ''.join(
            '\n' if char == '\n' else ' '
            for char in match.group(0))
            
    s = pattern.sub(replace, s)
    
    # 2. Remove trailing commas
    # [1, 2,] -> [1, 2]
    # {"a": 1,} -> {"a": 1}
    # We look for a comma followed by whitespace and then ] or }
    # Again, avoiding commas inside strings.
    
    # This is a bit trickier with regex alone to be 100% correct regarding strings,
    # but since we already know where the strings are from the previous pass,
    # we can do it safely.
    
    # Re-using the pattern to find strings and trailing commas
    trailing_comma_pattern = re.compile(
        r'("(?:[^"\\]|\\.)*")|'      # Group 1: Strings
        r'(,\s*([\]\}]))'            # Group 2: Trailing comma, Group 3: closing char
    )
    
    def replace_comma(match):
        if match.group(1):
            return match.group(1)
        else:
            return ' ' + match.group(3) # Replace comma with space, keep closing char
            
    s = trailing_comma_pattern.sub(replace_comma, s)
    
    try:
        return json.loads(s)
    except json.JSONDecodeError as error:
        failure = StaticError(str(error))
        # Comment stripping preserves line and column on purpose, so
        # the position survives the class change rather than being
        # readable only out of the message. A properly located
        # blueprint diagnostic — line, column and a rule id, as
        # ScriptParseError already carries — is the id pass's business.
        failure.lineno = error.lineno
        failure.colno = error.colno
        raise failure from error

def load(fp):
    """Load JSONC from a file-like object."""
    return loads(fp.read())
