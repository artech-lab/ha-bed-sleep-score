# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.1.0] - 2026-11-15

### Added

- `bed_sleep_score.set_score` action: sets the last score and, optionally, the 7-day average, to carry
  them over from another setup. The values persist across restarts; the imported score has no
  breakdown (`imported: true`) and the next window is scored as usual, even on the same day.
- Diagnostics report whether the tracker is settling (`settling`, `settling_until`).

### Fixed

- A spurious movement, and a distorted calm and intensity, after Home Assistant starts or the
  accelerometer comes back from `unavailable`/`unknown`: the readings are now ignored for 3 minutes
  (one standard-deviation window plus a margin) while the sensor settles.

### Changed

- Manifest: declare the `health_wellbeing` integration category.
- CI: `actions/setup-python` v7 (Node 24).

## [1.0.0] - 2026-11-15

First public release.

- Built-in analysis of the bed accelerometer: acceleration magnitude, rolling standard deviation and
  movement detection with hysteresis. No helpers, templates or automations are needed.
- Nightly 0-100 sleep score (formula v3: continuity, movements, wake-ups, calm, intensity) and
  7-day average.
- Editable sleep window, optional presence condition, recovery after restarts.
- Bundled `bed-sleep-score-card` dashboard card, loaded automatically, with a visual editor.
- English and Italian.
