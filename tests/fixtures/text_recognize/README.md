<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Text-recognize fixtures

Golden PNGs for `tests/test_text_recognize.py`. Each `.png` is
paired with a `.txt` of the expected character rows (trailing blank
rows omitted). Fixtures are rendered with Reliquary's own glyph
bank — regenerate with:

```powershell
uv run python -c "from reliquary import text_recognize as r; ..."
```

No hypervisor.
