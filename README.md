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
- Configurable in NVDA Settings → Symbol Compressor (enable/disable, min counts 2–10)
- Respects NVDA punctuation/symbol level

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
