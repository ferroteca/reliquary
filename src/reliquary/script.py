# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Script file management conveniences.
"""

import os

from .errors import PreflightError


def delete_script(name, *, context=None):
    """Remove the home script file for ``name``.

    Fails closed while any blueprint refers to the script.
    Never deletes package codex files — only a file under
    ``scripts/``. Returns the removed path.
    """
    from . import assets, json5reader, library
    from .errors import ReliquaryError
    from .home import scripts_dir

    # Check for blueprint references first.
    source = assets.source_for(context)
    blueprints = []
    for path in source.candidate_files("blueprint"):
        try:
            with open(path, encoding="utf-8") as handle:
                data = json5reader.loads(handle.read())
        except (OSError, ReliquaryError):
            continue

        if name in library._referenced_scripts(data):
            blueprints.append(assets.stem(path))

    if blueprints:
        ids = ", ".join(sorted(blueprints))
        raise PreflightError(
            f"script {name!r} still has "
            f"{len(blueprints)} blueprint(s):\n"
            f"  {ids}\n"
            "edit them to remove the reference first, then delete the script",
            rule_id="script.has-blueprints")

    path = os.path.join(scripts_dir(context), f"{name}.rlqs")
    if not os.path.isfile(path):
        raise PreflightError(
            f"script not found: {name}.rlqs\n"
            f"expected under {scripts_dir(context)}",
            rule_id="script.unknown")

    os.remove(path)
    return path
