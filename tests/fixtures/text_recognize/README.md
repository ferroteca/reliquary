<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Text-recognize fixtures

Golden PNGs for `tests/test_text_recognize.py`. Each `.png` is
paired with a `.txt` of the expected character rows (trailing blank
rows omitted).

**The `.txt` is the fixture; the `.png` is derived.** The rows are
real FreeDOS screens, which is what makes them worth pinning. The
image is those rows drawn with Reliquary's own bank — glyphs
computed from their codes rather than copied from any VGA font — so
it is **not a picture of readable text** and is not meant to be.
Nothing here needs to look like a screen: the round trip is what is
under test, and a constructed bank makes it unambiguous (any two
glyphs differ in at least a third of their pixels).

Regenerate after a change to the bank or to `render`:

```powershell
uv run python -c "import os; from reliquary import text_recognize as r; d='tests/fixtures/text_recognize'; [r.save_screen(os.path.join(d, s + '.png'), open(os.path.join(d, s + '.txt'), encoding='utf-8').read().splitlines()) for s in ('freedos-prompt', 'freedos-welcome', 'install-ready')]"
```

No hypervisor.
