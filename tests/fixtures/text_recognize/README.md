<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Text-recognize fixtures

Golden PNGs for `tests/test_text_recognize.py`. Each `.png` is paired
with a `.txt` file holding the expected character rows (trailing blank
rows are left out).

**The `.txt` file is the actual fixture; the `.png` is generated from
it.** The rows of text are taken from real FreeDOS screens, which is
what makes them worth testing against. The image is those same rows
drawn using Reliquary's own font bank — glyphs computed from their
character codes, rather than copied from any real VGA font — so it is
**not a picture of readable text**, and it isn't meant to be. Nothing
here needs to look like an actual screen: what's under test is the
round trip from text to image and back, and a synthetic font bank makes
that round trip unambiguous (any two glyphs in the bank differ in at
least a third of their pixels).

Regenerate the PNGs after a change to the font bank or to `render`:

```powershell
uv run python -c "import os; from reliquary import text_recognize as r; d='tests/fixtures/text_recognize'; [r.save_screen(os.path.join(d, s + '.png'), open(os.path.join(d, s + '.txt'), encoding='utf-8').read().splitlines()) for s in ('freedos-prompt', 'freedos-welcome', 'install-ready')]"
```

No hypervisor needed.
