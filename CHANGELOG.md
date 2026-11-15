# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
