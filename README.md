# Symbol Compressor for NVDA

NVDA add-on that compresses repeated symbols and emojis when spoken.
Instead of hearing "exclamation exclamation exclamation", you'll hear "3 exclamation".

- Add-on name: `symbolCompressor`
- Author: Rosendo Barde Hubilla Junior
- Current version: 3.0
- Minimum NVDA: 2021.1, Last tested: 2026.2

## Features

- Compress repeated punctuation: `!!!!` → "4 exclamation"
- Compress repeated emojis: `😂😂😂😂` → "4 face with tears of joy"
- Supports skin-tone modifiers, ZWJ sequences, and variation selectors
- Emoji 17.0 support (7 new emojis + ballet dancer sequences)
- Emoji 18.0 support (Unicode 18.0, September 2026) — 9 new emojis, 19 sequences:
  - Cracking face
  - Leftwards thumb sign (+ 5 skin tones)
  - Rightwards thumb sign (+ 5 skin tones)
  - Monarch butterfly
  - Pickle
  - Lighthouse
  - Meteor
  - Eraser
  - Net with handle
- Configurable in NVDA Settings → Symbol Compressor (per-category dropdown: Off, 2, 3, 4, 5)
- Respects NVDA punctuation/symbol level

## Important note about Off

Off means "let NVDA do its default". NVDA itself collapses any identical
character repeated 4 or more times into "N name" (built-in `characterProcessing`
repetition rule, no off switch — see
[nvaccess/nvda#20605](https://github.com/nvaccess/nvda/issues/20605)).
So with Off, 3 emojis are spoken individually but 4+ become e.g.
"4 smiling face with heart-eyes". Hearing every repeat individually at 4+
is currently not possible in NVDA.

## Changelog

### 3.0

- Emoji 18.0 support (Unicode 18.0, September 2026): cracking face,
  leftwards/rightwards thumb sign with skin tones, monarch butterfly,
  pickle, lighthouse, meteor, eraser, net with handle.
- Settings are now per-category dropdowns (Off, 2, 3, 4, 5) in
  NVDA Settings → Symbol Compressor; no more typing values.
- Tested up to NVDA 2026.2.

## Install

1. Download the latest `symbolCompressor_vX_X.nvda-addon` from Releases.
2. Press Enter on it, or NVDA Menu → Tools → Manage Add-ons → Install.
3. Restart NVDA when asked.

## Repo layout

- `manifest.ini` — add-on metadata
- `globalPlugins/symbolCompressor.py` — main code
- `doc/en/readme.html` — user guide

## License

GPL v2 or later (same as NVDA).
