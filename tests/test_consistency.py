"""Guards that keep the package easy to maintain."""

import json
from pathlib import Path
import re

ROOT = Path(__file__).parents[1] / "custom_components" / "bed_sleep_score"


def _keys(node, prefix=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _keys(value, f"{prefix}.{key}")
    else:
        yield prefix


def test_integration_translations_have_same_keys() -> None:
    en = json.loads((ROOT / "translations" / "en.json").read_text())
    it = json.loads((ROOT / "translations" / "it.json").read_text())
    assert set(_keys(en)) == set(_keys(it))


def test_card_translations_have_same_keys() -> None:
    card = (ROOT / "frontend" / "bed-sleep-score-card.js").read_text()
    english, italian = re.search(
        r"const STRINGS = \{\n  en: \{(.*?)\n  \},\n  it: \{(.*?)\n  \}\n\};", card, re.S
    ).groups()
    keys = [set(re.findall(r"^    (\w+):", block, re.M)) for block in (english, italian)]
    assert keys[0] and keys[0] == keys[1]


def test_version_lives_only_in_the_manifest() -> None:
    version = json.loads((ROOT / "manifest.json").read_text())["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    for path in [*ROOT.glob("*.py"), ROOT / "frontend" / "bed-sleep-score-card.js"]:
        assert version not in path.read_text(), f"hard-coded version in {path.name}"
