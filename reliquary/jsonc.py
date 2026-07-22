# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""JSON with Comments (JSONC) reader.

Implements RFC 8259 + // and /* */ comments + trailing commas.
Comments are replaced by spaces to preserve line and column numbers.
"""

import json
import re

def loads(s):
    """Load JSONC string."""
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
    
    return json.loads(s)

def load(fp):
    """Load JSONC from a file-like object."""
    return loads(fp.read())
