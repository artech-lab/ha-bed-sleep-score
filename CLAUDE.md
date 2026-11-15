# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project: Bed Sleep Score

Home Assistant custom integration (`custom_components/bed_sleep_score`) that analyses a bed accelerometer
and scores every night from 0 to 100, with a bundled dashboard card. Distributed through HACS (category
`integration`; from Home Assistant 2026.11 HACS is built in as the Marketplace).

Answer the maintainer in the language they write in. Code, comments, commit messages, entity IDs and the
README stay in English. User-facing strings exist in English and Italian.

## Commands

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements_test.txt   # once (Python 3.13)
scripts/check.sh                   # everything CI runs: ruff, card syntax, pytest
scripts/check.sh -k full_night     # extra arguments go to pytest
python scripts/screenshots.py      # rebuilds images/*.png from scripts/preview.html (needs playwright)
```

Slash commands: `/publish` (first publication) and `/release X.Y.Z` (later versions).

## Layout

| Path | Content |
| --- | --- |
| `const.py` | Every constant: config keys, analysis and scoring anchors. Tuning happens here |
| `scoring.py` | Pure functions, no Home Assistant imports: magnitude, standard deviation, score formula |
| `tracker.py` | `SleepTracker`: sensors -> agitation -> movements -> night accumulators -> score; window scheduling, restart recovery, storage |
| `entity.py`, `sensor.py`, `binary_sensor.py`, `time.py` | Thin entities reading the tracker; they hold no logic |
| `config_flow.py` | One setup form and one options form |
| `frontend/bed-sleep-score-card.js` | The card: one dependency-free ES module, no build step |
| `translations/en.json`, `it.json` | Integration strings (the card has its own `STRINGS` table) |
| `tests/` | `test_scoring.py` (pure), `test_tracker.py` (raw acceleration in, score out, on a real Home Assistant core), `test_config_flow.py`, `test_consistency.py` |

## Rules that keep it maintainable

- **One version**: `manifest.json` -> `version`. The integration appends it to the card URL
  (`?v=`), the card reads it from `import.meta.url`. Never hard-code it elsewhere (a test checks).
- **One release step**: pushing a new manifest version to `main` makes the `Release` job of
  `.github/workflows/validate.yml` create the tag and the GitHub release after all checks pass.
- **One tuning knob for users**: the movement threshold. `tracker.scale = threshold / DEFAULT_THRESHOLD`
  stretches the calm and intensity anchors. Do not add options without a strong reason.
- **Logic only in `scoring.py` and `tracker.py`**. The card displays what the integration computes and
  discovers its entities from the device of the score sensor (`translation_key` -> role).
- **Translations**: a new string goes in both `en.json` and `it.json`, or in both languages of `STRINGS`
  in the card (tests compare the key sets). Entity IDs are always English: `entity.py` sets them from
  the entry title and the description key.
- A new entity needs: a description in its platform file, a name in both translation files, an icon in
  `icons.json` and, if the card shows it, an entry in the card's `SIBLINGS` table.
- Changing the score formula: bump `FORMULA_VERSION`, update the table in the README and the reference
  night in `tests/test_scoring.py`. Scores before and after are not comparable: say so in the changelog.
- No personal data in the repository (names, e-mail addresses, entity IDs of a real installation).
- License: GPL-3.0-or-later. New source files start with `# SPDX-License-Identifier: GPL-3.0-or-later`.
