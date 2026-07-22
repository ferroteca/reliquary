# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
import json
import os
from collections.abc import Mapping

from . import jsonc

def _properties_path(home=None):
    """Return the path to the user properties file."""
    from .home import home as home_func
    effective_home = home or home_func()
    return os.path.join(effective_home, "user.properties")

def _load_properties(home=None):
    """Load the user properties from disk."""
    path = _properties_path(home)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = jsonc.load(handle)
    except (ValueError, UnicodeDecodeError):
        return {}
    if not isinstance(value, Mapping):
        return {}
    return dict(value)

def _save_properties(properties, home=None):
    """Save the user properties to disk."""
    path = _properties_path(home)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(properties, handle, indent=4)
        handle.write("\n")

def get_property(key, home=None):
    """Return the value of the named property, or None."""
    return _load_properties(home).get(key)

def set_property(key, value, secret=False, home=None):
    """Set the value of the named property.

    If secret is True, the value should be stored in the host's
    protected credential store (milestone 6). For now, it's just
    in the JSON file.
    """
    properties = _load_properties(home)
    properties[key] = value
    _save_properties(properties, home)

def unset_property(key, home=None):
    """Remove the named property."""
    properties = _load_properties(home)
    if key in properties:
        del properties[key]
        _save_properties(properties, home)

def list_properties(home=None):
    """Return a dictionary of all defined properties."""
    return _load_properties(home)
